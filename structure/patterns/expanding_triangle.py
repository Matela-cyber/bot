from __future__ import annotations

from typing import Any

import pandas as pd

from structure.patterns.base_pattern import BasePattern


class ExpandingTrianglePattern(BasePattern):
    """Detect Expanding Triangle continuation pattern: diverging trendlines (higher highs, lower lows)."""

    def __init__(self) -> None:
        super().__init__(name="Expanding_Triangle", direction="neutral")

    def detect(self, frame: pd.DataFrame, swings: dict[str, list[Any]]) -> dict[str, Any] | None:
        highs = swings.get("highs", [])
        lows = swings.get("lows", [])
        
        # Need enough swings for a valid triangle
        if len(highs) < 3 or len(lows) < 3:
            return None

        # Use the last 3-4 swings for detection
        recent_highs = highs[-4:]
        recent_lows = lows[-4:]

        # Check 1: Highs are RISING (slope > 0)
        high_slope, high_intercept = self._fit_line(recent_highs)
        if high_slope <= 0.0:
            return None  # Not expanding

        # Check 2: Lows are FALLING (slope < 0)
        low_slope, low_intercept = self._fit_line(recent_lows)
        if low_slope >= 0.0:
            return None  # Not expanding

        # Check 3: Verify touches on both trendlines
        # At least 2 touches on resistance (highs hitting upper line)
        resistance_touches = 0
        for high in recent_highs:
            trendline_value = self._line_value(high_slope, high_intercept, self._point_index(high))
            if abs(self._point_price(high) - trendline_value) < 0.0002:  # Within 2 pips
                resistance_touches += 1

        # At least 2 touches on support (lows hitting lower line)
        support_touches = 0
        for low in recent_lows:
            trendline_value = self._line_value(low_slope, low_intercept, self._point_index(low))
            if abs(self._point_price(low) - trendline_value) < 0.0002:
                support_touches += 1

        if resistance_touches < 2 or support_touches < 2:
            return None  # Not enough touches

        # Check 4: Triangle must have sufficient width (at least 5 pips)
        current_index = len(frame) - 1
        upper_trendline = self._line_value(high_slope, high_intercept, current_index)
        lower_trendline = self._line_value(low_slope, low_intercept, current_index)
        triangle_width = abs(upper_trendline - lower_trendline)
        if triangle_width < 0.0005:  # 5 pips minimum
            return None  # Too tight; not a meaningful triangle

        # Check 5: Breakout confirmation
        last_close = self._latest_close(frame)
        atr = self._atr(frame)

        # Determine breakout direction
        if last_close > upper_trendline:
            direction = "bull"
            breakout_level = upper_trendline
            stop_loss_zone = lower_trendline - max(atr * 0.3, 0.0002)
        elif last_close < lower_trendline:
            direction = "bear"
            breakout_level = lower_trendline
            stop_loss_zone = upper_trendline + max(atr * 0.3, 0.0002)
        else:
            # No breakout yet; wait for confirmation
            return None

        # Check 6: Breakout strength
        breakout_strength = self._proximity_strength(breakout_level, last_close, atr)
        if breakout_strength < 0.6:
            return None  # Too weak

        # Calculate quality
        quality = self._calculate_quality(
            recent_highs, recent_lows,
            resistance_touches, support_touches,
            triangle_width, atr,
            breakout_strength, direction
        )

        return {
            "pattern_name": self.name,
            "direction": direction,
            "breakout_level": round(breakout_level, 5),
            "stop_loss_zone": round(stop_loss_zone, 5),
            "swing_points": {"highs": recent_highs, "lows": recent_lows},
            "metadata": {
                "type": "continuation",
                "quality": quality,
                "slope_high": high_slope,
                "slope_low": low_slope,
                "resistance_touches": resistance_touches,
                "support_touches": support_touches,
                "triangle_width_pips": triangle_width * 10000,
            },
            "breakout_strength": breakout_strength,
        }

    def _calculate_quality(self, highs: list[Any], lows: list[Any],
                          res_touches: int, sup_touches: int,
                          triangle_width: float, atr: float,
                          breakout_strength: float, direction: str) -> float:
        """Calculate pattern quality (0-1)."""
        quality = 0.50

        # Bonus: more touches = higher quality
        total_touches = res_touches + sup_touches
        if total_touches >= 5:
            quality += 0.15
        elif total_touches >= 4:
            quality += 0.10
        elif total_touches >= 3:
            quality += 0.05

        # Bonus: wider triangle = higher quality (at least 10 pips)
        if triangle_width > 0.001:  # 10+ pips
            quality += 0.10
        elif triangle_width > 0.0008:  # 8-10 pips
            quality += 0.05

        # Bonus: strong breakout
        quality += breakout_strength * 0.10

        # Bonus: clear direction (not neutral)
        if direction in ["bull", "bear"]:
            quality += 0.05

        # Penalty: high volatility
        if atr > 0.0015:  # 15+ pips ATR
            quality -= 0.10

        return min(1.0, max(0.0, quality))