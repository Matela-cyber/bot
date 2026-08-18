"""Trend-following strategy."""
from __future__ import annotations

from typing import Any

import pandas as pd

from indicators.ema import calculate_ema
from indicators.atr import calculate_atr


class TrendStrategy:
    """Trend-following strategy using EMA crossovers and ATR-based SL/TP."""

    def __init__(self, frame: pd.DataFrame, regime: dict[str, Any]) -> None:
        """Initialize trend strategy."""
        self.frame = frame
        self.regime = regime

    def generate_signal(self) -> dict[str, Any]:
        """Generate trading signal based on trend analysis."""
        if self.frame.empty or len(self.frame) < 200:
            return {"signal": "none", "strategy": "trend_following"}

        ema_50 = calculate_ema(self.frame, 50).iloc[-1]
        ema_200 = calculate_ema(self.frame, 200).iloc[-1]
        price = self.frame["close"].iloc[-1]
        atr = calculate_atr(self.frame, 14).iloc[-1]

        # ATR fallback
        if atr is None or atr <= 0:
            atr = 0.001

        signal = "none"
        entry = float(price)

        if price > ema_50 > ema_200 and self.regime["direction"] == "bull":
            signal = "buy"
        elif price < ema_50 < ema_200 and self.regime["direction"] == "bear":
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
            "strategy": "trend_following",
        }
