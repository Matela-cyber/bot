from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import pytz
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")
LOCAL_TIMEZONE = pytz.timezone(
    os.getenv("LOCAL_TIMEZONE", "Africa/Johannesburg"))


@dataclass
class Settings:
    account_balance: float = float(os.getenv("ACCOUNT_BALANCE", "1000"))
    risk_per_trade: float = float(os.getenv("RISK_PER_TRADE", "0.01"))
    stop_loss_pips: int = int(os.getenv("STOP_LOSS_PIPS", "20"))
    take_profit_pips: int = int(os.getenv("TAKE_PROFIT_PIPS", "40"))
    daily_loss_limit: float = float(os.getenv("DAILY_LOSS_LIMIT", "0.03"))
    drawdown_limit: float = float(os.getenv("DRAWDOWN_LIMIT", "0.15"))
    loop_interval_seconds: int = int(os.getenv("LOOP_INTERVAL_SECONDS", "900"))
    sqlite_database_path: str = os.getenv("SQLITE_DATABASE_PATH", "bot.db")
    use_mt5_execution: bool = os.getenv(
        "USE_MT5_EXECUTION", "false").lower() == "true"
    mt5_account: int | None = int(
        os.getenv("MT5_ACCOUNT", "0")) if os.getenv("MT5_ACCOUNT") else None
    mt5_password: str | None = os.getenv("MT5_PASSWORD")
    mt5_server: str | None = os.getenv("MT5_SERVER")
    telegram_token: str | None = os.getenv("TELEGRAM_TOKEN")
    telegram_chat_id: str | None = os.getenv("TELEGRAM_CHAT_ID")
    xgboost_model_path: str | None = os.getenv("XGBOOST_MODEL_PATH")
    min_entry_confidence: float = float(
        os.getenv("MIN_ENTRY_CONFIDENCE", "0.70"))
    min_confirmation: float = float(os.getenv("MIN_CONFIRMATION", "0.50"))
    min_overall_score: float = float(os.getenv("MIN_OVERALL_SCORE", "0.70"))
    # Smart Money Concepts (SMC) tuning via env
    smc_min_fvg_size: float = float(os.getenv("SMC_MIN_FVG_SIZE", "0.00025"))
    smc_atr_period: int = int(os.getenv("SMC_ATR_PERIOD", "20"))
    smc_impulse_multiplier: float = float(
        os.getenv("SMC_IMPULSE_MULTIPLIER", "2.0"))
    smc_order_block_candles: int = int(
        os.getenv("SMC_ORDER_BLOCK_CANDLES", "3"))
    min_smc_score: float = float(os.getenv("MIN_SMC_SCORE", "0.5"))
    confluence_timeframe_scales_raw: str = os.getenv(
        "CONFLUENCE_TIMEFRAME_SCALES", "15min:1.0,1h:1.0,4h:1.0")
    confluence_asset_scales_raw: str = os.getenv("CONFLUENCE_ASSET_SCALES", "")
    # Weekend Filter
    weekend_allow_trading: bool = os.getenv(
        "WEEKEND_ALLOW_TRADING", "false").lower() == "true"
    market_open_sunday: int = int(os.getenv("MARKET_OPEN_SUNDAY", "22"))
    market_close_friday: int = int(os.getenv("MARKET_CLOSE_FRIDAY", "22"))
    # Low Liquidity Filter
    low_liquidity_filter_enabled: bool = os.getenv(
        "LOW_LIQUIDITY_FILTER_ENABLED", "false").lower() == "true"
    low_liquidity_allow_trading: bool = os.getenv(
        "LOW_LIQUIDITY_ALLOW_TRADING", "false").lower() == "true"
    low_liquidity_reduce_risk: bool = os.getenv(
        "LOW_LIQUIDITY_REDUCE_RISK", "false").lower() == "true"
    low_liquidity_block_start_utc: int = int(
        os.getenv("LOW_LIQUIDITY_BLOCK_START_UTC", "22"))
    low_liquidity_block_end_utc: int = int(
        os.getenv("LOW_LIQUIDITY_BLOCK_END_UTC", "2"))
    # Raw env strings for parsed properties
    trading_pairs_raw: str = os.getenv(
        "TRADING_PAIRS", "EURUSD,GBPUSD,USDJPY,AUDUSD,NZDUSD,USDCAD,USDCHF,EURGBP,EURAUD,GBPJPY")
    pair_risk_allocation_raw: str = os.getenv("PAIR_RISK_ALLOCATION", "")
    pair_timeframes_raw: str = os.getenv("PAIR_TIMEFRAMES", "")
    global_max_concurrent_positions: int = int(
        os.getenv("GLOBAL_MAX_CONCURRENT_POSITIONS", "5"))
    global_max_risk_percent: float = float(
        os.getenv("GLOBAL_MAX_RISK_PERCENT", "0.03"))
    global_daily_loss_limit: float = float(
        os.getenv("GLOBAL_DAILY_LOSS_LIMIT", "0.03"))
    global_drawdown_limit: float = float(
        os.getenv("GLOBAL_DRAWDOWN_LIMIT", "0.15"))
    friday_cutoff_hour: int = int(os.getenv("FRIDAY_CUTOFF_HOUR", "17"))
    max_positions_per_pair: int = int(os.getenv("MAX_POSITIONS_PER_PAIR", "2"))
    max_total_positions: int = int(os.getenv("MAX_TOTAL_POSITIONS", "5"))
    min_stacking_score: int = int(os.getenv("MIN_STACKING_SCORE", "70"))
    min_score_for_override: int = int(
        os.getenv("MIN_SCORE_FOR_OVERRIDE", "90"))
    wait_hours_before_override: int = int(
        os.getenv("WAIT_HOURS_BEFORE_OVERRIDE", "3"))
    max_override_positions: int = int(os.getenv("MAX_OVERRIDE_POSITIONS", "2"))
    # Regime-based strategy settings
    min_score: int = int(os.getenv("MIN_SCORE", "70"))
    max_concurrent_positions: int = int(
        os.getenv("MAX_CONCURRENT_POSITIONS", "1"))

    @property
    def trading_pairs(self) -> list[str]:
        """Parse trading pairs from environment."""
        return [p.strip() for p in self.trading_pairs_raw.split(",") if p.strip()]

    @property
    def pair_risk_allocation(self) -> dict[str, float]:
        """Parse pair-level risk allocation from environment."""
        result: dict[str, float] = {}
        if self.pair_risk_allocation_raw:
            for part in self.pair_risk_allocation_raw.split(","):
                if ":" in part:
                    key, value = part.split(":", 1)
                    try:
                        result[key.strip()] = float(value.strip())
                    except ValueError:
                        continue
        return result

    @property
    def pair_timeframes(self) -> dict[str, str]:
        """Parse pair timeframes from environment."""
        result: dict[str, str] = {}
        if self.pair_timeframes_raw:
            for part in self.pair_timeframes_raw.split(","):
                if ":" in part:
                    key, value = part.split(":", 1)
                    result[key.strip()] = value.strip()
        return result

    @staticmethod
    def _parse_scalar_map(raw: str) -> dict[str, float]:
        entries: dict[str, float] = {}
        for part in raw.split(","):
            if not part:
                continue
            if ":" not in part:
                continue
            key, value = part.split(":", 1)
            try:
                entries[key.strip().lower()] = float(value.strip())
            except ValueError:
                continue
        return entries

    @property
    def confluence_timeframe_scales(self) -> dict[str, float]:
        return self._parse_scalar_map(self.confluence_timeframe_scales_raw)

    @property
    def confluence_asset_scales(self) -> dict[str, float]:
        return self._parse_scalar_map(self.confluence_asset_scales_raw)

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.sqlite_database_path}"


TRADING_PAIRS = ["EURUSD", "GBPUSD", "USDJPY", "XAUUSD"]
PAIR_RISK_ALLOCATION = {
    "EURUSD": 0.005,
    "GBPUSD": 0.005,
    "USDJPY": 0.005,
    "XAUUSD": 0.003,
}
PAIR_TIMEFRAMES = {
    "EURUSD": "15m",
    "GBPUSD": "15m",
    "USDJPY": "15m",
    "XAUUSD": "1h",
}
GLOBAL_MAX_CONCURRENT_POSITIONS = 3
GLOBAL_MAX_RISK_PERCENT = 0.03
GLOBAL_DAILY_LOSS_LIMIT = 0.03
GLOBAL_DRAWDOWN_LIMIT = 0.15

settings = Settings()
