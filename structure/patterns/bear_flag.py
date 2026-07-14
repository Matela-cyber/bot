from __future__ import annotations

from typing import Any

import pandas as pd

from structure.patterns.base_pattern import BasePattern


class BearFlagPattern(BasePattern):
    def __init__(self) -> None:
        super().__init__(name="Bear_Flag", direction="bear")

    def detect(self, frame: pd.DataFrame, swings: dict[str, list[Any]]) -> dict[str, Any] | None:
        highs = swings.get("highs", [])[-4:]
        lows = swings.get("lows", [])[-4:]
        if len(highs) < 3 or len(lows) < 3:
            return None

        atr = self._atr(frame)
        impulse = float(frame["close"].iloc[-20] - frame["close"].iloc[-5]) if len(frame) >= 20 else 0.0
        if impulse <= max(atr * 0.6, 0.00035):
            return None

        slope_high, _ = self._fit_line(highs[-3:])
        slope_low, _ = self._fit_line(lows[-3:])
        if slope_high <= 0.0001 or slope_low <= 0.0001:
            return None

        breakout_level = min(self._point_price(point) for point in lows[-3:])
        resistance = max(self._point_price(point) for point in highs[-3:])
        stop_loss_zone = resistance + max(atr * 0.4, 0.0002)
        last_close = self._latest_close(frame)
        quality = 0.65
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
                "slope_low": slope_low,
            },
            "breakout_strength": self._proximity_strength(breakout_level, last_close, atr),
        }
