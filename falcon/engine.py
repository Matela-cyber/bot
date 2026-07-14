from __future__ import annotations

from typing import Any

import pandas as pd


class FalconEngine:
    """Simple Falcon-style questionnaire engine."""

    def generate_trade_plan(self, frame: pd.DataFrame, pattern: dict[str, Any]) -> dict[str, Any]:
        direction = pattern.get("direction", "neutral")
        quality = float(pattern.get("confidence", 0.0))
        candlestick_strength = float(pattern.get("candlestick_strength", 0.0))
        quality += min(0.05, candlestick_strength * 0.03)
        quality = min(1.0, quality)

        if direction == "neutral":
            quality *= 0.75

        entry_price = float(frame["close"].iloc[-1])
        if direction == "bull":
            stop_loss = float(pattern.get("stop_loss_zone", entry_price - 0.0005))
            take_profit = float(entry_price + abs(entry_price - stop_loss) * 2)
        elif direction == "bear":
            stop_loss = float(pattern.get("stop_loss_zone", entry_price + 0.0005))
            take_profit = float(entry_price - abs(entry_price - stop_loss) * 2)
        else:
            stop_loss = entry_price
            take_profit = entry_price

        return {
            "pattern_name": pattern.get("pattern_name"),
            "direction": direction,
            "quality": round(min(1.0, quality), 2),
            "status": (
                "High Confidence"
                if quality >= 0.78
                else "Moderate Confidence"
                if quality >= 0.65
                else "Risk Entry"
            ),
            "breakout_level": pattern.get("breakout_level"),
            "entry_price": entry_price,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
        }
