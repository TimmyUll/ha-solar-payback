"""The payback calculation.

Pure Python without Home Assistant imports so it can be tested on its own.

Everything is valued per hour since the start date:

* Home: energy the house used but did not buy (solar and battery) is worth what
  it would otherwise have cost, i.e. the hourly price plus the grid fee.
* Sold: the supplier's revenue for exported energy plus the grid company's
  compensation per exported kWh.
* Reward: a monthly amount (for example Tibber Grid Rewards), spread over the
  days of the month. Months without a value use the latest known month.
"""

from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, tzinfo


@dataclass
class Settings:
    """User settings that affect the calculation."""

    purchase_price: float
    start_date: date
    grid_fee_import: float = 0.0
    grid_fee_export: float = 0.0
    supplier_markup: float = 0.0
    vat_factor: float = 1.25
    forecast_days: int = 60


@dataclass
class Series:
    """Hourly long-term statistics, keyed by the hour's start as a UNIX timestamp."""

    import_kwh: dict[float, float]
    consumption: dict[float, float]
    import_cost: dict[float, float] = field(default_factory=dict)
    export_kwh: dict[float, float] = field(default_factory=dict)
    export_revenue: dict[float, float] = field(default_factory=dict)
    price: dict[float, float] = field(default_factory=dict)


@dataclass
class Day:
    """Savings for one local calendar day."""

    day: date
    home: float = 0.0
    sold: float = 0.0
    reward: float = 0.0
    has_consumption: bool = False
    home_estimated: bool = False
    reward_estimated: bool = False
    acc: float = 0.0

    @property
    def total(self) -> float:
        """Total savings for the day."""
        return self.home + self.sold + self.reward


@dataclass
class Month:
    """Savings for one calendar month."""

    month: str
    home: float
    sold: float
    reward: float
    estimated: bool

    @property
    def total(self) -> float:
        """Total savings for the month."""
        return self.home + self.sold + self.reward


@dataclass
class Result:
    """The outcome of a calculation."""

    days: list[Day]
    months: list[Month]
    total: float
    daily_rate: float
    purchase_price: float
    start_date: date
    today: date

    @property
    def paid_back_fraction(self) -> float:
        """How much of the purchase price has been earned back (0..1+)."""
        if self.purchase_price <= 0:
            return 1.0
        return self.total / self.purchase_price

    @property
    def remaining(self) -> float:
        """Amount left until the purchase price is earned back."""
        return max(0.0, self.purchase_price - self.total)

    @property
    def payback_date(self) -> date | None:
        """Estimated payback date at the recent daily rate."""
        if self.remaining <= 0:
            return self._reached_date()
        if self.daily_rate <= 0:
            return None
        days_left = self.remaining / self.daily_rate
        if days_left > 365 * 100:
            return None
        return self.today + timedelta(days=round(days_left))

    @property
    def payback_years(self) -> float | None:
        """Years from the start date to the (estimated) payback date."""
        paid = self.payback_date
        if paid is None:
            return None
        return (paid - self.start_date).days / 365.25

    def _reached_date(self) -> date:
        for d in self.days:
            if d.acc >= self.purchase_price:
                return d.day
        return self.today

    def month_total(self, month: str) -> float:
        """Total savings for a month (YYYY-MM), 0 if unknown."""
        for m in self.months:
            if m.month == month:
                return m.total
        return 0.0


def month_key(d: date) -> str:
    """Return YYYY-MM for a date."""
    return f"{d.year:04d}-{d.month:02d}"


