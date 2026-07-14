from __future__ import annotations

from typing import Any

import pandas as pd

from structure.patterns.base_pattern import BasePattern


class BearFlatPattern(BasePattern):
    def __init__(self) -> None:
        super().__init__(name="Bear_Flat", direction="bear")

    def detect(self, frame: pd.DataFrame, swings: dict[str, list[Any]]) -> dict[str, Any] | None:
        highs = swings.get("highs", [])[-4:]
        lows = swings.get("lows", [])[-4:]
        if len(highs) < 3 or len(lows) < 2:
            return None

        if not self._same_level(self._point_price(lows[-2]), self._point_price(lows[-1]), tolerance=0.04):
            return None

        slope_high, intercept_high = self._fit_line(highs[-3:])
        if slope_high >= 0.0:
            return None

        atr = self._atr(frame)
        breakout_level = min(self._point_price(point) for point in lows[-2:])
        stop_loss_zone = max(self._point_price(point) for point in highs[-3:]) + max(atr * 0.3, 0.0002)
        last_close = self._latest_close(frame)
        quality = 0.58
        return {
            "pattern_name": self.name,
            "direction": self.direction,
            "breakout_level": breakout_level,
            "stop_loss_zone": stop_loss_zone,
            "swing_points": {"highs": highs, "lows": lows},
            "metadata": {
                "type": "continuation",
                "quality": quality,
                "slope_high": slope_high,
            },
            "breakout_strength": self._proximity_strength(breakout_level, last_close, atr),
        }
