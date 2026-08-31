from __future__ import annotations

import logging
from datetime import datetime, timedelta

from config import LOCAL_TIMEZONE, settings

logger = logging.getLogger(__name__)


class WeekendFilter:
    """Filter that blocks trading during weekend market closures."""

    def is_weekend(self, current_time: datetime) -> bool:
        """Return True when the current local time is Saturday or Sunday."""
        local_time = current_time.astimezone(LOCAL_TIMEZONE)
        return local_time.weekday() in (5, 6)

    def _friday_closeout_deadline(self, local_time: datetime) -> datetime:
        """Return the Friday cutoff at which the bot should close before the weekend."""
        friday_close = local_time.replace(
            hour=settings.market_close_friday,
            minute=0,
            second=0,
            microsecond=0,
        )
        return friday_close - timedelta(minutes=30)

    def is_market_open(self, current_time: datetime) -> tuple[bool, str]:
        """Return whether Forex market trading hours are currently open in local time."""
        local_time = current_time.astimezone(LOCAL_TIMEZONE)
        weekday = local_time.weekday()

        if weekday >= 5:
            return False, "weekend"

        if weekday == 4 and local_time >= self._friday_closeout_deadline(local_time):
            return False, "market_closes_friday"

        return True, "market_open"

    def should_trade(self, current_time: datetime) -> tuple[bool, str]:
        """Return whether new trades are allowed at the current local time."""
        local_time = current_time.astimezone(LOCAL_TIMEZONE)
        if local_time.weekday() >= 5:
            return False, "weekend_trading_blocked"
        if local_time.weekday() == 4 and local_time.hour >= settings.friday_cutoff_hour:
            return False, "friday_cutoff_17h_local"
        return True, "trading_allowed"

    def should_close_all_positions(self, current_time: datetime) -> bool:
        """Return whether bot-owned positions must be closed before the weekend begins."""
        local_time = current_time.astimezone(LOCAL_TIMEZONE)
        if local_time.weekday() == 4:
            return local_time >= self._friday_closeout_deadline(local_time)
        return local_time.weekday() == 5

    def get_trading_hours(self) -> dict[str, object]:
        """Return configured Forex market hours expressed in local time."""
        now = datetime.now(LOCAL_TIMEZONE)
        is_open, _ = self.is_market_open(now)
        return {
            "opens": f"Sunday {settings.market_open_sunday:02d}:00 local",
            "closes": f"Friday {settings.friday_cutoff_hour:02d}:00 local",
            "is_open": is_open,
        }
