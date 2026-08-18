"""Market Regime Detection Engine."""
from __future__ import annotations

from typing import Any

import pandas as pd

from indicators.ema import calculate_ema
from indicators.adx import calculate_adx
from indicators.atr import calculate_atr


class MarketRegime:
    """Detect and classify market regime (trending, ranging, mixed)."""

    def __init__(self, frame: pd.DataFrame) -> None:
        """Initialize regime detector."""
        self.frame = frame
        self.adx = calculate_adx(frame).iloc[-1] if len(frame) > 30 else 0.0
        self.atr = calculate_atr(frame).iloc[-1] if len(frame) > 14 else 0.0
        self.ema_50 = calculate_ema(frame, 50).iloc[-1] if len(frame) > 50 else 0.0
        self.ema_200 = calculate_ema(frame, 200).iloc[-1] if len(frame) > 200 else 0.0
        self.current_price = frame["close"].iloc[-1]
        self.direction = self._get_direction()

    def _get_direction(self) -> str:
        """Determine price direction based on EMA alignment."""
        if self.current_price > self.ema_50 > self.ema_200:
            return "bull"
        if self.current_price < self.ema_50 < self.ema_200:
            return "bear"
        return "neutral"

    def get_regime(self) -> dict[str, Any]:
        """Return current market regime classification."""
        if self.adx > 25 and self.direction != "neutral":
            return {
                "regime": "trending",
                "direction": self.direction,
                "adx": float(self.adx),
                "atr": float(self.atr),
            }
        if self.adx < 20:
            return {
                "regime": "ranging",
                "direction": self.direction,
                "adx": float(self.adx),
                "atr": float(self.atr),
            }
        return {
            "regime": "mixed",
            "direction": self.direction,
            "adx": float(self.adx),
            "atr": float(self.atr),
        }

    def should_skip(self) -> bool:
        """Check if current regime should be skipped."""
        regime = self.get_regime()["regime"]
        return regime in ["mixed", "neutral"]
