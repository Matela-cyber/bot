from __future__ import annotations

import logging
from typing import Any

from config import settings
from core.pair_state import PairState

logger = logging.getLogger("portfolio_manager")


class PortfolioManager:
    """Portfolio-level risk and position management."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = config or {}
        self.trading_pairs = self.config.get("TRADING_PAIRS", settings.trading_pairs)
        self.pair_states = {symbol: PairState(symbol) for symbol in self.trading_pairs}
        self.total_open_positions = 0
        self.global_daily_pnl = 0.0
        self.global_drawdown = 0.0
        self._peak_equity: float | None = None

    def get_pair_state(self, symbol: str) -> PairState:
        """Return the state object for the requested symbol."""
        if symbol not in self.pair_states:
            self.pair_states[symbol] = PairState(symbol)
        return self.pair_states[symbol]

    def can_open_position(self, symbol: str, direction: str, risk_amount: float) -> tuple[bool, str]:
        """Check whether a new trade can be opened under current portfolio constraints."""
        if self.total_open_positions >= settings.global_max_concurrent_positions:
            return False, f"Global max positions reached: {self.total_open_positions}/{settings.global_max_concurrent_positions}"

        if risk_amount > settings.account_balance * settings.global_max_risk_percent:
            return False, f"Global risk limit would be exceeded: {risk_amount:.2f} > {settings.account_balance * settings.global_max_risk_percent:.2f}"

        pair_state = self.get_pair_state(symbol)
        if pair_state.consecutive_losses >= 3:
            return False, f"Pair {symbol} paused after 3 consecutive losses"

        return True, "Position allowed"

    def update_daily_pnl(self, pnl: float) -> None:
        """Update global daily PnL."""
        self.global_daily_pnl += pnl
        logger.info(f"Global daily PnL updated: {self.global_daily_pnl:.2f}")

    def update_drawdown(self, current_equity: float, peak_equity: float) -> None:
        """Update global drawdown."""
        if current_equity < peak_equity:
            self.global_drawdown = (peak_equity - current_equity) / peak_equity
        else:
            self.global_drawdown = 0.0
        logger.info(f"Global drawdown updated: {self.global_drawdown:.2%}")

    def get_peak_equity(self, current_equity: float) -> float:
        """Return and update the peak equity value."""
        if self._peak_equity is None:
            self._peak_equity = current_equity
        elif current_equity > self._peak_equity:
            self._peak_equity = current_equity
        return self._peak_equity

    def update_position_state(self, symbol: str, position: dict[str, Any]) -> None:
        """Update pair state with a new position."""
        pair_state = self.get_pair_state(symbol)
        pair_state.add_position(position)
        self.total_open_positions += 1
        logger.info(f"Position added for {symbol}: total={self.total_open_positions}")

    def remove_position_state(self, symbol: str, position_id: int) -> None:
        """Remove position from pair state."""
        pair_state = self.get_pair_state(symbol)
        pair_state.remove_position(position_id)
        self.total_open_positions = max(0, self.total_open_positions - 1)
        logger.info(f"Position removed for {symbol}: total={self.total_open_positions}")

    def check_global_limits(self) -> tuple[bool, str]:
        """Check account-level trading limits."""
        if self.global_drawdown >= settings.global_drawdown_limit:
            return False, f"Global drawdown limit reached: {self.global_drawdown:.2%} >= {settings.global_drawdown_limit:.2%}"

        if self.global_daily_pnl <= -settings.global_daily_loss_limit:
            return False, f"Global daily loss limit reached: ${self.global_daily_pnl:.2f} <= -${settings.global_daily_loss_limit:.2f}"

        if self.total_open_positions >= settings.global_max_concurrent_positions:
            return False, f"Global max positions reached: {self.total_open_positions}/{settings.global_max_concurrent_positions}"

        return True, "Within global limits"

