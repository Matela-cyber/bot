from __future__ import annotations

from typing import Any

import pandas as pd

from structure.patterns.base_pattern import BasePattern


class InverseHeadAndShouldersPattern(BasePattern):
    """Detect Inverse Head and Shoulders reversal pattern: left shoulder, head, right shoulder, neckline break."""

    def __init__(self) -> None:
        super().__init__(name="Inverse_Head_and_Shoulders", direction="bull")

    def detect(self, frame: pd.DataFrame, swings: dict[str, list[Any]]) -> dict[str, Any] | None:
        highs = swings.get("highs", [])
        lows = swings.get("lows", [])
        
        # Need at least 3 lows and 2 highs for a valid inverse H&S
        if len(lows) < 3 or len(highs) < 2:
            return None

        # Get the last 3 lows (should be left shoulder, head, right shoulder)
        left_shoulder, head, right_shoulder = lows[-3:]

        # Check 1: Head must be lower than both shoulders
        head_price = self._point_price(head)
        left_price = self._point_price(left_shoulder)
        right_price = self._point_price(right_shoulder)

        if not (head_price < left_price and head_price < right_price):
            return None  # Head is not the lowest

        # Check 2: Shoulders must be at similar level (within 8%)
        if not self._same_level(left_price, right_price, tolerance=0.08):
            return None  # Shoulders are not symmetrical enough

        # Check 3: Right shoulder must be higher than left shoulder (ideally)
        # (Optional: this is a "quality" check, not a hard requirement)
        if right_price < left_price:
            return None  # Right shoulder is too low; pattern is weak

        # Check 4: Find the neckline (the two peaks between the troughs)
        # The neckline connects the peak after left shoulder and the peak after head
        
        # Find peak after left shoulder (between left shoulder and head)
        left_peak = None
        for high in highs:
            if high.index > left_shoulder.index and high.index < head.index:
                if left_peak is None or high.price > left_peak.price:
                    left_peak = high

        # Find peak after head (between head and right shoulder)
        right_peak = None
        for high in highs:
            if high.index > head.index and high.index < right_shoulder.index:
                if right_peak is None or high.price > right_peak.price:
                    right_peak = high

        if left_peak is None or right_peak is None:
            return None  # No valid neckline

        # Check 5: Neckline must be a valid trendline (slope not too steep)
        slope_neck, intercept_neck = self._fit_line([left_peak, right_peak])
        if abs(slope_neck) > self._adaptive_slope_limit(frame):
            return None  # Neckline is too steep; not a valid inverse H&S

        # Check 6: Breakout confirmation
        last_close = self._latest_close(frame)
        current_index = len(frame) - 1
        breakout_level = self._line_value(slope_neck, intercept_neck, current_index)

        # ONLY signal if price has broken above the neckline
        if last_close < breakout_level:
            return None  # No breakout yet; wait for confirmation

        # Check 7: Breakout strength
        atr = self._atr(frame)
        breakout_strength = self._proximity_strength(breakout_level, last_close, atr)
        if breakout_strength < self._adaptive_breakout_threshold(frame):
            return None  # Too weak

        # Calculate stop-loss (below the head - ATR buffer)
        stop_loss_zone = head_price - max(atr * 0.4, 0.0002)

        # Calculate quality
        quality = self._calculate_quality(
            left_shoulder, head, right_shoulder,
            left_peak, right_peak,
            slope_neck, atr, breakout_strength
        )

        return {
            "pattern_name": self.name,
            "direction": self.direction,
            "breakout_level": round(breakout_level, 5),
            "stop_loss_zone": round(stop_loss_zone, 5),
            "swing_points": {
                "highs": [left_peak, right_peak],
                "lows": [left_shoulder, head, right_shoulder],
            },
            "metadata": {
                "type": "reversal",
                "quality": quality,
                "left_shoulder": left_price,
                "head": head_price,
                "right_shoulder": right_price,
                "neckline_slope": slope_neck,
                "left_peak": self._point_price(left_peak),
                "right_peak": self._point_price(right_peak),
                "shoulder_symmetry_pct": abs(left_price - right_price) / left_price * 100,
            },
            "breakout_strength": breakout_strength,
        }

    def _calculate_quality(
        self,
        left_shoulder: Any,
        head: Any,
        right_shoulder: Any,
        left_peak: Any,
        right_peak: Any,
        neckline_slope: float,
        atr: float,
        breakout_strength: float,
    ) -> float:
        """Calculate pattern quality (0-1)."""
        quality = 0.50

        left_price = self._point_price(left_shoulder)
        head_price = self._point_price(head)
        right_price = self._point_price(right_shoulder)

        # Bonus: symmetrical shoulders (within 3%)
        if abs(left_price - right_price) / left_price < 0.03:
            quality += 0.10
        elif abs(left_price - right_price) / left_price < 0.05:
            quality += 0.05

        # Bonus: head is significantly lower (at least 1% below shoulders)
        avg_shoulder = (left_price + right_price) / 2
        head_depth = (avg_shoulder - head_price) / avg_shoulder
        if head_depth > 0.01:  # 1% or more
            quality += 0.10
        elif head_depth > 0.007:  # 0.7% or more
            quality += 0.05

        # Bonus: neckline is flat (slope close to 0)
        if abs(neckline_slope) < 0.0001:
            quality += 0.05

        # Bonus: strong breakout
        quality += breakout_strength * 0.10

        # Penalty: high volatility
        if atr > 0.0015:  # 15+ pips ATR
            quality -= 0.10

        return min(1.0, max(0.0, quality))