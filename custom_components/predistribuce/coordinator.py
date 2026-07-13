"""Coordinator — stáhne rozvrh HDO jednou denně, stav dopočítává každou minutu."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import CONF_POVEL, DOMAIN, RETRY_BACKOFF_MAX, RETRY_BACKOFF_START, UPDATE_INTERVAL
from .parser import PreError, PreNoData, Window
from .pre_client import PreClient
from .state import HdoState, compute_state

_LOGGER = logging.getLogger(__name__)


class PreHdoCoordinator(DataUpdateCoordinator[HdoState]):
    """Drží rozvrh HDO a každou minutu z něj dopočítá aktuální stav.

    Rozvrh se během dne nemění, takže ho stahujeme jen při změně dne. Tahá se i zítřek,
    aby šlo správně spočítat okno přecházející přes půlnoc — ale zítřek je nepovinný:
    PRE zveřejňuje data jen zhruba dva týdny dopředu a občas vypadne, a to nesmí shodit
    dnešek, který už máme.
    """

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, client: PreClient
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {entry.data[CONF_POVEL]}",
            update_interval=UPDATE_INTERVAL,
        )
        self._client = client
        self._povel = entry.data[CONF_POVEL]
        self._cache: dict[date, list[Window]] = {}
        self._retry_after: datetime | None = None
        self._backoff = RETRY_BACKOFF_START

    async def _async_fetch(self, den: date) -> list[Window]:
        """Vrátí okna pro daný den, pokud možno z cache."""
        if den not in self._cache:
            self._cache[den] = await self._client.async_get_nt_windows(self._povel, den)
            self._cache = {
                d: w for d, w in self._cache.items() if d >= den - timedelta(days=1)
            }
        return self._cache[den]

    def _note_failure(self, now: datetime) -> None:
        """Po neúspěchu couvneme, ať nebušíme na cizí web každou minutu."""
        self._retry_after = now + timedelta(seconds=self._backoff)
        self._backoff = min(self._backoff * 2, RETRY_BACKOFF_MAX)

    async def _async_update_data(self) -> HdoState:
        now = dt_util.now()
        today = now.date()
        tomorrow = today + timedelta(days=1)

        have_today = today in self._cache
        waiting = self._retry_after is not None and now < self._retry_after

        if not have_today and waiting:
            raise UpdateFailed(
                f"Čekám na další pokus o stažení rozvrhu (do {self._retry_after:%H:%M:%S})."
            )

        if not have_today:
            try:
                await self._async_fetch(today)
            except PreNoData as err:
                self._note_failure(now)
                raise UpdateFailed(str(err)) from err
            except PreError as err:
                self._note_failure(now)
                raise UpdateFailed(str(err)) from err
            self._retry_after = None
            self._backoff = RETRY_BACKOFF_START

        # Zítřek potřebujeme jen kvůli oknu přes půlnoc. Když nedorazí, počítáme bez něj —
        # to je o poznání lepší než shodit i dnešek, který máme v ruce.
        tomorrow_windows: list[Window] = []
        if not waiting:
            try:
                tomorrow_windows = await self._async_fetch(tomorrow)
            except PreNoData:
                _LOGGER.debug("PRE zatím nemá rozvrh na %s, počítám bez něj.", tomorrow)
            except PreError as err:
                _LOGGER.warning("Rozvrh na zítřek se nepodařilo stáhnout: %s", err)
                self._note_failure(now)
        else:
            tomorrow_windows = self._cache.get(tomorrow, [])

        return compute_state(self._cache[today], tomorrow_windows, now)
