from __future__ import annotations

from datetime import datetime

from config import LOCAL_TIMEZONE
from core.session_manager import SessionManager
from position.position_manager import PositionManager


def local(hour: int, minute: int = 0) -> datetime:
    return LOCAL_TIMEZONE.localize(datetime(2026, 8, 24, hour, minute))


def test_session_boundaries_and_overlap() -> None:
    manager = SessionManager()

    assert manager.get_session(local(7))["name"] == "asia"
    assert manager.get_session(local(9))["name"] == "day"
    assert manager.get_session(local(12, 59))["name"] == "london"
    assert manager.get_session(local(15))["name"] == "overlap"
    assert manager.get_session(local(18))["name"] == "newyork"
    assert manager.get_session(local(22))["name"] == "off_hours"
    assert manager.get_session(local(23))["name"] == "off_hours"


def test_session_risk_and_position_profiles() -> None:
    manager = SessionManager()

    london = manager.get_session(local(10))
    overlap = manager.get_session(local(16))
    asia = manager.get_session(local(1))

    assert london["risk_multiplier"] == 1.0
    assert london["max_positions"] == 5
    assert overlap["risk_multiplier"] == 1.2
    assert overlap["sl_multiplier"] == 2.0
    assert asia["risk_multiplier"] == 0.5
    assert asia["trailing_enabled"] is False


def test_off_hours_block_new_entries_and_weekend() -> None:
    manager = SessionManager()

    allowed, reason = manager.should_trade(local(3))
    assert allowed is False
    assert "night spread window" in reason

    allowed, _ = manager.should_trade(local(21))
    assert allowed is True

    sunday = LOCAL_TIMEZONE.localize(datetime(2026, 8, 23, 12))
    allowed, _ = manager.should_trade(sunday)
    assert allowed is False


def test_spread_risk_time_windows() -> None:
    manager = SessionManager()

    assert manager.get_spread_risk(local(3)) == 0.0
    assert manager.get_spread_risk(local(6)) == 0.25
    assert manager.get_spread_risk(local(8)) == 0.50
    assert manager.get_spread_risk(local(10)) == 1.0
    assert manager.get_spread_risk(local(21)) == 1.0


def test_position_manager_respects_session_trailing_flag() -> None:
    manager = PositionManager()
    position: dict[str, object] = {
        "direction": "buy",
        "entry_price": 1.1000,
        "stop_loss": 1.0900,
        "take_profit": 1.1300,
        "current_price": 1.1250,
        "trailing_enabled": False,
    }

    result = manager.manage(position)

    assert result["action"] != "trail"
