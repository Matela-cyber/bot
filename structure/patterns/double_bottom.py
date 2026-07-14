from __future__ import annotations

from typing import Any

import pandas as pd

from structure.patterns.base_pattern import BasePattern


class DoubleBottomPattern(BasePattern):
    def __init__(self) -> None:
        super().__init__(name="Double_Bottom", direction="bull")

    def detect(self, frame: pd.DataFrame, swings: dict[str, list[Any]]) -> dict[str, Any] | None:
        lows = swings.get("lows", [])[-3:]
        highs = swings.get("highs", [])[-2:]
        if len(lows) < 2 or len(highs) < 1:
            return None

        left, right = lows[-2:]
        if not self._same_level(self._point_price(left), self._point_price(right), tolerance=0.05):
            return None

        peak = highs[-1]
        atr = self._atr(frame)
        breakout_level = self._point_price(peak)
        stop_loss_zone = min(self._point_price(left), self._point_price(right)) - max(atr * 0.2, 0.0001)
        last_close = self._latest_close(frame)
        quality = 0.62
        return {
            "pattern_name": self.name,
            "direction": self.direction,
            "breakout_level": breakout_level,
            "stop_loss_zone": stop_loss_zone,
            "swing_points": {"highs": highs, "lows": lows},
            "metadata": {
                "type": "reversal",
                "quality": quality,
                "slope_high": self._slope(highs),
                "slope_low": self._slope(lows),
            },
            "breakout_strength": self._proximity_strength(breakout_level, last_close, atr),
        }
