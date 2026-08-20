from __future__ import annotations

import logging
from datetime import datetime, timezone
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
        self.position_limit_hit_time: datetime | None = None
        self.override_mode_active = False
        self.override_positions_taken = 0
        self._clock = self.config.get("clock", lambda: datetime.now(timezone.utc))

    def get_pair_state(self, symbol: str) -> PairState:
        """Return the state object for the requested symbol."""
        if symbol not in self.pair_states:
            self.pair_states[symbol] = PairState(symbol)
        return self.pair_states[symbol]

    def get_positions_for_pair(self, symbol: str) -> list[dict[str, Any]]:
        """Get all currently tracked open positions for a pair."""
        return self.get_pair_state(symbol).open_positions

    def get_pair_count(self, symbol: str) -> int:
        """Get the number of open positions for a pair."""
        return len(self.get_positions_for_pair(symbol))

    def get_total_positions(self) -> int:
        """Get the total number of positions across all pair states."""
        return sum(len(state.open_positions) for state in self.pair_states.values())

    def _now(self) -> datetime:
        """Return the configured UTC clock value."""
        current = self._clock()
        if current.tzinfo is None:
            return current.replace(tzinfo=timezone.utc)
        return current.astimezone(timezone.utc)

    def can_open_position(self, symbol: str, direction: str, score_or_risk: float) -> tuple[bool, str]:
        """Apply pair limits and quality stacking rules before a new entry."""
        direction = direction.lower()
        pair_state = self.get_pair_state(symbol)
        pair_count = len(pair_state.open_positions)
        tracked_total = max(self.total_open_positions, self.get_total_positions())

        # Preserve the old bull/bear dollar-risk API for existing callers.
        if direction in {"bull", "bear"}:
            if tracked_total >= settings.global_max_concurrent_positions:
                return False, f"Global max positions reached: {tracked_total}/{settings.global_max_concurrent_positions}"
            risk_limit = settings.account_balance * settings.global_max_risk_percent
            if score_or_risk > risk_limit:
                return False, f"Global risk limit would be exceeded: {score_or_risk:.2f} > {risk_limit:.2f}"
            if pair_state.consecutive_losses >= 3:
                return False, f"Pair {symbol} paused after 3 consecutive losses"
            return True, "Position allowed"

        score = float(score_or_risk)
        if tracked_total < settings.max_total_positions:
            self.reset_position_limits()

        if tracked_total >= settings.max_total_positions:
            if self.position_limit_hit_time is None:
                self.position_limit_hit_time = self._now()
                logger.info("Position limit reached (%s). Starting recovery timer.", settings.max_total_positions)

            elapsed_hours = (self._now() - self.position_limit_hit_time).total_seconds() / 3600.0
            if elapsed_hours < settings.wait_hours_before_override:
                remaining = settings.wait_hours_before_override - elapsed_hours
                return False, f"Position limit reached. Waiting {remaining:.1f}h before override"

            if not self.override_mode_active:
                self.override_mode_active = True
                self.override_positions_taken = 0
                logger.info("Position-limit override mode activated after %.1fh.", elapsed_hours)

            if self.override_positions_taken >= settings.max_override_positions:
                return False, f"Max override positions ({settings.max_override_positions}) taken"
            if score < settings.min_score_for_override:
                return False, f"Score {score:g} < {settings.min_score_for_override} required for override"

        if pair_count >= settings.max_positions_per_pair:
            return False, f"Max positions per pair ({settings.max_positions_per_pair}) reached"
        if pair_state.consecutive_losses >= 3:
            return False, f"Pair {symbol} paused after 3 consecutive losses"

        if pair_count:
            if score <= pair_state.current_best_score:
                return False, f"Score {score:g} <= current best {pair_state.current_best_score:g}"
            if score < settings.min_stacking_score:
                return False, f"Score {score:g} < {settings.min_stacking_score} threshold for stacking"
        elif score < settings.min_score:
            return False, f"Score {score:g} < {settings.min_score} threshold"

        return True, "Position approved"

    def record_override_position(self) -> None:
        """Consume one override slot after an order is accepted."""
        if self.override_mode_active:
            self.override_positions_taken += 1
            logger.info(
                "Override position accepted: %s/%s",
                self.override_positions_taken,
                settings.max_override_positions,
            )

    def reset_position_limits(self) -> None:
        """Reset recovery state after the portfolio drops below its limit."""
        self.position_limit_hit_time = None
        self.override_mode_active = False
        self.override_positions_taken = 0
        logger.info("Position-limit recovery state reset.")

    def get_position_limit_status(self) -> dict[str, Any]:
        """Return position-limit recovery state for diagnostics."""
        total = self.get_total_positions()
        result: dict[str, Any] = {
            "total_positions": total,
            "max_positions": settings.max_total_positions,
            "limit_reached": total >= settings.max_total_positions,
            "override_active": self.override_mode_active,
            "override_positions_taken": self.override_positions_taken,
            "max_override_positions": settings.max_override_positions,
        }
        if self.position_limit_hit_time is not None:
            result["limit_hit_time"] = self.position_limit_hit_time.isoformat()
            result["elapsed_hours"] = (self._now() - self.position_limit_hit_time).total_seconds() / 3600.0
        return result

    def get_dynamic_risk(self, score: float) -> float:
        """Return the absolute risk fraction for a signal quality score."""
        if score >= 85:
            return 0.020
        if score >= 75:
            return 0.0095
        if score >= 65:
            return 0.008
        return 0.0

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
        self.add_position_state(symbol, position, float(position.get("score", 0.0) or 0.0))

    def add_position_state(self, symbol: str, position: dict[str, Any], score: float) -> None:
        """Add a scored position to pair state exactly once."""
        pair_state = self.get_pair_state(symbol)
        ticket = position.get("ticket")
        if ticket is not None and any(existing.get("ticket") == ticket for existing in pair_state.open_positions):
            return
        position["score"] = float(score)
        pair_state.add_position(position)
        self.total_open_positions += 1
        logger.info("Position added for %s: score=%.1f, total=%s", symbol, score, self.total_open_positions)

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

        daily_loss_limit_amount = float(settings.account_balance) * settings.global_daily_loss_limit
        if self.global_daily_pnl <= -daily_loss_limit_amount:
            return False, f"Global daily loss limit reached: ${self.global_daily_pnl:.2f} <= -${daily_loss_limit_amount:.2f}"

        return True, "Within global limits"

