from __future__ import annotations

from typing import Any

import pandas as pd

from structure.patterns.base_pattern import BasePattern


class DescendingChannelPattern(BasePattern):
    """Detect Descending Channel reversal pattern: parallel downward channel, buy when price breaks resistance."""

    def __init__(self) -> None:
        super().__init__(name="Descending_Channel", direction="bull")

    def detect(self, frame: pd.DataFrame, swings: dict[str, list[Any]]) -> dict[str, Any] | None:
        highs = swings.get("highs", [])
        lows = swings.get("lows", [])
        
        # Need at least 3 highs and 3 lows for a valid channel
        if len(highs) < 3 or len(lows) < 3:
            return None

        # Use the last 3-4 swings for detection
        recent_highs = highs[-4:]
        recent_lows = lows[-4:]

        # Check 1: Both slopes must be NEGATIVE (descending)
        slope_high, intercept_high = self._fit_line(recent_highs)
        slope_low, intercept_low = self._fit_line(recent_lows)
        if slope_high >= 0.0 or slope_low >= 0.0:
            return None

        # Check 2: Slopes must be PARALLEL (within 25% of each other)
        slope_ratio = abs(slope_high - slope_low) / max(abs(slope_high), 1e-8)
        if slope_ratio > 0.25:
            return None

        # Check 3: Verify touches on both trendlines
        # At least 2 touches on resistance (highs hitting upper line)
        resistance_touches = 0
        for high in recent_highs:
            trendline_value = self._line_value(slope_high, intercept_high, self._point_index(high))
            if abs(self._point_price(high) - trendline_value) < 0.0002:  # Within 2 pips
                resistance_touches += 1

        # At least 2 touches on support (lows hitting lower line)
        support_touches = 0
        for low in recent_lows:
            trendline_value = self._line_value(slope_low, intercept_low, self._point_index(low))
            if abs(self._point_price(low) - trendline_value) < 0.0002:
                support_touches += 1

        if resistance_touches < 2 or support_touches < 2:
            return None  # Not enough touches to be a valid channel

        # Check 4: Channel must have sufficient width (at least 5 pips)
        channel_width = abs(intercept_high - intercept_low)
        if channel_width < 0.0005:  # 5 pips minimum
            return None  # Too tight; not a meaningful channel

        # Check 5: Breakout confirmation
        last_close = self._latest_close(frame)
        breakout_level = self._line_value(slope_high, intercept_high, len(frame) - 1)

        # ONLY signal if price has broken above resistance
        if last_close < breakout_level:
            return None  # No breakout yet; wait for confirmation

        # Check 6: Breakout strength
        atr = self._atr(frame)
        breakout_strength = self._proximity_strength(breakout_level, last_close, atr)
        if breakout_strength < 0.6:
            return None  # Too weak

        # Calculate stop-loss (below the lower trendline + ATR buffer)
        lower_trendline = self._line_value(slope_low, intercept_low, len(frame) - 1)
        stop_loss_zone = lower_trendline - max(atr * 0.3, 0.0002)

        # Calculate quality score
        quality = self._calculate_quality(
            recent_highs, recent_lows,
            resistance_touches, support_touches,
            channel_width, atr,
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
                          channel_width: float, atr: float,
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

        # Bonus: wider channel = higher quality (at least 10 pips)
        if channel_width > 0.001:  # 10+ pips
            quality += 0.10
        elif channel_width > 0.0008:  # 8-10 pips
            quality += 0.05

        # Bonus: strong breakout
        quality += breakout_strength * 0.10

        # Penalty: high volatility
        if atr > 0.0015:  # 15+ pips ATR
            quality -= 0.10

        return min(1.0, max(0.0, quality))