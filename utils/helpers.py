"""Small, dependency-light helpers."""

from __future__ import annotations

import math
from datetime import datetime, time, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from zoneinfo import ZoneInfo


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return default


def round_to_pips(price: float, pip_size: float = 0.0001) -> float:
    if not math.isfinite(price) or not math.isfinite(pip_size) or pip_size <= 0:
        raise ValueError("price must be finite and pip_size must be positive")
    rounded = (Decimal(str(price)) / Decimal(str(pip_size))
               ).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return float(rounded * Decimal(str(pip_size)))


def calculate_pip_value(price: float, lot_size: float = 1.0, pip_size: float = 0.0001, contract_size: float = 100000.0) -> float:
    if price <= 0 or lot_size < 0 or pip_size <= 0 or contract_size <= 0:
        raise ValueError("price and sizing values must be positive")
    return contract_size * lot_size * pip_size / price


def calculate_pips_from_price(price_difference: float, pip_size: float = 0.0001) -> float:
    if not math.isfinite(price_difference) or pip_size <= 0:
        raise ValueError(
            "price_difference must be finite and pip_size must be positive")
    return abs(price_difference) / pip_size


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _in_session(now: datetime, timezone_name: str, start: time, end: time) -> bool:
    local_time = now.astimezone(ZoneInfo(timezone_name)).time()
    if start <= end:
        return start <= local_time < end
    return local_time >= start or local_time < end


def is_london_ny_session(now: datetime | None = None) -> bool:
    current = now or utc_now()
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return _in_session(current, "Europe/London", time(8), time(17)) or _in_session(
        current, "America/New_York", time(8), time(17)
    )


def get_session_name(now: datetime | None = None) -> str:
    current = now or utc_now()
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    sessions = (
        ("Tokyo", "Asia/Tokyo", time(9), time(18)),
        ("London", "Europe/London", time(8), time(17)),
        ("New York", "America/New_York", time(8), time(17)),
    )
    active = [name for name, zone, start,
              end in sessions if _in_session(current, zone, start, end)]
    return "/".join(active) if active else "Closed"
