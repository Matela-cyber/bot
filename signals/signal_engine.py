"""Signal scoring engine (0-100)."""
from __future__ import annotations

from typing import Any

import pandas as pd

from indicators.rsi import calculate_rsi
from indicators.atr import calculate_atr


class SignalEngine:
    """Score trading signals on a 0-100 scale."""

    def __init__(self, frame: pd.DataFrame | None = None) -> None:
        """Initialize signal engine."""
        self.frame = frame

    def score(self, signal: dict[str, Any], regime: dict[str, Any], structure: dict[str, Any]) -> dict[str, Any]:
        """Calculate signal score based on multiple criteria."""
        score = 0

        # 1. HTF Trend alignment (20 pts)
        if regime["direction"] == "bull" and signal["signal"] == "buy":
            score += 20
        elif regime["direction"] == "bear" and signal["signal"] == "sell":
            score += 20

        # 2. Market Structure (20 pts)
        bos_result = structure.get("bos")
        if bos_result and bos_result.get("status") and bos_result.get("confirmed"):
            score += 20

        # 3. SMC Setup (15 pts)
        choch_result = structure.get("choch")
        if choch_result and choch_result.get("status") and choch_result.get("confirmed"):
            score += 15

        # 4. Momentum (10 pts)
        score += self._score_momentum(signal)

        # 5. Volatility (10 pts)
        score += self._score_volatility()

        # 6. Entry Location (10 pts)
        score += self._score_entry_location(signal)

        return {
            "signal": signal.get("signal", "none"),
            "score": score,
            "grade": self._grade(score),
        }

    def _score_momentum(self, signal: dict[str, Any]) -> int:
        """Score momentum based on RSI trend."""
        if self.frame is None or self.frame.empty:
            return 0

        rsi = calculate_rsi(self.frame, 14).iloc[-1]
        if signal["signal"] == "buy" and rsi > 50:
            return 10
        if signal["signal"] == "sell" and rsi < 50:
            return 10
        return 0

    def _score_volatility(self) -> int:
        """Score volatility based on ATR relative to average."""
        if self.frame is None or self.frame.empty:
            return 0

        atr = calculate_atr(self.frame, 14).iloc[-1]
        avg_atr = calculate_atr(self.frame, 50).iloc[-1]
        if avg_atr <= 0:
            return 5
        if atr > avg_atr * 0.5:
            return 10
        return 0

    def _score_entry_location(self, signal: dict[str, Any]) -> int:
        """Score entry location based on proximity to support/resistance."""
        if self.frame is None or self.frame.empty:
            return 0

        price = self.frame["close"].iloc[-1]
        high_20 = self.frame["high"].tail(20).max()
        low_20 = self.frame["low"].tail(20).min()
        range_20 = high_20 - low_20

        if range_20 <= 0:
            return 0

        if signal["signal"] == "buy" and price < low_20 + range_20 * 0.3:
            return 10
        if signal["signal"] == "sell" and price > high_20 - range_20 * 0.3:
            return 10
        return 0

    @staticmethod
    def _grade(score: int) -> str:
        """Assign quality grade based on score."""
        if score >= 85:
            return "A+"
        if score >= 75:
            return "STRONG"
        if score >= 65:
            return "ACCEPTABLE"
        return "NO TRADE"
