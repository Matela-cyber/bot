from __future__ import annotations

from contextlib import contextmanager
from datetime import date, datetime
from typing import Any, Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from db.models import Base, DailyStat, PatternEvent, Trade


class Repository:
    """Production-style repository wrapper for the local SQLite analysis database."""

    def __init__(self, database_url: str = "sqlite:///bot.db") -> None:
        self.engine = create_engine(database_url, future=True, echo=False)
        Base.metadata.create_all(self.engine)
        self._migrate_schema()
        self.Session = sessionmaker(bind=self.engine, future=True)

    def _migrate_schema(self) -> None:
        with self.engine.connect() as conn:
            if self.engine.dialect.name != "sqlite":
                return

            required_columns = {
                "pnl_amount": "FLOAT DEFAULT 0.0",
                "pnl_percentage": "FLOAT DEFAULT 0.0",
                "position_size": "FLOAT DEFAULT 0.0",
                "exit_reason": "VARCHAR(50)",
                "rl_action_taken": "VARCHAR(20)",
                "reward": "FLOAT DEFAULT 0.0",
                "take_profit": "FLOAT DEFAULT 0.0",
            }

            result = conn.execute(text("PRAGMA table_info(trades)"))
            existing_columns = {row[1] for row in result.fetchall()}

            for column_name, column_definition in required_columns.items():
                if column_name not in existing_columns:
                    conn.execute(text(f"ALTER TABLE trades ADD COLUMN {column_name} {column_definition}"))
            conn.commit()

    @contextmanager
    def session(self) -> Iterator[Session]:
        with self.Session() as session:
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()

    def add_pattern_event(self, payload: dict[str, Any]) -> None:
        timestamp = payload.get("timestamp")
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)

        event = PatternEvent(
            timestamp=timestamp,
            timeframe=payload.get("timeframe", "15m"),
            pattern_name=payload.get("pattern_name", "unknown"),
            breakout_level=float(payload.get("breakout_level") or 0.0),
            stop_loss_zone=float(payload.get("stop_loss_zone") or 0.0),
            ml_confidence=float(payload.get("confidence") or 0.0),
            candlestick_bonus=bool(payload.get("candlestick_bonus", False)),
            final_score=float(payload.get("final_score") or 0.0),
            executed=bool(payload.get("executed", False)),
            result=payload.get("result"),
        )
        with self.session() as session:
            session.add(event)

    def add_trade(self, payload: dict[str, Any]) -> None:
        entry_time = payload.get("entry_time")
        if isinstance(entry_time, str):
            entry_time = datetime.fromisoformat(entry_time)

        exit_time = payload.get("exit_time")
        if isinstance(exit_time, str):
            exit_time = datetime.fromisoformat(exit_time)

        trade = Trade(
            trade_id=payload["trade_id"],
            entry_time=entry_time,
            exit_time=exit_time,
            direction=payload.get("direction", "neutral"),
            entry_price=float(payload.get("entry_price") or 0.0),
            stop_loss=float(payload.get("stop_loss") or 0.0),
            take_profit=float(payload.get("take_profit") or 0.0),
            exit_price=float(payload.get("exit_price") or 0.0),
            pnl_pips=int(payload.get("pnl_pips", 0)),
            pnl_amount=float(payload.get("pnl_amount") or 0.0),
            pnl_percentage=float(payload.get("pnl_percentage") or 0.0),
            position_size=float(payload.get("position_size") or 0.0),
            exit_reason=payload.get("exit_reason"),
            rl_action_taken=payload.get("rl_action_taken"),
            reward=float(payload.get("reward") or 0.0),
        )
        with self.session() as session:
            session.add(trade)

    def upsert_daily_stat(self, payload: dict[str, Any]) -> None:
        stat_date = payload.get("date")
        if isinstance(stat_date, str):
            stat_date = date.fromisoformat(stat_date)

        with self.session() as session:
            existing = session.get(DailyStat, stat_date)
            if existing is None:
                existing = DailyStat(
                    date=stat_date,
                    start_balance=float(payload.get("start_balance") or 0.0),
                    end_balance=float(payload.get("end_balance") or 0.0),
                    daily_pnl=float(payload.get("daily_pnl") or 0.0),
                    drawdown_peak=float(payload.get("drawdown_peak") or 0.0),
                    drawdown_percent=float(payload.get("drawdown_percent") or 0.0),
                    halt_triggered=bool(payload.get("halt_triggered", False)),
                )
                session.add(existing)
            else:
                existing.start_balance = float(payload.get("start_balance") or existing.start_balance)
                existing.end_balance = float(payload.get("end_balance") or existing.end_balance)
                existing.daily_pnl = float(payload.get("daily_pnl") or existing.daily_pnl)
                existing.drawdown_peak = float(payload.get("drawdown_peak") or existing.drawdown_peak)
                existing.drawdown_percent = float(payload.get("drawdown_percent") or existing.drawdown_percent)
                existing.halt_triggered = bool(payload.get("halt_triggered", existing.halt_triggered))
