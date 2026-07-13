"""Společný základ entit."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_POVEL, DOMAIN
from .coordinator import PreHdoCoordinator


class PreEntity(CoordinatorEntity[PreHdoCoordinator]):
    """Entita svázaná s jedním povelem HDO."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: PreHdoCoordinator, entry: ConfigEntry, key: str
    ) -> None:
        super().__init__(coordinator)
        povel = entry.data[CONF_POVEL]
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=f"HDO {povel}",
            manufacturer="PREdistribuce",
            model=f"Povel {povel}",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url="https://www.predistribuce.cz/cs/potrebuji-zaridit/zakaznici/stav-hdo/",
        )
