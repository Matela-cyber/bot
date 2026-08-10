from __future__ import annotations

from core.pair_state import PairState


def test_pair_state_add_trade_updates_counts() -> None:
    pair = PairState("EURUSD")
    pair.add_trade({"pnl_amount": 25.0})
    pair.add_trade({"pnl_amount": -20.0})

    assert pair.total_trades == 2
    assert pair.winning_trades == 1
    assert pair.losing_trades == 1
    assert pair.daily_pnl == 5.0
    assert pair.consecutive_losses == 1


def test_pair_state_reset_daily_stats() -> None:
    pair = PairState("EURUSD")
    pair.add_trade({"pnl_amount": 10.0})
    pair.add_trade({"pnl_amount": -5.0})

    pair.reset_daily_stats()

    assert pair.daily_pnl == 0.0
    assert pair.total_trades == 0
    assert pair.winning_trades == 0
    assert pair.losing_trades == 0
    assert pair.consecutive_losses == 0
