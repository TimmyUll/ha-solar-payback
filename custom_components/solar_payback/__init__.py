"""Solar Payback: how much solar panels and a battery have earned back."""

from __future__ import annotations

import logging
import re
from pathlib import Path

import voluptuous as vol
from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_AMOUNT,
    ATTR_CONFIG_ENTRY,
    ATTR_INCLUDES_VAT,
    ATTR_MONTH,
    CARD_FILE,
    CARD_URL_BASE,
    CONF_REWARDS_INCLUDE_VAT,
    CONF_VAT,
    DEFAULT_VAT,
    DOMAIN,
    SERVICE_REMOVE_REWARD,
    SERVICE_SET_REWARD,
    VERSION,
)
from .coordinator import STORAGE_VERSION, SolarPaybackCoordinator, entry_config

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type SolarPaybackConfigEntry = ConfigEntry[SolarPaybackCoordinator]

MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def _month(value: str) -> str:
    value = str(value).strip()
    if not MONTH_RE.match(value):
        raise vol.Invalid("Month must look like 2026-09")
    return value


SET_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_CONFIG_ENTRY): cv.string,
        vol.Required(ATTR_MONTH): _month,
        vol.Required(ATTR_AMOUNT): vol.Coerce(float),
        vol.Optional(ATTR_INCLUDES_VAT): cv.boolean,
    }
)
REMOVE_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_CONFIG_ENTRY): cv.string,
        vol.Required(ATTR_MONTH): _month,
    }
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the card and the services."""
    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_URL_BASE, str(Path(__file__).parent / "frontend"), True)]
    )
    add_extra_js_url(hass, f"{CARD_URL_BASE}/{CARD_FILE}?v={VERSION}")

    def _coordinator(call: ServiceCall) -> tuple[SolarPaybackCoordinator, ConfigEntry]:
        entries = [
            e for e in hass.config_entries.async_loaded_entries(DOMAIN)
            if getattr(e, "runtime_data", None) is not None
        ]
        entry_id = call.data.get(ATTR_CONFIG_ENTRY)
        if entry_id:
            entries = [e for e in entries if e.entry_id == entry_id]
        if not entries:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="no_entry"
            )
        if len(entries) > 1:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="pick_entry"
            )
        return entries[0].runtime_data, entries[0]

    async def set_reward(call: ServiceCall) -> None:
        coordinator, entry = _coordinator(call)
        c = entry_config(entry)
        includes_vat = call.data.get(
            ATTR_INCLUDES_VAT, c.get(CONF_REWARDS_INCLUDE_VAT, False)
        )
        vat = float(c.get(CONF_VAT, DEFAULT_VAT))
        amount = abs(call.data[ATTR_AMOUNT])
        value = amount if includes_vat else amount * vat
        await coordinator.async_set_reward(call.data[ATTR_MONTH], round(value, 2))

    async def remove_reward(call: ServiceCall) -> None:
        coordinator, _ = _coordinator(call)
        await coordinator.async_set_reward(call.data[ATTR_MONTH], None)

    hass.services.async_register(DOMAIN, SERVICE_SET_REWARD, set_reward, SET_SCHEMA)
    hass.services.async_register(
        DOMAIN, SERVICE_REMOVE_REWARD, remove_reward, REMOVE_SCHEMA
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: SolarPaybackConfigEntry) -> bool:
    """Set up from a config entry."""
    coordinator = SolarPaybackCoordinator(hass, entry)
    await coordinator.async_load_rewards()
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def _async_reload(hass: HomeAssistant, entry: SolarPaybackConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: SolarPaybackConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove stored rewards with the entry."""
    await Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}").async_remove()

