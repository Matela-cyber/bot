from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

try:
    import talib
except ImportError:  # pragma: no cover - optional dependency
    talib = None  # type: ignore[assignment]


@dataclass(frozen=True)
class CandlestickBonus:
    """Captures candlestick pattern bonus and priority grading."""

    confirmed: bool
    pattern_name: str | None
    priority_level: str | None
    bonus: float
    pattern_type: str | None


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
    priority_bonus: float
    priority_pattern: str | None
    priority_level: str | None


class CandlestickValidator:
    """Detect candlestick patterns and assign priority-based bonus scoring."""

    PRIORITY_BONUSES: dict[str, tuple[str, float, str]] = {
        "CDLENGULFING": ("High", 0.20, "Engulfing"),
        "CDLMORNINGSTAR": ("High", 0.20, "Morning Star"),
        "CDLEVENINGSTAR": ("High", 0.20, "Evening Star"),
        "CDLHAMMER": ("Medium", 0.15, "Hammer"),
        "CDLSHOOTINGSTAR": ("Medium", 0.15, "Shooting Star"),
        "CDLPIERCING": ("Medium", 0.15, "Piercing Line"),
        "CDLDARKCLOUDCOVER": ("Medium", 0.15, "Dark Cloud Cover"),
        "CDLDOJI": ("Low", 0.10, "Doji"),
        "CDL3WHITESOLDIERS": ("Low", 0.10, "Three White Soldiers"),
        "CDL3BLACKCROWS": ("Low", 0.10, "Three Black Crows"),
    }

    def evaluate(self, frame: pd.DataFrame) -> CandlestickBonus:
        if len(frame) < 3:
            return CandlestickBonus(False, None, None, 0.0, None)

        if talib is None:
            return CandlestickBonus(False, None, None, 0.0, None)

        candles = {
            "open": frame["open"].to_numpy(dtype="float64"),
            "high": frame["high"].to_numpy(dtype="float64"),
            "low": frame["low"].to_numpy(dtype="float64"),
            "close": frame["close"].to_numpy(dtype="float64"),
        }

        choice: CandlestickBonus = CandlestickBonus(False, None, None, 0.0, None)
        for function_name, (level, bonus, label) in self.PRIORITY_BONUSES.items():
            talib_func = getattr(talib, function_name, None)
            if talib_func is None:
                continue
            values = talib_func(candles["open"], candles["high"], candles["low"], candles["close"])
            if len(values) == 0:
                continue
            last_value = int(values[-1])
            if last_value == 0:
                continue

            direction = "bull" if last_value > 0 else "bear"
            priority_name = f"{direction.title()} {label}"
            if choice.bonus < bonus:
                choice = CandlestickBonus(True, priority_name, level, bonus, label)

        return choice


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
        return CandlestickConfirmation(False, None, 0.0, 0.0, False, 0.0, 0.0, 0.0, 0.0, 0.0, None, None)

    last = frame.iloc[-1]
    prev = frame.iloc[-2]
    open_price = float(last["open"])
    close_price = float(last["close"])
    high_price = float(last["high"])
    low_price = float(last["low"])
    candle_body = abs(close_price - open_price)
    candle_range = high_price - low_price

    if candle_range <= 0:
        return CandlestickConfirmation(False, None, 0.0, 0.0, False, 0.0, 0.0, 0.0, 0.0, 0.0, None, None)

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

    bonus = CandlestickValidator().evaluate(frame)
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
        bonus.bonus,
        bonus.pattern_name,
        bonus.priority_level,
    )


def detect_candlestick_confirmation(frame: pd.DataFrame) -> bool:
    """Return True when the latest candle confirms a directional breakout."""
    result = analyze_candlestick_confirmation(frame)
    return result.confirmed
