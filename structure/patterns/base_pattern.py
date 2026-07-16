from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, cast

import numpy as np
import pandas as pd


@dataclass
class BasePattern:
    """Base class for market structure pattern detectors."""

    name: str
    direction: str = "neutral"
    metadata: dict[str, Any] = field(default_factory=lambda: cast(dict[str, Any], {}))

    def detect(self, frame: pd.DataFrame, swings: dict[str, list[Any]]) -> dict[str, Any] | None:
        raise NotImplementedError

    @staticmethod
    def _point_price(point: dict[str, Any] | Any) -> float:
        if isinstance(point, dict):
            point_dict = cast(dict[str, Any], point)
            value: Any = point_dict["price"] if "price" in point_dict else 0.0
        else:
            value = getattr(point, "price", None)
        if isinstance(value, (int, float, str)):
            return float(value)
        return 0.0

    @staticmethod
    def _point_index(point: dict[str, Any] | Any) -> float:
        if isinstance(point, dict):
            point_dict = cast(dict[str, Any], point)
            value: Any = point_dict["index"] if "index" in point_dict else 0
        else:
            value = getattr(point, "index", None)
        if isinstance(value, (int, float, str)):
            return float(value)
        return 0.0

    @staticmethod
    def _calculate_slope(points: list[Any]) -> float:
        if len(points) < 2:
            return 0.0
        x = np.asarray([BasePattern._point_index(point) for point in points], dtype=float)
        y = np.asarray([BasePattern._point_price(point) for point in points], dtype=float)
        return float(np.polyfit(x, y, 1)[0])

    @staticmethod
    def _project_line(slope: float, intercept: float, x: float) -> float:
        return float(slope * x + intercept)

    def _fit_line(self, points: list[Any]) -> tuple[float, float]:
        if len(points) < 2:
            return 0.0, 0.0
        x = np.asarray([self._point_index(point) for point in points], dtype=float)
        y = np.asarray([self._point_price(point) for point in points], dtype=float)
        slope, intercept = np.polyfit(x, y, 1)
        return float(slope), float(intercept)

    def _line_value(self, slope: float, intercept: float, x: float) -> float:
        return float(slope * x + intercept)

    def _trendline_touches(
        self,
        swings: list[Any],
        slope: float,
        intercept: float,
        tolerance: float = 0.0002,
    ) -> int:
        """Count swings that touch a trendline within tolerance."""
        touches = 0
        for swing in swings:
            line_price = self._line_value(slope, intercept, self._point_index(swing))
            if abs(self._point_price(swing) - line_price) <= tolerance:
                touches += 1
        return touches

    def _is_breakout(
        self,
        frame: pd.DataFrame,
        level: float,
        direction: str,
        atr: float | None = None,
    ) -> tuple[bool, float]:
        """Check breakout direction and return confirmation strength."""
        if atr is None:
            atr = self._atr(frame)

        last_close = self._latest_close(frame)
        if direction == "bull":
            if last_close < level:
                return False, 0.0
        else:
            if last_close > level:
                return False, 0.0

        strength = self._proximity_strength(level, last_close, atr)
        return True, strength

    def _slope(self, points: list[Any]) -> float:
        return self._calculate_slope(points)

    def _atr(self, frame: pd.DataFrame, window: int = 14) -> float:
        if len(frame) < 2:
            return 0.0
        true_range = (frame["high"] - frame["low"]).abs()
        if len(true_range) < window:
            return float(true_range.mean()) if not true_range.empty else 0.0
        return float(true_range.rolling(window).mean().dropna().iloc[-1])

    @staticmethod
    def _flat_slope(slope: float, tolerance: float = 0.00015) -> bool:
        return abs(slope) <= tolerance

    @staticmethod
    def _same_level(a: float, b: float, tolerance: float = 0.05) -> bool:
        if max(abs(a), abs(b), 1e-8) == 0:
            return True
        return abs(a - b) / max(abs(a), abs(b)) <= tolerance

    @staticmethod
    def _latest_close(frame: pd.DataFrame) -> float:
        return float(frame["close"].iloc[-1])

    @staticmethod
    def _latest_open(frame: pd.DataFrame) -> float:
        return float(frame["open"].iloc[-1])

    @staticmethod
    def _latest_high(frame: pd.DataFrame) -> float:
        return float(frame["high"].iloc[-1])

    @staticmethod
    def _latest_low(frame: pd.DataFrame) -> float:
        return float(frame["low"].iloc[-1])

    def _proximity_strength(self, target: float, value: float, atr: float) -> float:
        if atr <= 0:
            return 0.0

        # Breakout strength favors closes above the level, and still provides a gradient
        # when price is approaching the breakout level.
        distance = value - target
        if distance >= 0:
            return float(min(1.0, 0.7 + 0.3 * min(1.0, distance / max(atr * 2.0, 1e-8))))

        normalized = max(0.0, 1.0 - abs(distance) / max(atr * 2.0, 1e-8))
        return float(max(0.0, 0.3 + normalized * 0.4))
