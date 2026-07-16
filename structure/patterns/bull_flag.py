from __future__ import annotations

from typing import Any

import pandas as pd

from structure.patterns.base_pattern import BasePattern


class BullFlagPattern(BasePattern):
    """Detect Bull Flag continuation pattern: impulse up + descending channel, break above resistance."""

    def __init__(self) -> None:
        super().__init__(name="Bull_Flag", direction="bull")

    def detect(self, frame: pd.DataFrame, swings: dict[str, list[Any]]) -> dict[str, Any] | None:
        highs = swings.get("highs", [])
        lows = swings.get("lows", [])
        
        # Need enough swings for a valid flag
        if len(highs) < 3 or len(lows) < 3:
            return None

        # Use the last 3-4 swings for detection
        recent_highs = highs[-4:]
        recent_lows = lows[-4:]

        # Determine the consolidation range and exclude the final breakout high when present.
        consolidation_highs = recent_highs[:-1] if len(recent_highs) >= 4 else recent_highs
        consolidation_lows = recent_lows[-3:] if len(recent_lows) >= 3 else recent_lows

        # Check 1: Impulse up (at least 0.35% or notable momentum)
        atr = self._atr(frame)
        impulse = self._detect_impulse(frame)
        if impulse <= 0:  # Negative impulse means DOWN, not a bull flag
            return None
        if impulse < max(atr * 0.6, 0.00035):
            return None  # Not enough momentum

        # Check 2: Flag should be relatively flat or slightly descending
        high_slope, _ = self._fit_line(consolidation_highs)
        low_slope, _ = self._fit_line(consolidation_lows)
        if high_slope > 0.00018 or low_slope > 0.00018:
            return None  # Not a valid flag channel

        # Check 3: Flag duration (at least 5 candles between first and last swing)
        if len(frame) < 10:
            return None  # Too short to be a flag

        # Check 4: Flag must be contained (width reasonable compared to ATR)
        flag_width = max(self._point_price(h) for h in consolidation_highs) - min(self._point_price(l) for l in consolidation_lows)
        if flag_width > atr * 35:
            return None  # Too wide; not a flag

        # Check 5: Breakout confirmation using the breakout swing high
        last_close = self._latest_close(frame)
        breakout_level = max(self._point_price(h) for h in consolidation_highs)
        breakout_strength = self._proximity_strength(breakout_level, last_close, atr)

        if last_close < breakout_level and breakout_strength < 0.25:
            return None  # No breakout yet; wait for confirmation

        # Check 6: Breakout strength
        if breakout_strength < 0.35:
            return None  # Too weak

        # Calculate stop-loss (below the lowest low - ATR buffer)
        support = min(self._point_price(l) for l in recent_lows)
        stop_loss_zone = support - max(atr * 0.4, 0.0002)

        # Calculate quality score
        quality = self._calculate_quality(
            recent_highs, recent_lows, 
            impulse, flag_width, atr, 
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
                "flag_width_pips": flag_width * 10000,
                "impulse_pips": impulse * 10000,
            },
            "breakout_strength": breakout_strength,
        }

    def _detect_impulse(self, frame: pd.DataFrame) -> float:
        """Detect the impulse move that preceded the flag."""
        if len(frame) < 30:
            return 0.0

        recent_close = frame["close"].iloc[-30:]
        max_impulse = 0.0
        for start in range(0, len(recent_close) - 5):
            base_price = float(recent_close.iloc[start])
            target_price = float(recent_close.iloc[start + 5])
            impulse = target_price - base_price
            if impulse > max_impulse:
                max_impulse = impulse

        return max_impulse

    def _calculate_quality(self, highs: list[Any], lows: list[Any], impulse: float, 
                          flag_width: float, atr: float, breakout_strength: float) -> float:
        """Calculate pattern quality (0-1)."""
        quality = 0.50

        # Bonus: strong impulse (more than 1x ATR)
        if impulse > atr:
            quality += 0.10
        elif impulse > atr * 0.8:
            quality += 0.05

        # Bonus: multiple touches on flag (3+ highs and 3+ lows)
        if len(highs) >= 3 and len(lows) >= 3:
            quality += 0.10

        # Bonus: tight flag (width < 1x ATR)
        if flag_width < atr:
            quality += 0.10
        elif flag_width < atr * 1.5:
            quality += 0.05

        # Bonus: strong breakout
        quality += breakout_strength * 0.10

        # Penalty: weak impulse
        if impulse < atr * 0.5:
            quality -= 0.10

        return min(1.0, max(0.0, quality))