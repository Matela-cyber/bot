from __future__ import annotations

from typing import Any

import pandas as pd

from structure.patterns.base_pattern import BasePattern


class BullFlatPattern(BasePattern):
    def __init__(self) -> None:
        super().__init__(name="Bull_Flat", direction="bull")

    def detect(self, frame: pd.DataFrame, swings: dict[str, list[Any]]) -> dict[str, Any] | None:
        highs = swings.get("highs", [])[-4:]
        lows = swings.get("lows", [])[-4:]
        if len(highs) < 2 or len(lows) < 3:
            return None

        if not self._same_level(self._point_price(highs[-2]), self._point_price(highs[-1]), tolerance=0.04):
            return None

        slope_low, intercept_low = self._fit_line(lows[-3:])
        if slope_low <= 0.0:
            return None

        atr = self._atr(frame)
        breakout_level = max(self._point_price(point) for point in highs[-2:])
        stop_loss_zone = min(self._point_price(point) for point in lows[-3:]) - max(atr * 0.3, 0.0002)
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
                "slope_low": slope_low,
            },
            "breakout_strength": self._proximity_strength(breakout_level, last_close, atr),
        }
