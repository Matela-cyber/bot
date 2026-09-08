"""SQLAlchemy models and database session helpers for the trading bot."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import Date, DateTime, Float, Integer, String, create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from config import config


class Base(DeclarativeBase):
    """Base class for all database models."""


class Trade(Base):
    """A single opened or closed trade."""

    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    direction: Mapped[str] = mapped_column(String(10), nullable=False)
    entry_price: Mapped[float] = mapped_column(Float, nullable=False)
    stop_loss: Mapped[float | None] = mapped_column(Float, nullable=True)
    take_profit: Mapped[float | None] = mapped_column(Float, nullable=True)
    position_size: Mapped[float] = mapped_column(Float, nullable=False)
    entry_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True)
    exit_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    exit_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    profit: Mapped[float | None] = mapped_column(Float, nullable=True)
    profit_pips: Mapped[float | None] = mapped_column(Float, nullable=True)
    exit_reason: Mapped[str | None] = mapped_column(String(50), nullable=True)
    strategy: Mapped[str | None] = mapped_column(String(50), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)


class DailyStats(Base):
    """Aggregated account performance for one calendar day."""

    __tablename__ = "daily_stats"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(
        Date, nullable=False, unique=True, index=True)
    starting_balance: Mapped[float] = mapped_column(Float, nullable=False)
    ending_balance: Mapped[float] = mapped_column(Float, nullable=False)
    total_trades: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0)
    winning_trades: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0)
    losing_trades: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0)
    total_profit: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0)
    total_loss: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0)
    net_profit: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0)
    max_drawdown: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0)
    win_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)


def _database_url(db_path: str | Path | None) -> str:
    """Build a SQLite URL from a path, preserving support for in-memory DBs."""
    path = str(db_path or config.db_path)
    if path == ":memory:":
        return "sqlite+pysqlite:///:memory:"
    database_path = Path(path).expanduser()
    if not database_path.is_absolute():
        database_path = Path(__file__).resolve().parent.parent / database_path
    database_path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite+pysqlite:///{database_path.as_posix()}"


def init_db(db_path: str | Path | None = None) -> Engine:
    """Create database tables and return the configured SQLite engine."""
    engine = create_engine(_database_url(db_path), future=True)
    Base.metadata.create_all(engine)
    return engine


def get_session(engine: Engine | None = None, db_path: str | Path | None = None) -> Session:
    """Return a new SQLAlchemy session for the configured SQLite database."""
    active_engine = engine or init_db(db_path)
    return sessionmaker(bind=active_engine, autoflush=False, expire_on_commit=False)()


def model_values(model: Any) -> dict[str, Any]:
    """Return mapped column values from a model instance."""
    return {column.name: getattr(model, column.name) for column in model.__table__.columns}
