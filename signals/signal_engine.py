"""Signal scoring engine (0-100) with multi-timeframe and candlestick support."""
from __future__ import annotations

from typing import Any

from indicators.rsi import calculate_rsi
from indicators.atr import calculate_atr


class SignalEngine:
    """Score trading signals on a 0-100 scale with multi-timeframe confluence."""

    def score(self, signal: dict[str, Any], regime: dict[str, Any], structure: dict[str, Any]) -> dict[str, Any]:
        """Calculate signal score using the classic single-timeframe method."""
        score = 0

        if regime["direction"] == "bull" and signal["signal"] == "buy":
            score += 20
        elif regime["direction"] == "bear" and signal["signal"] == "sell":
            score += 20

        bos_result = structure.get("bos")
        if bos_result and bos_result.get("status") and bos_result.get("confirmed"):
            score += 20

        choch_result = structure.get("choch")
        if choch_result and choch_result.get("status") and choch_result.get("confirmed"):
            score += 15

        score += self._score_momentum(signal)
        score += self._score_volatility(signal)
        score += self._score_entry_location(signal)

        return {
            "signal": signal.get("signal", "none"),
            "score": min(100, score),
            "grade": self._grade(score),
        }

    def score_multi_timeframe(
        self,
        signal: dict[str, Any],
        h4_regime: dict[str, Any],
        h1_regime: dict[str, Any],
        m15_regime: dict[str, Any],
        structure: dict[str, Any],
        frame_15m: Any,
        candlestick_result: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Score a signal with multi-timeframe confluence and candlestick confirmation."""
        score = 0

        if signal["signal"] == "buy":
            if h4_regime["direction"] == "bull" and h1_regime["direction"] == "bull":
                score += 20
            elif h4_regime["direction"] == "bull" or h1_regime["direction"] == "bull":
                score += 10
        elif signal["signal"] == "sell":
            if h4_regime["direction"] == "bear" and h1_regime["direction"] == "bear":
                score += 20
            elif h4_regime["direction"] == "bear" or h1_regime["direction"] == "bear":
                score += 10

        bos_score = 0
        if structure.get("bos_4h", {}).get("status"):
            bos_score += 10
        if structure.get("bos_1h", {}).get("status"):
            bos_score += 7
        if structure.get("bos_15m", {}).get("status"):
            bos_score += 3
        score += min(20, bos_score)

        choch_score = 0
        if structure.get("choch_4h", {}).get("status"):
            choch_score += 8
        if structure.get("choch_1h", {}).get("status"):
            choch_score += 5
        if structure.get("choch_15m", {}).get("status"):
            choch_score += 2
        score += min(15, choch_score)

        rsi = calculate_rsi(frame_15m, 14).iloc[-1]
        if signal["signal"] == "buy" and rsi > 50:
            score += 10
        elif signal["signal"] == "sell" and rsi < 50:
            score += 10

        atr = calculate_atr(frame_15m, 14).iloc[-1]
        avg_atr = calculate_atr(frame_15m, 50).iloc[-1]
        if avg_atr > 0 and atr > avg_atr * 0.5:
            score += 10

        price = frame_15m["close"].iloc[-1]
        high_20 = frame_15m["high"].tail(20).max()
        low_20 = frame_15m["low"].tail(20).min()
        range_20 = high_20 - low_20
        if range_20 > 0:
            if signal["signal"] == "buy" and price < low_20 + range_20 * 0.3:
                score += 10
            elif signal["signal"] == "sell" and price > high_20 - range_20 * 0.3:
                score += 10

        if candlestick_result and candlestick_result.get("confirmed"):
            bonus = candlestick_result.get("bonus", 0.0)
            score += min(20, int(bonus * 100))

        return {
            "signal": signal.get("signal", "none"),
            "score": min(100, score),
            "grade": self._grade(score),
            "h4_regime": h4_regime["regime"],
            "h1_regime": h1_regime["regime"],
            "m15_regime": m15_regime["regime"],
            "candlestick": candlestick_result,
        }

    def _score_momentum(self, signal: dict[str, Any]) -> int:
        """Score momentum based on RSI trend."""
        if not hasattr(self, "frame"):
            return 0
        if self.frame is None or self.frame.empty:
            return 0

        rsi = calculate_rsi(self.frame, 14).iloc[-1]
        if signal["signal"] == "buy" and rsi > 50:
            return 10
        if signal["signal"] == "sell" and rsi < 50:
            return 10
        return 0

    def _score_volatility(self, signal: dict[str, Any]) -> int:
        """Score volatility based on ATR relative to average."""
        if not hasattr(self, "frame"):
            return 0
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
        if not hasattr(self, "frame"):
            return 0
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
        if score >= 50:
            return "WEAK"
        return "NO TRADE"
