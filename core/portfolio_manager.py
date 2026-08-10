from __future__ import annotations

import logging
from typing import Any

from config import settings
from core.pair_state import PairState

logger = logging.getLogger(__name__)


class PortfolioManager:
    """Manages all trading pairs and global portfolio limits."""

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.pairs = {symbol: PairState(symbol) for symbol in config.get("TRADING_PAIRS", [])}
        self.global_daily_pnl = 0.0
        self.global_equity_peak = 0.0
        self.global_drawdown = 0.0
        self.total_open_positions = 0

    def get_pair_state(self, symbol: str) -> PairState:
        """Return the state holder for a specific symbol."""
        if symbol not in self.pairs:
            self.pairs[symbol] = PairState(symbol)
        return self.pairs[symbol]

    def update_global_pnl(self, pnl: float) -> None:
        """Update global realized daily PnL."""
        self.global_daily_pnl += float(pnl)

    def check_global_limits(self) -> tuple[bool, str]:
        """Check global daily loss and drawdown limits."""
        daily_loss_limit_amount = float(settings.account_balance) * float(settings.global_daily_loss_limit)
        if self.global_daily_pnl < -daily_loss_limit_amount:
            return False, f"Global daily loss limit reached: {self.global_daily_pnl:.2f}"
        if self.global_drawdown > settings.global_drawdown_limit:
            return False, f"Global drawdown limit reached: {self.global_drawdown:.2%}"
        return True, "OK"

    def can_open_position(self, symbol: str, direction: str, risk_amount: float) -> tuple[bool, str]:
        """Check if a new position can be opened."""
        if self.total_open_positions >= settings.global_max_concurrent_positions:
            return False, f"Global max positions reached ({self.total_open_positions})"

        total_risk = self.calculate_total_risk()
        max_risk_amount = settings.global_max_risk_percent * self.get_total_equity()
        if total_risk + risk_amount > max_risk_amount:
            return False, "Global risk limit would be exceeded"

        pair_state = self.pairs[symbol]
        if pair_state.consecutive_losses >= 3:
            return False, f"{symbol}: 3 consecutive losses, pausing"

        return True, "OK"

    def calculate_total_risk(self) -> float:
        """Calculate total active risk across all open positions."""
        total_risk = 0.0
        for pair_state in self.pairs.values():
            for trade in pair_state.open_positions:
                total_risk += self._extract_risk_amount(trade)
        return float(total_risk)

    @staticmethod
    def _extract_risk_amount(trade: dict[str, Any]) -> float:
        if trade.get("risk_amount") is not None:
            return float(trade.get("risk_amount", 0.0) or 0.0)

        entry_price = float(trade.get("entry_price", 0.0) or 0.0)
        stop_loss = float(trade.get("stop_loss", 0.0) or 0.0)
        position_size = float(trade.get("position_size", 0.0) or 0.0)
        if entry_price and stop_loss and position_size:
            return abs(entry_price - stop_loss) * position_size
        return 0.0

    def get_total_equity(self) -> float:
        """Return current equity estimate used for global portfolio sizing."""
        equity = float(settings.account_balance) + float(self.global_daily_pnl)
        return max(equity, 0.0)

    def get_total_equity(self) -> float:
        """Return current equity estimate used for global portfolio sizing."""
        return float(settings.account_balance)

    def get_summary(self) -> dict[str, Any]:
        """Return summary of all pairs."""
        return {
            "total_positions": self.total_open_positions,
            "global_daily_pnl": self.global_daily_pnl,
            "global_drawdown": self.global_drawdown,
            "pairs": {
                symbol: {
                    "open_positions": len(state.open_positions),
                    "daily_pnl": state.daily_pnl,
                    "win_rate": state.get_win_rate(),
                    "consecutive_losses": state.consecutive_losses,
                }
                for symbol, state in self.pairs.items()
            },
        }
