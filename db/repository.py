from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import date, datetime
from typing import Any, Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from db.models import Base, DailyStat, FailedOrder, PatternEvent, Trade


class Repository:
    """Production-style repository wrapper for the local SQLite analysis database."""

    def __init__(self, database_url: str = "sqlite:///bot.db") -> None:
        self.engine = create_engine(database_url, future=True, echo=False)
        Base.metadata.create_all(self.engine)
        self._migrate_schema()
        self.Session = sessionmaker(bind=self.engine, future=True)

    @staticmethod
    def _update_float_attribute(instance: object, attr: str, value: Any, default: float = 0.0) -> None:
        if value is None:
            raw = getattr(instance, attr, default)
            try:
                new_value = float(raw)
            except (TypeError, ValueError):
                new_value = default
        else:
            try:
                new_value = float(value)
            except (TypeError, ValueError):
                new_value = default
        setattr(instance, attr, new_value)

    @staticmethod
    def _update_bool_attribute(instance: object, attr: str, value: Any, default: bool = False) -> None:
        if value is None:
            raw = getattr(instance, attr, default)
            new_value = bool(raw)
        else:
            new_value = bool(value)
        setattr(instance, attr, new_value)

    def _migrate_schema(self) -> None:
        with self.engine.connect() as conn:
            if self.engine.dialect.name != "sqlite":
                return

            required_trade_columns = {
                "pnl_amount": "FLOAT DEFAULT 0.0",
                "pnl_percentage": "FLOAT DEFAULT 0.0",
                "position_size": "FLOAT DEFAULT 0.0",
                "pattern_name": "VARCHAR(50)",
                "falcon_scores": "TEXT",
                "mae_pips": "INTEGER DEFAULT 0",
                "mfe_pips": "INTEGER DEFAULT 0",
                "hold_time_minutes": "INTEGER DEFAULT 0",
                "exit_reason": "VARCHAR(20)",
                "rl_action_taken": "VARCHAR(20)",
                "reward": "FLOAT DEFAULT 0.0",
                "take_profit": "FLOAT DEFAULT 0.0",
                "falcon_overall_score": "FLOAT DEFAULT 0.0",
                "falcon_report": "TEXT",
            }
            required_pattern_columns = {
                "candlestick_pattern": "VARCHAR(80)",
                "candlestick_priority": "VARCHAR(20)",
                "candlestick_priority_bonus": "FLOAT DEFAULT 0.0",
            }
            required_daily_stat_columns = {
                "daily_loss": "FLOAT DEFAULT 0.0",
            }

            result = conn.execute(text("PRAGMA table_info(trades)"))
            existing_trade_columns = {row[1] for row in result.fetchall()}
            for column_name, column_definition in required_trade_columns.items():
                if column_name not in existing_trade_columns:
                    conn.execute(text(f"ALTER TABLE trades ADD COLUMN {column_name} {column_definition}"))

            result = conn.execute(text("PRAGMA table_info(pattern_events)"))
            existing_pattern_columns = {row[1] for row in result.fetchall()}
            for column_name, column_definition in required_pattern_columns.items():
                if column_name not in existing_pattern_columns:
                    conn.execute(text(f"ALTER TABLE pattern_events ADD COLUMN {column_name} {column_definition}"))

            result = conn.execute(text("PRAGMA table_info(daily_stats)"))
            existing_daily_stat_columns = {row[1] for row in result.fetchall()}
            for column_name, column_definition in required_daily_stat_columns.items():
                if column_name not in existing_daily_stat_columns:
                    conn.execute(text(f"ALTER TABLE daily_stats ADD COLUMN {column_name} {column_definition}"))
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

    def get_daily_stat(self, stat_date: date) -> DailyStat | None:
        with self.session() as session:
            return session.get(DailyStat, stat_date)

    def get_daily_loss(self, stat_date: date) -> float:
        with self.session() as session:
            total_loss = session.execute(
                text(
                    "SELECT SUM(pnl_amount) FROM trades WHERE DATE(entry_time) = :date AND pnl_amount < 0.0"
                ),
                {"date": stat_date.isoformat()},
            ).scalar()
            if total_loss is None:
                return 0.0
            return abs(float(total_loss))

    def get_daily_pnl(self, stat_date: date) -> float:
        with self.session() as session:
            total_pnl = session.execute(
                text("SELECT SUM(pnl_amount) FROM trades WHERE DATE(entry_time) = :date"),
                {"date": stat_date.isoformat()},
            ).scalar()
            return float(total_pnl or 0.0)

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
            candlestick_pattern=payload.get("candlestick_pattern"),
            candlestick_priority=payload.get("candlestick_priority"),
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

        falcon_report = payload.get("falcon_report")
        if isinstance(falcon_report, dict):
            falcon_report = json.dumps(falcon_report)

        falcon_scores = payload.get("falcon_scores")
        if isinstance(falcon_scores, dict):
            falcon_scores = json.dumps(falcon_scores)

        trade = Trade(
            trade_id=payload["trade_id"],
            symbol=payload.get("symbol", "EURUSD"),
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
            pattern_name=payload.get("pattern_name"),
            falcon_scores=falcon_scores,
            mae_pips=int(payload.get("mae_pips", 0)),
            mfe_pips=int(payload.get("mfe_pips", 0)),
            hold_time_minutes=int(payload.get("hold_time_minutes", 0)),
            exit_reason=payload.get("exit_reason"),
            rl_action_taken=payload.get("rl_action_taken"),
            reward=float(payload.get("reward") or 0.0),
            falcon_overall_score=float(payload.get("falcon_overall_score") or 0.0),
            falcon_report=falcon_report,
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
                    daily_loss=float(payload.get("daily_loss") or 0.0),
                    drawdown_peak=float(payload.get("drawdown_peak") or 0.0),
                    drawdown_percent=float(payload.get("drawdown_percent") or 0.0),
                    halt_triggered=bool(payload.get("halt_triggered", False)),
                )
                session.add(existing)
            else:
                self._update_float_attribute(existing, "start_balance", payload.get("start_balance"))
                self._update_float_attribute(existing, "end_balance", payload.get("end_balance"))
                self._update_float_attribute(existing, "daily_pnl", payload.get("daily_pnl"))
                self._update_float_attribute(existing, "daily_loss", payload.get("daily_loss"))
                self._update_float_attribute(existing, "drawdown_peak", payload.get("drawdown_peak"))
                self._update_float_attribute(existing, "drawdown_percent", payload.get("drawdown_percent"))
                self._update_bool_attribute(existing, "halt_triggered", payload.get("halt_triggered"), False)

    def update_trade_exit(
        self,
        trade_id: str,
        exit_price: float,
        pnl: float,
        pattern_name: str | None,
        falcon_scores: dict[str, Any] | None,
        mae: int,
        mfe: int,
        hold_time: int,
        exit_reason: str,
    ) -> None:
        serialized_scores: str | None = None
        if falcon_scores is not None:
            serialized_scores = json.dumps(falcon_scores)

        with self.session() as session:
            trade = session.get(Trade, trade_id)
            if trade is None:
                raise ValueError(f"Trade {trade_id} not found")

            trade.exit_price = float(exit_price)
            trade.pnl_amount = float(pnl)
            trade.exit_reason = exit_reason
            trade.pattern_name = pattern_name
            trade.falcon_scores = serialized_scores
            trade.mae_pips = int(mae)
            trade.mfe_pips = int(mfe)
            trade.hold_time_minutes = int(hold_time)
            trade.pnl_percentage = float((float(pnl) / float(trade.entry_price)) * 100) if trade.entry_price else 0.0

    def get_trade_by_id(self, trade_id: str) -> Trade | None:
        with self.session() as session:
            return session.get(Trade, trade_id)

    def add_failed_order(self, payload: dict[str, Any]) -> None:
        failed_order = FailedOrder(
            symbol=payload.get("symbol", ""),
            order_type=payload.get("order_type"),
            volume=float(payload.get("volume") or 0.0),
            sl=float(payload.get("stop_loss") or 0.0),
            tp=float(payload.get("take_profit") or 0.0),
            error_code=int(payload.get("error_code")) if payload.get("error_code") is not None else None,
            error_message=payload.get("error_message"),
            payload=json.dumps(payload.get("payload", {}), default=str),
        )
        with self.session() as session:
            session.add(failed_order)
