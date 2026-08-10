from __future__ import annotations

from datetime import datetime

import pytz

from config import settings
from filter.liquidity_filter import LowLiquidityFilter


def test_liquidity_filter_disabled_allows_trading() -> None:
    original_enabled = settings.low_liquidity_filter_enabled
    settings.low_liquidity_filter_enabled = False
    try:
        liquidity_filter = LowLiquidityFilter()
        current_time = datetime(2026, 8, 7, 23, 0, tzinfo=pytz.UTC)

        trade_allowed, reason = liquidity_filter.should_trade(current_time)
        assert trade_allowed is True
        assert reason == "low_liquidity_disabled"
        assert liquidity_filter.get_risk_multiplier(current_time) == 1.0
    finally:
        settings.low_liquidity_filter_enabled = original_enabled


def test_liquidity_filter_blocks_low_liquidity_window() -> None:
    original_enabled = settings.low_liquidity_filter_enabled
    original_allow = settings.low_liquidity_allow_trading
    original_reduce = settings.low_liquidity_reduce_risk
    original_start = settings.low_liquidity_block_start_utc
    original_end = settings.low_liquidity_block_end_utc
    settings.low_liquidity_filter_enabled = True
    settings.low_liquidity_allow_trading = False
    settings.low_liquidity_reduce_risk = False
    settings.low_liquidity_block_start_utc = 22
    settings.low_liquidity_block_end_utc = 2
    try:
        liquidity_filter = LowLiquidityFilter()
        current_time = datetime(2026, 8, 7, 23, 0, tzinfo=pytz.UTC)

        trade_allowed, reason = liquidity_filter.should_trade(current_time)
        assert trade_allowed is False
        assert reason == "low_liquidity_blocked"
        assert liquidity_filter.get_risk_multiplier(current_time) == 0.0
    finally:
        settings.low_liquidity_filter_enabled = original_enabled
        settings.low_liquidity_allow_trading = original_allow
        settings.low_liquidity_reduce_risk = original_reduce
        settings.low_liquidity_block_start_utc = original_start
        settings.low_liquidity_block_end_utc = original_end


def test_liquidity_filter_reduces_risk_when_allowed() -> None:
    original_enabled = settings.low_liquidity_filter_enabled
    original_allow = settings.low_liquidity_allow_trading
    original_reduce = settings.low_liquidity_reduce_risk
    original_start = settings.low_liquidity_block_start_utc
    original_end = settings.low_liquidity_block_end_utc
    settings.low_liquidity_filter_enabled = True
    settings.low_liquidity_allow_trading = True
    settings.low_liquidity_reduce_risk = True
    settings.low_liquidity_block_start_utc = 22
    settings.low_liquidity_block_end_utc = 2
    try:
        liquidity_filter = LowLiquidityFilter()
        current_time = datetime(2026, 8, 7, 23, 0, tzinfo=pytz.UTC)

        trade_allowed, reason = liquidity_filter.should_trade(current_time)
        assert trade_allowed is True
        assert reason == "low_liquidity_reduce_risk"
        assert liquidity_filter.get_risk_multiplier(current_time) == 0.5
    finally:
        settings.low_liquidity_filter_enabled = original_enabled
        settings.low_liquidity_allow_trading = original_allow
        settings.low_liquidity_reduce_risk = original_reduce
        settings.low_liquidity_block_start_utc = original_start
        settings.low_liquidity_block_end_utc = original_end
