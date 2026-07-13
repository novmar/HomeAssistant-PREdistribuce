"""Senzory — čas do přepnutí tarifu, aktuální cena a co to právě teď stojí."""

from __future__ import annotations

import logging

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT, UnitOfPower, UnitOfTime
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.util.unit_conversion import PowerConverter

from . import PreConfigEntry
from .const import CONF_CENA_NT, CONF_CENA_VT, CONF_POWER_SENSOR
from .coordinator import PreHdoCoordinator
from .entity import PreEntity

_LOGGER = logging.getLogger(__name__)

CURRENCY_PER_KWH = "CZK/kWh"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PreConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    entities: list[SensorEntity] = [
        PreMinutyDoNT(coordinator, entry),
        PreMinutyDoVT(coordinator, entry),
        PreCena(coordinator, entry),
    ]

    # Náklady umíme spočítat, jen když víme, kolik se právě teď odebírá.
    if entry.options.get(CONF_POWER_SENSOR):
        entities += [
            PreNaklady(coordinator, entry, per_minute=False),
            PreNaklady(coordinator, entry, per_minute=True),
        ]

    async_add_entities(entities)


class PreMinutyDoNT(PreEntity, SensorEntity):
    """Za jak dlouho začne nízký tarif (0 = běží)."""

    _attr_translation_key = "minut_do_nt"
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_icon = "mdi:timer-sand"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: PreHdoCoordinator, entry: PreConfigEntry) -> None:
        super().__init__(coordinator, entry, "minut_do_nt")

    @property
    def native_value(self) -> int | None:
        return self.coordinator.data.minutes_to_nt


class PreMinutyDoVT(PreEntity, SensorEntity):
    """Za jak dlouho nízký tarif skončí (0 = neběží)."""

    _attr_translation_key = "minut_do_vt"
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_icon = "mdi:timer-sand-complete"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: PreHdoCoordinator, entry: PreConfigEntry) -> None:
        super().__init__(coordinator, entry, "minut_do_vt")

    @property
    def native_value(self) -> int | None:
        return self.coordinator.data.minutes_to_vt


class PreCena(PreEntity, SensorEntity):
    """Cena za kWh podle právě běžícího tarifu."""

    _attr_translation_key = "cena"
    _attr_native_unit_of_measurement = CURRENCY_PER_KWH
    _attr_icon = "mdi:cash"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 2

    def __init__(self, coordinator: PreHdoCoordinator, entry: PreConfigEntry) -> None:
        super().__init__(coordinator, entry, "cena")
        self._entry = entry

    @property
    def native_value(self) -> float:
        return _cena(self._entry, self.coordinator)

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        return {
            "tarif": "NT" if self.coordinator.data.is_nt else "VT",
            "cena_vt": self._entry.options[CONF_CENA_VT],
            "cena_nt": self._entry.options[CONF_CENA_NT],
        }


def _cena(entry: PreConfigEntry, coordinator: PreHdoCoordinator) -> float:
    options = entry.options
    if coordinator.data.is_nt:
        return float(options[CONF_CENA_NT])
    return float(options[CONF_CENA_VT])


class PreNaklady(PreEntity, SensorEntity):
    """Kolik stojí aktuální odběr — za hodinu, nebo za minutu."""

    _attr_icon = "mdi:cash-clock"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self, coordinator: PreHdoCoordinator, entry: PreConfigEntry, per_minute: bool
    ) -> None:
        key = "naklady_za_minutu" if per_minute else "naklady_za_hodinu"
        super().__init__(coordinator, entry, key)
        self._entry = entry
        self._per_minute = per_minute
        self._power_entity: str = entry.options[CONF_POWER_SENSOR]
        self._attr_translation_key = key
        self._attr_native_unit_of_measurement = "CZK/min" if per_minute else "CZK/h"
        self._attr_suggested_display_precision = 4 if per_minute else 2

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        # Bez tohohle by se náklady přepočítaly až s coordinatorem, tedy jednou za minutu —
        # a skok v odběru by se na dashboardu objevil se zpožděním.
        self.async_on_remove(
            async_track_state_change_event(
                self.hass, [self._power_entity], self._handle_power_change
            )
        )

    @callback
    def _handle_power_change(self, event: Event[EventStateChangedData]) -> None:
        self.async_write_ha_state()

    def _watts(self) -> float | None:
        """Aktuální příkon ve wattech, ať už senzor hlásí cokoli.

        Senzor příkonu nemusí být ve wattech — Shelly i střídače běžně hlásí kW. Kdybychom
        hodnotu brali slepě jako watty, spletli bychom se o tři řády a nic by to nenaznačilo.
        """
        state = self.hass.states.get(self._power_entity)
        if state is None:
            return None
        try:
            value = float(state.state)
        except (TypeError, ValueError):
            return None

        unit = state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        if unit == UnitOfPower.WATT or unit is None:
            return value
        try:
            return PowerConverter.convert(value, unit, UnitOfPower.WATT)
        except (HomeAssistantError, ValueError, TypeError):
            # PowerConverter hází HomeAssistantError, ne ValueError. Bez toho by výjimka
            # proletěla ven z available/native_value uvnitř callbacku, místo aby entita
            # jen zešedla — třeba u senzoru ve VA nebo kVA.
            _LOGGER.warning(
                "Senzor %s hlásí jednotku %r, kterou neumím převést na watty.",
                self._power_entity,
                unit,
            )
            return None

    @property
    def available(self) -> bool:
        return super().available and self._watts() is not None

    @property
    def native_value(self) -> float | None:
        watts = self._watts()
        if watts is None:
            return None
        za_hodinu = watts / 1000 * _cena(self._entry, self.coordinator)
        return round(za_hodinu / 60, 4) if self._per_minute else round(za_hodinu, 2)
