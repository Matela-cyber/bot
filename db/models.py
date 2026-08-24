from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for typed SQLAlchemy models."""


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp for database defaults."""
    return datetime.now(timezone.utc)


class PatternEvent(Base):
    __tablename__ = "pattern_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    timestamp: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=utc_now)
    timeframe: Mapped[str | None] = mapped_column(String(10))
    pattern_name: Mapped[str | None] = mapped_column(String(50))
    breakout_level: Mapped[float | None] = mapped_column(Float)
    stop_loss_zone: Mapped[float | None] = mapped_column(Float)
    ml_confidence: Mapped[float | None] = mapped_column(Float)
    candlestick_bonus: Mapped[bool] = mapped_column(default=False)
    candlestick_pattern: Mapped[str | None] = mapped_column(String(80))
    candlestick_priority: Mapped[str | None] = mapped_column(String(20))
    candlestick_priority_bonus: Mapped[float] = mapped_column(
        Float, default=0.0)
    final_score: Mapped[float | None] = mapped_column(Float)
    executed: Mapped[bool] = mapped_column(default=False)
    result: Mapped[str | None] = mapped_column(String(10))


class Trade(Base):
    __tablename__ = "trades"
    trade_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    symbol: Mapped[str] = mapped_column(
        String(10), nullable=False, default="EURUSD")
    entry_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True))
    exit_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    direction: Mapped[str | None] = mapped_column(String(4))
    entry_price: Mapped[float | None] = mapped_column(Float)
    stop_loss: Mapped[float | None] = mapped_column(Float)
    take_profit: Mapped[float | None] = mapped_column(Float)
    exit_price: Mapped[float | None] = mapped_column(Float)
    pnl_pips: Mapped[int | None] = mapped_column(Integer)
    pnl_amount: Mapped[float | None] = mapped_column(Float)
    pnl_percentage: Mapped[float | None] = mapped_column(Float)
    position_size: Mapped[float | None] = mapped_column(Float)
    pattern_name: Mapped[str | None] = mapped_column(String(50))
    score: Mapped[int] = mapped_column(Integer, default=0)
    regime: Mapped[str | None] = mapped_column(String(20))
    falcon_scores: Mapped[str | None] = mapped_column(Text)
    mae_pips: Mapped[int] = mapped_column(Integer, default=0)
    mfe_pips: Mapped[int] = mapped_column(Integer, default=0)
    hold_time_minutes: Mapped[int] = mapped_column(Integer, default=0)
    exit_reason: Mapped[str | None] = mapped_column(String(20))
    rl_action_taken: Mapped[str | None] = mapped_column(String(20))
    reward: Mapped[float | None] = mapped_column(Float)
    falcon_overall_score: Mapped[float] = mapped_column(Float, default=0.0)
    falcon_report: Mapped[str | None] = mapped_column(Text)


class FailedOrder(Base):
    __tablename__ = "failed_orders"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    timestamp: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=utc_now)
    symbol: Mapped[str] = mapped_column(String(10), nullable=False)
    order_type: Mapped[str | None] = mapped_column(String(10))
    volume: Mapped[float | None] = mapped_column(Float)
    sl: Mapped[float | None] = mapped_column(Float)
    tp: Mapped[float | None] = mapped_column(Float)
    error_code: Mapped[int | None] = mapped_column(Integer)
    error_message: Mapped[str | None] = mapped_column(Text)
    payload: Mapped[str | None] = mapped_column(Text)


class DailyStat(Base):
    __tablename__ = "daily_stats"
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    start_balance: Mapped[float | None] = mapped_column(Float)
    end_balance: Mapped[float | None] = mapped_column(Float)
    daily_pnl: Mapped[float | None] = mapped_column(Float)
    daily_loss: Mapped[float] = mapped_column(Float, default=0.0)
    drawdown_peak: Mapped[float | None] = mapped_column(Float)
    drawdown_percent: Mapped[float | None] = mapped_column(Float)
    halt_triggered: Mapped[bool | None] = mapped_column(default=False)
