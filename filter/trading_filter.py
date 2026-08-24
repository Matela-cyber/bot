from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Protocol

import pytz

from config import settings
from filter.liquidity_filter import LowLiquidityFilter
from filter.weekend_filter import WeekendFilter

logger = logging.getLogger(__name__)


class VolatilitySource(Protocol):
    """Interface required by TradingFilter for volatility gating."""

    def should_trade(self, symbol: str) -> tuple[bool, str, float]:
        """Return entry permission, reason, and risk multiplier."""
        ...


class TradingFilter:
    """Combined filter that prevents trading during unsafe periods."""

    def __init__(
        self,
        volatility_detector: VolatilitySource,
        weekend_filter: WeekendFilter,
        liquidity_filter: LowLiquidityFilter | None = None,
    ) -> None:
        self.volatility_detector = volatility_detector
        self.weekend_filter = weekend_filter
        self.liquidity_filter = liquidity_filter or LowLiquidityFilter()

    def should_trade(self, current_time: datetime, symbol: str | None = None) -> dict[str, Any]:
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
                "volatility": {},
            },
        }

        weekend = self.weekend_filter.is_weekend(utc_time)
        result["details"]["weekend"] = weekend
        weekend_allowed, weekend_reason = self.weekend_filter.should_trade(
            utc_time)
        if not weekend_allowed:
            result.update({
                "trade": False,
                "risk_multiplier": 0.0,
                "reason": weekend_reason,
                "checks_passed": 0,
            })
            logger.info(
                "TradingFilter: Blocked by weekend schedule (%s)", weekend_reason)
            return result

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

        market_open, market_reason = self.weekend_filter.is_market_open(
            utc_time)
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
            logger.info(
                "TradingFilter: Blocked due to market hours (%s)", market_reason)
            return result

        volatility_reason = "volatility_check_deferred"
        volatility_multiplier = 1.0
        if symbol is not None:
            volatility_trade, volatility_reason, volatility_multiplier = self.volatility_detector.should_trade(
                symbol)
            result["details"]["volatility"] = {
                "trade": volatility_trade,
                "reason": volatility_reason,
                "risk_multiplier": volatility_multiplier,
            }
            if not volatility_trade:
                result.update(
                    {
                        "trade": False,
                        "risk_multiplier": 0.0,
                        "reason": volatility_reason,
                        "checks_passed": 2,
                    }
                )
                logger.info(
                    "TradingFilter: Blocked by volatility (%s)", volatility_reason)
                return result
        else:
            result["details"]["volatility"] = {
                "trade": True, "reason": volatility_reason, "risk_multiplier": 1.0}

        result["checks_passed"] += 1
        liquidity_trade, liquidity_reason = self.liquidity_filter.should_trade(
            utc_time)
        liquidity_multiplier = self.liquidity_filter.get_risk_multiplier(
            utc_time)
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
            logger.info(
                "TradingFilter: Blocked due to liquidity (%s)", liquidity_reason)
            return result

        result["risk_multiplier"] = min(
            volatility_multiplier, liquidity_multiplier)
        result["reason"] = f"{volatility_reason}; {liquidity_reason}"
        result["checks_passed"] = 3
        logger.info(
            "TradingFilter: Trading allowed with risk multiplier %.2f (%s)",
            result["risk_multiplier"],
            result["reason"],
        )
        return result
