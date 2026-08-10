from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import pytz

from config import settings

logger = logging.getLogger(__name__)


class LowLiquidityFilter:
    """Filter that prevents trading during configured low-liquidity windows."""

    def is_low_liquidity(self, current_time: datetime) -> bool:
        """Return True when current time falls into the configured low-liquidity window."""
        if not settings.low_liquidity_filter_enabled:
            return False

        utc_time = current_time.astimezone(pytz.UTC)
        hour = utc_time.hour

        start = settings.low_liquidity_block_start_utc
        end = settings.low_liquidity_block_end_utc

        if start <= end:
            return start <= hour < end
        return hour >= start or hour < end

    def should_trade(self, current_time: datetime) -> tuple[bool, str]:
        """Decide whether trading should proceed given low-liquidity periods."""
        if not settings.low_liquidity_filter_enabled:
            logger.info("LowLiquidityFilter: disabled")
            return True, "low_liquidity_disabled"

        if not self.is_low_liquidity(current_time):
            logger.info("LowLiquidityFilter: trading window is liquid")
            return True, "liquidity_ok"

        if settings.low_liquidity_allow_trading:
            if settings.low_liquidity_reduce_risk:
                logger.info("LowLiquidityFilter: low liquidity, reduce risk")
                return True, "low_liquidity_reduce_risk"
            logger.info("LowLiquidityFilter: low liquidity, trading allowed by override")
            return True, "low_liquidity_override"

        logger.info("LowLiquidityFilter: blocked due to low liquidity")
        return False, "low_liquidity_blocked"

    def get_risk_multiplier(self, current_time: datetime) -> float:
        """Return risk multiplier for low liquidity windows."""
        if not settings.low_liquidity_filter_enabled:
            return 1.0
        if not self.is_low_liquidity(current_time):
            return 1.0
        if settings.low_liquidity_allow_trading and settings.low_liquidity_reduce_risk:
            return 0.5
        if settings.low_liquidity_allow_trading:
            return 1.0
        return 0.0
