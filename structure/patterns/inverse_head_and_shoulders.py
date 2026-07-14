from __future__ import annotations

from typing import Any

import pandas as pd

from structure.patterns.base_pattern import BasePattern


class InverseHeadAndShouldersPattern(BasePattern):
    def __init__(self) -> None:
        super().__init__(name="Inverse_Head_and_Shoulders", direction="bull")

    def detect(self, frame: pd.DataFrame, swings: dict[str, list[Any]]) -> dict[str, Any] | None:
        lows = swings.get("lows", [])[-5:]
        highs = swings.get("highs", [])[-4:]
        if len(lows) < 3 or len(highs) < 2:
            return None

        left, head, right = lows[-3:]
        if not (self._point_price(head) < self._point_price(left) and self._point_price(head) < self._point_price(right)):
            return None
        if not self._same_level(self._point_price(left), self._point_price(right), tolerance=0.08):
            return None

        slope_neck, intercept_neck = self._fit_line(highs[-2:])
        atr = self._atr(frame)
        breakout_level = self._line_value(slope_neck, intercept_neck, self._point_index(head))
        stop_loss_zone = self._point_price(head) - max(atr * 0.4, 0.0002)
        last_close = self._latest_close(frame)
        quality = 0.68
        return {
            "pattern_name": self.name,
            "direction": self.direction,
            "breakout_level": breakout_level,
            "stop_loss_zone": stop_loss_zone,
            "swing_points": {"highs": highs[-2:], "lows": [left, head, right]},
            "metadata": {
                "type": "reversal",
                "quality": quality,
                "slope_high": slope_neck,
                "slope_low": self._slope([left, head, right]),
            },
            "breakout_strength": self._proximity_strength(breakout_level, last_close, atr),
        }
