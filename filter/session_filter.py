"""Session, day, and hour filtering for strategies."""

from datetime import datetime
from typing import List, Optional


class SessionFilter:
    """Filter trading sessions by day, hour, and session type."""

    ASIA_HOURS = range(0, 8)  # 0-8 UTC
    LONDON_HOURS = range(8, 16)  # 8-16 UTC
    NEW_YORK_HOURS = range(13, 21)  # 13-21 UTC

    GOOD_DAYS_MR = [0, 3]  # Monday, Thursday

    @classmethod
    def is_asia_session(cls, dt: datetime) -> bool:
        """Check if time is in Asia session."""
        return dt.hour in cls.ASIA_HOURS

    @classmethod
    def is_london_session(cls, dt: datetime) -> bool:
        """Check if time is in London session."""
        return dt.hour in cls.LONDON_HOURS

    @classmethod
    def is_new_york_session(cls, dt: datetime) -> bool:
        """Check if time is in New York session."""
        return dt.hour in cls.NEW_YORK_HOURS

    @classmethod
    def is_good_day_mr(cls, dt: datetime) -> bool:
        """Check if day is good for Mean Reversion."""
        return dt.weekday() in cls.GOOD_DAYS_MR

    @classmethod
    def is_good_hour_mr(cls, dt: datetime, hours: Optional[List[int]] = None) -> bool:
        """Check if hour is good for Mean Reversion."""
        if hours is None:
            hours = [0, 5, 11]
        return dt.hour in hours

    @classmethod
    def is_good_hour_smc(cls, dt: datetime, hour: Optional[int] = None) -> bool:
        """Check if hour is good for SMC Breakout."""
        if hour is None:
            hour = 18
        return dt.hour == hour

    @classmethod
    def get_session_name(cls, dt: datetime) -> str:
        """Get current session name."""
        if cls.is_asia_session(dt):
            return "asia"
        elif cls.is_london_session(dt):
            return "london"
        elif cls.is_new_york_session(dt):
            return "new_york"
        return "closed"
