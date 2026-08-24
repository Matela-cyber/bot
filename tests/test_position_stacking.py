from __future__ import annotations

from datetime import datetime, timedelta, timezone

from core.pair_state import PairState
from core.portfolio_manager import PortfolioManager


def test_pair_state_tracks_best_score() -> None:
    state = PairState("EURUSD")
    state.add_position({"ticket": 1, "direction": "buy", "score": 72})
    state.add_position({"ticket": 2, "direction": "sell", "score": 81})

    assert state.current_best_score == 81
    state.remove_position(2)
    assert state.current_best_score == 72


def test_first_position_is_approved_at_quality_threshold() -> None:
    manager = PortfolioManager({"TRADING_PAIRS": ["EURUSD"]})

    approved, reason = manager.can_open_position("EURUSD", "buy", 72)

    assert approved is True
    assert reason == "Position approved"


def test_same_direction_stacking_is_allowed_when_score_improves() -> None:
    manager = PortfolioManager({"TRADING_PAIRS": ["EURUSD"]})
    manager.add_position_state(
        "EURUSD", {"ticket": 1, "direction": "buy", "score": 72}, 72)

    approved, reason = manager.can_open_position("EURUSD", "buy", 90)

    assert approved is True
    assert reason == "Position approved"


def test_same_direction_stacking_is_rejected_when_score_does_not_improve() -> None:
    manager = PortfolioManager({"TRADING_PAIRS": ["EURUSD"]})
    manager.add_position_state(
        "EURUSD", {"ticket": 1, "direction": "buy", "score": 72}, 72)

    approved, reason = manager.can_open_position("EURUSD", "buy", 72)

    assert approved is False
    assert "current best" in reason


def test_opposite_direction_requires_better_high_quality_score() -> None:
    manager = PortfolioManager({"TRADING_PAIRS": ["EURUSD"]})
    manager.add_position_state(
        "EURUSD", {"ticket": 1, "direction": "buy", "score": 80}, 80)

    rejected, rejected_reason = manager.can_open_position("EURUSD", "sell", 75)
    approved, approved_reason = manager.can_open_position("EURUSD", "sell", 85)

    assert rejected is False
    assert "current best" in rejected_reason
    assert approved is True
    assert approved_reason == "Position approved"


def test_stacking_score_is_scoped_to_each_pair() -> None:
    manager = PortfolioManager({"TRADING_PAIRS": ["EURUSD", "GBPUSD"]})
    manager.add_position_state(
        "EURUSD", {"ticket": 1, "direction": "buy", "score": 90}, 90)

    approved, reason = manager.can_open_position("GBPUSD", "buy", 72)

    assert approved is True
    assert reason == "Position approved"


def test_same_direction_stack_requires_minimum_score() -> None:
    manager = PortfolioManager({"TRADING_PAIRS": ["EURUSD"]})
    manager.add_position_state(
        "EURUSD", {"ticket": 1, "direction": "buy", "score": 65}, 65)

    approved, reason = manager.can_open_position("EURUSD", "buy", 69)

    assert approved is False
    assert "threshold" in reason


def test_dynamic_risk_tiers() -> None:
    manager = PortfolioManager({"TRADING_PAIRS": ["EURUSD"]})

    assert manager.get_dynamic_risk(90) == 0.02
    assert manager.get_dynamic_risk(80) == 0.0095
    assert manager.get_dynamic_risk(70) == 0.008
    assert manager.get_dynamic_risk(64) == 0.0


def test_position_limit_recovery_waits_then_allows_two_high_score_overrides() -> None:
    now = [datetime(2026, 8, 20, tzinfo=timezone.utc)]

    def clock() -> datetime:
        return now[0]

    manager = PortfolioManager(
        {"TRADING_PAIRS": ["EURUSD", "GBPUSD", "USDJPY"], "clock": clock})
    for ticket in range(5):
        manager.add_position_state(
            "EURUSD" if ticket < 2 else "GBPUSD" if ticket < 4 else "USDJPY",
            {"ticket": ticket, "direction": "buy", "score": 70},
            70,
        )

    waiting, waiting_reason = manager.can_open_position("USDJPY", "buy", 95)
    assert waiting is False
    assert "Waiting" in waiting_reason
    assert manager.get_position_limit_status()["elapsed_hours"] == 0.0

    now[0] += timedelta(hours=1)
    waiting, waiting_reason = manager.can_open_position("USDJPY", "buy", 95)
    assert waiting is False
    assert "Waiting" in waiting_reason

    now[0] += timedelta(hours=2)
    approved, approval_reason = manager.can_open_position("USDJPY", "sell", 95)
    assert approved is True
    assert approval_reason == "Position approved"
    manager.record_override_position()

    approved, approval_reason = manager.can_open_position("USDJPY", "sell", 96)
    assert approved is True
    manager.record_override_position()

    rejected, rejected_reason = manager.can_open_position("USDJPY", "sell", 97)
    assert rejected is False
    assert "Max override positions" in rejected_reason


def test_position_limit_recovery_resets_when_exposure_drops() -> None:
    now = [datetime(2026, 8, 20, tzinfo=timezone.utc)]

    manager = PortfolioManager(
        {"TRADING_PAIRS": ["EURUSD"], "clock": lambda: now[0]})
    for ticket in range(5):
        manager.add_position_state(
            "EURUSD", {"ticket": ticket, "direction": "buy", "score": 70}, 70)

    manager.can_open_position("EURUSD", "buy", 95)
    assert manager.position_limit_hit_time is not None

    manager.remove_position_state("EURUSD", 0)
    approved, reason = manager.can_open_position("EURUSD", "buy", 70)

    assert approved is False
    assert "Same direction" not in reason
    assert manager.position_limit_hit_time is None
