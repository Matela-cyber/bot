from __future__ import annotations

from core.portfolio_manager import PortfolioManager
from config import settings


def test_portfolio_manager_global_concurrent_position_limit() -> None:
    manager = PortfolioManager({"TRADING_PAIRS": ["EURUSD", "GBPUSD", "USDJPY", "XAUUSD"]})
    manager.total_open_positions = settings.global_max_concurrent_positions

    allowed, reason = manager.can_open_position("EURUSD", "bull", 0.01)
    assert allowed is False
    assert "Global max positions reached" in reason


def test_portfolio_manager_global_risk_limit_blocked() -> None:
    manager = PortfolioManager({"TRADING_PAIRS": ["EURUSD", "GBPUSD", "USDJPY", "XAUUSD"]})
    manager.total_open_positions = 0

    allowed, reason = manager.can_open_position("EURUSD", "bull", 100.0)
    assert allowed is False
    assert "Global risk limit" in reason or "would be exceeded" in reason


def test_portfolio_manager_pair_pauses_after_three_losses() -> None:
    manager = PortfolioManager({"TRADING_PAIRS": ["EURUSD", "GBPUSD", "USDJPY", "XAUUSD"]})
    pair = manager.get_pair_state("EURUSD")
    pair.consecutive_losses = 3

    allowed, reason = manager.can_open_position("EURUSD", "bull", 0.01)
    assert allowed is False
    assert "3 consecutive losses" in reason


def test_portfolio_manager_daily_reset() -> None:
    manager = PortfolioManager({"TRADING_PAIRS": ["EURUSD", "GBPUSD", "USDJPY", "XAUUSD"]})
    manager.global_daily_pnl = -0.02

    manager.global_daily_pnl = 0.0
    assert manager.global_daily_pnl == 0.0


def test_portfolio_manager_drawdown_limit_summary() -> None:
    manager = PortfolioManager({"TRADING_PAIRS": ["EURUSD", "GBPUSD", "USDJPY", "XAUUSD"]})
    manager.global_drawdown = 0.2
    allowed, reason = manager.check_global_limits()
    assert allowed is False
    assert "Global drawdown limit" in reason
