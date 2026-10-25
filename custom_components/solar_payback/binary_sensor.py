"""Binary sensor that tells when last month's reward has not been entered."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SolarPaybackConfigEntry
from .calc import missing_reward_month, month_key
from .entity import SolarPaybackEntity, remove_entity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SolarPaybackConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the binary sensor, only for systems that get a monthly reward."""
    if not entry.runtime_data.rewards_enabled:
        remove_entity(hass, entry, "binary_sensor", "reward_missing")
        return
    async_add_entities([RewardMissingSensor(entry.runtime_data, "reward_missing")])


class RewardMissingSensor(SolarPaybackEntity, BinarySensorEntity):
    """On when the previous month has no reward value."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    @property
    def is_on(self) -> bool:
        """True if last month's reward is missing."""
        r = self.coordinator.data
        return missing_reward_month(r.today, r.start_date, self.coordinator.rewards) is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Which month it is about."""
        today = self.coordinator.data.today
        return {"month": month_key(today.replace(day=1) - timedelta(days=1))}
