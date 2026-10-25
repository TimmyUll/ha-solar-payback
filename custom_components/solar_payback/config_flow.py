"""Config flow for Solar Payback."""

from __future__ import annotations

from datetime import date
from typing import Any

import voluptuous as vol
from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.statistics import list_statistic_ids
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import selector

from .const import (
    CONF_CONSUMPTION,
    CONF_EXPORT_KWH,
    CONF_EXPORT_REVENUE,
    CONF_FORECAST_DAYS,
    CONF_GRID_FEE_EXPORT,
    CONF_GRID_FEE_IMPORT,
    CONF_IMPORT_COST,
    CONF_IMPORT_KWH,
    CONF_MARKUP,
    CONF_NAME,
    CONF_PRICE,
    CONF_PURCHASE_PRICE,
    CONF_REWARD_LABEL,
    CONF_REWARDS_INCLUDE_VAT,
    CONF_SOURCE,
    CONF_START_DATE,
    CONF_TIBBER_HOME,
    CONF_VAT,
    DEFAULT_FORECAST_DAYS,
    DEFAULT_GRID_FEE_EXPORT,
    DEFAULT_GRID_FEE_IMPORT,
    DEFAULT_MARKUP,
    DEFAULT_NAME,
    DEFAULT_REWARD_LABEL,
    DEFAULT_VAT,
    DOMAIN,
    SOURCE_CUSTOM,
    SOURCE_TIBBER,
    TIBBER_PREFIX,
)

MONEY = selector.NumberSelector(
    selector.NumberSelectorConfig(min=0, step="any", mode=selector.NumberSelectorMode.BOX)
)
ENERGY_STAT = selector.StatisticSelector(selector.StatisticSelectorConfig())
PRICE_ENTITY = selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor"))


async def _tibber_homes(hass: HomeAssistant) -> list[str]:
    """Tibber home ids that have consumption statistics."""
    ids = await get_instance(hass).async_add_executor_job(
        list_statistic_ids, hass, None, "sum"
    )
    return sorted(
        s["statistic_id"][len(TIBBER_PREFIX) :]
        for s in ids
        if s["statistic_id"].startswith(TIBBER_PREFIX)
    )


def _tibber_ids(home: str) -> dict[str, str]:
    return {
        CONF_IMPORT_KWH: f"tibber:energy_consumption_{home}",
        CONF_IMPORT_COST: f"tibber:energy_totalcost_{home}",
        CONF_EXPORT_KWH: f"tibber:energy_production_{home}",
        CONF_EXPORT_REVENUE: f"tibber:energy_profit_{home}",
    }


def _fees_schema(c: dict[str, Any]) -> dict[Any, Any]:
    return {
        vol.Required(
            CONF_GRID_FEE_IMPORT, default=c.get(CONF_GRID_FEE_IMPORT, DEFAULT_GRID_FEE_IMPORT)
        ): MONEY,
        vol.Required(
            CONF_GRID_FEE_EXPORT, default=c.get(CONF_GRID_FEE_EXPORT, DEFAULT_GRID_FEE_EXPORT)
        ): MONEY,
        vol.Required(CONF_MARKUP, default=c.get(CONF_MARKUP, DEFAULT_MARKUP)): MONEY,
        vol.Required(CONF_VAT, default=c.get(CONF_VAT, DEFAULT_VAT)): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=1, max=2, step=0.01, mode=selector.NumberSelectorMode.BOX
            )
        ),
        vol.Required(
            CONF_FORECAST_DAYS, default=c.get(CONF_FORECAST_DAYS, DEFAULT_FORECAST_DAYS)
        ): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=7, max=730, step=1, mode=selector.NumberSelectorMode.BOX
            )
        ),
        vol.Required(
            CONF_REWARD_LABEL, default=c.get(CONF_REWARD_LABEL, DEFAULT_REWARD_LABEL)
        ): selector.TextSelector(),
        vol.Required(
            CONF_REWARDS_INCLUDE_VAT, default=c.get(CONF_REWARDS_INCLUDE_VAT, False)
        ): selector.BooleanSelector(),
    }


def _optional(key: str, c: dict[str, Any]) -> vol.Optional:
    """Optional field that keeps its current value as suggestion."""
    if c.get(key):
        return vol.Optional(key, description={"suggested_value": c[key]})
    return vol.Optional(key)


def _custom_schema(c: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_IMPORT_KWH, default=c.get(CONF_IMPORT_KWH, vol.UNDEFINED)): ENERGY_STAT,
            _optional(CONF_IMPORT_COST, c): ENERGY_STAT,
            _optional(CONF_EXPORT_KWH, c): ENERGY_STAT,
            _optional(CONF_EXPORT_REVENUE, c): ENERGY_STAT,
            _optional(CONF_PRICE, c): PRICE_ENTITY,
        }
    )


def _consumption_schema(c: dict[str, Any], need_price: bool) -> vol.Schema:
    schema: dict[Any, Any] = {
        vol.Required(CONF_CONSUMPTION, default=c.get(CONF_CONSUMPTION, vol.UNDEFINED)): ENERGY_STAT,
    }
    if need_price:
        schema[_optional(CONF_PRICE, c)] = PRICE_ENTITY
    return vol.Schema(schema)


