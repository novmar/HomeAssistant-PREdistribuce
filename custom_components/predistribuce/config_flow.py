"""Config flow — povel se vybírá z nabídky stažené přímo z webu PRE."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
)

from .const import (
    CONF_CENA_NT,
    CONF_CENA_VT,
    CONF_PERIODS,
    CONF_POVEL,
    CONF_POWER_SENSOR,
    DEFAULT_CENA_NT,
    DEFAULT_CENA_VT,
    DOMAIN,
)
from .pre_client import PreClient, PreError


def _cena_selector() -> NumberSelector:
    return NumberSelector(
        NumberSelectorConfig(
            min=0,
            max=50,
            step=0.001,
            mode=NumberSelectorMode.BOX,
            unit_of_measurement="CZK/kWh",
        )
    )


def _power_selector() -> EntitySelector:
    return EntitySelector(
        EntitySelectorConfig(domain="sensor", device_class="power")
    )


def parse_periods(raw: str | list[int] | None) -> list[int]:
    """Rozparsuje '30, 90, 180' na [30, 90, 180]. Vyčleněno kvůli testovatelnosti."""
    if not raw:
        return []
    if isinstance(raw, list):
        return sorted({int(x) for x in raw})
    out: list[int] = []
    for chunk in str(raw).replace(";", ",").split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if not chunk.isdigit() or not 1 <= int(chunk) <= 1440:
            raise ValueError(chunk)
        out.append(int(chunk))
    return sorted(set(out))


class PreDistribuceConfigFlow(ConfigFlow, domain=DOMAIN):
    """Průvodce nastavením."""

    VERSION = 1

    def __init__(self) -> None:
        self._povely: dict[str, str] | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        # Seznam povelů stahujeme jen kvůli vykreslení formuláře. Kdyby se tahal i při
        # odeslání, jeden timeout z PRE by uživateli zahodil vyplněné hodnoty.
        if self._povely is None:
            client = PreClient(async_get_clientsession(self.hass))
            try:
                self._povely = await client.async_get_povel_list()
            except PreError:
                errors["base"] = "cannot_connect"

        if user_input is not None and not errors:
            povel = user_input[CONF_POVEL]
            await self.async_set_unique_id(f"{DOMAIN}_{povel}")
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=f"HDO {povel}",
                data={CONF_POVEL: povel},
                options={
                    CONF_CENA_VT: user_input[CONF_CENA_VT],
                    CONF_CENA_NT: user_input[CONF_CENA_NT],
                    CONF_POWER_SENSOR: user_input.get(CONF_POWER_SENSOR),
                    CONF_PERIODS: [],
                },
            )

        if self._povely is None:
            # Bez seznamu povelů nemá formulář co nabídnout; ať to uživatel zkusí znovu.
            return self.async_show_form(step_id="user", errors=errors)

        schema = vol.Schema(
            {
                vol.Required(CONF_POVEL): SelectSelector(
                    SelectSelectorConfig(
                        options=[
                            {"value": code, "label": label}
                            for code, label in sorted(self._povely.items())
                        ],
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(CONF_CENA_VT, default=DEFAULT_CENA_VT): _cena_selector(),
                vol.Required(CONF_CENA_NT, default=DEFAULT_CENA_NT): _cena_selector(),
                vol.Optional(CONF_POWER_SENSOR): _power_selector(),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return PreDistribuceOptionsFlow()


class PreDistribuceOptionsFlow(OptionsFlow):
    """Ceny, senzor příkonu a hlídané délky nízkého tarifu."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        options = self.config_entry.options

        if user_input is not None:
            try:
                periods = parse_periods(user_input.get(CONF_PERIODS))
            except ValueError:
                errors[CONF_PERIODS] = "invalid_periods"
            else:
                return self.async_create_entry(
                    data={
                        CONF_CENA_VT: user_input[CONF_CENA_VT],
                        CONF_CENA_NT: user_input[CONF_CENA_NT],
                        CONF_POWER_SENSOR: user_input.get(CONF_POWER_SENSOR),
                        CONF_PERIODS: periods,
                    }
                )

        current_periods = ", ".join(str(p) for p in options.get(CONF_PERIODS, []))
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_CENA_VT, default=options.get(CONF_CENA_VT, DEFAULT_CENA_VT)
                ): _cena_selector(),
                vol.Required(
                    CONF_CENA_NT, default=options.get(CONF_CENA_NT, DEFAULT_CENA_NT)
                ): _cena_selector(),
                vol.Optional(
                    CONF_POWER_SENSOR,
                    description={"suggested_value": options.get(CONF_POWER_SENSOR)},
                ): _power_selector(),
                vol.Optional(
                    CONF_PERIODS,
                    description={"suggested_value": current_periods},
                ): TextSelector(),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)
