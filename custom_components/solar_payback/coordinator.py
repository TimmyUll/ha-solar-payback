"""Fetches statistics and runs the calculation once an hour."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.statistics import statistics_during_period
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .calc import Result, Series, Settings, calculate
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
    CONF_PRICE,
    CONF_PURCHASE_PRICE,
    CONF_REWARDS_ENABLED,
    CONF_START_DATE,
    CONF_VAT,
    DEFAULT_FORECAST_DAYS,
    DEFAULT_GRID_FEE_EXPORT,
    DEFAULT_GRID_FEE_IMPORT,
    DEFAULT_MARKUP,
    DEFAULT_VAT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)
STORAGE_VERSION = 1


def entry_config(entry: ConfigEntry) -> dict[str, Any]:
    """Entry data with options on top."""
    return {**entry.data, **entry.options}


class SolarPaybackCoordinator(DataUpdateCoordinator[Result]):
    """Keeps the latest calculation result."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Set up the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(hours=1),
        )
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}"
        )
        self.rewards: dict[str, float] = {}

    async def async_load_rewards(self) -> None:
        """Load stored monthly rewards."""
        data = await self._store.async_load() or {}
        self.rewards = {k: float(v) for k, v in data.get("rewards", {}).items()}

    async def async_set_reward(self, month: str, value: float | None) -> None:
        """Store (or remove with None) a month's reward value and recalculate."""
        if value is None:
            self.rewards.pop(month, None)
        else:
            self.rewards[month] = value
        await self._store.async_save({"rewards": dict(sorted(self.rewards.items()))})
        await self.async_refresh()

    @property
    def rewards_enabled(self) -> bool:
        """Whether the system gets a monthly reward (on for entries from before the option)."""
        return bool(entry_config(self.config_entry).get(CONF_REWARDS_ENABLED, True))

    @property
    def settings(self) -> Settings:
        """Settings from the config entry."""
        c = entry_config(self.config_entry)
        return Settings(
            purchase_price=float(c[CONF_PURCHASE_PRICE]),
            start_date=date.fromisoformat(c[CONF_START_DATE]),
            grid_fee_import=float(c.get(CONF_GRID_FEE_IMPORT, DEFAULT_GRID_FEE_IMPORT)),
            grid_fee_export=float(c.get(CONF_GRID_FEE_EXPORT, DEFAULT_GRID_FEE_EXPORT)),
            supplier_markup=float(c.get(CONF_MARKUP, DEFAULT_MARKUP)),
            vat_factor=float(c.get(CONF_VAT, DEFAULT_VAT)),
            forecast_days=int(c.get(CONF_FORECAST_DAYS, DEFAULT_FORECAST_DAYS)),
        )

    async def _async_update_data(self) -> Result:
        c = entry_config(self.config_entry)
        settings = self.settings
        tz = ZoneInfo(self.hass.config.time_zone)
        start = datetime.combine(settings.start_date, datetime.min.time(), tz)
        now = dt_util.now()

        sums = {
            key: c.get(key)
            for key in (
                CONF_IMPORT_KWH,
                CONF_IMPORT_COST,
                CONF_EXPORT_KWH,
                CONF_EXPORT_REVENUE,
                CONF_CONSUMPTION,
            )
            if c.get(key)
        }
        price_id = c.get(CONF_PRICE)
        try:
            changes = await self._fetch(start, now, set(sums.values()), "change")
            means = await self._fetch(start, now, {price_id}, "mean") if price_id else {}
        except Exception as err:
            raise UpdateFailed(f"Could not read statistics: {err}") from err

        def get(key: str) -> dict[float, float]:
            sid = sums.get(key)
            return changes.get(sid, {}) if sid else {}

        series = Series(
            import_kwh=get(CONF_IMPORT_KWH),
            consumption=get(CONF_CONSUMPTION),
            import_cost=get(CONF_IMPORT_COST),
            export_kwh=get(CONF_EXPORT_KWH),
            export_revenue=get(CONF_EXPORT_REVENUE),
            price=means.get(price_id, {}) if price_id else {},
        )
        if not series.consumption:
            _LOGGER.warning(
                "No statistics found for the house consumption (%s)",
                sums.get(CONF_CONSUMPTION),
            )
        return await self.hass.async_add_executor_job(
            calculate,
            settings,
            series,
            dict(self.rewards) if self.rewards_enabled else {},
            tz,
            now,
        )

    async def _fetch(
        self, start: datetime, end: datetime, ids: set[str], kind: str
    ) -> dict[str, dict[float, float]]:
        """Hourly statistics as {statistic_id: {hour start timestamp: value}}."""
        if not ids:
            return {}
        rows = await get_instance(self.hass).async_add_executor_job(
            statistics_during_period,
            self.hass,
            dt_util.as_utc(start),
            dt_util.as_utc(end),
            ids,
            "hour",
            None,
            {kind},
        )
        out: dict[str, dict[float, float]] = {}
        for sid, points in rows.items():
            values: dict[float, float] = {}
            for p in points:
                value = p.get(kind)
                if value is None:
                    continue
                ts = p["start"]
                if isinstance(ts, datetime):
                    ts = ts.timestamp()
                values[float(ts)] = float(value)
            out[sid] = values
        return out