def calculate(
    settings: Settings,
    series: Series,
    rewards: dict[str, float],
    tz: tzinfo,
    now: datetime,
) -> Result:
    """Calculate savings per day from hourly statistics.

    ``rewards`` maps YYYY-MM to the value of that month's reward, already
    including whatever VAT it saves.
    """
    today = now.astimezone(tz).date()
    days: dict[date, Day] = {}

    def day_for(ts: float) -> Day:
        d = datetime.fromtimestamp(ts, tz).date()
        if d not in days:
            days[d] = Day(d)
        return days[d]

    imp, load = series.import_kwh, series.consumption
    hours = sorted(set(imp) | set(series.export_kwh) | set(load))
    first_load = min(load) if load else float("inf")
    # Hours without consumption data (e.g. Home Assistant was down) catch up in the
    # next hour that has data, because the consumption counter jumps then. The
    # energy bought during the gap is saved and subtracted there, otherwise the
    # gap's consumption would look free.
    gap_kwh = gap_cost = 0.0
    last_price: float | None = None
    for ts in hours:
        d = day_for(ts)
        if d.day < settings.start_date:
            continue
        bought = max(0.0, imp.get(ts) or 0.0)
        exported = max(0.0, series.export_kwh.get(ts) or 0.0)
        # Price that hour: the supplier's own cost per kWh, otherwise the spot price.
        price = None
        if bought > 0.05 and ts in series.import_cost:
            price = series.import_cost[ts] / bought
        spot = series.price.get(ts)
        if price is None and spot is not None:
            price = (spot + settings.supplier_markup) * settings.vat_factor
        if price is None:
            price = last_price if last_price is not None else 0.0
        last_price = price
        if series.export_revenue:
            d.sold += series.export_revenue.get(ts) or 0.0
        elif spot is not None:
            d.sold += exported * spot
        d.sold += exported * settings.grid_fee_export
        if ts in load:
            d.has_consumption = True
            used = max(0.0, load.get(ts) or 0.0)
            bought_total = bought + gap_kwh
            avg_price = (bought * price + gap_cost) / bought_total if bought_total > 0 else price
            d.home += (used - bought_total) * (avg_price + settings.grid_fee_import)
            gap_kwh = gap_cost = 0.0
        elif ts > first_load:
            gap_kwh += bought
            gap_cost += bought * price

    # Every day from start to today
    d = settings.start_date
    while d <= today:
        days.setdefault(d, Day(d))
        d += timedelta(days=1)
    day_list = sorted((x for x in days.values() if x.day >= settings.start_date), key=lambda x: x.day)

    # Days before the consumption statistics existed: average of the first 30 full days with data.
    first_load_day = (
        datetime.fromtimestamp(first_load, tz).date() if load else today + timedelta(days=1)
    )
    with_load = [x for x in day_list if x.has_consumption and x.day != today]
    first30 = with_load[:30]
    home_avg = sum(x.home for x in first30) / len(first30) if first30 else 0.0
    for x in day_list:
        if not x.has_consumption and x.day < first_load_day:
            x.home = home_avg
            x.home_estimated = True

    # Monthly rewards, spread over the days of the month (from the start date).
    by_month: dict[str, list[Day]] = {}
    for x in day_list:
        by_month.setdefault(month_key(x.day), []).append(x)
    known = sorted(rewards)
    last_rate = 0.0
    if known:
        last = known[-1]
        y, m = int(last[:4]), int(last[5:7])
        last_rate = rewards[last] / monthrange(y, m)[1]
    for key, ds in by_month.items():
        if key in rewards:
            for x in ds:
                x.reward = rewards[key] / len(ds)
        else:
            for x in ds:
                x.reward = last_rate
                x.reward_estimated = bool(known)

    acc = 0.0
    for x in day_list:
        acc += x.total
        x.acc = acc

    months = [
        Month(
            month=key,
            home=sum(x.home for x in ds),
            sold=sum(x.sold for x in ds),
            reward=sum(x.reward for x in ds),
            estimated=any(x.home_estimated or x.reward_estimated for x in ds),
        )
        for key, ds in sorted(by_month.items())
    ]

    full = [x for x in day_list if x.day != today]
    recent = full[-settings.forecast_days :] if settings.forecast_days > 0 else full
    rate = sum(x.total for x in recent) / len(recent) if recent else 0.0

    return Result(
        days=day_list,
        months=months,
        total=acc,
        daily_rate=rate,
        purchase_price=settings.purchase_price,
        start_date=settings.start_date,
        today=today,
    )
