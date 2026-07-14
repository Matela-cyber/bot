from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class CandlestickConfirmation:
    """Structured confirmation result for the latest candle."""

    confirmed: bool
    direction: str | None
    strength: float
    body_ratio: float
    breakout: bool
    upper_shadow_ratio: float
    lower_shadow_ratio: float
    breakout_strength: float
    close_position: float


def detect_candlestick_confirmation(frame: pd.DataFrame) -> bool:
    """Return True when the latest candle confirms a directional breakout."""
    result = analyze_candlestick_confirmation(frame)
    return result.confirmed


def _estimate_atr(frame: pd.DataFrame, window: int = 14) -> float:
    if len(frame) < 2:
        return 0.0
    tr = (frame["high"] - frame["low"]).abs()
    if len(tr) < window:
        return float(tr.mean()) if not tr.empty else 0.0
    return float(tr.rolling(window).mean().dropna().iloc[-1])


def analyze_candlestick_confirmation(frame: pd.DataFrame) -> CandlestickConfirmation:
    """Analyze the latest candle for confirmation strength and breakout quality."""
    if len(frame) < 2:
        return CandlestickConfirmation(False, None, 0.0, 0.0, False, 0.0, 0.0, 0.0, 0.0)

    last = frame.iloc[-1]
    prev = frame.iloc[-2]
    open_price = float(last["open"])
    close_price = float(last["close"])
    high_price = float(last["high"])
    low_price = float(last["low"])
    candle_body = abs(close_price - open_price)
    candle_range = high_price - low_price

    if candle_range <= 0:
        return CandlestickConfirmation(False, None, 0.0, 0.0, False, 0.0, 0.0, 0.0, 0.0)

    body_ratio = candle_body / candle_range
    upper_shadow = high_price - max(open_price, close_price)
    lower_shadow = min(open_price, close_price) - low_price
    upper_shadow_ratio = upper_shadow / candle_range
    lower_shadow_ratio = lower_shadow / candle_range

    bullish = close_price > open_price
    bearish = close_price < open_price
    breakout = False
    direction: str | None = None
    breakout_distance = 0.0

    if bullish and close_price > float(prev["high"]):
        direction = "bull"
        breakout = True
        breakout_distance = close_price - float(prev["high"])
    elif bearish and close_price < float(prev["low"]):
        direction = "bear"
        breakout = True
        breakout_distance = float(prev["low"]) - close_price

    atr = max(_estimate_atr(frame), 1e-8)
    breakout_strength = min(1.0, breakout_distance / atr) if breakout else 0.0
    close_position = (
        (close_price - low_price) / candle_range if direction == "bull" else (high_price - close_price) / candle_range
    ) if direction else (close_price - low_price) / candle_range if bullish else (high_price - close_price) / candle_range

    if breakout:
        confirmed = body_ratio >= 0.35 and close_position >= 0.65
        strength = min(1.0, body_ratio * 0.7 + breakout_strength * 0.3)
    else:
        momentum = min(1.0, candle_body / atr)
        confinement = 1.0 - max(upper_shadow_ratio, lower_shadow_ratio)
        strength = min(1.0, body_ratio * 0.6 + momentum * 0.2 + confinement * 0.2)
        confirmed = False

    return CandlestickConfirmation(
        confirmed,
        direction,
        strength,
        body_ratio,
        breakout,
        upper_shadow_ratio,
        lower_shadow_ratio,
        breakout_strength,
        close_position,
    )
