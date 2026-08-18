"""Breakout strategy."""
from __future__ import annotations

from typing import Any

import pandas as pd

from indicators.atr import calculate_atr


class BreakoutStrategy:
    """Breakout strategy based on 20-period highs/lows and ATR-based SL/TP."""

    def __init__(self, frame: pd.DataFrame, regime: dict[str, Any]) -> None:
        """Initialize breakout strategy."""
        self.frame = frame
        self.regime = regime

    def generate_signal(self) -> dict[str, Any]:
        """Generate trading signal based on breakout levels."""
        if self.frame.empty or len(self.frame) < 20:
            return {"signal": "none", "strategy": "breakout"}

        price = self.frame["close"].iloc[-1]
        high_20 = self.frame["high"].tail(20).max()
        low_20 = self.frame["low"].tail(20).min()
        atr = calculate_atr(self.frame, 14).iloc[-1]

        # ATR fallback
        if atr is None or atr <= 0:
            atr = 0.001

        signal = "none"
        entry = float(price)

        if price > high_20:
            signal = "buy"
        elif price < low_20:
            signal = "sell"

        if signal == "buy":
            stop_loss = float(price - 1.5 * atr)
            take_profit = float(price + 3.0 * atr)
        elif signal == "sell":
            stop_loss = float(price + 1.5 * atr)
            take_profit = float(price - 3.0 * atr)
        else:
            stop_loss = price
            take_profit = price

        return {
            "signal": signal,
            "entry": entry,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "strategy": "breakout",
        }
