from __future__ import annotations

from typing import Any

import pandas as pd
import numpy as np

from structure.patterns.base_pattern import BasePattern


class HeadAndShouldersPattern(BasePattern):
    """Detect Head and Shoulders reversal pattern: left shoulder, head, right shoulder, neckline break."""

    def __init__(self) -> None:
        super().__init__(name="Head_and_Shoulders", direction="bear")

    def detect(self, frame: pd.DataFrame, swings: dict[str, list[Any]]) -> dict[str, Any] | None:
        highs = swings.get("highs", [])
        lows = swings.get("lows", [])
        
        # Need at least 3 highs and 2 lows for a valid H&S
        if len(highs) < 3 or len(lows) < 2:
            return None

        # Get the last 3 highs (should be left shoulder, head, right shoulder)
        left_shoulder, head, right_shoulder = highs[-3:]

        # Check 1: Head must be higher than both shoulders
        head_price = self._point_price(head)
        left_price = self._point_price(left_shoulder)
        right_price = self._point_price(right_shoulder)

        if not (head_price > left_price and head_price > right_price):
            return None  # Head is not the highest

        # Check 2: Shoulders must be at similar level (within 8%)
        if not self._same_level(left_price, right_price, tolerance=0.08):
            return None  # Shoulders are not symmetrical enough

        # Check 3: Right shoulder must be lower than left shoulder (ideally)
        # (Optional: this is a "quality" check, not a hard requirement)
        if right_price > left_price:
            return None  # Right shoulder is too high; pattern is weak

        # Check 4: Find the neckline (the two lows between the peaks)
        # The neckline connects the trough after left shoulder and the trough after head
        # We need the last two lows that are between the shoulders and head
        
        # Find trough after left shoulder (between left shoulder and head)
        left_trough = None
        for low in lows:
            if low.index > left_shoulder.index and low.index < head.index:
                if left_trough is None or low.price < left_trough.price:
                    left_trough = low

        # Find trough after head (between head and right shoulder)
        right_trough = None
        for low in lows:
            if low.index > head.index and low.index < right_shoulder.index:
                if right_trough is None or low.price < right_trough.price:
                    right_trough = low

        if left_trough is None or right_trough is None:
            return None  # No valid neckline

        # Check 5: Neckline must be a valid trendline (slope not too steep)
        slope_neck, intercept_neck = self._fit_line([left_trough, right_trough])
        if abs(slope_neck) > 0.0005:  # More than 5 pips per candle
            return None  # Neckline is too steep; not a valid H&S

        # Check 6: Breakout confirmation
        last_close = self._latest_close(frame)
        current_index = len(frame) - 1
        breakout_level = self._line_value(slope_neck, intercept_neck, current_index)

        # ONLY signal if price has broken below the neckline
        if last_close > breakout_level:
            return None  # No breakout yet; wait for confirmation

        # Check 7: Breakout strength
        atr = self._atr(frame)
        breakout_strength = self._proximity_strength(breakout_level, last_close, atr)
        if breakout_strength < 0.6:
            return None  # Too weak

        # Calculate stop-loss (above the head + ATR buffer)
        stop_loss_zone = head_price + max(atr * 0.4, 0.0002)

        # Calculate quality
        quality = self._calculate_quality(
            left_shoulder, head, right_shoulder,
            left_trough, right_trough,
            slope_neck, atr, breakout_strength
        )

        return {
            "pattern_name": self.name,
            "direction": self.direction,
            "breakout_level": round(breakout_level, 5),
            "stop_loss_zone": round(stop_loss_zone, 5),
            "swing_points": {
                "highs": [left_shoulder, head, right_shoulder],
                "lows": [left_trough, right_trough],
            },
            "metadata": {
                "type": "reversal",
                "quality": quality,
                "left_shoulder": left_price,
                "head": head_price,
                "right_shoulder": right_price,
                "neckline_slope": slope_neck,
                "left_trough": self._point_price(left_trough),
                "right_trough": self._point_price(right_trough),
                "shoulder_symmetry_pct": abs(left_price - right_price) / left_price * 100,
            },
            "breakout_strength": breakout_strength,
        }

    def _calculate_quality(self, left_shoulder, head, right_shoulder,
                          left_trough, right_trough,
                          neckline_slope: float, atr: float,
                          breakout_strength: float) -> float:
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

        # Bonus: head is significantly higher (at least 1% above shoulders)
        avg_shoulder = (left_price + right_price) / 2
        head_height = (head_price - avg_shoulder) / avg_shoulder
        if head_height > 0.01:  # 1% or more
            quality += 0.10
        elif head_height > 0.007:  # 0.7% or more
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