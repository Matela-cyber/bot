from __future__ import annotations

from typing import Any

import pandas as pd

from structure.patterns.base_pattern import BasePattern


class FallingWedgePattern(BasePattern):
    """Detect Falling Wedge reversal pattern: converging downward trendlines, break above resistance."""

    def __init__(self) -> None:
        super().__init__(name="Falling_Wedge", direction="bull")

    def detect(self, frame: pd.DataFrame, swings: dict[str, list[Any]]) -> dict[str, Any] | None:
        highs = swings.get("highs", [])
        lows = swings.get("lows", [])
        
        # Need enough swings for a valid wedge
        if len(highs) < 3 or len(lows) < 3:
            return None

        # Use the most recent swings scaled to timeframe and history
        recent_highs = self._recent_swings(highs, frame)
        recent_lows = self._recent_swings(lows, frame)

        # Check 1: Both slopes must be NEGATIVE (falling)
        high_slope, high_intercept = self._fit_line(recent_highs)
        low_slope, low_intercept = self._fit_line(recent_lows)
        if high_slope >= 0.0 or low_slope >= 0.0:
            return None  # Not falling

        # Check 2: Low slope must be STEEPER than high slope (converging)
        if abs(low_slope) <= abs(high_slope):
            return None  # Not converging

        # Check 3: Verify touches on both trendlines using adaptive tolerance
        tolerance = self._adaptive_tolerance(frame)
        # At least 2 touches on resistance (highs hitting upper line)
        resistance_touches = 0
        for high in recent_highs:
            trendline_value = self._line_value(high_slope, high_intercept, self._point_index(high))
            if abs(self._point_price(high) - trendline_value) <= tolerance:
                resistance_touches += 1

        # At least 2 touches on support (lows hitting lower line)
        support_touches = 0
        for low in recent_lows:
            trendline_value = self._line_value(low_slope, low_intercept, self._point_index(low))
            if abs(self._point_price(low) - trendline_value) <= tolerance:
                support_touches += 1

        if resistance_touches < 2 or support_touches < 2:
            return None  # Not enough touches

        # Check 4: Wedge must have sufficient duration
        if len(frame) < self._minimum_pattern_candles(frame):
            return None  # Too short to be a wedge

        # Check 5: Wedge must have sufficient width (at least 3 pips)
        current_index = len(frame) - 1
        upper_trendline = self._line_value(high_slope, high_intercept, current_index)
        lower_trendline = self._line_value(low_slope, low_intercept, current_index)
        wedge_width = abs(upper_trendline - lower_trendline)
        if wedge_width < self._adaptive_channel_width(frame):
            return None  # Too tight; not a meaningful wedge

        # Check 6: Breakout confirmation
        last_close = self._latest_close(frame)
        breakout_level = upper_trendline

        # ONLY signal if price has broken above resistance
        if last_close < breakout_level:
            return None  # No breakout yet; wait for confirmation

        # Check 7: Breakout strength
        atr = self._atr(frame)
        breakout_strength = self._proximity_strength(breakout_level, last_close, atr)
        if breakout_strength < self._adaptive_breakout_threshold(frame):
            return None  # Too weak

        # Calculate stop-loss (below the lower trendline - ATR buffer)
        stop_loss_zone = lower_trendline - max(atr * 0.3, 0.0002)

        # Calculate quality
        quality = self._calculate_quality(
            recent_highs, recent_lows,
            high_slope, low_slope,
            resistance_touches, support_touches,
            wedge_width, atr,
            breakout_strength
        )

        return {
            "pattern_name": self.name,
            "direction": self.direction,
            "breakout_level": round(breakout_level, 5),
            "stop_loss_zone": round(stop_loss_zone, 5),
            "swing_points": {"highs": recent_highs, "lows": recent_lows},
            "metadata": {
                "type": "reversal",
                "quality": quality,
                "slope_high": high_slope,
                "slope_low": low_slope,
                "slope_ratio": abs(low_slope) / abs(high_slope) if abs(high_slope) > 1e-8 else 0,
                "wedge_width_pips": wedge_width * 10000,
                "resistance_touches": resistance_touches,
                "support_touches": support_touches,
            },
            "breakout_strength": breakout_strength,
        }

    def _calculate_quality(self, highs: list[Any], lows: list[Any],
                          high_slope: float, low_slope: float,
                          res_touches: int, sup_touches: int,
                          wedge_width: float, atr: float,
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

        # Bonus: wider wedge = higher quality (at least 5 pips)
        if wedge_width > 0.0005:  # 5+ pips
            quality += 0.10
        elif wedge_width > 0.0003:  # 3-5 pips
            quality += 0.05

        # Bonus: strong breakout
        quality += breakout_strength * 0.10

        # Bonus: clear convergence (low slope significantly steeper)
        if abs(low_slope) > abs(high_slope) * 1.5:
            quality += 0.05

        # Penalty: high volatility
        if atr > 0.0015:  # 15+ pips ATR
            quality -= 0.10

        return min(1.0, max(0.0, quality))