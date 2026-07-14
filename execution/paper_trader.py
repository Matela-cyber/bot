from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd


class PaperTradeSimulator:
    """Simulates a trade exit for paper trading based on recent trend and risk limits."""

    def execute_trade(self, frame: pd.DataFrame, trade_plan: dict[str, Any]) -> dict[str, Any]:
        entry_price = float(trade_plan["entry_price"])
        stop_loss = float(trade_plan["stop_loss"])
        take_profit = float(trade_plan["take_profit"])
        direction = trade_plan.get("direction", "neutral")

        exit_data = self._simulate_exit(frame, direction, entry_price, stop_loss, take_profit)
        exit_price = exit_data["exit_price"]
        price_diff = exit_price - entry_price
        if direction == "bear":
            price_diff = entry_price - exit_price

        position_size = float(trade_plan.get("position_size", 0.0))
        pnl_amount = price_diff * position_size
        notional = entry_price * position_size if entry_price and position_size else 1.0
        pnl_percentage = round(100.0 * pnl_amount / notional, 4) if notional else 0.0
        pnl_pips = int(round(price_diff * 10000))

        return {
            "trade_id": f"trade-{datetime.now(timezone.utc):%Y%m%d%H%M%S}",
            "exit_time": datetime.now(timezone.utc),
            "exit_price": exit_price,
            "pnl_pips": pnl_pips,
            "pnl_amount": pnl_amount,
            "pnl_percentage": pnl_percentage,
            "exit_reason": exit_data["reason"],
            "rl_action_taken": "paper_execution",
            "reward": round(pnl_amount / 1000.0, 4),
        }

    def _simulate_exit(
        self,
        frame: pd.DataFrame,
        direction: str,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
    ) -> dict[str, Any]:
        recent = frame["close"].pct_change().dropna().tail(10)
        momentum = float(recent.sum()) if not recent.empty else 0.0

        if direction == "bull":
            if momentum >= 0.0:
                return {"exit_price": take_profit, "reason": "take_profit"}
            return {"exit_price": stop_loss, "reason": "stop_loss"}

        if direction == "bear":
            if momentum <= 0.0:
                return {"exit_price": take_profit, "reason": "take_profit"}
            return {"exit_price": stop_loss, "reason": "stop_loss"}

        return {"exit_price": entry_price, "reason": "neutral"}
