from __future__ import annotations

from typing import Any

import pandas as pd

from structure.patterns.base_pattern import BasePattern


class BearFlagPattern(BasePattern):
    """Detect Bear Flag continuation pattern: impulse down + ascending channel, break below support."""

    def __init__(self) -> None:
        super().__init__(name="Bear_Flag", direction="bear")

    def detect(self, frame: pd.DataFrame, swings: dict[str, list[Any]]) -> dict[str, Any] | None:
        highs = swings.get("highs", [])
        lows = swings.get("lows", [])
        
        # Need enough swings for a valid flag
        if len(highs) < 3 or len(lows) < 3:
            return None

        # Use the most recent 3-4 swings scaled to timeframe and history
        recent_highs = self._recent_swings(highs, frame)
        recent_lows = self._recent_swings(lows, frame)

        # Check 1: Impulse down (at least 3x ATR or 5 pips)
        atr = self._atr(frame)
        impulse = self._detect_impulse(frame)
        if impulse >= 0:  # Positive impulse means UP, not a bear flag
            return None
        if abs(impulse) < max(atr * 0.6, 0.00035):
            return None  # Not enough momentum

        # Check 2: Flag must be ASCENDING (higher highs, higher lows)
        slope_high, _ = self._fit_line(recent_highs)
        slope_low, _ = self._fit_line(recent_lows)
        if slope_high <= 0.0 or slope_low <= 0.0:
            return None  # Not ascending

        # Check 3: Flag duration should scale to the timeframe
        if len(frame) < self._minimum_pattern_candles(frame):
            return None  # Too short to be a flag

        # Check 4: Flag must be contained (width <= 2x ATR)
        flag_width = max(self._point_price(h) for h in recent_highs) - min(self._point_price(l) for l in recent_lows)
        if flag_width > atr * 2:
            return None  # Too wide; not a flag

        # Check 5: Breakout confirmation
        last_close = self._latest_close(frame)
        breakout_level = min(self._point_price(l) for l in recent_lows)

        # ONLY signal if price has broken below support
        if last_close > breakout_level:
            return None  # No breakout yet; wait for confirmation

        # Check 6: Breakout strength
        breakout_strength = self._proximity_strength(breakout_level, last_close, atr)
        if breakout_strength < self._adaptive_breakout_threshold(frame):
            return None  # Too weak

        # Calculate stop-loss (above the highest high + ATR buffer)
        resistance = max(self._point_price(h) for h in recent_highs)
        stop_loss_zone = resistance + max(atr * 0.4, 0.0002)

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
                "slope_high": slope_high,
                "slope_low": slope_low,
                "flag_width_pips": flag_width * 10000,
                "impulse_pips": abs(impulse) * 10000,
            },
            "breakout_strength": breakout_strength,
        }

    def _detect_impulse(self, frame: pd.DataFrame) -> float:
        """Detect the impulse move that preceded the flag."""
        # Look back up to 30 candles for the impulse
        if len(frame) < 30:
            return 0.0

        # Check for a significant move down over 5-10 candles
        for lookback in range(20, 5, -5):
            start = frame["close"].iloc[-lookback]
            end = frame["close"].iloc[-lookback + 5] if lookback > 5 else frame["close"].iloc[-1]
            if end < start * 0.998:  # At least 0.2% drop
                return float(end - start)

        return 0.0

    def _calculate_quality(self, highs: list[Any], lows: list[Any], impulse: float, 
                          flag_width: float, atr: float, breakout_strength: float) -> float:
        """Calculate pattern quality (0-1)."""
        quality = 0.50

        # Bonus: strong impulse (more than 1x ATR)
        if abs(impulse) > atr:
            quality += 0.10
        elif abs(impulse) > atr * 0.8:
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
        if abs(impulse) < atr * 0.5:
            quality -= 0.10

        return min(1.0, max(0.0, quality))