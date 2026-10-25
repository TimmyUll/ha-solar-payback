"""Base entity for Solar Payback."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, VERSION
from .coordinator import SolarPaybackCoordinator


class SolarPaybackEntity(CoordinatorEntity[SolarPaybackCoordinator]):
    """Common entity setup."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: SolarPaybackCoordinator, key: str) -> None:
        """Set up the entity."""
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self._attr_translation_key = key
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            entry_type=DeviceEntryType.SERVICE,
            sw_version=VERSION,
        )
