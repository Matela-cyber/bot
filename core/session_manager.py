"""Local-time trading-session profiles and entry permissions."""
from __future__ import annotations

from datetime import datetime, time
from typing import Any
from config import LOCAL_TIMEZONE


class SessionManager:
    """Provide session-specific risk, position, and management rules."""

    SESSIONS: dict[str, dict[str, Any]] = {
        "asia": {
            "start": time(0, 0),
            "end": time(8, 0),
            "risk_multiplier": 0.5,
            "max_positions": 3,
            "sl_multiplier": 0.75,
            "tp_multiplier": 0.75,
            "trailing_enabled": False,
            "description": "Asia (low volatility)",
        },
        "london": {
            "start": time(10, 0),
            "end": time(18, 0),
            "risk_multiplier": 1.0,
            "max_positions": 5,
            "sl_multiplier": 1.0,
            "tp_multiplier": 1.0,
            "trailing_enabled": True,
            "description": "London (high volatility)",
        },
        "newyork": {
            "start": time(15, 0),
            "end": time(22, 0),
            "risk_multiplier": 0.8,
            "max_positions": 4,
            "sl_multiplier": 1.0,
            "tp_multiplier": 1.0,
            "trailing_enabled": True,
            "description": "New York (high volatility)",
        },
        "overlap": {
            "start": time(15, 0),
            "end": time(18, 0),
            "risk_multiplier": 1.2,
            "max_positions": 5,
            "sl_multiplier": 2.0,
            "tp_multiplier": 2.0,
            "trailing_enabled": True,
            "description": "London-New York Overlap (extreme volatility)",
        },
        "off_hours": {
            "start": time(20, 0),
            "end": time(22, 0),
            "risk_multiplier": 0.0,
            "max_positions": 0,
            "sl_multiplier": 1.0,
            "tp_multiplier": 1.0,
            "trailing_enabled": False,
            "description": "Off-Hours (spread-adjusted)",
        },
        "day": {
            "start": time(8, 0),
            "end": time(22, 0),
            "risk_multiplier": 1.0,
            "max_positions": 5,
            "sl_multiplier": 1.0,
            "tp_multiplier": 1.0,
            "trailing_enabled": True,
            "description": "Day transition (normal conditions)",
        },
    }

    def get_session(self, current_time: datetime) -> dict[str, Any]:
        """Return the active local session, including its name."""
        local_time = current_time.astimezone(LOCAL_TIMEZONE)
        current = local_time.time()
        if local_time.weekday() >= 5:
            return self._get_session_data("off_hours")
        if time(15, 0) <= current < time(18, 0):
            return self._get_session_data("overlap")
        if time(8, 0) <= current < time(22, 0):
            for name in ("london", "newyork", "day"):
                profile = self.SESSIONS[name]
                if profile["start"] <= current < profile["end"]:
                    return self._get_session_data(name)
        for name in ("asia", "london", "newyork", "off_hours"):
            profile = self.SESSIONS[name]
            start = profile["start"]
            end = profile["end"]
            if start < end and start <= current < end:
                return self._get_session_data(name)
            if start > end and (current >= start or current < end):
                return self._get_session_data(name)
        return self._get_session_data("off_hours")

    def _get_session_data(self, session_name: str) -> dict[str, Any]:
        """Return a copy of a session profile with its name."""
        data = self.SESSIONS[session_name].copy()
        data["name"] = session_name
        return data

    def get_risk_multiplier(self, current_time: datetime) -> float:
        """Return the active session risk multiplier."""
        return float(self.get_session(current_time)["risk_multiplier"])

    def get_max_positions(self, current_time: datetime) -> int:
        """Return the active session position limit."""
        return int(self.get_session(current_time)["max_positions"])

    def should_trade(self, current_time: datetime) -> tuple[bool, str]:
        """Return whether new entries are allowed in the active session."""
        session = self.get_session(current_time)
        local_time = current_time.astimezone(LOCAL_TIMEZONE)
        if local_time.weekday() >= 5:
            return False, "Trading blocked: weekend"
        if local_time.hour >= 22:
            return False, "Trading blocked: off-hours (22:00-00:00 local)"
        spread_risk = self.get_spread_risk(current_time)
        if spread_risk <= 0:
            return False, "Trading blocked: night spread window (00:00-04:00 UTC)"
        return True, f"Trading allowed: {session['description']}"

    def get_spread_risk(self, current_time: datetime) -> float:
        """Return the time-of-day spread-risk multiplier in local time."""
        hour = current_time.astimezone(LOCAL_TIMEZONE).hour
        if 2 <= hour < 6:
            return 0.0
        if 6 <= hour < 8:
            return 0.25
        if 8 <= hour < 10:
            return 0.50
        return 1.0
