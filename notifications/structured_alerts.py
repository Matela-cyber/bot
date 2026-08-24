"""Consistent, rate-limited Telegram alerts for critical bot events."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from notifications.telegram_sender import TelegramSender

logger = logging.getLogger(__name__)


class StructuredAlerts:
    """Format and rate-limit operational Telegram alerts."""

    def __init__(self, telegram_sender: TelegramSender) -> None:
        self.telegram = telegram_sender
        self._last_alert_time: dict[str, datetime] = {}
        self._cooldowns = {
            "rejected_signal": 60,
            "error": 300,
            "status": 3600,
            "session_change": 1800,
        }

    def _can_send(self, alert_type: str) -> bool:
        last = self._last_alert_time.get(alert_type)
        cooldown = self._cooldowns.get(alert_type)
        if last is None or cooldown is None:
            return True
        return (datetime.now(timezone.utc) - last).total_seconds() >= cooldown

    def _format_alert(self, emoji: str, title: str, fields: dict[str, Any], action: str = "") -> str:
        lines = [
            f"{emoji} {title}",
            "===========================",
            f"Time: {datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S} UTC",
        ]
        for key, value in fields.items():
            if value is not None:
                lines.append(f"{key}: {value}")
        if action:
            lines.append(f"Action: {action}")
        return "\n".join(lines)

    def _send(self, alert_type: str, message: str) -> bool:
        if not self._can_send(alert_type):
            return False
        sent = self.telegram.send(message)
        if sent:
            self._last_alert_time[alert_type] = datetime.now(timezone.utc)
        return sent

    def send_bot_started(self, config_summary: dict[str, Any]) -> bool:
        return self._send("startup", self._format_alert("[START]", "BOT STARTED", {
            "Balance": f"${float(config_summary.get('balance', 0)):.2f}",
            "Pairs": config_summary.get("pairs", 0),
            "Max Positions": config_summary.get("max_positions", 0),
            "Min Score": config_summary.get("min_score", 0),
            "Version": config_summary.get("version", "v2.0"),
        }, "Ready for trading"))

    def send_health_check(self, health: dict[str, Any]) -> bool:
        return self._send("status", self._format_alert("[HEALTH]", "HEALTH CHECK", {
            "Status": "OK" if health.get("healthy") else "FAILED",
            "MT5": "Connected" if health.get("mt5_ok") else "Failed",
            "Database": "OK" if health.get("db_ok") else "Failed",
            "Data Feed": f"{health.get('candles', 0)} candles",
            "Open Positions": health.get("positions", 0),
            "Error": health.get("error"),
        }))

    def send_signal_detected(self, symbol: str, signal: dict[str, Any]) -> bool:
        return self._send("signal", self._format_alert("[SIGNAL]", "SIGNAL DETECTED", {
            "Symbol": symbol,
            "Direction": str(signal.get("direction", signal.get("signal", "unknown"))).upper(),
            "Score": f"{signal.get('score', 0)}/100",
            "Grade": signal.get("grade"),
            "Pattern": signal.get("pattern", signal.get("pattern_name", "Unknown")),
            "Regime": signal.get("regime"),
        }, "Evaluating"))

    def send_signal_rejected(self, symbol: str, score: float, reason: str) -> bool:
        return self._send("rejected_signal", self._format_alert("[REJECT]", "SIGNAL REJECTED", {
            "Symbol": symbol, "Score": f"{score}/100", "Reason": reason,
        }, "No trade executed"))

    def send_order_placed(self, result: dict[str, Any]) -> bool:
        return self._send("trade", self._format_alert("[ORDER]", "ORDER PLACED", {
            "Symbol": result.get("symbol"), "Direction": str(result.get("direction", "")).upper(),
            "Ticket": result.get("ticket"), "Entry": result.get("entry_price"),
            "SL": result.get("stop_loss"), "TP": result.get("take_profit"),
            "Size": result.get("volume"), "Status": result.get("status"),
        }, "Monitoring position"))

    def send_position_entry(self, position: dict[str, Any]) -> bool:
        return self._send("trade", self._format_alert("[ENTRY]", "POSITION OPENED", {
            "Symbol": position.get("symbol"), "Direction": str(position.get("direction", "")).upper(),
            "Ticket": position.get("ticket"), "Entry": position.get("entry_price"),
            "Size": position.get("volume"), "Risk": position.get("risk_amount"),
        }, "Active"))

    def send_position_exit(self, position: dict[str, Any], reason: str) -> bool:
        pnl = float(position.get("pnl", 0.0) or 0.0)
        return self._send("trade", self._format_alert("[EXIT]", "POSITION CLOSED", {
            "Symbol": position.get("symbol"), "Ticket": position.get("ticket"),
            "P&L": f"${pnl:.2f}", "Reason": reason,
        }, "Done"))

    def send_sl_moved(self, position: dict[str, Any], new_sl: float, reason: str) -> bool:
        return self._send("position", self._format_alert("[SL]", "STOP LOSS MOVED", {
            "Symbol": position.get("symbol"), "Ticket": position.get("ticket"),
            "New SL": new_sl, "Reason": reason,
        }, "Protecting position"))

    def send_session_change(self, new_session: str, old_session: str | None, risk: float, max_positions: int) -> bool:
        return self._send("session_change", self._format_alert("[SESSION]", "SESSION CHANGE", {
            "From": old_session or "START", "To": new_session.upper(),
            "Risk": f"{risk * 100:.0f}%", "Max Positions": max_positions,
        }, "Parameters adjusted"))

    def send_volatility(self, symbol: str, level: str, reason: str, risk_multiplier: float) -> bool:
        return self._send("volatility", self._format_alert("[VOLATILITY]", "VOLATILITY EVENT", {
            "Symbol": symbol, "Level": level.upper(), "Risk": f"{risk_multiplier * 100:.0f}%", "Details": reason,
        }, "Trading paused" if risk_multiplier == 0 else "Risk reduced"))

    def send_friday_cutoff(self) -> bool:
        return self._send("time", self._format_alert("[TIME]", "FRIDAY CUTOFF", {
            "Status": "No new trades", "Close": "Bot positions close at Saturday 00:00 local",
        }, "Preparing for weekend"))

    def send_error(self, error_type: str, message: str, context: dict[str, Any] | None = None) -> bool:
        fields: dict[str, Any] = {"Type": error_type, "Error": message[:300]}
        if context:
            fields.update(context)
        return self._send("error", self._format_alert("[ERROR]", "SYSTEM ERROR", fields, "Investigate immediately"))
