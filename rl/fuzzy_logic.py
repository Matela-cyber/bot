from __future__ import annotations


def calculate_fuzzy_quality(pattern_name: str, phase: str, ml_score: float, candlestick_bonus: bool, hour: int) -> float:
    """Combine pattern, phase, score, and timing into a fuzzy quality value."""
    score = 0.0
    if pattern_name in {"Bull_Flag", "Bear_Flag"}:
        score += 0.3
    elif pattern_name in {"Ascending_Channel", "Descending_Channel"}:
        score += 0.25
    elif pattern_name in {"Head_and_Shoulders", "Double_Bottom"}:
        score += 0.2
    else:
        score += 0.1

    if phase == "Impulsive":
        score += 0.3
    elif phase == "Corrective":
        score += 0.2

    score += (ml_score - 0.65) * 1.5
    if candlestick_bonus:
        score += 0.1
    if 8 <= hour <= 16:
        score += 0.1
    return max(0.0, min(1.0, score))
