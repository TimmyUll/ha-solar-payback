"""Tests for the calculation."""

from datetime import UTC, date, datetime, timedelta

import pytest

from custom_components.solar_payback.calc import Series, Settings, calculate

START = date(2026, 6, 1)


def ts(day: int, hour: int, month: int = 6) -> float:
    return datetime(2026, month, day, hour, tzinfo=UTC).timestamp()


def settings(**kw) -> Settings:
    return Settings(purchase_price=10000, start_date=START, **kw)


def test_home_value_uses_supplier_cost_and_grid_fee() -> None:
    # 3 kWh used, 1 kWh bought for 2.0 -> 2 kWh from solar worth (2.0 + 0.5) each
    series = Series(
        import_kwh={ts(1, 10): 1.0},
        import_cost={ts(1, 10): 2.0},
        consumption={ts(1, 10): 3.0},
    )
    r = calculate(settings(grid_fee_import=0.5), series, {}, UTC, datetime(2026, 6, 2, 12, tzinfo=UTC))
    assert r.days[0].home == pytest.approx(5.0)
    assert r.total == pytest.approx(5.0)


def test_spot_price_fallback_with_markup_and_vat() -> None:
    series = Series(
        import_kwh={ts(1, 10): 0.0},
        consumption={ts(1, 10): 2.0},
        price={ts(1, 10): 1.0},
    )
    r = calculate(settings(supplier_markup=0.2, vat_factor=1.25), series, {}, UTC, datetime(2026, 6, 2, tzinfo=UTC))
    assert r.days[0].home == pytest.approx(2 * 1.5)


def test_sold_uses_revenue_and_grid_compensation() -> None:
    series = Series(
        import_kwh={},
        consumption={ts(1, 12): 0.0},
        export_kwh={ts(1, 12): 4.0},
        export_revenue={ts(1, 12): 3.0},
    )
    r = calculate(settings(grid_fee_export=0.1), series, {}, UTC, datetime(2026, 6, 2, tzinfo=UTC))
    assert r.days[0].sold == pytest.approx(3.4)


def test_sold_valued_at_spot_without_revenue() -> None:
    series = Series(
        import_kwh={},
        consumption={ts(1, 12): 0.0},
        export_kwh={ts(1, 12): 2.0},
        price={ts(1, 12): 0.8},
    )
    r = calculate(settings(), series, {}, UTC, datetime(2026, 6, 2, tzinfo=UTC))
    assert r.days[0].sold == pytest.approx(1.6)


def test_gap_in_consumption_is_caught_up() -> None:
    # Hour 11 missing consumption; the counter jump at 12 includes it.
    series = Series(
        import_kwh={ts(1, 10): 0.0, ts(1, 11): 1.0, ts(1, 12): 0.0},
        import_cost={ts(1, 11): 1.0},
        consumption={ts(1, 10): 1.0, ts(1, 12): 2.0},
    )
    r = calculate(settings(), series, {}, UTC, datetime(2026, 6, 2, tzinfo=UTC))
    # hour 10: 1 kWh solar at price 0 (no price known yet) -> 0
    # hour 12: 2 used - 1 bought during gap, at gap price 1.0 -> 1.0
    assert r.days[0].home == pytest.approx(1.0)


def test_days_before_consumption_are_estimated() -> None:
    consumption = {ts(d, 10, 7): 2.0 for d in range(1, 11)}
    imp = {k: 0.0 for k in consumption}
    price = {k: 1.0 for k in consumption}
    series = Series(import_kwh=imp, consumption=consumption, price=price)
    r = calculate(settings(), series, {}, UTC, datetime(2026, 7, 11, 12, tzinfo=UTC))
    june = [d for d in r.days if d.day.month == 6]
    assert len(june) == 30
    assert all(d.home_estimated and d.home == pytest.approx(2.0 * 1.25) for d in june)
    assert r.months[0].estimated


def test_rewards_spread_and_estimated_from_last_month() -> None:
    series = Series(import_kwh={}, consumption={})
    rewards = {"2026-06": 300.0}
    r = calculate(settings(), series, rewards, UTC, datetime(2026, 7, 31, 12, tzinfo=UTC))
    june = next(m for m in r.months if m.month == "2026-06")
    july = next(m for m in r.months if m.month == "2026-07")
    assert june.reward == pytest.approx(300.0)
    assert july.reward == pytest.approx(310.0)  # 10/day for 31 days
    assert not any(d.reward_estimated for d in r.days if d.day.month == 6)
    assert all(d.reward_estimated for d in r.days if d.day.month == 7)


def test_forecast_and_payback() -> None:
    series = Series(import_kwh={}, consumption={})
    rewards = {"2026-06": 3000.0}  # 100 per day
    now = datetime(2026, 6, 30, 12, tzinfo=UTC)
    r = calculate(settings(forecast_days=10), series, rewards, UTC, now)
    assert r.daily_rate == pytest.approx(100.0)
    assert r.total == pytest.approx(3000.0)
    assert r.remaining == pytest.approx(7000.0)
    assert r.payback_date == date(2026, 6, 30) + timedelta(days=70)
    assert r.paid_back_fraction == pytest.approx(0.3)


def test_paid_off_date_is_reached_day() -> None:
    series = Series(import_kwh={}, consumption={})
    r = calculate(
        Settings(purchase_price=1000, start_date=START), series, {"2026-06": 3000.0}, UTC,
        datetime(2026, 6, 30, 12, tzinfo=UTC),
    )
    assert r.remaining == 0
    assert r.payback_date == date(2026, 6, 10)


def test_nothing_before_start_date() -> None:
    series = Series(
        import_kwh={ts(31, 10, 5): 0.0},
        consumption={ts(31, 10, 5): 5.0},
        price={ts(31, 10, 5): 1.0},
    )
    r = calculate(settings(), series, {}, UTC, datetime(2026, 6, 2, tzinfo=UTC))
    assert r.days[0].day == START
    assert r.total == pytest.approx(0.0)


def test_missing_reward_month() -> None:
    from custom_components.solar_payback.calc import missing_reward_month

    today = date(2026, 10, 25)
    assert missing_reward_month(today, START, {}) == "2026-09"
    assert missing_reward_month(today, START, {"2026-09": 1.0}) is None
    # Last month is before the start date
    assert missing_reward_month(today, date(2026, 10, 1), {}) is None
