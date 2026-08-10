from __future__ import annotations

from datetime import datetime

import pytz

from filter.weekend_filter import WeekendFilter


def test_weekend_filter_detects_weekend() -> None:
    weekend_filter = WeekendFilter()
    current_time = datetime(2026, 8, 8, 12, 0, tzinfo=pytz.UTC)

    assert weekend_filter.is_weekend(current_time) is True
    is_open, reason = weekend_filter.is_market_open(current_time)
    assert is_open is False
    assert reason == "weekend"


def test_weekend_filter_market_open_on_weekday() -> None:
    weekend_filter = WeekendFilter()
    current_time = datetime(2026, 8, 7, 12, 0, tzinfo=pytz.UTC)

    assert weekend_filter.is_weekend(current_time) is False
    is_open, reason = weekend_filter.is_market_open(current_time)
    assert is_open is True
    assert reason == "market_open"


def test_weekend_filter_closes_friday_evening() -> None:
    weekend_filter = WeekendFilter()
    current_time = datetime(2026, 8, 7, 22, 0, tzinfo=pytz.UTC)

    is_open, reason = weekend_filter.is_market_open(current_time)
    assert is_open is False
    assert reason == "market_closes_friday"


def test_weekend_filter_not_open_sunday_before_open() -> None:
    weekend_filter = WeekendFilter()
    current_time = datetime(2026, 8, 9, 21, 0, tzinfo=pytz.UTC)

    is_open, reason = weekend_filter.is_market_open(current_time)
    assert is_open is False
    assert reason == "market_not_open_yet"
