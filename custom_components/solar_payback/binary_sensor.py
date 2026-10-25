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
from .calc import month_key
from .entity import SolarPaybackEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SolarPaybackConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the binary sensor."""
    async_add_entities([RewardMissingSensor(entry.runtime_data, "reward_missing")])


class RewardMissingSensor(SolarPaybackEntity, BinarySensorEntity):
    """On when the previous month has no reward value."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def _previous_month(self) -> str:
        today = self.coordinator.data.today
        return month_key(today.replace(day=1) - timedelta(days=1))

    @property
    def is_on(self) -> bool:
        """True if last month's reward is missing."""
        prev = self._previous_month()
        if prev < month_key(self.coordinator.data.start_date):
            return False
        return prev not in self.coordinator.rewards

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Which month it is about."""
        return {"month": self._previous_month()}
