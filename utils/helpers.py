from __future__ import annotations


def pips_to_price_distance(pips: float, price: float = 1.0) -> float:
    """Convert pips to a price distance for a simple Forex estimate."""
    return pips * 0.0001 * price
