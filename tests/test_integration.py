"""Tests for setup, config flow, sensors and services."""

from datetime import timedelta

import pytest
from homeassistant import config_entries
from homeassistant.components.recorder.models import StatisticData, StatisticMetaData
from homeassistant.components.recorder.statistics import async_add_external_statistics
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.components.recorder.common import (
    async_wait_recording_done,
)

from custom_components.solar_payback.const import DOMAIN

HOME = "abc123"


@pytest.fixture(autouse=True)
def setup_fixtures(recorder_mock, enable_custom_integrations):
    """Recorder first (it must start before hass), then custom integrations."""
    return


def _add(hass: HomeAssistant, kind: str, unit: str, values: list[float]) -> None:
    """Add hourly Tibber-like statistics (one value per hour from start)."""
    sid = f"tibber:energy_{kind}_{HOME}"
    meta = StatisticMetaData(
        has_mean=False,
        has_sum=True,
        name=None,
        source="tibber",
        statistic_id=sid,
        unit_of_measurement=unit,
        unit_class=None,
        mean_type=0,
    )
    start = dt_util.start_of_local_day(dt_util.now() - timedelta(days=2))
    total = 0.0
    rows = []
    for i, v in enumerate(values):
        total += v
        rows.append(StatisticData(start=start + timedelta(hours=i), state=total, sum=total))
    async_add_external_statistics(hass, meta, rows)


async def _setup_stats(hass: HomeAssistant) -> None:
    hours = 30
    _add(hass, "consumption", "kWh", [1.0] * hours)  # bought 1 kWh/h
    _add(hass, "totalcost", "SEK", [2.0] * hours)  # for 2 SEK/kWh
    _add(hass, "production", "kWh", [0.5] * hours)
    _add(hass, "profit", "SEK", [0.4] * hours)
    # House consumption as external statistic too (3 kWh/h)
    meta = StatisticMetaData(
        has_mean=False, has_sum=True, name=None, source="test",
        statistic_id="test:house_load", unit_of_measurement="kWh",
        unit_class=None, mean_type=0,
    )
    start = dt_util.start_of_local_day(dt_util.now() - timedelta(days=2))
    async_add_external_statistics(
        hass, meta,
        [StatisticData(start=start + timedelta(hours=i), state=3.0 * (i + 1), sum=3.0 * (i + 1)) for i in range(hours)],
    )
    await async_wait_recording_done(hass)


def _start_date() -> str:
    return (dt_util.now() - timedelta(days=2)).date().isoformat()


async def test_config_flow_tibber(hass: HomeAssistant) -> None:
    """The flow finds the Tibber home and creates an entry."""
    await _setup_stats(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"name": "Sol", "purchase_price": 100000, "start_date": _start_date()},
    )
    assert result["step_id"] == "source"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"source": "tibber"})
    # Only one home: straight to consumption
    assert result["step_id"] == "consumption"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"consumption": "test:house_load"}
    )
    assert result["step_id"] == "fees"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "grid_fee_import": 0.5, "grid_fee_export": 0.1, "supplier_markup": 0.0,
            "vat_factor": 1.25, "forecast_days": 60, "reward_label": "Grid Rewards",
            "rewards_include_vat": False,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Sol"
    assert result["data"]["import_kwh"] == f"tibber:energy_consumption_{HOME}"
    assert result["data"]["export_revenue"] == f"tibber:energy_profit_{HOME}"
    # New systems have no monthly reward unless it is turned on
    assert result["data"]["rewards_enabled"] is False


