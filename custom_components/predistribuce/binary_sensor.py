"""Binární senzory — běží nízký tarif, a vydrží ještě dost dlouho?"""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import PreConfigEntry
from .const import CONF_PERIODS
from .coordinator import PreHdoCoordinator
from .entity import PreEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PreConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    entities: list[BinarySensorEntity] = [PreNizkyTarif(coordinator, entry)]
    # Pro každou hlídanou délku vznikne senzor, který je zapnutý jen tehdy, když nízký
    # tarif vydrží aspoň tak dlouho. Přesně to potřebuje automatizace, která chce
    # spustit spotřebič a nechat ho doběhnout ještě v NT.
    entities += [
        PreNizkyTarifVydrzi(coordinator, entry, minutes)
        for minutes in entry.options.get(CONF_PERIODS, [])
    ]
    async_add_entities(entities)


class PreNizkyTarif(PreEntity, BinarySensorEntity):
    """Běží právě teď nízký tarif?"""

    _attr_translation_key = "nizky_tarif"
    _attr_icon = "mdi:transmission-tower"

    def __init__(self, coordinator: PreHdoCoordinator, entry: PreConfigEntry) -> None:
        super().__init__(coordinator, entry, "nizky_tarif")

    @property
    def is_on(self) -> bool | None:
        return self.coordinator.data.is_nt

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        data = self.coordinator.data
        return {
            "okna_nt_dnes": [
                f"{s // 60:02d}:{s % 60:02d}–{e // 60:02d}:{e % 60:02d}"
                for s, e in data.windows_today
            ],
            "minut_do_nt": data.minutes_to_nt,
            "minut_do_vt": data.minutes_to_vt,
        }


class PreNizkyTarifVydrzi(PreEntity, BinarySensorEntity):
    """Běží nízký tarif a vydrží ještě aspoň N minut?"""

    _attr_translation_key = "nizky_tarif_vydrzi"
    _attr_icon = "mdi:timer-check-outline"

    def __init__(
        self, coordinator: PreHdoCoordinator, entry: PreConfigEntry, minutes: int
    ) -> None:
        super().__init__(coordinator, entry, f"nt_min_{minutes}")
        self._minutes = minutes
        self._attr_translation_placeholders = {"minutes": str(minutes)}

    @property
    def is_on(self) -> bool | None:
        data = self.coordinator.data
        if not data.is_nt or data.minutes_to_vt is None:
            return False
        return data.minutes_to_vt >= self._minutes
