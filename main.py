from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal, TypedDict, cast
from uuid import uuid4
import time

import pytz

from config import settings
from core.portfolio_manager import PortfolioManager
from data.ingestor import fetch_mt5_ohlcv
from data.preprocessor import prepare_ohlcv
from execution.mt5_client import MT5Client
from filter.liquidity_filter import LowLiquidityFilter
from filter.news_filter import NewsFilter
from filter.trading_filter import TradingFilter
from filter.weekend_filter import WeekendFilter
from structure.swing_detector import detect_swings
from strategic.decision_engine import StrategicDecisionEngine
from utils.logger import get_logger

logger = get_logger("main")
mt5_client = MT5Client(settings.mt5_account, settings.mt5_password, settings.mt5_server)
news_filter = NewsFilter()
weekend_filter = WeekendFilter()
liquidity_filter = LowLiquidityFilter()
trading_filter = TradingFilter(news_filter, weekend_filter, liquidity_filter)
portfolio_manager = PortfolioManager({"TRADING_PAIRS": settings.trading_pairs})


class TradePlan(TypedDict):
    symbol: str
    pattern_name: str
    direction: str
    entry_price: float
    stop_loss: float
    take_profit: float
    position_size: float
    risk_amount: float
    falcon_score: float
    quality: float
    confluence_score: float
    smc_data: dict[str, Any]


class TradePlanWithExtras(TradePlan, total=False):
    falcon_scores: dict[str, Any]


ActionType = Literal["SKIP", "HOLD", "WAIT", "EXECUTE"]


class BaseDecision(TypedDict):
    action: ActionType
    reason: str
    cycles_passed: int


class ExecuteDecision(TypedDict):
    action: Literal["EXECUTE"]
    reason: str
    cycles_passed: int
    pattern: dict[str, Any]
    smc_data: dict[str, Any]
    confluence: float
    trade_plan: TradePlan


class DecisionResult(BaseDecision, total=False):
    pattern: dict[str, Any]
    smc_data: dict[str, Any]
    confluence: float
    trade_plan: TradePlan


