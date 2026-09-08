"""Telegram notification sender."""

import logging
from typing import Optional

import requests

logger = logging.getLogger(__name__)


class TelegramSender:
    def __init__(self, token: str, chat_id: str):
        self.token = token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{token}"
        self.enabled = bool(token and chat_id and token !=
                            "your_bot_token" and chat_id != "your_chat_id")

    def send_message(self, message: str, parse_mode: str = "HTML") -> bool:
        if not self.enabled:
            return False

        if len(message) > 4000:
            message = message[:3950] + "\n\n... (truncated)"

        try:
            url = f"{self.base_url}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": parse_mode
            }
            response = requests.post(url, json=payload, timeout=10)

            if response.status_code == 200:
                logger.info(f"Telegram message sent")
                return True
            else:
                logger.error(f"Telegram send failed: {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"Telegram send error: {e}")
            return False

    def send_trade_signal(self, signal_data: dict) -> bool:
        """Format and send a trade signal."""
        symbol = signal_data.get("symbol", "UNKNOWN")
        direction = signal_data.get("signal", "").upper()
        trade = signal_data.get("trade", {})
        entry = trade.get("entry", 0)
        stop_loss = trade.get("stop_loss", 0)
        take_profit = trade.get("take_profit", 0)
        confidence = signal_data.get("confidence", 0)
        size = signal_data.get("size", 0)
        strategy = signal_data.get("strategy", "mean_reversion")

        message = (
            f"📈 <b>{direction} {symbol}</b>\n"
            f"Entry: {entry:.5f}\n"
            f"SL: {stop_loss:.5f}\n"
            f"TP: {take_profit:.5f}\n"
            f"Size: {size:.2f} lots\n"
            f"Confidence: {confidence:.1f}%\n"
            f"Strategy: {strategy}"
        )
        return self.send_message(message)

    def send_error(self, error_message: str) -> bool:
        message = f"❌ <b>Error</b>\n{error_message[:500]}"
        return self.send_message(message)
