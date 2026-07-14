from __future__ import annotations


def score_trade_quality(pattern_confidence: float, quality_score: float) -> float:
    """Blend the pattern confidence with the Falcon quality score."""
    return round(min(1.0, (pattern_confidence * 0.7) + (quality_score * 0.3)), 2)
