from __future__ import annotations

from datetime import datetime, timedelta

import pytz

from filter.news_filter import NewsFilter


def test_news_filter_no_news_returns_safe() -> None:
    news_filter = NewsFilter()
    news_filter.fetch_calendar = lambda date=None: []

    current_time = datetime(2026, 8, 6, 12, 0, tzinfo=pytz.UTC)
    trade_allowed, reason = news_filter.should_trade(current_time)
    assert trade_allowed is True
    assert reason == "No news"
    assert news_filter.get_risk_multiplier(current_time) == 1.0


def test_news_filter_medium_impact_reduces_risk() -> None:
    news_filter = NewsFilter()
    event_time = datetime(2026, 8, 6, 12, 15, tzinfo=pytz.UTC)
    news_filter.fetch_calendar = lambda date=None: [
        {
            "date": "2026-08-06",
            "time": "12:15",
            "currency": "USD",
            "impact": "Medium",
            "event": "Retail Sales",
        }
    ]

    current_time = datetime(2026, 8, 6, 12, 0, tzinfo=pytz.UTC)
    trade_allowed, reason = news_filter.should_trade(current_time)

    assert trade_allowed is True
    assert "reduce risk" in reason
    assert news_filter.get_risk_multiplier(current_time) == 0.5


def test_news_filter_high_impact_blocks_trade() -> None:
    news_filter = NewsFilter()
    news_filter.fetch_calendar = lambda date=None: [
        {
            "date": "2026-08-06",
            "time": "12:10",
            "currency": "USD",
            "impact": "High",
            "event": "FOMC",
        }
    ]

    current_time = datetime(2026, 8, 6, 12, 0, tzinfo=pytz.UTC)
    trade_allowed, reason = news_filter.should_trade(current_time)

    assert trade_allowed is False
    assert "High-impact news" in reason
    assert news_filter.get_risk_multiplier(current_time) == 0.0
