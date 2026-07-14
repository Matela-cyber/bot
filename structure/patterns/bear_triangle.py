from __future__ import annotations

from typing import Any

import pandas as pd

from structure.patterns.base_pattern import BasePattern


class BearTrianglePattern(BasePattern):
    """Detect Bear Triangle (Descending Triangle) continuation pattern: flat support with falling resistance."""

    def __init__(self) -> None:
        super().__init__(name="Bear_Triangle", direction="bear")

    def detect(self, frame: pd.DataFrame, swings: dict[str, list[Any]]) -> dict[str, Any] | None:
        highs = swings.get("highs", [])
        lows = swings.get("lows", [])
        
        # Need enough swings for a valid triangle
        if len(highs) < 3 or len(lows) < 3:
            return None

        # Use the last 3-4 swings for detection
        recent_highs = highs[-4:]
        recent_lows = lows[-4:]

        # Check 1: Resistance is FALLING (slope < 0)
        high_slope, high_intercept = self._fit_line(recent_highs)
        if high_slope >= 0.0:
            return None  # Not falling

        # Check 2: Support is FLAT (slope ~ 0)
        low_slope, low_intercept = self._fit_line(recent_lows)
        if abs(low_slope) > 0.0001:  # More than 1 pip per candle means not flat
            return None  # Support is not flat

        # Check 3: Resistance slope should be moderate (not too steep)
        if abs(high_slope) > 0.0005:  # More than 5 pips per candle
            return None  # Too steep; this is a channel, not a triangle

        # Check 4: Verify touches on both trendlines
        # At least 2 touches on resistance
        resistance_touches = 0
        for high in recent_highs:
            trendline_value = self._line_value(high_slope, high_intercept, self._point_index(high))
            if abs(self._point_price(high) - trendline_value) < 0.0002:  # Within 2 pips
                resistance_touches += 1

        # At least 2 touches on support
        support_touches = 0
        for low in recent_lows:
            trendline_value = self._line_value(low_slope, low_intercept, self._point_index(low))
            if abs(self._point_price(low) - trendline_value) < 0.0002:
                support_touches += 1

        if resistance_touches < 2 or support_touches < 2:
            return None  # Not enough touches

        # Check 5: Triangle must have sufficient width (at least 5 pips)
        triangle_width = abs(high_intercept - low_intercept)
        if triangle_width < 0.0005:  # 5 pips minimum
            return None  # Too tight; not a meaningful triangle

        # Check 6: Breakout confirmation
        last_close = self._latest_close(frame)
        breakout_level = min(self._point_price(l) for l in recent_lows)

        # ONLY signal if price has broken below support
        if last_close > breakout_level:
            return None  # No breakout yet; wait for confirmation

        # Check 7: Breakout strength
        atr = self._atr(frame)
        breakout_strength = self._proximity_strength(breakout_level, last_close, atr)
        if breakout_strength < 0.6:
            return None  # Too weak

        # Calculate stop-loss (above the highest high + ATR buffer)
        resistance = max(self._point_price(h) for h in recent_highs)
        stop_loss_zone = resistance + max(atr * 0.3, 0.0002)

        # Calculate quality score
        quality = self._calculate_quality(
            recent_highs, recent_lows,
            high_slope, low_slope,
            resistance_touches, support_touches,
            triangle_width, atr,
            breakout_strength
        )

        return {
            "pattern_name": self.name,
            "direction": self.direction,
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
                          high_slope: float, low_slope: float,
                          res_touches: int, sup_touches: int,
                          triangle_width: float, atr: float,
                          breakout_strength: float) -> float:
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

        # Bonus: gentle slope (not too steep)
        if abs(high_slope) < 0.0002:
            quality += 0.05

        # Penalty: high volatility
        if atr > 0.0015:  # 15+ pips ATR
            quality -= 0.10

        return min(1.0, max(0.0, quality))