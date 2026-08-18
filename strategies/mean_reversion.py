"""Mean-reversion strategy."""
from __future__ import annotations

from typing import Any

import pandas as pd

from indicators.rsi import calculate_rsi
from indicators.atr import calculate_atr


class MeanReversionStrategy:
    """Mean-reversion strategy using RSI extremes and ATR-based SL/TP."""

    def __init__(self, frame: pd.DataFrame, regime: dict[str, Any]) -> None:
        """Initialize mean reversion strategy."""
        self.frame = frame
        self.regime = regime

    def generate_signal(self) -> dict[str, Any]:
        """Generate trading signal based on RSI reversal levels."""
        if self.frame.empty or len(self.frame) < 30:
            return {"signal": "none", "strategy": "mean_reversion"}

        rsi = calculate_rsi(self.frame, 14).iloc[-1]
        price = self.frame["close"].iloc[-1]
        atr = calculate_atr(self.frame, 14).iloc[-1]

        # ATR fallback
        if atr is None or atr <= 0:
            atr = 0.001

        signal = "none"
        entry = float(price)

        # RSI extreme with candlestick confirmation
        last_candle_bullish = self.frame["close"].iloc[-1] > self.frame["open"].iloc[-1]
        last_candle_bearish = self.frame["close"].iloc[-1] < self.frame["open"].iloc[-1]

        if rsi < 30 and last_candle_bullish:
            signal = "buy"
        elif rsi > 70 and last_candle_bearish:
            signal = "sell"

        if signal == "buy":
            stop_loss = float(price - 1.5 * atr)
            take_profit = float(price + 2.5 * atr)
        elif signal == "sell":
            stop_loss = float(price + 1.5 * atr)
            take_profit = float(price - 2.5 * atr)
        else:
            stop_loss = price
            take_profit = price

        return {
            "signal": signal,
            "entry": entry,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "strategy": "mean_reversion",
        }
