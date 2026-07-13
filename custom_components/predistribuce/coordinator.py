"""Coordinator — stáhne rozvrh HDO jednou denně, stav dopočítává každou minutu."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, UPDATE_INTERVAL
from .pre_client import PreClient, PreError

_LOGGER = logging.getLogger(__name__)

MINUTES_PER_DAY = 24 * 60


@dataclass(frozen=True)
class HdoState:
    """Stav HDO v daném okamžiku."""

    is_nt: bool
    minutes_to_nt: int | None
    """Za kolik minut začne nízký tarif. 0 pokud už běží."""
    minutes_to_vt: int | None
    """Za kolik minut nízký tarif skončí. 0 pokud neběží."""
    windows_today: list[tuple[int, int]]


class PreHdoCoordinator(DataUpdateCoordinator[HdoState]):
    """Drží rozvrh HDO a každou minutu z něj dopočítá aktuální stav.

    Rozvrh se během dne nemění, takže ho stahujeme jen při změně dne. Tahá se i zítřek,
    aby šlo správně spočítat zbývající čas u okna, které přechází přes půlnoc.
    """

    def __init__(self, hass: HomeAssistant, client: PreClient, povel: str) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} {povel}",
            update_interval=UPDATE_INTERVAL,
        )
        self._client = client
        self._povel = povel
        self._cache: dict[date, list[tuple[int, int]]] = {}

    async def _async_windows(self, den: date) -> list[tuple[int, int]]:
        if den not in self._cache:
            self._cache[den] = await self._client.async_get_nt_windows(self._povel, den)
            # Starší dny už nepotřebujeme.
            self._cache = {
                d: w for d, w in self._cache.items() if d >= den - timedelta(days=1)
            }
        return self._cache[den]

    async def _async_update_data(self) -> HdoState:
        now = datetime.now()
        today = now.date()

        try:
            today_windows = await self._async_windows(today)
            tomorrow_windows = await self._async_windows(today + timedelta(days=1))
        except PreError as err:
            raise UpdateFailed(str(err)) from err

        # Okna zítřka posuneme o den, ať se dá počítat v jedné ose. Okno, které končí
        # o půlnoci a zítra hned pokračuje, spojíme — jinak bychom hlásili konec NT
        # o půlnoci, i když ve skutečnosti běží dál.
        timeline = list(today_windows)
        timeline += [
            (start + MINUTES_PER_DAY, end + MINUTES_PER_DAY)
            for start, end in tomorrow_windows
        ]
        merged: list[tuple[int, int]] = []
        for start, end in timeline:
            if merged and merged[-1][1] == start:
                merged[-1] = (merged[-1][0], end)
            else:
                merged.append((start, end))

        now_minutes = now.hour * 60 + now.minute

        is_nt = False
        minutes_to_nt: int | None = None
        minutes_to_vt: int | None = None

        for start, end in merged:
            if start <= now_minutes < end:
                is_nt = True
                minutes_to_nt = 0
                minutes_to_vt = end - now_minutes
                break
        else:
            upcoming = [start for start, _ in merged if start > now_minutes]
            minutes_to_vt = 0
            minutes_to_nt = min(upcoming) - now_minutes if upcoming else None

        return HdoState(
            is_nt=is_nt,
            minutes_to_nt=minutes_to_nt,
            minutes_to_vt=minutes_to_vt,
            windows_today=today_windows,
        )
