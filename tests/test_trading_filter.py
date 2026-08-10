from __future__ import annotations

from datetime import datetime

import pytz

from filter.liquidity_filter import LowLiquidityFilter
from filter.news_filter import NewsFilter
from filter.trading_filter import TradingFilter
from filter.weekend_filter import WeekendFilter


def test_trading_filter_blocks_weekend() -> None:
    news_filter = NewsFilter()
    weekend_filter = WeekendFilter()
    liquidity_filter = LowLiquidityFilter()
    trading_filter = TradingFilter(news_filter, weekend_filter, liquidity_filter)
    current_time = datetime(2026, 8, 8, 12, 0, tzinfo=pytz.UTC)

    result = trading_filter.should_trade(current_time)

    assert result["trade"] is False
    assert result["risk_multiplier"] == 0.0
    assert result["reason"] == "weekend_trading_blocked"
    assert result["details"]["weekend"] is True


def test_trading_filter_blocks_market_hours_before_open() -> None:
    news_filter = NewsFilter()
    weekend_filter = WeekendFilter()
    liquidity_filter = LowLiquidityFilter()
    trading_filter = TradingFilter(news_filter, weekend_filter, liquidity_filter)
    current_time = datetime(2026, 8, 9, 21, 0, tzinfo=pytz.UTC)

    result = trading_filter.should_trade(current_time)

    assert result["trade"] is False
    assert result["reason"] == "weekend_trading_blocked"
    assert result["details"]["weekend"] is True


def test_trading_filter_allows_trade_during_safe_period() -> None:
    news_filter = NewsFilter()
    weekend_filter = WeekendFilter()
    liquidity_filter = LowLiquidityFilter()
    trading_filter = TradingFilter(news_filter, weekend_filter, liquidity_filter)
    news_filter.should_trade = lambda current_time: (True, "No news")
    news_filter.is_high_impact_news = lambda current_time, lookahead_minutes: {
        "halt": False,
        "reason": "no_upcoming_news",
        "impact": None,
        "event_name": "",
        "minutes_until": -1,
    }

    current_time = datetime(2026, 8, 7, 12, 0, tzinfo=pytz.UTC)
    result = trading_filter.should_trade(current_time)

    assert result["trade"] is True
    assert result["risk_multiplier"] == 1.0
    assert result["checks_passed"] == 3
