from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def _default_open_positions() -> list[dict[str, Any]]:
    """Factory function for default open positions list."""
    return []


@dataclass
class PairState:
    """State tracker for a single trading pair."""

    symbol: str
    consecutive_losses: int = 0
    consecutive_wins: int = 0
    daily_pnl: float = 0.0
    open_positions: list[dict[str, Any]] = field(default_factory=_default_open_positions)
    last_trade_time: str | None = None

    def reset_consecutive_losses(self) -> None:
        """Reset consecutive loss counter."""
        self.consecutive_losses = 0

    def record_loss(self) -> None:
        """Record a loss and reset win counter."""
        self.consecutive_losses += 1
        self.consecutive_wins = 0

    def record_win(self) -> None:
        """Record a win and reset loss counter."""
        self.consecutive_wins += 1
        self.consecutive_losses = 0

    def add_position(self, position: dict[str, Any]) -> None:
        """Add an open position to the state."""
        self.open_positions.append(position)

    def remove_position(self, position_id: int) -> None:
        """Remove a closed position from the state."""
        self.open_positions = [p for p in self.open_positions if p.get("ticket") != position_id]

    def update_daily_pnl(self, pnl: float) -> None:
        """Update daily PnL for this pair."""
        self.daily_pnl += pnl

