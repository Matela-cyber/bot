from __future__ import annotations

from typing import Any

import pandas as pd

from structure.patterns.base_pattern import BasePattern


class DoubleBottomPattern(BasePattern):
    """Detect Double Bottom reversal pattern: two troughs at similar level with a peak in between."""

    def __init__(self) -> None:
        super().__init__(name="Double_Bottom", direction="bull")

    def detect(self, frame: pd.DataFrame, swings: dict[str, list[Any]]) -> dict[str, Any] | None:
        highs = swings.get("highs", [])
        lows = swings.get("lows", [])
        
        # Need at least 2 lows and 1 high for a double bottom
        if len(lows) < 2 or len(highs) < 1:
            return None

        # Get the last two lows (these should be the troughs)
        left_trough = lows[-2]
        right_trough = lows[-1]

        # Check if troughs are at same level (within 5%)
        if not self._same_level(self._point_price(left_trough), self._point_price(right_trough), tolerance=0.05):
            return None

        # Find the middle peak between the two troughs
        middle_peak = None
        for high in reversed(highs):  # Search from most recent backwards
            if high.index > left_trough.index and high.index < right_trough.index:
                middle_peak = high
                break

        if middle_peak is None:
            # No peak found between the troughs → not a valid double bottom
            return None

        # Check that the middle peak is significantly higher than the troughs (at least 0.5%)
        avg_trough = (self._point_price(left_trough) + self._point_price(right_trough)) / 2
        peak_height = (self._point_price(middle_peak) - avg_trough) / avg_trough
        if peak_height < 0.005:  # 0.5% minimum
            return None  # Too shallow; not a valid double bottom

        # Check if price has broken above the middle peak (breakout confirmation)
        last_close = self._latest_close(frame)
        breakout_level = self._point_price(middle_peak)

        # ONLY signal if price has actually broken above the peak
        if last_close < breakout_level:
            return None  # No breakout yet; wait for confirmation

        # Check breakout strength
        atr = self._atr(frame)
        breakout_strength = self._proximity_strength(breakout_level, last_close, atr)
        if breakout_strength < 0.6:
            return None  # Too weak

        # Calculate stop-loss (below the lower trough - ATR buffer)
        lower_trough = min(self._point_price(left_trough), self._point_price(right_trough))
        stop_loss_zone = lower_trough - max(atr * 0.2, 0.0001)

        # Calculate quality
        quality = self._calculate_quality(
            left_trough, right_trough, middle_peak,
            peak_height, breakout_strength, atr
        )

        return {
            "pattern_name": self.name,
            "direction": self.direction,
            "breakout_level": round(breakout_level, 5),
            "stop_loss_zone": round(stop_loss_zone, 5),
            "swing_points": {
                "highs": [middle_peak],
                "lows": [left_trough, right_trough],
            },
            "metadata": {
                "type": "reversal",
                "quality": quality,
                "left_trough": self._point_price(left_trough),
                "right_trough": self._point_price(right_trough),
                "middle_peak": self._point_price(middle_peak),
                "peak_height_pct": peak_height * 100,
                "trough_diff_pips": abs(self._point_price(left_trough) - self._point_price(right_trough)) * 10000,
            },
            "breakout_strength": breakout_strength,
        }

    def _calculate_quality(
        self,
        left_trough: Any,
        right_trough: Any,
        middle_peak: Any,
        peak_height: float,
        breakout_strength: float,
        atr: float,
    ) -> float:
        """Calculate pattern quality (0-1)."""
        quality = 0.50

        # Bonus: troughs are very close (within 2%)
        price_diff = abs(self._point_price(left_trough) - self._point_price(right_trough))
        if price_diff / self._point_price(left_trough) < 0.02:
            quality += 0.10

        # Bonus: peak is significantly higher (more than 1%)
        if peak_height > 0.01:  # 1% or more
            quality += 0.10
        elif peak_height > 0.007:  # 0.7% or more
            quality += 0.05

        # Bonus: strong breakout
        quality += breakout_strength * 0.10

        # Bonus: low volatility (clean pattern)
        if atr < 0.0008:  # 8 pips or less
            quality += 0.05

        # Penalty: high volatility (choppy pattern)
        if atr > 0.0015:  # 15+ pips ATR
            quality -= 0.10

        return min(1.0, max(0.0, quality))