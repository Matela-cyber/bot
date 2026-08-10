from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, cast
import re

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

    def _infer_timeframe(self, frame: pd.DataFrame) -> str | None:
        if not isinstance(frame.index, pd.DatetimeIndex):
            return None

        timeframe = pd.infer_freq(frame.index)
        if timeframe is not None:
            return timeframe

        diffs = frame.index.to_series().diff().dropna()
        if diffs.empty:
            return None

        mode = diffs.mode()
        if mode.empty:
            return None
        return str(mode.iloc[0])

    def _timeframe_minutes(self, frame: pd.DataFrame) -> int:
        timeframe = self._infer_timeframe(frame)
        if timeframe is None:
            return 15

        match = re.search(r"(\d+)([Tt]|min|H|D|W|M)$", timeframe)
        if not match:
            return 15

        value = int(match.group(1))
        unit = match.group(2).upper()
        if unit in {"T", "MIN"}:
            return value
        if unit == "H":
            return value * 60
        if unit == "D":
            return value * 1440
        if unit == "W":
            return value * 10080
        if unit == "M":
            return value * 43200
        return 15

    def _recent_swings(self, swings: list[Any], frame: pd.DataFrame, min_swings: int = 3, max_swings: int = 4) -> list[Any]:
        if not swings:
            return []

        window = max(min_swings, min(max_swings, int(len(frame) / max(15.0, self._timeframe_minutes(frame)))))
        return swings[-window:]

    def _adaptive_tolerance(self, frame: pd.DataFrame, base: float = 0.00018, scale: float = 0.20) -> float:
        atr = self._atr(frame)
        if atr <= 0:
            return base
        return max(base, atr * scale)

    def _adaptive_channel_width(self, frame: pd.DataFrame, min_width: float = 0.0005) -> float:
        atr = self._atr(frame)
        if atr <= 0:
            return min_width
        return max(min_width, atr * 0.40)

    def _adaptive_slope_limit(self, frame: pd.DataFrame, base_limit: float = 0.0005) -> float:
        atr = self._atr(frame)
        if atr <= 0:
            return base_limit
        return max(base_limit, atr * 0.45)

    def _adaptive_flat_slope_tolerance(self, frame: pd.DataFrame, base_tolerance: float = 0.00018) -> float:
        atr = self._atr(frame)
        if atr <= 0:
            return base_tolerance
        return max(base_tolerance, atr * 0.18)

    def _adaptive_breakout_threshold(self, frame: pd.DataFrame, base: float = 0.65) -> float:
        minutes = self._timeframe_minutes(frame)
        if minutes >= 240:
            return min(0.80, base + 0.10)
        return base

    def _minimum_pattern_candles(self, frame: pd.DataFrame, base: int = 10) -> int:
        return max(base, min(20, max(6, int(len(frame) * 0.08))))

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
