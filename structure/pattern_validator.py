from __future__ import annotations

from typing import Any, TypedDict, cast


class SwingPoints(TypedDict, total=False):
    highs: list[Any]
    lows: list[Any]


class PatternMetadata(TypedDict, total=False):
    type: str


class PatternValidator:
    """Score pattern detections using structure, breakout strength, and confirmation quality."""

    def __init__(self, threshold: float = 0.62) -> None:
        self.threshold = threshold

    def score(self, pattern: dict[str, Any]) -> float:
        confidence = 0.1

        direction = pattern.get("direction")
        if direction == "bull":
            confidence += 0.12
        elif direction == "bear":
            confidence += 0.10

        breakout_strength = min(0.30, max(0.0, float(pattern.get("breakout_strength", 0.0)) * 0.9))
        confidence += breakout_strength

        candlestick_strength = min(1.0, max(0.0, float(pattern.get("candlestick_strength", 0.0))))
        confidence += candlestick_strength * 0.20
        if pattern.get("candlestick_bonus"):
            confidence += 0.08

        trend_strength = min(0.18, max(0.0, abs(float(pattern.get("trend_strength", 0.0))) * 0.5))
        confidence += trend_strength

        contraction = max(0.0, float(pattern.get("range_contraction", 0.0)))
        confidence += min(0.10, contraction * 0.5)

        swing_quality = 0.0
        raw_swing_points = pattern.get("swing_points")
        swing_points: SwingPoints = cast(SwingPoints, raw_swing_points) if isinstance(raw_swing_points, dict) else {}
        highs = swing_points.get("highs", [])
        lows = swing_points.get("lows", [])
        if len(highs) >= 2 and len(lows) >= 2:
            swing_quality += 0.08
        if len(highs) >= 3 and len(lows) >= 3:
            swing_quality += 0.06
        confidence += swing_quality

        raw_metadata = pattern.get("metadata")
        metadata: PatternMetadata = cast(PatternMetadata, raw_metadata) if isinstance(raw_metadata, dict) else {}
        metadata_type = metadata.get("type")
        if metadata_type == "reversal":
            confidence += 0.04
        elif metadata_type == "continuation":
            confidence += 0.03

        ml_score = min(1.0, max(0.0, float(pattern.get("ml_score", 0.5))))
        confidence += (ml_score - 0.5) * 0.14

        return min(0.99, max(0.0, confidence))

    def is_accepted(self, pattern: dict[str, Any]) -> bool:
        return self.score(pattern) >= self.threshold
