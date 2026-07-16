from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")


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
    use_paper_trading: bool = os.getenv("USE_PAPER_TRADING", "true").lower() == "true"
    use_mt5_execution: bool = os.getenv("USE_MT5_EXECUTION", "false").lower() == "true"
    mt5_account: int | None = int(os.getenv("MT5_ACCOUNT", "0")) if os.getenv("MT5_ACCOUNT") else None
    mt5_password: str | None = os.getenv("MT5_PASSWORD")
    mt5_server: str | None = os.getenv("MT5_SERVER")
    telegram_token: str | None = os.getenv("TELEGRAM_TOKEN")
    telegram_chat_id: str | None = os.getenv("TELEGRAM_CHAT_ID")
    xgboost_model_path: str | None = os.getenv("XGBOOST_MODEL_PATH")
    min_entry_confidence: float = float(os.getenv("MIN_ENTRY_CONFIDENCE", "0.65"))

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.sqlite_database_path}"


settings = Settings()
