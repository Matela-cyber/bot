from __future__ import annotations

from typing import Any

import pandas as pd

from structure.patterns.base_pattern import BasePattern


class ExpandingTrianglePattern(BasePattern):
    def __init__(self) -> None:
        super().__init__(name="Expanding_Triangle", direction="neutral")

    def detect(self, frame: pd.DataFrame, swings: dict[str, list[Any]]) -> dict[str, Any] | None:
        highs = swings.get("highs", [])[-4:]
        lows = swings.get("lows", [])[-4:]
        if len(highs) < 3 or len(lows) < 3:
            return None

        slope_high = self._slope(highs[-3:])
        slope_low = self._slope(lows[-3:])
        if slope_high <= 0.0001 or slope_low >= -0.0001:
            return None

        atr = self._atr(frame)
        last_close = self._latest_close(frame)
        upper_line = self._line_value(*self._fit_line(highs[-3:]), self._point_index(highs[-1]))
        lower_line = self._line_value(*self._fit_line(lows[-3:]), self._point_index(lows[-1]))
        direction = "bull" if last_close > upper_line else "bear" if last_close < lower_line else "neutral"
        breakout_level = upper_line if direction == "bull" else lower_line
        stop_loss_zone = lower_line if direction == "bull" else upper_line
        quality = 0.50
        return {
            "pattern_name": self.name,
            "direction": direction,
            "breakout_level": breakout_level,
            "stop_loss_zone": stop_loss_zone,
            "swing_points": {"highs": highs, "lows": lows},
            "metadata": {
                "type": "continuation",
                "quality": quality,
                "slope_high": slope_high,
                "slope_low": slope_low,
            },
            "breakout_strength": self._proximity_strength(breakout_level, last_close, atr),
        }
