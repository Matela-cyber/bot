from __future__ import annotations

from typing import Any

import pandas as pd

from structure.patterns.base_pattern import BasePattern


class HeadAndShouldersPattern(BasePattern):
    def __init__(self) -> None:
        super().__init__(name="Head_and_Shoulders", direction="bear")

    def detect(self, frame: pd.DataFrame, swings: dict[str, list[Any]]) -> dict[str, Any] | None:
        highs = swings.get("highs", [])[-5:]
        lows = swings.get("lows", [])[-4:]
        if len(highs) < 3 or len(lows) < 2:
            return None

        left, head, right = highs[-3:]
        if not (self._point_price(head) > self._point_price(left) and self._point_price(head) > self._point_price(right)):
            return None
        if not self._same_level(self._point_price(left), self._point_price(right), tolerance=0.08):
            return None

        slope_neck, intercept_neck = self._fit_line(lows[-2:])
        atr = self._atr(frame)
        breakout_level = self._line_value(slope_neck, intercept_neck, self._point_index(head))
        stop_loss_zone = self._point_price(head) + max(atr * 0.4, 0.0002)
        last_close = self._latest_close(frame)
        quality = 0.68
        return {
            "pattern_name": self.name,
            "direction": self.direction,
            "breakout_level": breakout_level,
            "stop_loss_zone": stop_loss_zone,
            "swing_points": {"highs": [left, head, right], "lows": lows[-2:]},
            "metadata": {
                "type": "reversal",
                "quality": quality,
                "slope_high": self._slope([left, head, right]),
                "slope_low": slope_neck,
            },
            "breakout_strength": self._proximity_strength(breakout_level, last_close, atr),
        }
