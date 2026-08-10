from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


class PairState:
    """Tracks the state of a single trading pair."""

    def __init__(self, symbol: str) -> None:
        self.symbol = symbol
        self.current_pattern: dict[str, Any] | None = None
        self.last_pattern_time: datetime | None = None
        self.open_positions: list[dict[str, Any]] = []
        self.daily_pnl = 0.0
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.consecutive_losses = 0
        self.last_trade_time: datetime | None = None
        self.equity_peak = 0.0
        self.drawdown = 0.0

    def add_trade(self, trade: dict[str, Any]) -> None:
        """Record a completed trade in the pair state."""
        self.total_trades += 1
        self.last_trade_time = datetime.utcnow()
        self.open_positions.append(trade)
        pnl = float(trade.get("pnl_amount", 0.0) or 0.0)
        self.update_pnl(pnl)

        if pnl > 0:
            self.winning_trades += 1
            self.consecutive_losses = 0
        else:
            self.losing_trades += 1
            self.consecutive_losses += 1

    def update_pnl(self, pnl: float) -> None:
        """Update pair-level daily PnL and drawdown metrics."""
        self.daily_pnl += float(pnl)

    def get_win_rate(self) -> float:
        """Return trading win rate for the pair."""
        if self.total_trades == 0:
            return 0.0
        return self.winning_trades / self.total_trades

    def get_current_drawdown(self) -> float:
        """Return current pair drawdown ratio from equity peak."""
        return self.drawdown

    def reset_daily_stats(self) -> None:
        """Clear daily counters for the current pair."""
        self.daily_pnl = 0.0
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.consecutive_losses = 0

