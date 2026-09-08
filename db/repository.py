"""Persistence operations for trades and daily account statistics."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

from sqlalchemy import func, select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from .models import DailyStats, Trade, get_session, init_db


class RepositoryError(RuntimeError):
    """Raised when a repository operation cannot be committed."""


class TradeRepository:
    """Repository for trade records backed by SQLite."""

    def __init__(self, db_path: str | Path | None = None, engine: Engine | None = None) -> None:
        """Initialize the repository and create missing tables."""
        self.engine = engine or init_db(db_path)
        self.session: Session = get_session(self.engine)

    def _commit(self) -> None:
        """Commit the current transaction and normalize database errors."""
        try:
            self.session.commit()
        except SQLAlchemyError as exc:
            self.session.rollback()
            raise RepositoryError("Database transaction failed") from exc

    def save_trade(self, trade: Trade | Mapping[str, Any]) -> Trade:
        """Save and return a trade, accepting a model or column mapping."""
        record = trade if isinstance(trade, Trade) else Trade(**dict(trade))
        try:
            self.session.add(record)
            self._commit()
            self.session.refresh(record)
            return record
        except (SQLAlchemyError, TypeError) as exc:
            self.session.rollback()
            if isinstance(exc, RepositoryError):
                raise
            raise RepositoryError("Could not save trade") from exc

    def update_trade(self, trade_id: int, **updates: Any) -> Trade | None:
        """Update a trade by ID and return it, or ``None`` when not found."""
        try:
            record = self.session.get(Trade, trade_id)
            if record is None:
                return None
            valid_columns = {
                column.name for column in Trade.__table__.columns if column.name != "id"}
            for key, value in updates.items():
                if key not in valid_columns:
                    raise ValueError(f"Unknown trade field: {key}")
                setattr(record, key, value)
            self._commit()
            return record
        except ValueError:
            self.session.rollback()
            raise
        except SQLAlchemyError as exc:
            self.session.rollback()
            raise RepositoryError("Could not update trade") from exc

    def get_open_trades(self) -> list[Trade]:
        """Return trades that do not yet have an exit time."""
        return list(self.session.scalars(select(Trade).where(Trade.exit_time.is_(None)).order_by(Trade.entry_time)).all())

    def get_closed_trades(self) -> list[Trade]:
        """Return trades that have an exit time."""
        return list(self.session.scalars(select(Trade).where(Trade.exit_time.is_not(None)).order_by(Trade.exit_time.desc())).all())

    def get_today_trades(self) -> list[Trade]:
        """Return trades entered since the start of the current UTC day."""
        start = datetime.combine(datetime.now(
            timezone.utc).date(), time.min, tzinfo=timezone.utc)
        return list(self.session.scalars(select(Trade).where(Trade.entry_time >= start).order_by(Trade.entry_time)).all())

    def get_today_profit(self) -> float:
        """Return the sum of today's realized profits, treating open trades as zero."""
        start = datetime.combine(datetime.now(
            timezone.utc).date(), time.min, tzinfo=timezone.utc)
        result = self.session.scalar(select(func.coalesce(
            func.sum(Trade.profit), 0.0)).where(Trade.entry_time >= start))
        return float(result or 0.0)

    def get_stats(self, days: int = 30) -> list[DailyStats]:
        """Return daily statistics for the most recent ``days`` calendar days."""
        if days < 1:
            raise ValueError("days must be at least 1")
        first_day = date.today() - timedelta(days=days - 1)
        return list(self.session.scalars(select(DailyStats).where(DailyStats.date >= first_day).order_by(DailyStats.date)).all())

    def close(self) -> None:
        """Close the repository's active database session."""
        self.session.close()
