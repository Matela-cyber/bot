from __future__ import annotations

import logging
from datetime import datetime

import pytz

from config import settings

logger = logging.getLogger(__name__)


class WeekendFilter:
    """Filter that blocks trading during weekend market closures."""

    def is_weekend(self, current_time: datetime) -> bool:
        """Return True when the current time is Saturday UTC."""
        utc_time = current_time.astimezone(pytz.UTC)
        return utc_time.weekday() == 5

    def is_market_open(self, current_time: datetime) -> tuple[bool, str]:
        """Return whether Forex market trading hours are currently open."""
        utc_time = current_time.astimezone(pytz.UTC)
        weekday = utc_time.weekday()
        hour = utc_time.hour

        if weekday == 5:
            return False, "weekend"

        if weekday == 4 and hour >= settings.market_close_friday:
            return False, "market_closes_friday"

        if weekday == 6 and hour < settings.market_open_sunday:
            return False, "market_not_open_yet"

        return True, "market_open"

    def get_trading_hours(self) -> dict[str, object]:
        """Return configured Forex market open and close hours in UTC."""
        now = datetime.now(pytz.UTC)
        is_open, _ = self.is_market_open(now)
        return {
            "opens": f"Sunday {settings.market_open_sunday:02d}:00 UTC",
            "closes": f"Friday {settings.market_close_friday:02d}:00 UTC",
            "is_open": is_open,
        }
