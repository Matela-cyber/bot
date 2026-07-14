from __future__ import annotations

from typing import Any

import pandas as pd

from structure.patterns.base_pattern import BasePattern


class BullFlatPattern(BasePattern):
    """Detect Bull Flat continuation pattern: flat resistance with rising support."""

    def __init__(self) -> None:
        super().__init__(name="Bull_Flat", direction="bull")

    def detect(self, frame: pd.DataFrame, swings: dict[str, list[Any]]) -> dict[str, Any] | None:
        highs = swings.get("highs", [])
        lows = swings.get("lows", [])
        
        # Need enough swings for a valid flat
        if len(highs) < 3 or len(lows) < 3:
            return None

        # Use the last 3-4 swings for detection
        recent_highs = highs[-4:]
        recent_lows = lows[-4:]

        # Check 1: Resistance is FLAT (slope ~ 0)
        high_slope, _ = self._fit_line(recent_highs)
        if abs(high_slope) > 0.0001:  # More than 1 pip per candle means not flat
            return None

        # Check 2: Support is RISING (slope > 0)
        low_slope, _ = self._fit_line(recent_lows)
        if low_slope <= 0.0:
            return None

        # Check 3: Consolidation period is sufficient (at least 10 candles between first and last swing)
        if len(frame) < 10:
            return None

        # Check 4: Breakout confirmation
        last_close = self._latest_close(frame)
        breakout_level = max(self._point_price(h) for h in recent_highs)

        # ONLY signal if price has broken above resistance
        if last_close < breakout_level:
            return None  # No breakout yet; wait for confirmation

        # Check 5: Breakout strength (price must close above resistance with momentum)
        atr = self._atr(frame)
        breakout_strength = self._proximity_strength(breakout_level, last_close, atr)
        if breakout_strength < 0.6:  # Too weak
            return None

        # Check 6: Ensure breakout candle has volume (or high volatility)
        last_candle = frame.iloc[-1]
        if last_candle["close"] < last_candle["open"]:
            return None  # Last candle is red; not a strong breakout

        # Calculate stop-loss (below the lowest low of the flat, with ATR buffer)
        lowest_low = min(self._point_price(l) for l in recent_lows)
        stop_loss_zone = lowest_low - max(atr * 0.3, 0.0002)

        # Calculate quality score
        quality = self._calculate_quality(recent_highs, recent_lows, breakout_strength, frame)

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
                "touch_points": len(recent_highs) + len(recent_lows),
            },
            "breakout_strength": breakout_strength,
        }

    def _calculate_quality(self, highs: list[Any], lows: list[Any], breakout_strength: float, frame: pd.DataFrame) -> float:
        """Calculate pattern quality (0-1)."""
        quality = 0.50

        # Bonus: multiple touches on resistance (2+)
        if len(highs) >= 3:
            quality += 0.10

        # Bonus: multiple touches on support (2+)
        if len(lows) >= 3:
            quality += 0.10

        # Bonus: strong breakout
        quality += breakout_strength * 0.10

        # Bonus: support slope is steep (strong upward momentum)
        slope_low, _ = self._fit_line(lows)
        if slope_low > 0.0003:  # More than 3 pips per candle
            quality += 0.05

        # Penalty: high volatility (ATR too large)
        atr = self._atr(frame)
        if atr > 0.0015:  # 15+ pips ATR
            quality -= 0.10

        # Bonus: low volatility (clean flat)
        if atr < 0.0008:  # 8 pips or less
            quality += 0.05

        return min(1.0, max(0.0, quality))