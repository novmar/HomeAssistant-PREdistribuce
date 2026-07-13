"""Integrace PREdistribuce — nízký tarif (HDO) a cena elektřiny."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_PERIODS, CONF_POWER_SENSOR
from .coordinator import PreHdoCoordinator
from .pre_client import PreClient

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]

type PreConfigEntry = ConfigEntry[PreHdoCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: PreConfigEntry) -> bool:
    client = PreClient(async_get_clientsession(hass))
    coordinator = PreHdoCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    _async_remove_stale_entities(hass, entry)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: PreConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_reload_entry(hass: HomeAssistant, entry: PreConfigEntry) -> None:
    """Změna cen nebo hlídaných období mění i entity — načteme integraci znovu."""
    await hass.config_entries.async_reload(entry.entry_id)


def _async_remove_stale_entities(hass: HomeAssistant, entry: PreConfigEntry) -> None:
    """Zahodí entity, které už nastavení nepožaduje.

    Bez tohohle by po odebrání hlídané délky (nebo senzoru příkonu) zůstaly viset
    v registru navždy jako `unavailable` a vypadalo by to jako porucha.
    """
    wanted = {"nizky_tarif", "minut_do_nt", "minut_do_vt", "cena"}
    wanted |= {f"nt_min_{minutes}" for minutes in entry.options.get(CONF_PERIODS, [])}
    if entry.options.get(CONF_POWER_SENSOR):
        wanted |= {"naklady_za_hodinu", "naklady_za_minutu"}

    registry = er.async_get(hass)
    prefix = f"{entry.entry_id}_"
    for regentry in er.async_entries_for_config_entry(registry, entry.entry_id):
        if not regentry.unique_id.startswith(prefix):
            continue
        if regentry.unique_id.removeprefix(prefix) not in wanted:
            registry.async_remove(regentry.entity_id)
