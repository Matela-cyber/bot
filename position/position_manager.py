"""Position management (breakeven, trailing, partial exits)."""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("position.manager")


class PositionManager:
    """
    Manage position lifecycle with breakeven, trailing stops, and partial exits.
    
    Rules:
    - Move SL to breakeven when price moves +1R (risk amount)
    - Close 50% at +1.5R
    - Trail remaining position at +2R with dynamic ATR-based trailing
    - Close remaining at +3R or when trailing stop is hit
    """

    def __init__(
        self,
        breakeven_trigger_r: float = 1.0,
        partial_exit_r: float = 1.5,
        partial_exit_percent: float = 0.5,
        trailing_trigger_r: float = 2.0,
        trailing_distance_multiplier: float = 0.5,
        max_hold_hours: int = 48,
    ) -> None:
        """
        Initialize position manager with configurable rules.
        
        Args:
            breakeven_trigger_r: R multiple to move SL to breakeven (default: 1.0)
            partial_exit_r: R multiple to take partial profits (default: 1.5)
            partial_exit_percent: Percentage of position to close (default: 0.5)
            trailing_trigger_r: R multiple to start trailing (default: 2.0)
            trailing_distance_multiplier: ATR multiplier for trailing distance (default: 0.5)
            max_hold_hours: Maximum hours to hold a position (default: 48)
        """
        self.breakeven_trigger_r = breakeven_trigger_r
        self.partial_exit_r = partial_exit_r
        self.partial_exit_percent = partial_exit_percent
        self.trailing_trigger_r = trailing_trigger_r
        self.trailing_distance_multiplier = trailing_distance_multiplier
        self.max_hold_hours = max_hold_hours

    def manage(self, position: dict[str, Any]) -> dict[str, Any]:
        """
        Apply position management rules.

        Args:
            position: dict with keys:
                - direction: "buy" or "sell"
                - entry_price: float
                - stop_loss: float
                - take_profit: float
                - current_price: float
                - open_time: datetime
                - pnl: float
                - volume: float
                - risk_amount: float (entry - SL distance)
                - ticket: int

        Returns:
            Updated position dict with management decisions:
                - action: "hold", "breakeven", "partial_exit", "trail", "close"
                - new_sl: float (if changed)
                - new_tp: float (if changed)
                - close_percent: float (0-1)
                - reason: str
        """
        result: dict[str, Any] = {
            "action": "hold",
            "new_sl": position.get("stop_loss"),
            "new_tp": position.get("take_profit"),
            "close_percent": 0.0,
            "reason": "No action taken",
        }

        # Extract position data
        direction = str(position.get("direction", "")).lower()
        entry = float(position.get("entry_price", 0))
        current_price = float(position.get("current_price", 0))
        stop_loss = float(position.get("stop_loss", 0))
        risk_amount = abs(entry - stop_loss)
        open_time = position.get("open_time")

        # Validate inputs
        if risk_amount <= 0 or entry == 0:
            result["reason"] = "Invalid position data (risk_amount=0)"
            return result

        # Calculate current R multiple (profit/risk)
        if direction == "buy":
            current_r = (current_price - entry) / risk_amount
        else:  # sell
            current_r = (entry - current_price) / risk_amount

        # 1. Time-based exit (max hold time)
        if open_time is not None:
            from datetime import datetime

            if isinstance(open_time, str):
                from dateutil import parser
                open_time = parser.parse(open_time)
            hours_held = (datetime.now() - open_time).total_seconds() / 3600
            if hours_held > self.max_hold_hours:
                result.update({
                    "action": "close",
                    "close_percent": 1.0,
                    "reason": f"Max hold time reached ({hours_held:.1f}h > {self.max_hold_hours}h)",
                })
                return result

        # 2. Trail remaining position at +2R
        if current_r >= self.trailing_trigger_r:
            # Calculate trailing stop distance
            atr = position.get("atr", risk_amount * 0.75)
            trail_distance = atr * self.trailing_distance_multiplier
            
            if direction == "buy":
                new_sl = current_price - trail_distance
            else:
                new_sl = current_price + trail_distance
            
            # Only trail if it improves the SL (moves in our favor)
            if direction == "buy" and new_sl > stop_loss:
                result.update({
                    "action": "trail",
                    "new_sl": new_sl,
                    "reason": f"Trailing stop triggered at {current_r:.2f}R",
                })
                return result
            elif direction == "sell" and new_sl < stop_loss:
                result.update({
                    "action": "trail",
                    "new_sl": new_sl,
                    "reason": f"Trailing stop triggered at {current_r:.2f}R",
                })
                return result

        # 3. Partial exit at +1.5R
        if current_r >= self.partial_exit_r:
            result.update({
                "action": "partial_exit",
                "close_percent": self.partial_exit_percent,
                "reason": f"Partial exit triggered at {current_r:.2f}R",
            })
            return result

        # 4. Breakeven at +1R
        if current_r >= self.breakeven_trigger_r:
            if direction == "buy" and stop_loss < entry:
                result.update({
                    "action": "breakeven",
                    "new_sl": entry,
                    "reason": f"Breakeven triggered at {current_r:.2f}R",
                })
                return result
            elif direction == "sell" and stop_loss > entry:
                result.update({
                    "action": "breakeven",
                    "new_sl": entry,
                    "reason": f"Breakeven triggered at {current_r:.2f}R",
                })
                return result

        return result

    def should_exit(self, position: dict[str, Any]) -> tuple[bool, str]:
        """
        Check if position should be closed immediately.
        
        Returns:
            (should_exit, reason)
        """
        result = self.manage(position)
        if result["action"] == "close":
            return True, result["reason"]
        return False, ""

    def get_trailing_stop(self, position: dict[str, Any]) -> float | None:
        """
        Calculate trailing stop level if applicable.
        
        Returns:
            New SL level or None if no trailing stop
        """
        result = self.manage(position)
        if result["action"] == "trail":
            return result["new_sl"]
        return None

    def should_move_to_breakeven(self, position: dict[str, Any]) -> tuple[bool, float | None]:
        """
        Check if SL should move to breakeven.
        
        Returns:
            (should_move, new_sl_level)
        """
        result = self.manage(position)
        if result["action"] == "breakeven":
            return True, result["new_sl"]
        return False, None

    def should_partial_exit(self, position: dict[str, Any]) -> tuple[bool, float]:
        """
        Check if partial exit should be taken.
        
        Returns:
            (should_exit, percent_to_close)
        """
        result = self.manage(position)
        if result["action"] == "partial_exit":
            return True, result["close_percent"]
        return False, 0.0