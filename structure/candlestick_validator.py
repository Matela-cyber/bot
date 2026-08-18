"""Candlestick pattern validation used for trade confirmation."""
from __future__ import annotations

from typing import Any

import pandas as pd


class CandlestickValidator:
    """Detect candlestick confirmation patterns and assign a confidence bonus."""

    def validate(self, frame: pd.DataFrame | None, direction: str) -> dict[str, Any]:
        """Validate the most recent candle or pattern sequence for a direction."""
        if frame is None or frame.empty:
            return {"confirmed": False, "pattern_name": "no_data", "bonus": 0.0}

        if len(frame) < 3:
            return {"confirmed": False, "pattern_name": "insufficient_data", "bonus": 0.0}

        last = frame.iloc[-1]
        prev = frame.iloc[-2]
        prev2 = frame.iloc[-3]

        pattern_name = "none"
        bonus = 0.0
        confirmed = False

        body = abs(last["close"] - last["open"])
        total_range = max(last["high"] - last["low"], 1e-9)
        body_ratio = body / total_range if total_range else 0.0

        bullish = last["close"] >= last["open"]
        bearish = last["close"] <= last["open"]

        bullish_engulf = (
            last["close"] > last["open"]
            and prev["close"] < prev["open"]
            and last["close"] > prev["open"]
            and last["open"] < prev["close"]
        )
        bearish_engulf = (
            last["close"] < last["open"]
            and prev["close"] > prev["open"]
            and last["close"] < prev["open"]
            and last["open"] > prev["close"]
        )

        doji = body_ratio < 0.1 and total_range > 0
        hammer = bullish and (last["low"] < prev["low"]) and body_ratio > 0.4 and (last["close"] >= last["open"])
        shooting_star = bearish and (last["high"] > prev["high"]) and body_ratio > 0.4 and (last["close"] <= last["open"])

        morning_star = (
            prev["close"] < prev["open"]
            and prev2["close"] > prev2["open"]
            and last["close"] > last["open"]
            and last["close"] > prev["open"]
        )
        evening_star = (
            prev["close"] > prev["open"]
            and prev2["close"] < prev2["open"]
            and last["close"] < last["open"]
            and last["close"] < prev["open"]
        )

        if direction == "buy":
            if bullish_engulf or hammer or morning_star:
                pattern_name = "bullish_engulfing" if bullish_engulf else "hammer" if hammer else "morning_star"
                bonus = 0.20
                confirmed = True
            elif doji:
                pattern_name = "doji"
                bonus = 0.08
                confirmed = True
        elif direction == "sell":
            if bearish_engulf or shooting_star or evening_star:
                pattern_name = "bearish_engulfing" if bearish_engulf else "shooting_star" if shooting_star else "evening_star"
                bonus = 0.20
                confirmed = True
            elif doji:
                pattern_name = "doji"
                bonus = 0.08
                confirmed = True

        return {
            "confirmed": confirmed,
            "pattern_name": pattern_name,
            "bonus": bonus,
            "direction": direction,
            "body_ratio": float(body_ratio),
            "bullish": bool(bullish),
            "bearish": bool(bearish),
        }
