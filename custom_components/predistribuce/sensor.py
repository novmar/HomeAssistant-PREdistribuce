"""Senzory — čas do přepnutí tarifu, aktuální cena a co to právě teď stojí."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.const import UnitOfTime
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event

from . import PreConfigEntry
from .const import CONF_CENA_NT, CONF_CENA_VT, CONF_POWER_SENSOR
from .entity import PreEntity

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

    _attr_name = "Minut do nízkého tarifu"
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_icon = "mdi:timer-sand"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry, "minut_do_nt")

    @property
    def native_value(self) -> int | None:
        return self.coordinator.data.minutes_to_nt


class PreMinutyDoVT(PreEntity, SensorEntity):
    """Za jak dlouho nízký tarif skončí (0 = neběží)."""

    _attr_name = "Minut do vysokého tarifu"
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_icon = "mdi:timer-sand-complete"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry, "minut_do_vt")

    @property
    def native_value(self) -> int | None:
        return self.coordinator.data.minutes_to_vt


class PreCena(PreEntity, SensorEntity):
    """Cena za kWh podle právě běžícího tarifu."""

    _attr_name = "Cena elektřiny"
    _attr_native_unit_of_measurement = CURRENCY_PER_KWH
    _attr_icon = "mdi:cash"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 2

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry, "cena")
        self._entry = entry

    @property
    def native_value(self) -> float:
        options = self._entry.options
        if self.coordinator.data.is_nt:
            return float(options[CONF_CENA_NT])
        return float(options[CONF_CENA_VT])

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        return {
            "tarif": "NT" if self.coordinator.data.is_nt else "VT",
            "cena_vt": self._entry.options[CONF_CENA_VT],
            "cena_nt": self._entry.options[CONF_CENA_NT],
        }


class PreNaklady(PreEntity, SensorEntity):
    """Kolik stojí aktuální odběr — za hodinu, nebo za minutu."""

    _attr_icon = "mdi:cash-clock"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, entry, per_minute: bool) -> None:
        super().__init__(
            coordinator, entry, "naklady_za_minutu" if per_minute else "naklady_za_hodinu"
        )
        self._entry = entry
        self._per_minute = per_minute
        self._power_entity = entry.options[CONF_POWER_SENSOR]
        self._attr_name = (
            "Náklady za minutu" if per_minute else "Náklady za hodinu"
        )
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

    @property
    def available(self) -> bool:
        if not super().available:
            return False
        state = self.hass.states.get(self._power_entity)
        if state is None:
            return False
        try:
            float(state.state)
        except (TypeError, ValueError):
            return False
        return True

    @property
    def native_value(self) -> float | None:
        state = self.hass.states.get(self._power_entity)
        if state is None:
            return None
        try:
            watts = float(state.state)
        except (TypeError, ValueError):
            return None

        options = self._entry.options
        cena = float(
            options[CONF_CENA_NT] if self.coordinator.data.is_nt else options[CONF_CENA_VT]
        )
        za_hodinu = watts / 1000 * cena
        return round(za_hodinu / 60, 4) if self._per_minute else round(za_hodinu, 2)
