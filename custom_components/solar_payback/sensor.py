"""Sensors for Solar Payback."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SolarPaybackConfigEntry
from .calc import Result, month_key
from .const import (
    CONF_FORECAST_DAYS,
    CONF_GRID_FEE_IMPORT,
    CONF_REWARD_LABEL,
    DEFAULT_FORECAST_DAYS,
    DEFAULT_GRID_FEE_IMPORT,
    DEFAULT_REWARD_LABEL,
)
from .coordinator import SolarPaybackCoordinator, entry_config
from .entity import SolarPaybackEntity

CURRENCY = "currency"  # replaced with the configured currency


@dataclass(frozen=True, kw_only=True)
class PaybackSensorDescription(SensorEntityDescription):
    """Describes a payback sensor."""

    value_fn: Callable[[Result], float | date | None]


def _round(value: float | None, digits: int = 0) -> float | None:
    return None if value is None else round(value, digits)


SENSORS: tuple[PaybackSensorDescription, ...] = (
    PaybackSensorDescription(
        key="saved_total",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=CURRENCY,
        suggested_display_precision=0,
        value_fn=lambda r: _round(r.total, 2),
    ),
    PaybackSensorDescription(
        key="paid_back",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda r: _round(r.paid_back_fraction * 100, 2),
    ),
    PaybackSensorDescription(
        key="remaining",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=CURRENCY,
        suggested_display_precision=0,
        value_fn=lambda r: _round(r.remaining, 2),
    ),
    PaybackSensorDescription(
        key="payback_date",
        device_class=SensorDeviceClass.DATE,
        value_fn=lambda r: r.payback_date,
    ),
    PaybackSensorDescription(
        key="payback_years",
        native_unit_of_measurement=UnitOfTime.YEARS,
        suggested_display_precision=1,
        value_fn=lambda r: _round(r.payback_years, 2),
    ),
    PaybackSensorDescription(
        key="daily_rate",
        native_unit_of_measurement=f"{CURRENCY}/d",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda r: _round(r.daily_rate, 2),
    ),
    PaybackSensorDescription(
        key="saved_this_month",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=CURRENCY,
        suggested_display_precision=0,
        value_fn=lambda r: _round(r.month_total(month_key(r.today)), 2),
    ),
    PaybackSensorDescription(
        key="rewards_total",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=CURRENCY,
        suggested_display_precision=0,
        value_fn=lambda r: _round(sum(m.reward for m in r.months), 2),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SolarPaybackConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        (TotalSensor if d.key == "saved_total" else PaybackSensor)(coordinator, d)
        for d in SENSORS
    )


class PaybackSensor(SolarPaybackEntity, SensorEntity):
    """A value from the calculation."""

    entity_description: PaybackSensorDescription

    def __init__(
        self, coordinator: SolarPaybackCoordinator, description: PaybackSensorDescription
    ) -> None:
        """Set up the sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description
        unit = description.native_unit_of_measurement
        if unit and CURRENCY in unit:
            self._attr_native_unit_of_measurement = unit.replace(
                CURRENCY, coordinator.hass.config.currency
            )

    @property
    def native_value(self) -> float | date | None:
        """Current value."""
        return self.entity_description.value_fn(self.coordinator.data)


class TotalSensor(PaybackSensor):
    """Saved so far, with everything the card needs as attributes."""

    # The card data is rebuilt every hour, keep it out of the database.
    _unrecorded_attributes = frozenset(
        {"days", "months", "purchase_price", "start_date", "daily_rate",
         "payback_date", "reward_label", "grid_fee_import", "forecast_days",
         "estimated_until"}
    )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Data for the card."""
        r = self.coordinator.data
        c = entry_config(self.coordinator.config_entry)
        estimated = [d.day for d in r.days if d.home_estimated]
        paid = r.payback_date
        return {
            "purchase_price": r.purchase_price,
            "start_date": r.start_date.isoformat(),
            "daily_rate": round(r.daily_rate, 2),
            "payback_date": paid.isoformat() if paid else None,
            "reward_label": c.get(CONF_REWARD_LABEL, DEFAULT_REWARD_LABEL),
            "grid_fee_import": c.get(CONF_GRID_FEE_IMPORT, DEFAULT_GRID_FEE_IMPORT),
            "forecast_days": c.get(CONF_FORECAST_DAYS, DEFAULT_FORECAST_DAYS),
            "estimated_until": estimated[-1].isoformat() if estimated else None,
            "months": [
                {
                    "month": m.month,
                    "home": round(m.home, 1),
                    "sold": round(m.sold, 1),
                    "reward": round(m.reward, 1),
                    "estimated": m.estimated,
                }
                for m in r.months
            ],
            # [date, home, sold, reward] per day
            "days": [
                [d.day.isoformat(), round(d.home, 1), round(d.sold, 1), round(d.reward, 1)]
                for d in r.days
            ],
        }
