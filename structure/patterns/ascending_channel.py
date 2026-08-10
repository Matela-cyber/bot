from __future__ import annotations

from typing import Any

import pandas as pd

from structure.patterns.base_pattern import BasePattern


class AscendingChannelPattern(BasePattern):
    """Detect Ascending Channel reversal pattern: parallel upward channel, sell when price breaks support."""

    def __init__(self) -> None:
        super().__init__(name="Ascending_Channel", direction="bear")

    def detect(self, frame: pd.DataFrame, swings: dict[str, list[Any]]) -> dict[str, Any] | None:
        highs = swings.get("highs", [])
        lows = swings.get("lows", [])
        
        # Need at least 3 highs and 3 lows for a valid channel
        if len(highs) < 3 or len(lows) < 3:
            return None

        # Use the last 3-4 swings for detection
        recent_highs = self._recent_swings(highs, frame)
        recent_lows = self._recent_swings(lows, frame)

        # Check 1: Both slopes must be POSITIVE (ascending)
        slope_high, intercept_high = self._fit_line(recent_highs)
        slope_low, intercept_low = self._fit_line(recent_lows)
        if slope_high <= 0.0 or slope_low <= 0.0:
            return None

        # Check 2: Slopes must be PARALLEL (within 25% of each other)
        slope_ratio = abs(slope_high - slope_low) / max(abs(slope_low), 1e-8)
        if slope_ratio > 0.25:
            return None

        # Check 3: Verify touches on both trendlines
        tolerance = self._adaptive_tolerance(frame)

        # At least 2 touches on resistance (highs hitting upper line)
        resistance_touches = self._trendline_touches(recent_highs, slope_high, intercept_high, tolerance=tolerance)

        # At least 2 touches on support (lows hitting lower line)
        support_touches = self._trendline_touches(recent_lows, slope_low, intercept_low, tolerance=tolerance)

        if resistance_touches < 2 or support_touches < 2:
            return None  # Not enough touches to be a valid channel

        # Check 4: Channel must have sufficient width relative to volatility
        channel_width = abs(intercept_high - intercept_low)
        if channel_width < self._adaptive_channel_width(frame):
            return None  # Too tight; not a meaningful channel

        # Check 5: Price must have rejected the upper trendline
        last_close = self._latest_close(frame)
        upper_trendline = self._line_value(slope_high, intercept_high, len(frame) - 1)
        lower_trendline = self._line_value(slope_low, intercept_low, len(frame) - 1)

        # If price is near the upper trendline (within 2 pips), that's a reversal signal
        # But we need price to actually break the lower trendline for confirmation
        atr = self._atr(frame)
        
        # Check 6: Breakout confirmation (price must break below support)
        breakout_level = lower_trendline
        if last_close > breakout_level:
            return None  # No breakout yet; wait for confirmation

        # Check 7: Breakout strength (price should be well below support)
        breakout_strength = self._proximity_strength(breakout_level, last_close, atr)
        if breakout_strength < self._adaptive_breakout_threshold(frame):
            return None

        # Calculate stop-loss (above the upper trendline + ATR buffer)
        stop_loss_zone = upper_trendline + max(atr * 0.3, 0.0002)

        # Calculate quality score
        quality = self._calculate_quality(
            recent_highs, recent_lows, 
            resistance_touches, support_touches, 
            channel_width, atr
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
                "slope_high": slope_high,
                "slope_low": slope_low,
                "slope_ratio": slope_ratio,
                "channel_width_pips": channel_width * 10000,
                "resistance_touches": resistance_touches,
                "support_touches": support_touches,
            },
            "breakout_strength": breakout_strength,
        }

    def _calculate_quality(self, highs: list[Any], lows: list[Any], 
                          res_touches: int, sup_touches: int, 
                          channel_width: float, atr: float) -> float:
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

        # Bonus: wider channel = higher quality (at least 10 pips)
        if channel_width > 0.001:  # 10+ pips
            quality += 0.10
        elif channel_width > 0.0008:  # 8-10 pips
            quality += 0.05

        # Bonus: low volatility (clean channel)
        if atr < 0.001:  # 10 pips or less
            quality += 0.05

        # Penalty: high volatility (choppy channel)
        if atr > 0.0015:  # 15+ pips
            quality -= 0.10

        return min(1.0, max(0.0, quality))