from __future__ import annotations

from typing import Any

import pandas as pd

from structure.patterns.base_pattern import BasePattern


class FallingWedgePattern(BasePattern):
    def __init__(self) -> None:
        super().__init__(name="Falling_Wedge", direction="bull")

    def detect(self, frame: pd.DataFrame, swings: dict[str, list[Any]]) -> dict[str, Any] | None:
        highs = swings.get("highs", [])[-4:]
        lows = swings.get("lows", [])[-4:]
        if len(highs) < 3 or len(lows) < 3:
            return None

        slope_high, intercept_high = self._fit_line(highs[-3:])
        slope_low, intercept_low = self._fit_line(lows[-3:])
        if slope_high >= 0.0 or slope_low >= 0.0 or abs(slope_low) >= abs(slope_high):
            return None

        atr = self._atr(frame)
        breakout_level = self._line_value(slope_high, intercept_high, self._point_index(highs[-1]))
        stop_loss_zone = min(self._line_value(slope_low, intercept_low, self._point_index(lows[-1])), self._point_price(lows[-1]))
        last_close = self._latest_close(frame)
        quality = 0.68
        return {
            "pattern_name": self.name,
            "direction": self.direction,
            "breakout_level": breakout_level,
            "stop_loss_zone": stop_loss_zone,
            "swing_points": {"highs": highs, "lows": lows},
            "metadata": {
                "type": "reversal",
                "quality": quality,
                "slope_high": slope_high,
                "slope_low": slope_low,
            },
            "breakout_strength": self._proximity_strength(breakout_level, last_close, atr),
        }
