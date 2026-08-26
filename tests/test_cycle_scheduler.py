from __future__ import annotations

from main import AdaptiveTradingBot


def test_scheduler_prioritizes_main_cycle_once_per_slot() -> None:
    bot = AdaptiveTradingBot.__new__(AdaptiveTradingBot)
    bot._last_main_cycle_slot = None
    bot._has_emergency_positions = lambda: False

    first = bot._next_scheduled_cycle()
    second = bot._next_scheduled_cycle()

    assert first == "standard"
    assert second == "micro"


def test_scheduler_prioritizes_emergency_between_main_cycles() -> None:
    bot = AdaptiveTradingBot.__new__(AdaptiveTradingBot)
    bot._last_main_cycle_slot = None
    bot._has_emergency_positions = lambda: True

    assert bot._next_scheduled_cycle() == "standard"
    assert bot._next_scheduled_cycle() == "emergency"
