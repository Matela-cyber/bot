"""Static annual holiday filter."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo


class HolidayFilter:
    """Block entries on major 2026 US, UK, and euro-area holidays."""

    HOLIDAYS = frozenset({
        date(2026, 1, 1), date(2026, 1, 19), date(2026, 2, 16),
        date(2026, 4, 3), date(2026, 4, 6), date(2026, 5, 25),
        date(2026, 7, 3), date(2026, 9, 7), date(2026, 10, 12),
        date(2026, 11, 11), date(2026, 11, 26), date(2026, 12, 25),
        date(2026, 12, 28),
    })

    def __init__(self, config: Any) -> None:
        self.timezone = ZoneInfo(
            getattr(config, "local_timezone", "Africa/Johannesburg"))

    def should_trade(self, current_time: datetime) -> bool:
        return current_time.astimezone(self.timezone).date() not in self.HOLIDAYS