def _check_custom(data: dict[str, Any]) -> dict[str, str]:
    errors: dict[str, str] = {}
    if not data.get(CONF_IMPORT_COST) and not data.get(CONF_PRICE):
        errors["base"] = "need_price"
    elif data.get(CONF_EXPORT_KWH) and not data.get(CONF_EXPORT_REVENUE) and not data.get(CONF_PRICE):
        errors["base"] = "need_export_value"
    return errors


class SolarPaybackConfigFlow(ConfigFlow, domain=DOMAIN):
    """Set up Solar Payback step by step."""

    VERSION = 1

    def __init__(self) -> None:
        """Start with empty data."""
        self._data: dict[str, Any] = {}
        self._homes: list[str] = []

    @staticmethod
    @callback
    def async_get_options_flow(entry: ConfigEntry) -> SolarPaybackOptionsFlow:
        """Options."""
        return SolarPaybackOptionsFlow()

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Step 1: what the system cost and when it started."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if date.fromisoformat(user_input[CONF_START_DATE]) > date.today():
                errors[CONF_START_DATE] = "start_in_future"
            else:
                self._data.update(user_input)
                return await self.async_step_source()
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME, default=DEFAULT_NAME): selector.TextSelector(),
                    vol.Required(CONF_PURCHASE_PRICE): MONEY,
                    vol.Required(CONF_START_DATE): selector.DateSelector(),
                }
            ),
            errors=errors,
        )

    async def async_step_source(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Step 2: where bought and sold energy comes from."""
        self._homes = await _tibber_homes(self.hass)
        options = [SOURCE_TIBBER, SOURCE_CUSTOM] if self._homes else [SOURCE_CUSTOM]
        if len(options) == 1:
            return await self.async_step_custom()
        if user_input is not None:
            self._data[CONF_SOURCE] = user_input[CONF_SOURCE]
            if user_input[CONF_SOURCE] == SOURCE_TIBBER:
                return await self.async_step_tibber()
            return await self.async_step_custom()
        return self.async_show_form(
            step_id="source",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SOURCE, default=SOURCE_TIBBER): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=options, translation_key=CONF_SOURCE
                        )
                    )
                }
            ),
        )

    async def async_step_tibber(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Step 3a: pick the Tibber home."""
        if len(self._homes) == 1 and user_input is None:
            user_input = {CONF_TIBBER_HOME: self._homes[0]}
        if user_input is not None:
            self._data[CONF_SOURCE] = SOURCE_TIBBER
            self._data[CONF_TIBBER_HOME] = user_input[CONF_TIBBER_HOME]
            self._data.update(_tibber_ids(user_input[CONF_TIBBER_HOME]))
            return await self.async_step_consumption()
        return self.async_show_form(
            step_id="tibber",
            data_schema=vol.Schema(
                {vol.Required(CONF_TIBBER_HOME): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=self._homes)
                )}
            ),
        )

    async def async_step_custom(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Step 3b: pick statistics for bought and sold energy."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _check_custom(user_input)
            if not errors:
                self._data[CONF_SOURCE] = SOURCE_CUSTOM
                self._data.update(user_input)
                return await self.async_step_consumption()
        return self.async_show_form(
            step_id="custom",
            data_schema=self.add_suggested_values_to_schema(
                _custom_schema({}), user_input or {}
            ),
            errors=errors,
        )

    async def async_step_consumption(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Step 4: the house's consumption (and a spot price as backup for Tibber)."""
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_fees()
        return self.async_show_form(
            step_id="consumption",
            data_schema=_consumption_schema(
                {}, need_price=self._data.get(CONF_SOURCE) == SOURCE_TIBBER
            ),
        )

    async def async_step_fees(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Step 5: grid fees and other settings."""
        if user_input is not None:
            self._data.update(user_input)
            data = {k: v for k, v in self._data.items() if v not in (None, "")}
            return self.async_create_entry(title=data.pop(CONF_NAME), data=data)
        return self.async_show_form(step_id="fees", data_schema=vol.Schema(_fees_schema({})))


class SolarPaybackOptionsFlow(OptionsFlow):
    """Change the settings afterwards."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Investment, consumption and fees."""
        c = {**self.config_entry.data, **self.config_entry.options}
        if user_input is not None:
            if c.get(CONF_SOURCE) == SOURCE_TIBBER:
                user_input.setdefault(CONF_PRICE, None)
            return self.async_create_entry(data=user_input)
        schema: dict[Any, Any] = {
            vol.Required(CONF_PURCHASE_PRICE, default=c[CONF_PURCHASE_PRICE]): MONEY,
            vol.Required(CONF_START_DATE, default=c[CONF_START_DATE]): selector.DateSelector(),
            vol.Required(CONF_CONSUMPTION, default=c[CONF_CONSUMPTION]): ENERGY_STAT,
        }
        if c.get(CONF_SOURCE) == SOURCE_TIBBER:
            schema[_optional(CONF_PRICE, c)] = PRICE_ENTITY
        schema.update(_fees_schema(c))
        return self.async_show_form(step_id="init", data_schema=vol.Schema(schema))
