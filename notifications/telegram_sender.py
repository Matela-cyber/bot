from __future__ import annotations

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
        direction_emoji = "🚀" if trade_plan.get("direction") == "bull" else "🔻"
        message = (
            f"*Trade Alert*\n"
            f"Pattern: `{trade_plan.get('pattern_name')}`\n"
            f"Direction: {direction_emoji} {trade_plan.get('direction', 'neutral').title()}\n"
            f"Quality: {trade_plan.get('quality', 0.0):.2f}\n"
            f"Position Size: {trade_plan.get('position_size', 0.0):.4f}\n"
            f"Entry: {trade_plan.get('entry_price', 0.0):.5f}\n"
            f"Stop Loss: {trade_plan.get('stop_loss', 0.0):.5f}\n"
            f"Take Profit: {trade_plan.get('take_profit', 0.0):.5f}\n"
            f"Result: `{execution_result.get('exit_reason')}`\n"
            f"Status: `{trade_plan.get('status', 'unknown')}`\n"
        )
        return message
