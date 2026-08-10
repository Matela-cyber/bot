from __future__ import annotations

from typing import Any
import re

import numpy as np
import pandas as pd
from scipy.signal import argrelextrema  # type: ignore[reportMissingTypeStubs]


class SwingPoint(dict[str, Any]):
    """Represents a swing point with metadata and price-like behavior."""

    def __init__(self, index: int, time: Any, price: float) -> None:
        super().__init__(index=index, time=time, price=price)
        self.index = index
        self.time = time
        self.price = price

    def __float__(self) -> float:
        return float(self.get("price", 0.0))

    def __sub__(self, other: Any) -> float:
        return float(self) - float(other)

    def __lt__(self, other: Any) -> bool:
        return float(self) < float(other)

    def __gt__(self, other: Any) -> bool:
        return float(self) > float(other)


class AdaptiveSwingDetector:
    """Detect market structure swings with adaptive order, distance, and noise filtering."""

    def __init__(
        self,
        order: int | None = None,
        min_distance: int | None = None,
        min_move: float | None = None,
    ) -> None:
        self.order = order
        self.min_distance = min_distance
        self.min_move = min_move

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

    def _adaptive_order(self, frame: pd.DataFrame) -> int:
        if self.order is not None:
            return max(2, self.order)

        length = len(frame)
        minutes = self._timeframe_minutes(frame)
        if length < 20:
            return 2

        ratio = max(0.05, min(0.15, 0.06 + (minutes / 1440) * 0.02))
        order = int(max(2, min(14, round(length * ratio))))
        if minutes <= 5:
            order = min(14, max(order, 5))
        elif minutes <= 15:
            order = min(12, max(order, 4))
        elif minutes <= 60:
            order = min(10, max(order, 3))
        else:
            order = min(8, max(order, 3))
        return order

    def _adaptive_min_distance(self, frame: pd.DataFrame, order: int) -> int:
        if self.min_distance is not None:
            return max(1, self.min_distance)

        minutes = self._timeframe_minutes(frame)
        base = max(2, min(order - 1, int(order * 0.5)))
        if minutes >= 240:
            return min(order - 1, max(base, 3))
        return min(order - 1, max(base, 2))

    def _estimate_min_move(self, frame: pd.DataFrame) -> float:
        if self.min_move is not None:
            return self.min_move
        if len(frame) < 2:
            return 0.0

        atr = (frame["high"] - frame["low"]).abs().rolling(14, min_periods=1).mean().fillna(0)
        last_atr = float(atr.iloc[-1]) if not atr.empty else 0.0
        return max(last_atr * 0.5, 0.00005)

    def _filter_swings(self, frame: pd.DataFrame, raw_points: list[SwingPoint], min_distance: int) -> list[SwingPoint]:
        if not raw_points:
            return []

        filtered: list[SwingPoint] = []
        min_move = self._estimate_min_move(frame)
        for point in raw_points:
            if filtered:
                last = filtered[-1]
                if abs(point.price - last.price) < min_move and abs(point.index - last.index) < min_distance:
                    if (point.price > last.price and point > last) or (point.price < last.price and point < last):
                        filtered[-1] = point
                    continue
            filtered.append(point)

        return filtered

    def detect(self, frame: pd.DataFrame) -> dict[str, list[SwingPoint]]:
        if frame.empty:
            return {"highs": [], "lows": []}

        required = {"open", "high", "low", "close"}
        missing = required.difference(frame.columns)
        if missing:
            raise ValueError(f"Frame missing required OHLC columns: {sorted(missing)}")

        if "volume" not in frame.columns:
            frame = frame.copy()
            frame["volume"] = 0.0

        order = self._adaptive_order(frame)
        min_distance = self._adaptive_min_distance(frame, order)

        if order >= len(frame) // 2:
            order = max(2, len(frame) // 4)

        highs_idx = argrelextrema(frame["high"].to_numpy(), np.greater, order=order, mode="clip")[0]
        lows_idx = argrelextrema(frame["low"].to_numpy(), np.less, order=order, mode="clip")[0]

        raw_highs: list[SwingPoint] = []
        raw_lows: list[SwingPoint] = []
        for i in highs_idx:
            idx = int(i)
            raw_highs.append(SwingPoint(idx, frame.index[idx], float(frame["high"].iloc[idx])))
        for i in lows_idx:
            idx = int(i)
            raw_lows.append(SwingPoint(idx, frame.index[idx], float(frame["low"].iloc[idx])))

        highs = self._filter_swings(frame, raw_highs, min_distance)
        lows = self._filter_swings(frame, raw_lows, min_distance)
        return {"highs": highs, "lows": lows}
