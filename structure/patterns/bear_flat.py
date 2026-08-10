from __future__ import annotations

from typing import Any

import pandas as pd

from structure.patterns.base_pattern import BasePattern


class BearFlatPattern(BasePattern):
    """Detect Bear Flat continuation pattern: flat support with falling resistance."""

    def __init__(self) -> None:
        super().__init__(name="Bear_Flat", direction="bear")

    def detect(self, frame: pd.DataFrame, swings: dict[str, list[Any]]) -> dict[str, Any] | None:
        highs = swings.get("highs", [])
        lows = swings.get("lows", [])
        # Need enough swings for a valid flat
        if len(highs) < 3 or len(lows) < 2:
            return None

        # Use the most recent swings scaled to timeframe and history
        recent_highs = self._recent_swings(highs, frame)
        recent_lows = self._recent_swings(lows, frame)

        # Check 1: Support is FLAT (slope ~ 0)
        low_slope, _ = self._fit_line(recent_lows)
        if abs(low_slope) > 0.0001:
            return None

        # Check 2: Resistance is FALLING (slope < 0)
        high_slope, _ = self._fit_line(recent_highs)
        if high_slope >= 0.0:
            return None

        # Check 3: Resistance slope should not be too steep (adaptive)
        if abs(high_slope) > self._adaptive_slope_limit(frame):
            return None

        # Check 4: Consolidation period is sufficient
        if len(frame) < self._minimum_pattern_candles(frame):
            return None

        # Check 5: Verify support touches (use adaptive tolerance)
        support_touches = 0
        tol = self._adaptive_tolerance(frame)
        for low in recent_lows:
            if self._point_price(low) <= min(self._point_price(l) for l in recent_lows) + tol:
                support_touches += 1
        if support_touches < 2:
            return None

        # Check 6: Breakout confirmation
        last_close = self._latest_close(frame)
        breakout_level = min(self._point_price(l) for l in recent_lows)
        if last_close > breakout_level:
            return None

        # Check 7: Breakout strength (adaptive)
        atr = self._atr(frame)
        breakout_strength = self._proximity_strength(breakout_level, last_close, atr)
        if breakout_strength < self._adaptive_breakout_threshold(frame):
            return None

        # Calculate stop-loss (above the highest high + ATR buffer)
        resistance = max(self._point_price(h) for h in recent_highs)
        stop_loss_zone = resistance + max(atr * 0.3, 0.0002)

        # Calculate quality score
        quality = self._calculate_quality(
            recent_highs,
            recent_lows,
            high_slope,
            low_slope,
            support_touches,
            atr,
            breakout_strength,
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
                "support_touches": support_touches,
                "resistance_touches": len(recent_highs),
            },
            "breakout_strength": breakout_strength,
        }

    def _calculate_quality(self, highs: list[Any], lows: list[Any],
                          high_slope: float, low_slope: float,
                          support_touches: int, atr: float, 
                          breakout_strength: float) -> float:
        """Calculate pattern quality (0-1)."""
        quality = 0.50

        # Bonus: multiple touches on support (2+)
        if support_touches >= 3:
            quality += 0.10
        elif support_touches >= 2:
            quality += 0.05

        # Bonus: multiple touches on resistance (3+)
        if len(highs) >= 3:
            quality += 0.10

        # Bonus: strong breakout
        quality += breakout_strength * 0.10

        # Bonus: resistance slope is gently falling (not too steep)
        if -0.0002 < high_slope < 0:
            quality += 0.05

        # Penalty: high volatility
        if atr > 0.0015:  # 15+ pips ATR
            quality -= 0.10

        # Bonus: low volatility (clean flat)
        if atr < 0.0008:  # 8 pips or less
            quality += 0.05

        return min(1.0, max(0.0, quality))