async def test_config_flow_custom_needs_price(hass: HomeAssistant) -> None:
    """Custom statistics without cost or price give an error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"name": "Sol", "purchase_price": 1000, "start_date": _start_date()},
    )
    # No Tibber statistics: straight to custom
    assert result["step_id"] == "custom"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"import_kwh": "test:import"}
    )
    assert result["errors"] == {"base": "need_price"}


async def test_sensors_and_reward_service(hass: HomeAssistant) -> None:
    """Sensors are calculated and the reward service changes them."""
    await _setup_stats(hass)
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Sol",
        data={
            "purchase_price": 100000,
            "start_date": _start_date(),
            "source": "tibber",
            "tibber_home": HOME,
            "import_kwh": f"tibber:energy_consumption_{HOME}",
            "import_cost": f"tibber:energy_totalcost_{HOME}",
            "export_kwh": f"tibber:energy_production_{HOME}",
            "export_revenue": f"tibber:energy_profit_{HOME}",
            "consumption": "test:house_load",
            "grid_fee_import": 0.5,
            "grid_fee_export": 0.1,
            "vat_factor": 1.25,
            "forecast_days": 60,
            "reward_label": "Grid Rewards",
            "rewards_include_vat": False,
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # 30 hours:
    # home: (3 - 1) * (2 + 0.5) = 5/h, sold: 0.4 + 0.5 * 0.1 = 0.45/h
    state = hass.states.get("sensor.sol_saved_so_far")
    assert state is not None
    assert float(state.state) == pytest.approx(30 * 5.45, rel=1e-3)
    assert state.attributes["unit_of_measurement"] == hass.config.currency
    assert len(state.attributes["days"]) >= 3
    assert state.attributes["config_entry_id"] == entry.entry_id
    assert state.attributes["rewards"] == {}
    assert hass.states.get("sensor.sol_paid_back") is not None
    assert hass.states.get("binary_sensor.sol_monthly_reward_missing") is not None

    month = dt_util.now().strftime("%Y-%m")
    await hass.services.async_call(
        DOMAIN, "set_monthly_reward", {"month": month, "amount": 100}, blocking=True
    )
    await hass.async_block_till_done()
    state = hass.states.get("sensor.sol_saved_so_far")
    assert float(state.state) == pytest.approx(30 * 5.45 + 125, rel=1e-3)
    assert hass.states.get("sensor.sol_saved_so_far").attributes["rewards"] == {month: 125.0}
    rewards = hass.states.get("sensor.sol_monthly_rewards_total")
    assert float(rewards.state) == pytest.approx(125)

    await hass.services.async_call(
        DOMAIN, "remove_monthly_reward", {"month": month}, blocking=True
    )
    await hass.async_block_till_done()
    assert float(hass.states.get("sensor.sol_saved_so_far").state) == pytest.approx(30 * 5.45, rel=1e-3)

    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_options_flow(hass: HomeAssistant) -> None:
    """Settings can be changed afterwards."""
    await _setup_stats(hass)
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Sol",
        data={
            "purchase_price": 1000,
            "start_date": _start_date(),
            "source": "custom",
            "import_kwh": f"tibber:energy_consumption_{HOME}",
            "import_cost": f"tibber:energy_totalcost_{HOME}",
            "consumption": "test:house_load",
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    # Entries from before the option count as having rewards
    assert hass.states.get("binary_sensor.sol_monthly_reward_missing") is not None
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "purchase_price": 2000, "start_date": _start_date(), "consumption": "test:house_load",
            "grid_fee_import": 0.0, "grid_fee_export": 0.0, "supplier_markup": 0.0,
            "vat_factor": 1.25, "forecast_days": 30, "rewards_enabled": False,
            "reward_label": "Rewards", "rewards_include_vat": True,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    state = hass.states.get("sensor.sol_saved_so_far")
    assert state.attributes["purchase_price"] == 2000
    assert state.attributes["reward_label"] == "Rewards"
    # Turning rewards off removes the reminder and the rewards total
    assert state.attributes["rewards_enabled"] is False
    assert state.attributes["missing_reward_month"] is None
    assert hass.states.get("binary_sensor.sol_monthly_reward_missing") is None
    assert hass.states.get("sensor.sol_monthly_rewards_total") is None


async def test_rewards_ignored_when_off(hass: HomeAssistant) -> None:
    """A stored reward does not count when the system has no monthly reward."""
    await _setup_stats(hass)
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Sol",
        data={
            "purchase_price": 100000,
            "start_date": _start_date(),
            "source": "custom",
            "import_kwh": f"tibber:energy_consumption_{HOME}",
            "import_cost": f"tibber:energy_totalcost_{HOME}",
            "export_kwh": f"tibber:energy_production_{HOME}",
            "export_revenue": f"tibber:energy_profit_{HOME}",
            "consumption": "test:house_load",
            "grid_fee_import": 0.5,
            "grid_fee_export": 0.1,
            "rewards_enabled": False,
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    month = dt_util.now().strftime("%Y-%m")
    await hass.services.async_call(
        DOMAIN, "set_monthly_reward", {"month": month, "amount": 100}, blocking=True
    )
    await hass.async_block_till_done()
    state = hass.states.get("sensor.sol_saved_so_far")
    assert float(state.state) == pytest.approx(30 * 5.45, rel=1e-3)
    assert all(m["reward"] == 0 for m in state.attributes["months"])
