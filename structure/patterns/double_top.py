from __future__ import annotations

from typing import Any

import pandas as pd

from structure.patterns.base_pattern import BasePattern


class DoubleTopPattern(BasePattern):
    """Detect Double Top reversal pattern: two peaks at similar level with a trough in between."""

    def __init__(self) -> None:
        super().__init__(name="Double_Top", direction="bear")

    def detect(self, frame: pd.DataFrame, swings: dict[str, list[Any]]) -> dict[str, Any] | None:
        highs = swings.get("highs", [])
        lows = swings.get("lows", [])
        
        # Need at least 2 highs and 1 low for a double top
        if len(highs) < 2 or len(lows) < 1:
            return None

        # Get the last two highs (these should be the peaks)
        left_peak = highs[-2]
        right_peak = highs[-1]

        # Check if peaks are at same level (within 5%)
        if not self._same_level(self._point_price(left_peak), self._point_price(right_peak), tolerance=0.05):
            return None

        left_index = self._point_index(left_peak)
        right_index = self._point_index(right_peak)

        trough_candidates = [
            low
            for low in lows
            if self._point_index(low) > left_index and self._point_index(low) < right_index
        ]
        if not trough_candidates:
            return None

        middle_trough = min(trough_candidates, key=lambda low: self._point_price(low))
        breakout_level = self._point_price(middle_trough)
        last_close = self._latest_close(frame)

        if last_close > breakout_level:
            return None

        atr = self._atr(frame)
        higher_peak = max(self._point_price(left_peak), self._point_price(right_peak))
        stop_loss_zone = higher_peak + max(atr * 0.2, 0.0001)
        quality = self._calculate_quality(left_peak, right_peak, middle_trough, frame)

        return {
            "pattern_name": self.name,
            "direction": self.direction,
            "breakout_level": round(breakout_level, 5),
            "stop_loss_zone": round(stop_loss_zone, 5),
            "swing_points": {
                "highs": [left_peak, right_peak],
                "lows": [middle_trough],
            },
            "metadata": {
                "type": "reversal",
                "quality": quality,
                "left_peak": self._point_price(left_peak),
                "right_peak": self._point_price(right_peak),
                "trough": self._point_price(middle_trough),
                "peak_distance_pips": abs(self._point_price(left_peak) - self._point_price(right_peak)) * 10000,
            },
            "breakout_strength": self._proximity_strength(breakout_level, last_close, atr),
        }

    def _calculate_quality(self, left_peak: Any, right_peak: Any, middle_trough: Any, frame: pd.DataFrame) -> float:
        """Calculate pattern quality (0-1)."""
        # Base quality
        quality = 0.60

        # Bonus: peaks are very close (within 2%)
        price_diff = abs(self._point_price(left_peak) - self._point_price(right_peak))
        if price_diff / self._point_price(left_peak) < 0.02:
            quality += 0.10

        # Bonus: trough is significantly below peaks (at least 0.5% lower)
        avg_peak = (self._point_price(left_peak) + self._point_price(right_peak)) / 2
        trough_depth = (avg_peak - self._point_price(middle_trough)) / avg_peak
        if trough_depth > 0.005:
            quality += 0.10

        # Bonus: clear breakout (price below trough)
        last_close = self._latest_close(frame)
        if last_close < self._point_price(middle_trough):
            quality += 0.05

        # Penalty: too many recent swings (market choppy)
        atr = self._atr(frame)
        if atr > 0.001:  # High volatility (10+ pips)
            quality -= 0.05

        return min(1.0, max(0.0, quality))