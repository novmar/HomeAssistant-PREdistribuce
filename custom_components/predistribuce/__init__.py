"""Integrace PREdistribuce — nízký tarif (HDO) a cena elektřiny."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_POVEL
from .coordinator import PreHdoCoordinator
from .pre_client import PreClient

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]

type PreConfigEntry = ConfigEntry[PreHdoCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: PreConfigEntry) -> bool:
    client = PreClient(async_get_clientsession(hass))
    coordinator = PreHdoCoordinator(hass, client, entry.data[CONF_POVEL])
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: PreConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_reload_entry(hass: HomeAssistant, entry: PreConfigEntry) -> None:
    """Změna cen nebo hlídaných období mění i entity — načteme integraci znovu."""
    await hass.config_entries.async_reload(entry.entry_id)
