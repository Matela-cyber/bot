"""Compact cycle summaries for logs and notifications."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


def _new_history() -> list[str]:
    """Create an empty event history."""
    return []


@dataclass
class CycleSummary:
    """Aggregate the important outcomes of one trading cycle."""

    timestamp: datetime
    total_pairs: int
    pairs_processed: int = 0
    pairs_skipped: int = 0
    signals_detected: int = 0
    signals_rejected: int = 0
    signals_accepted: int = 0
    trades_opened: int = 0
    trades_closed: int = 0
    trades_won: int = 0
    trades_lost: int = 0
    volatility_blocks: int = 0
    current_volatility: str = "normal"
    open_positions: int = 0
    current_pnl: float = 0.0
    current_session: str = "unknown"
    risk_multiplier: float = 1.0
    _history: list[str] = field(default_factory=_new_history)

    def add_event(self, event: str) -> None:
        """Record a repeatable event for compressed output."""
        self._history.append(event)

    def get_summary_line(self) -> str:
        """Return one scan-friendly summary line."""
        return (
            f"Pairs: {self.pairs_processed}/{self.total_pairs} | "
            f"Signals: {self.signals_detected} ({self.signals_accepted} accepted) | "
            f"Trades: {self.trades_opened} | Positions: {self.open_positions} | "
            f"PnL: ${self.current_pnl:.2f} | "
            f"Session: {self.current_session} ({self.risk_multiplier:.0%})"
        )

    def get_compressed_log(self) -> str:
        """Return the summary plus grouped repeated events."""
        if not self._history:
            return self.get_summary_line()
        counts: dict[str, int] = {}
        for event in self._history:
            counts[event] = counts.get(event, 0) + 1
        events = " | ".join(f"{count}x {event}" for event,
                            count in counts.items())
        return f"{self.get_summary_line()} | Events: {events}"
