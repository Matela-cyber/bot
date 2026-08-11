from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, Date, DateTime, Integer, String, Float, Boolean, Text
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class PatternEvent(Base):
    __tablename__ = "pattern_events"
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    timeframe = Column(String(10))
    pattern_name = Column(String(50))
    breakout_level = Column(Float)
    stop_loss_zone = Column(Float)
    ml_confidence = Column(Float)
    candlestick_bonus = Column(Boolean, default=False)
    candlestick_pattern = Column(String(80), nullable=True)
    candlestick_priority = Column(String(20), nullable=True)
    candlestick_priority_bonus = Column(Float, default=0.0)
    final_score = Column(Float)
    executed = Column(Boolean, default=False)
    result = Column(String(10))


class Trade(Base):
    __tablename__ = "trades"
    trade_id = Column(String(36), primary_key=True)
    symbol = Column(String(10), nullable=False, default="EURUSD")
    entry_time = Column(DateTime)
    exit_time = Column(DateTime)
    direction = Column(String(4))
    entry_price = Column(Float)
    stop_loss = Column(Float)
    take_profit = Column(Float)
    exit_price = Column(Float)
    pnl_pips = Column(Integer)
    pnl_amount = Column(Float)
    pnl_percentage = Column(Float)
    position_size = Column(Float)
    pattern_name = Column(String(50), nullable=True)
    falcon_scores = Column(Text, nullable=True)
    mae_pips = Column(Integer, default=0)
    mfe_pips = Column(Integer, default=0)
    hold_time_minutes = Column(Integer, default=0)
    exit_reason = Column(String(20))
    rl_action_taken = Column(String(20))
    reward = Column(Float)
    falcon_overall_score = Column(Float, default=0.0)
    falcon_report = Column(Text)


class FailedOrder(Base):
    __tablename__ = "failed_orders"
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    symbol = Column(String(10), nullable=False)
    order_type = Column(String(10))
    volume = Column(Float)
    sl = Column(Float)
    tp = Column(Float)
    error_code = Column(Integer)
    error_message = Column(Text)
    payload = Column(Text)


class DailyStat(Base):
    __tablename__ = "daily_stats"
    date = Column(Date, primary_key=True)
    start_balance = Column(Float)
    end_balance = Column(Float)
    daily_pnl = Column(Float)
    daily_loss = Column(Float, default=0.0)
    drawdown_peak = Column(Float)
    drawdown_percent = Column(Float)
    halt_triggered = Column(Boolean)
