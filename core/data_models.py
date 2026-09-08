"""Shared data models."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum


class Direction(Enum):
    BUY = "buy"
    SELL = "sell"


class ExitReason(Enum):
    TAKE_PROFIT = "take_profit"
    STOP_LOSS = "stop_loss"
    BREAKEVEN = "breakeven"
    PARTIAL_EXIT = "partial_exit"
    TIME_EXIT = "time_exit"
    TRAILING_STOP = "trailing_stop"


@dataclass
class Candle:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: Optional[float] = None


@dataclass
class Signal:
    pair: str
    strategy: str
    direction: Direction
    entry: float
    stop_loss: float
    take_profit: float
    confidence: float
    timestamp: datetime
    reason: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Trade:
    pair: str
    strategy: str
    direction: Direction
    entry_price: float
    stop_loss: float
    take_profit: float
    position_size: float
    entry_time: datetime
    exit_price: Optional[float] = None
    exit_time: Optional[datetime] = None
    profit_pips: Optional[float] = None
    profit: Optional[float] = None
    exit_reason: Optional[ExitReason] = None
    confidence: float = 0.0
    risk_percent: float = 0.0
    commission: float = 0.0
    slippage: float = 0.0


@dataclass
class BacktestConfig:
    start_date: datetime
    end_date: datetime
    pairs: List[str]
    strategies: List[str]
    risk_percents: List[float]
    timeframe: str = "5m"
    initial_balance: float = 100.0
    max_open_positions: int = 4
    commission_per_lot: float = 6.0
    slippage_pips: float = 0.5
    output_dir: str = "results"
