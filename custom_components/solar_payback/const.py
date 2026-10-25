"""Constants for Solar Payback."""

from __future__ import annotations

DOMAIN = "solar_payback"
VERSION = "0.2.0"

# Investment
CONF_NAME = "name"
CONF_PURCHASE_PRICE = "purchase_price"
CONF_START_DATE = "start_date"

# Data sources (long-term statistic ids)
CONF_SOURCE = "source"
SOURCE_TIBBER = "tibber"
SOURCE_CUSTOM = "custom"
CONF_TIBBER_HOME = "tibber_home"
CONF_IMPORT_KWH = "import_kwh"
CONF_IMPORT_COST = "import_cost"
CONF_EXPORT_KWH = "export_kwh"
CONF_EXPORT_REVENUE = "export_revenue"
CONF_CONSUMPTION = "consumption"
CONF_PRICE = "price"

# Fees and settings
CONF_GRID_FEE_IMPORT = "grid_fee_import"
CONF_GRID_FEE_EXPORT = "grid_fee_export"
CONF_MARKUP = "supplier_markup"
CONF_VAT = "vat_factor"
CONF_FORECAST_DAYS = "forecast_days"
CONF_REWARD_LABEL = "reward_label"
CONF_REWARDS_INCLUDE_VAT = "rewards_include_vat"

DEFAULT_NAME = "Solar Payback"
DEFAULT_GRID_FEE_IMPORT = 0.0
DEFAULT_GRID_FEE_EXPORT = 0.0
DEFAULT_MARKUP = 0.0
DEFAULT_VAT = 1.25
DEFAULT_FORECAST_DAYS = 60
DEFAULT_REWARD_LABEL = "Grid Rewards"

TIBBER_PREFIX = "tibber:energy_consumption_"

# Service
SERVICE_SET_REWARD = "set_monthly_reward"
SERVICE_REMOVE_REWARD = "remove_monthly_reward"
ATTR_CONFIG_ENTRY = "config_entry_id"
ATTR_MONTH = "month"
ATTR_AMOUNT = "amount"
ATTR_INCLUDES_VAT = "includes_vat"

# Frontend
CARD_FILE = "solar-payback-card.js"
CARD_URL_BASE = "/solar_payback_static"
