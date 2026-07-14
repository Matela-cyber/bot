from __future__ import annotations

from datetime import date
from uuid import uuid4
import time
from typing import Any

from config import settings
from data.ingestor import fetch_local_ohlcv
from data.preprocessor import prepare_ohlcv
from db.repository import Repository
from execution.mt5_client import MT5Client
from execution.paper_trader import PaperTradeSimulator
from falcon.engine import FalconEngine
from risk.manager import RiskManager
from structure.patterns import detect_patterns
from structure.swing_detector import detect_swings
from utils.logger import get_logger

logger = get_logger("main")
repository = Repository(settings.database_url)
mt5_client = MT5Client(settings.mt5_account, settings.mt5_password, settings.mt5_server)


def select_best_pattern(patterns: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Select the highest-confidence pattern from the current cycle."""
    if not patterns:
        return None
    return max(patterns, key=lambda item: item.get("confidence", 0.0))


def is_trade_entry_confident(pattern: dict[str, Any], trade_plan: dict[str, Any], threshold: float) -> bool:
    """Require both pattern confidence and trade plan quality to exceed the minimum threshold."""
    pattern_confidence = float(pattern.get("confidence", 0.0))
    plan_quality = float(trade_plan.get("quality", 0.0))
    return pattern_confidence >= threshold and plan_quality >= threshold


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

    data = fetch_local_ohlcv(days=90)
    frame = prepare_ohlcv(data)
    swings = detect_swings(frame)
    patterns = detect_patterns(frame, swings)

    if not patterns:
        logger.info("No patterns detected")
        return

    best_pattern = select_best_pattern(patterns)
    if best_pattern is None:
        logger.info("No patterns detected")
        return

    logger.info("Detected %s pattern(s)", len(patterns))
    logger.info(
        "Best pattern: %s | confidence: %.2f",
        best_pattern.get("pattern_name"),
        best_pattern.get("confidence", 0.0),
    )

    engine = FalconEngine()
    trade_plan = engine.generate_trade_plan(frame, best_pattern)

    current_balance = float(settings.account_balance)
    if not is_trade_entry_confident(best_pattern, trade_plan, settings.min_entry_confidence):
        trade_plan.setdefault("position_size", 0.0)
        logger.warning(
            "Signal below minimum entry confidence %.2f; skipping execution.",
            settings.min_entry_confidence,
        )
        execution_result = _build_execution_result(frame, trade_plan, "low_confidence", "none")

        repository.add_pattern_event(
            {
                "timestamp": frame.index[-1].to_pydatetime(),
                "timeframe": "15m",
                "pattern_name": best_pattern.get("pattern_name"),
                "breakout_level": best_pattern.get("breakout_level"),
                "stop_loss_zone": best_pattern.get("stop_loss_zone"),
                "confidence": best_pattern.get("confidence", 0.0),
                "candlestick_bonus": best_pattern.get("candlestick_bonus", False),
                "final_score": trade_plan.get("quality", 0.0),
                "executed": False,
                "result": execution_result["exit_reason"],
            }
        )

        trade_payload: dict[str, Any] = {
            "trade_id": execution_result["trade_id"],
            "entry_time": frame.index[-1].to_pydatetime(),
            "exit_time": execution_result["exit_time"],
            "direction": trade_plan["direction"],
            "entry_price": trade_plan["entry_price"],
            "stop_loss": trade_plan["stop_loss"],
            "take_profit": trade_plan["take_profit"],
            "exit_price": execution_result["exit_price"],
            "pnl_pips": execution_result["pnl_pips"],
            "pnl_amount": execution_result["pnl_amount"],
            "pnl_percentage": execution_result["pnl_percentage"],
            "position_size": trade_plan["position_size"],
            "exit_reason": execution_result["exit_reason"],
            "rl_action_taken": execution_result["rl_action_taken"],
            "reward": execution_result["reward"],
        }

        repository.add_trade(trade_payload)
        repository.upsert_daily_stat(
            {
                "date": date.today().isoformat(),
                "start_balance": current_balance,
                "end_balance": current_balance + execution_result.get("pnl_amount", 0.0),
                "daily_pnl": execution_result.get("pnl_amount", 0.0),
                "drawdown_peak": 0.0,
                "drawdown_percent": 0.0,
                "halt_triggered": False,
            }
        )
        return

    mt5_live = False
    if settings.use_mt5_execution and mt5_client.is_configured():
        try:
            mt5_client.connect()
            current_balance = mt5_client.get_balance()
            mt5_live = True
            logger.info("Using live MT5 account balance: %s", current_balance)
        except Exception as exc:  # pragma: no cover - runtime integration path
            logger.exception("Failed to fetch live MT5 balance: %s", exc)
            logger.warning("Falling back to configured account balance for risk calculation")
    elif settings.use_mt5_execution:
        logger.warning("MT5 execution requested but MT5 is not configured; using configured account balance for risk calculation")

    risk_manager = RiskManager(account_balance=current_balance)
    assessment = risk_manager.assess_trade(trade_plan)
    trade_plan["position_size"] = round(assessment.position_size, 4)

    risk_amount = current_balance * settings.risk_per_trade
    risk_percentage = (risk_amount / current_balance) * 100 if current_balance > 0 else 0.0
    logger.info("Risk: $%.2f (%.2f%% of $%.2f)", risk_amount, risk_percentage, current_balance)

    execution_result: dict[str, Any]
    if not assessment.allowed:
        logger.warning("Trade plan exceeds risk limits; skipping execution. Reason: %s", assessment.reason)
        execution_result = _build_execution_result(frame, trade_plan, "risk_skipped", "none")
    else:
        logger.info("Trade plan ready: %s", trade_plan)
        if settings.use_mt5_execution:
            if mt5_live:
                try:
                    order_type = "buy" if trade_plan["direction"] == "bull" else "sell"
                    analysis_comment = (
                        f"{trade_plan['pattern_name'][:7]} {trade_plan['direction'][0].upper()} "
                        f"E{trade_plan['entry_price']:.4f} SL{trade_plan['stop_loss']:.4f}"
                    )
                    logger.info(
                        "MT5 thought process: pattern=%s direction=%s entry=%.5f sl=%.5f tp=%.5f",
                        trade_plan["pattern_name"],
                        trade_plan["direction"],
                        trade_plan["entry_price"],
                        trade_plan["stop_loss"],
                        trade_plan["take_profit"],
                    )
                    mt5_client.draw_analysis("EURUSD", trade_plan)
                    order_result = mt5_client.place_order(
                        symbol="EURUSD",
                        order_type=order_type,
                        lots=max(0.01, round(assessment.position_size / 100000.0, 2)),
                        stop_loss=trade_plan["stop_loss"],
                        take_profit=trade_plan["take_profit"],
                        reference_entry_price=trade_plan["entry_price"],
                        comment=analysis_comment,
                    )
                    execution_result = _build_execution_result(
                        frame,
                        trade_plan,
                        "mt5_order_sent",
                        "mt5_execution",
                        exit_price=order_result.get("entry_price", trade_plan["entry_price"]),
                    )
                    execution_result["trade_id"] = order_result.get("order_id", execution_result["trade_id"])
                except Exception as exc:  # pragma: no cover - runtime integration path
                    logger.exception("MT5 execution failed: %s", exc)
                    execution_result = _build_execution_result(frame, trade_plan, "mt5_failed", "none")
                finally:
                    mt5_client.disconnect()
            else:
                logger.error("MT5 execution requested but MT5 live balance was unavailable; aborting live execution and not falling back.")
                execution_result = _build_execution_result(frame, trade_plan, "mt5_unavailable", "none")
        elif settings.use_paper_trading:
            logger.info("No MT5 requested; using paper trading mode")
            simulator = PaperTradeSimulator()
            execution_result = simulator.execute_trade(frame, trade_plan)
        else:
            logger.error("No execution mode available; skipping trade.")
            execution_result = _build_execution_result(frame, trade_plan, "no_execution_mode", "none")

    repository.add_pattern_event(
        {
            "timestamp": frame.index[-1].to_pydatetime(),
            "timeframe": "15m",
            "pattern_name": best_pattern.get("pattern_name"),
            "breakout_level": best_pattern.get("breakout_level"),
            "stop_loss_zone": best_pattern.get("stop_loss_zone"),
            "confidence": best_pattern.get("confidence", 0.0),
            "candlestick_bonus": best_pattern.get("candlestick_bonus", False),
            "final_score": trade_plan.get("quality", 0.0),
            "executed": assessment.allowed,
            "result": execution_result["exit_reason"],
        }
    )

    trade_payload: dict[str, Any] = {
        "trade_id": execution_result["trade_id"],
        "entry_time": frame.index[-1].to_pydatetime(),
        "exit_time": execution_result["exit_time"],
        "direction": trade_plan["direction"],
        "entry_price": trade_plan["entry_price"],
        "stop_loss": trade_plan["stop_loss"],
        "take_profit": trade_plan["take_profit"],
        "exit_price": execution_result["exit_price"],
        "pnl_pips": execution_result["pnl_pips"],
        "pnl_amount": execution_result["pnl_amount"],
        "pnl_percentage": execution_result["pnl_percentage"],
        "position_size": trade_plan["position_size"],
        "exit_reason": execution_result["exit_reason"],
        "rl_action_taken": execution_result["rl_action_taken"],
        "reward": execution_result["reward"],
    }

    repository.add_trade(trade_payload)
    repository.upsert_daily_stat(
        {
            "date": date.today().isoformat(),
            "start_balance": current_balance,
            "end_balance": current_balance + execution_result.get("pnl_amount", 0.0),
            "daily_pnl": execution_result.get("pnl_amount", 0.0),
            "drawdown_peak": 0.0,
            "drawdown_percent": 0.0,
            "halt_triggered": False,
        }
    )


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
