from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import pytz

from config import settings
from filter.liquidity_filter import LowLiquidityFilter
from filter.news_filter import NewsFilter
from filter.weekend_filter import WeekendFilter

logger = logging.getLogger(__name__)


class TradingFilter:
    """Combined filter that prevents trading during unsafe periods."""

    def __init__(
        self,
        news_filter: NewsFilter,
        weekend_filter: WeekendFilter,
        liquidity_filter: LowLiquidityFilter | None = None,
    ) -> None:
        self.news_filter = news_filter
        self.weekend_filter = weekend_filter
        self.liquidity_filter = liquidity_filter or LowLiquidityFilter()

    def should_trade(self, current_time: datetime) -> dict[str, Any]:
        """Return combined trading permission, risk multiplier, and reason."""
        utc_time = current_time.astimezone(pytz.UTC)
        result: dict[str, Any] = {
            "trade": True,
            "risk_multiplier": 1.0,
            "reason": "ready",
            "checks_passed": 0,
            "details": {
                "weekend": False,
                "market_open": False,
                "news": {},
            },
        }

        weekend = self.weekend_filter.is_weekend(utc_time)
        result["details"]["weekend"] = weekend
        if weekend and not settings.weekend_allow_trading:
            result.update(
                {
                    "trade": False,
                    "risk_multiplier": 0.0,
                    "reason": "weekend_trading_blocked",
                    "checks_passed": 0,
                }
            )
            logger.info("TradingFilter: Blocked due to weekend")
            return result

        market_open, market_reason = self.weekend_filter.is_market_open(utc_time)
        result["details"]["market_open"] = market_open
        if not market_open:
            result.update(
                {
                    "trade": False,
                    "risk_multiplier": 0.0,
                    "reason": market_reason,
                    "checks_passed": 1 if not weekend else 0,
                }
            )
            logger.info("TradingFilter: Blocked due to market hours (%s)", market_reason)
            return result

        news_reason = "news_filter_disabled"
        if settings.news_filter_enabled:
            result["checks_passed"] += 1
            news_trade, news_reason = self.news_filter.should_trade(utc_time)
            news_result = self.news_filter.is_high_impact_news(utc_time, settings.news_lookahead_minutes)
            result["details"]["news"] = news_result

            if not news_trade:
                result.update(
                    {
                        "trade": False,
                        "risk_multiplier": 0.0,
                        "reason": news_reason,
                        "checks_passed": 2,
                    }
                )
                logger.info("TradingFilter: Blocked due to news (%s)", news_reason)
                return result
        else:
            result["details"]["news"] = {
                "halt": False,
                "reason": "news_filter_disabled",
                "impact": None,
                "event_name": "",
                "minutes_until": -1,
            }

        result["checks_passed"] += 1
        liquidity_trade, liquidity_reason = self.liquidity_filter.should_trade(utc_time)
        liquidity_multiplier = self.liquidity_filter.get_risk_multiplier(utc_time)
        result["details"]["liquidity"] = {
            "trade": liquidity_trade,
            "reason": liquidity_reason,
            "risk_multiplier": liquidity_multiplier,
        }

        if not liquidity_trade:
            result.update(
                {
                    "trade": False,
                    "risk_multiplier": 0.0,
                    "reason": liquidity_reason,
                    "checks_passed": 3,
                }
            )
            logger.info("TradingFilter: Blocked due to liquidity (%s)", liquidity_reason)
            return result

        result["risk_multiplier"] = min(
            self.news_filter.get_risk_multiplier(utc_time) if settings.news_filter_enabled else 1.0,
            liquidity_multiplier,
        )
        result["reason"] = (
            f"{news_reason}; {liquidity_reason}" if settings.news_filter_enabled else liquidity_reason
        )
        result["checks_passed"] = 3
        logger.info(
            "TradingFilter: Trading allowed with risk multiplier %.2f (%s)",
            result["risk_multiplier"],
            result["reason"],
        )
        return result
