"""Pre-trade market and account filters."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from indicators.atr import calculate_atr
from filter.market_safety import (
    AdaptiveVolatilityFilter,
    LowLiquidityFilter,
    MarketShockFilter,
    WeekendFilter,
)
from filter.holidays import HolidayFilter
from utils.helpers import get_session_name


class TradingFilter:
    ATR_PERIOD = 14
    DEFAULT_MIN_ATR = 0.0002
    DEFAULT_MAX_ATR = 0.003
    DEFAULT_MAX_SPREAD = 0.0003

    def __init__(self, config: Any, mt5_client: Any | None = None) -> None:
        if config is None:
            raise ValueError("config is required")
        self.config = config
        self.mt5_client = mt5_client
        self.logger = logging.getLogger(__name__)

        self.weekend_filter = WeekendFilter(config)
        self.liquidity_filter = LowLiquidityFilter(config)
        self.adaptive_volatility = AdaptiveVolatilityFilter(config)
        self.holiday_filter = HolidayFilter(config)
        self.shock_filter = MarketShockFilter(config)

        self.spread_filter_enabled = getattr(
            config, 'spread_filter_enabled', True)
        self.max_spread = getattr(
            config, 'max_spread', self.DEFAULT_MAX_SPREAD)

    def should_trade(
        self,
        data: pd.DataFrame,
        current_time: datetime | None = None,
        spread: float | None = None,
        include_spread: bool = True,
    ) -> bool:
        try:
            evaluation_time = current_time or self._current_time()

            checks = [
                self.check_volatility(data, evaluation_time),
                self.check_session(evaluation_time),
                self.holiday_filter.should_trade(evaluation_time),
                self.shock_filter.should_trade(data),
                self.adaptive_volatility.should_trade(data),
            ]

            if include_spread and self.spread_filter_enabled:
                checks.append(self.check_spread(spread))

            return all(checks)

        except Exception as exc:
            self.logger.exception("Trading filter evaluation failed: %s", exc)
            return False

    def check_volatility(self, data: pd.DataFrame, current_time: datetime | None = None) -> bool:
        if data.empty:
            return False

        current = current_time or self._current_time()

        if not self.weekend_filter.should_trade(current):
            return False

        if not self.liquidity_filter.should_trade(current):
            return False

        atr = calculate_atr(data, period=self.ATR_PERIOD).iloc[-1]
        if not np.isfinite(atr):
            return False

        minimum = float(getattr(self.config, "min_atr", self.DEFAULT_MIN_ATR))
        maximum = float(getattr(self.config, "max_atr", self.DEFAULT_MAX_ATR))

        if minimum < 0 or maximum < minimum:
            raise ValueError("Invalid ATR bounds")

        return minimum <= float(atr) <= maximum

    def check_spread(self, spread: float | None = None) -> bool:
        if not self.spread_filter_enabled:
            return True

        maximum = float(self.max_spread)

        if spread is None:
            spread = getattr(self.config, "current_spread",
                             getattr(self.config, "spread", None))

        if spread is None:
            client = self.mt5_client or getattr(
                self.config, "mt5_client", None)
            symbol = getattr(self.config, "symbol", None)

            if client is not None and symbol:
                api = client.get_api() if hasattr(client, "get_api") else client
                tick = api.symbol_info_tick(symbol)
                if tick is not None:
                    spread = float(tick.ask) - float(tick.bid)

        if spread is None or not np.isfinite(float(spread)) or maximum < 0:
            return False

        return 0 <= float(spread) < maximum

    def check_session(self, current_time: datetime | None = None) -> bool:
        current = current_time or getattr(self.config, "current_time", None)

        if current is None:
            current = datetime.now(timezone.utc)

        if not isinstance(current, datetime):
            raise TypeError("current_time must be a datetime")

        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)

        local = current.astimezone(
            ZoneInfo(getattr(self.config, "local_timezone", "Africa/Johannesburg")))

        if local.weekday() >= 5:
            return False

        if local.weekday() == 4 and local.hour >= int(getattr(self.config, "friday_cutoff_hour", 17)):
            return False

        start = int(getattr(self.config, "low_liquidity_block_start_utc", 22))
        end = int(getattr(self.config, "low_liquidity_block_end_utc", 2))

        if getattr(self.config, "low_liquidity_filter_enabled", True):
            hour = current.hour
            blocked = hour >= start or hour < end if start > end else start <= hour < end
            if blocked:
                return False

        return get_session_name(current) != "Closed"

    def _current_time(self) -> datetime:
        current = getattr(self.config, "current_time", None)
        if current is None:
            current = datetime.now(timezone.utc)

        if not isinstance(current, datetime):
            raise TypeError("current_time must be a datetime")

        return current.replace(tzinfo=timezone.utc) if current.tzinfo is None else current
