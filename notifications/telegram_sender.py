from __future__ import annotations

from datetime import datetime
from typing import Any

import requests


class TelegramSender:
    """Minimal Telegram alert sender with safety and diagnostics."""

    def __init__(self, token: str | None = None, chat_id: str | None = None) -> None:
        self.token = token
        self.chat_id = chat_id

    def send(self, message: str) -> bool:
        if not self.token or not self.chat_id:
            return False
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        try:
            response = requests.post(
                url,
                json={"chat_id": self.chat_id, "text": message},
                timeout=10,
            )
            response.raise_for_status()
            return True
        except requests.RequestException:
            return False

    def compose_trade_alert(self, trade_plan: dict[str, Any], execution_result: dict[str, Any]) -> str:
        symbol = trade_plan.get("symbol", "UNKNOWN")
        direction = trade_plan.get("direction", "neutral").title()
        direction_emoji = "🚀" if trade_plan.get("direction") == "bull" else "🔻"
        when = execution_result.get("exit_time")
        if isinstance(when, datetime):
            when = when.strftime("%Y-%m-%d %H:%M UTC")
        elif when is None:
            when = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

        message = (
            "Trade Alert\n"
            f"Symbol: {symbol}\n"
            f"When: {when}\n"
            f"Pattern: {trade_plan.get('pattern_name', 'unknown')}\n"
            f"Direction: {direction_emoji} {direction}\n"
            f"Entry: {trade_plan.get('entry_price', 0.0):.5f}\n"
            f"Stop Loss: {trade_plan.get('stop_loss', 0.0):.5f}\n"
            f"Take Profit: {trade_plan.get('take_profit', 0.0):.5f}\n"
            f"Position Size: {trade_plan.get('position_size', 0.0):.4f}\n"
            f"Risk Amount: ${trade_plan.get('risk_amount', 0.0):.2f}\n"
            f"Quality: {trade_plan.get('quality', 0.0):.2f}\n"
            f"Confluence Score: {trade_plan.get('confluence_score', 0.0):.2f}\n"
            f"Result: {execution_result.get('exit_reason', 'executed')}\n"
        )
        return message
