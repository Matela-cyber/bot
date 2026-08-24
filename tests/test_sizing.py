from __future__ import annotations

import pytest
from typing import Any

from risk.sizing import calculate_lot_size, calculate_position_size


def test_calculate_lot_size_applies_quality_and_rounding() -> None:
    lots, risk = calculate_lot_size(
        account_balance=1000.0,
        stop_loss_pips=20,
        base_risk_percent=0.005,
        quality_multiplier=1.5,
    )

    assert lots == 0.04
    assert risk == 8.0


def test_calculate_lot_size_caps_total_risk_at_two_percent() -> None:
    lots, risk = calculate_lot_size(
        account_balance=1000.0,
        stop_loss_pips=10,
        base_risk_percent=0.01,
        quality_multiplier=2.0,
        session_multiplier=2.0,
        spread_multiplier=2.0,
    )

    assert lots == 0.2
    assert risk == 20.0


def test_calculate_position_size_wrapper_matches_canonical_function() -> None:
    expected = calculate_lot_size(1000.0, 20, 0.005, 1.25, 0.8, 1.0)
    actual = calculate_position_size(1000.0, 0.005, 20, 0.8, 1.25, 1.0)

    assert actual == expected


@pytest.mark.parametrize(
    "kwargs",
    [
        {"account_balance": 0.0, "stop_loss_pips": 20},
        {"account_balance": 1000.0, "stop_loss_pips": 0},
        {"account_balance": 1000.0, "stop_loss_pips": 20, "quality_multiplier": -1.0},
    ],
)
def test_calculate_lot_size_rejects_invalid_inputs(kwargs: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        calculate_lot_size(**kwargs)