def select_best_pattern(patterns: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Select the highest-confidence pattern from the current cycle."""
    if not patterns:
        return None
    return max(patterns, key=lambda item: item.get("confidence", 0.0))


def _build_execution_result(frame: Any, trade_plan: dict[str, Any], reason: str, rl_action_taken: str, exit_price: float | None = None) -> dict[str, Any]:
    return {
        "trade_id": f"trade-{frame.index[-1].strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:8]}",
        "exit_time": frame.index[-1].to_pydatetime(),
        "exit_price": exit_price if exit_price is not None else trade_plan["entry_price"],
        "pnl_pips": 0,
        "pnl_amount": 0.0,
        "pnl_percentage": 0.0,
        "exit_reason": reason,
        "rl_action_taken": rl_action_taken,
        "reward": 0.0,
    }


def run_cycle() -> None:
    """Run one analysis cycle, persist results, and safely route execution."""
    logger.info("Starting bot cycle")

    if settings.use_mt5_execution:
        try:
            mt5_client.connect()
            open_positions = mt5_client.get_open_positions()
            if open_positions:
                logger.info("Monitoring %s open position(s)", len(open_positions))
                for pos in open_positions:
                    pnl_str = f"+${pos['pnl']:.2f}" if pos["pnl"] > 0 else f"-${abs(pos['pnl']):.2f}"
                    logger.info(
                        "   %s %s | Price: %.5f | PnL: %s (%.2f%%)",
                        pos["symbol"],
                        pos["type"].upper(),
                        pos["current_price"],
                        pnl_str,
                        pos["pnl_percent"],
                    )
            mt5_client.disconnect()
        except Exception as exc:  # pragma: no cover - runtime integration path
            logger.warning("Position monitoring failed: %s", exc)

    if settings.use_mt5_execution and mt5_client.is_configured():
        try:
            data = fetch_mt5_ohlcv(days=90, timeframe="15m")
            logger.info("Fetched live 15m OHLCV from MT5")
        except Exception as exc:  # pragma: no cover - runtime integration path
            logger.warning("MT5 OHLCV fetch failed: %s", exc)
            return
    else:
        logger.warning("MT5 execution requested but MT5 is not configured; aborting cycle")
        return

    current_time = datetime.now(pytz.UTC)
    filter_result = trading_filter.should_trade(current_time)
    if not filter_result["trade"]:
        logger.info("Trading blocked: %s", filter_result["reason"])
        return

    if filter_result["risk_multiplier"] < 1.0:
        logger.info(
            "Risk multiplier reduced to %.0f%% due to safety filters: %s",
            filter_result["risk_multiplier"] * 100,
            filter_result["reason"],
        )

    if not portfolio_manager.check_global_limits()[0]:
        logger.warning("Global limit hit: %s", portfolio_manager.check_global_limits()[1])
        return

    decision_engine = StrategicDecisionEngine()

    for symbol in settings.trading_pairs:
        pair_state = portfolio_manager.get_pair_state(symbol)
        if pair_state.consecutive_losses >= 3:
            logger.debug("%s: Skipping, 3 consecutive losses", symbol)
            continue

        try:
            if settings.use_mt5_execution and mt5_client.is_configured():
                data = fetch_mt5_ohlcv(days=90, timeframe=settings.pair_timeframes.get(symbol, "15m"), symbol=symbol)
            else:
                logger.warning("%s: MT5 execution not configured for symbol, skipping", symbol)
                continue

            frame = prepare_ohlcv(data)
            if frame.empty:
                logger.warning("%s: No data fetched", symbol)
                continue

            swings = detect_swings(frame)
            if not swings.get("highs") or not swings.get("lows"):
                logger.info("%s: No usable swing structure", symbol)
                continue

            decision = cast(
                DecisionResult,
                decision_engine.think(
                    frame,
                    swings,
                    mt5_client,
                    symbol,
                    risk_multiplier=filter_result["risk_multiplier"],
                ),
            )
            action: ActionType = decision["action"]
            reason = decision["reason"]
            logger.info("%s: Decision engine action=%s reason=%s cycles=%s", symbol, action, reason, decision["cycles_passed"])

            if action == "EXECUTE":
                execute_decision = cast(ExecuteDecision, decision)
                trade_plan: TradePlan = execute_decision["trade_plan"]
                trade_plan["position_size"] = round(float(trade_plan.get("position_size", 0.0)), 4)
                trade_plan["risk_amount"] = float(trade_plan.get("risk_amount", 0.0) or 0.0)

                can_open, can_open_reason = portfolio_manager.can_open_position(
                    symbol,
                    trade_plan["direction"],
                    trade_plan["risk_amount"],
                )
                if not can_open:
                    logger.warning("%s: %s", symbol, can_open_reason)
                    continue

                logger.info(
                    "%s: Trade executed - %s | %s | size=%.4f | risk=%.2f",
                    symbol,
                    trade_plan.get("pattern_name"),
                    trade_plan.get("direction"),
                    trade_plan["position_size"],
                    trade_plan["risk_amount"],
                )
                pair_state.add_trade({
                    "symbol": symbol,
                    "pnl_amount": 0.0,
                    "position_size": trade_plan["position_size"],
                    "entry_price": trade_plan["entry_price"],
                    "stop_loss": trade_plan["stop_loss"],
                    "risk_amount": trade_plan["risk_amount"],
                })
                portfolio_manager.total_open_positions += 1
            else:
                logger.info("%s: Decision engine returned %s", symbol, action)
        except Exception as exc:
            logger.exception("%s: Error: %s", symbol, exc)
            continue

    summary = portfolio_manager.get_summary()
    logger.info("Portfolio summary: %s positions, Daily PnL: $%.2f", summary["total_positions"], summary["global_daily_pnl"])


def main() -> None:
    logger.info("Bot started on localhost")
    while True:
        try:
            run_cycle()
            time.sleep(settings.loop_interval_seconds)
        except KeyboardInterrupt:
            logger.info("Bot stopped by user")
            break


if __name__ == "__main__":
    main()
