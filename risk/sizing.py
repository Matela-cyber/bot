"""Centralized position sizing logic."""
from __future__ import annotations


def calculate_lot_size(
    account_balance: float,
    stop_loss_pips: int,
    base_risk_percent: float = 0.005,
    quality_multiplier: float = 1.0,
    session_multiplier: float = 1.0,
    spread_multiplier: float = 1.0,
    min_lot: float = 0.01,
    max_lot: float = 1.0,
) -> tuple[float, float]:
    """Calculate rounded lots and the risk represented by that rounded volume."""
    if account_balance <= 0:
        raise ValueError("account_balance must be positive")
    if stop_loss_pips <= 0:
        raise ValueError("stop_loss_pips must be positive")
    if base_risk_percent < 0 or quality_multiplier < 0 or session_multiplier < 0 or spread_multiplier < 0:
        raise ValueError("risk percentages and multipliers cannot be negative")
    if min_lot <= 0 or max_lot < min_lot:
        raise ValueError("lot bounds are invalid")

    total_risk_pct = min(
        base_risk_percent * quality_multiplier *
        session_multiplier * spread_multiplier,
        0.02,
    )
    risk_amount = account_balance * total_risk_pct
    pip_value_per_lot = 10.0
    raw_lot_size = risk_amount / (stop_loss_pips * pip_value_per_lot)
    lot_size = round(raw_lot_size / 0.01) * 0.01
    lot_size = max(min_lot, min(lot_size, max_lot))
    actual_risk = lot_size * stop_loss_pips * pip_value_per_lot
    return round(lot_size, 2), round(actual_risk, 2)


def calculate_position_size(
    account_balance: float,
    risk_per_trade: float,
    stop_loss_pips: int,
    session_risk_multiplier: float = 1.0,
    quality_multiplier: float = 1.0,
    spread_multiplier: float = 1.0,
) -> tuple[float, float]:
    """Compatibility wrapper using the canonical lot-size calculation."""
    return calculate_lot_size(
        account_balance=account_balance,
        stop_loss_pips=stop_loss_pips,
        base_risk_percent=risk_per_trade,
        quality_multiplier=quality_multiplier,
        session_multiplier=session_risk_multiplier,
        spread_multiplier=spread_multiplier,
    )
