"""Configuration for the Mean Reversion bot."""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, List

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent
load_dotenv(PROJECT_ROOT / ".env")


def _env(name: str, default: str) -> str:
    value = os.getenv(name)
    return value.strip() if value and value.strip() else default


def _env_int(name: str, default: int) -> int:
    try:
        return int(_env(name, str(default)))
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(_env(name, str(default)))
    except ValueError:
        return default


@dataclass(frozen=True)
class Config:
    """Validated runtime settings."""

    # MT5
    mt5_path: str = _env("MT5_PATH", "")
    mt5_server: str = _env("MT5_SERVER", "ICMarkets-Demo")
    mt5_login: str = _env("MT5_LOGIN", "")
    mt5_password: str = _env("MT5_PASSWORD", "")

    # Trading
    symbol: str = _env("SYMBOL", "EURUSD")
    timeframe: str = _env("TIMEFRAME", "5m")
    cycle_interval: int = _env_int("CYCLE_INTERVAL", 30)

    # Risk (3% contract)
    risk_per_trade: float = _env_float("RISK_PER_TRADE", 0.03)
    max_daily_loss: float = _env_float("MAX_DAILY_LOSS", 0.05)
    drawdown_limit: float = _env_float("DRAWDOWN_LIMIT", 0.50)
    max_open_trades: int = _env_int("MAX_OPEN_TRADES", 4)
    max_positions_per_pair: int = _env_int("MAX_POSITIONS_PER_PAIR", 2)
    max_total_positions: int = _env_int("MAX_TOTAL_POSITIONS", 5)

    @property
    def trading_pairs(self) -> List[str]:
        return ["AUDCAD", "GBPJPY", "EURJPY", "EURUSD", "EURGBP", "USDJPY", "USDCAD"]

    # Mean Reversion Settings
    mr_hours: List[int] = field(default_factory=lambda: [0, 5, 11])
    mr_days: List[int] = field(default_factory=lambda: [0, 3])
    mr_rsi_threshold: float = _env_float("MR_RSI_THRESHOLD", 25.0)
    mr_tp_ratio: float = _env_float("MR_TP_RATIO", 1.5)
    mr_sl_pips: int = _env_int("MR_SL_PIPS", 20)
    mr_atr_multiplier: float = _env_float("MR_ATR_MULTIPLIER", 1.0)
    mr_min_confidence: float = _env_float("MR_MIN_CONFIDENCE", 60.0)

    # Filters
    max_spread: float = _env_float("MAX_SPREAD", 0.0003)
    spread_filter_enabled: bool = _env(
        "SPREAD_FILTER_ENABLED", "true").lower() == "true"
    local_timezone: str = _env("LOCAL_TIMEZONE", "Africa/Johannesburg")
    friday_cutoff_hour: int = _env_int("FRIDAY_CUTOFF_HOUR", 17)
    low_liquidity_filter_enabled: bool = _env(
        "LOW_LIQUIDITY_FILTER_ENABLED", "true").lower() == "true"
    low_liquidity_block_start_utc: int = _env_int(
        "LOW_LIQUIDITY_BLOCK_START_UTC", 22)
    low_liquidity_block_end_utc: int = _env_int(
        "LOW_LIQUIDITY_BLOCK_END_UTC", 2)
    shock_filter_enabled: bool = _env(
        "SHOCK_FILTER_ENABLED", "true").lower() == "true"

    # Database
    db_path: str = _env("DB_PATH", "bot.db")

    # Telegram
    telegram_token: str = _env("TELEGRAM_TOKEN", "")
    telegram_chat_id: str = _env("TELEGRAM_CHAT_ID", "")

    # Logging
    log_level: str = _env("LOG_LEVEL", "INFO").upper()

    def is_telegram_enabled(self) -> bool:
        placeholders = {"", "your_bot_token", "your_chat_id"}
        return self.telegram_token not in placeholders and self.telegram_chat_id not in placeholders


config = Config()
