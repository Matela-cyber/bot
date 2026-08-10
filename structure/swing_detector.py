from __future__ import annotations

from typing import Any

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


class SwingDetector:
    """Detect market structure swings using highs/lows with noise filtering and validation."""

    def __init__(self, order: int = 5, min_distance: int = 3, min_move: float | None = None) -> None:
        self.order = order
        self.min_distance = min_distance
        self.min_move = min_move

    def _estimate_min_move(self, frame: pd.DataFrame) -> float:
        if self.min_move is not None:
            return self.min_move
        if len(frame) < 2:
            return 0.0
        atr = (frame["high"] - frame["low"]).abs().rolling(14).mean().fillna(0)
        return float(atr.iloc[-1] * 0.75) if not atr.empty else 0.0

    def _filter_swings(self, frame: pd.DataFrame, raw_points: list[SwingPoint]) -> list[SwingPoint]:
        if not raw_points:
            return []

        filtered: list[SwingPoint] = []
        min_move = self._estimate_min_move(frame)
        for point in raw_points:
            if filtered and min_move > 0 and abs(float(point["price"]) - float(filtered[-1]["price"])) < min_move:
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

        effective_order = max(2, min(self.order, max(2, len(frame) // 4)))
        highs_idx = argrelextrema(frame["high"].to_numpy(), np.greater, order=effective_order, mode="clip")[0]
        lows_idx = argrelextrema(frame["low"].to_numpy(), np.less, order=effective_order, mode="clip")[0]

        raw_highs: list[SwingPoint] = []
        for i in highs_idx:
            idx = int(i)
            if idx >= self.min_distance:
                raw_highs.append(SwingPoint(idx, frame.index[idx], float(frame["high"].iloc[idx])))

        raw_lows: list[SwingPoint] = []
        for i in lows_idx:
            idx = int(i)
            if idx >= self.min_distance:
                raw_lows.append(SwingPoint(idx, frame.index[idx], float(frame["low"].iloc[idx])))

        highs = self._filter_swings(frame, raw_highs)
        lows = self._filter_swings(frame, raw_lows)
        return {"highs": highs, "lows": lows}


def detect_swings(frame: pd.DataFrame) -> dict[str, list[Any]]:
    try:
        # Prefer the adaptive detector when available
        from structure.adaptive_swing_detector import AdaptiveSwingDetector  # type: ignore

        detector = AdaptiveSwingDetector()
        return detector.detect(frame)
    except Exception:
        detector = SwingDetector()
        return detector.detect(frame)
