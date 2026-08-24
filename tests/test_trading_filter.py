from __future__ import annotations

from datetime import datetime
import pytz

from filter.liquidity_filter import LowLiquidityFilter
from filter.trading_filter import TradingFilter
from filter.weekend_filter import WeekendFilter


class NormalVolatility:
    def should_trade(self, symbol: str) -> tuple[bool, str, float]:
        return True, "Normal market", 1.0


def test_trading_filter_blocks_weekend() -> None:
    weekend_filter = WeekendFilter()
    liquidity_filter = LowLiquidityFilter()
    trading_filter = TradingFilter(
        NormalVolatility(), weekend_filter, liquidity_filter)
    current_time = datetime(2026, 8, 8, 12, 0, tzinfo=pytz.UTC)

    result = trading_filter.should_trade(current_time)

    assert result["trade"] is False
    assert result["risk_multiplier"] == 0.0
    assert result["reason"] == "weekend_trading_blocked"
    assert result["details"]["weekend"] is True


def test_trading_filter_blocks_market_hours_before_open() -> None:
    weekend_filter = WeekendFilter()
    liquidity_filter = LowLiquidityFilter()
    trading_filter = TradingFilter(
        NormalVolatility(), weekend_filter, liquidity_filter)
    current_time = datetime(2026, 8, 9, 21, 0, tzinfo=pytz.UTC)

    result = trading_filter.should_trade(current_time)

    assert result["trade"] is False
    assert result["reason"] == "weekend_trading_blocked"
    assert result["details"]["weekend"] is True


def test_trading_filter_allows_trade_during_safe_period() -> None:
    weekend_filter = WeekendFilter()
    liquidity_filter = LowLiquidityFilter()
    trading_filter = TradingFilter(
        NormalVolatility(), weekend_filter, liquidity_filter)

    current_time = datetime(2026, 8, 7, 12, 0, tzinfo=pytz.UTC)
    result = trading_filter.should_trade(current_time)

    assert result["trade"] is True
    assert result["risk_multiplier"] == 1.0
    assert result["checks_passed"] == 3


def test_trading_filter_blocks_friday_cutoff() -> None:
    trading_filter = TradingFilter(
        NormalVolatility(), WeekendFilter(), LowLiquidityFilter())

    result = trading_filter.should_trade(
        datetime(2026, 8, 7, 15, 0, tzinfo=pytz.UTC))

    assert result["trade"] is False
    assert result["reason"] == "friday_cutoff_17h_local"
    assert result["risk_multiplier"] == 0.0
