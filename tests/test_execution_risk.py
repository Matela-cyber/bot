from __future__ import annotations

from types import SimpleNamespace

from execution.mt5_client import MT5Client
from risk.manager import RiskManager


def test_risk_manager_assesses_daily_limit_and_position_size() -> None:
    manager = RiskManager(account_balance=1000.0, daily_loss=40.0)
    assessment = manager.assess_trade({"entry_price": 1.1000, "stop_loss": 1.0900})

    assert assessment.allowed is False
    assert assessment.reason == "daily_loss_limit"
    assert assessment.position_size >= 0.0


def test_risk_manager_halts_on_drawdown_limit() -> None:
    manager = RiskManager(account_balance=1000.0, daily_loss=0.0)
    allowed, reason = manager.check_limits(current_equity=850.0, peak_equity=1000.0)

    assert allowed is False
    assert reason == "overall_drawdown_limit"


def test_risk_manager_rejects_trade_when_portfolio_risk_exceeds_limit() -> None:
    class FakeMT5Client:
        def get_open_positions(self) -> list[dict[str, Any]]:
            return [
                {
                    "ticket": 1,
                    "symbol": "EURUSD",
                    "type": "buy",
                    "entry_price": 1.1000,
                    "sl": 1.0900,
                    "tp": 1.1200,
                    "current_price": 1.1000,
                    "pnl": 0.0,
                    "pnl_percent": 0.0,
                    "volume": 3.0,
                }
            ]

        def get_equity(self) -> float:
            return 100000.0

    manager = RiskManager(account_balance=1000.0, daily_loss=0.0)
    approved, reason = manager.approve_trade("bull", FakeMT5Client())

    assert approved is False
    assert reason == "max_total_risk_percent"


def test_mt5_client_uses_absolute_sl_tp_levels(monkeypatch) -> None:
    captured: list[dict] = []

    class FakeMT5:
        ORDER_TYPE_BUY = 0
        ORDER_TYPE_SELL = 1
        TRADE_ACTION_DEAL = 1
        ORDER_TIME_GTC = 0
        ORDER_FILLING_IOC = 0
        TRADE_RETCODE_DONE = 10009

        def initialize(self, **kwargs) -> bool:
            return True

        def last_error(self) -> str:
            return "ok"

        def shutdown(self) -> None:
            return None

        def account_info(self) -> SimpleNamespace:
            return SimpleNamespace(balance=1000.0)

        def symbol_info(self, symbol: str) -> SimpleNamespace:
            return SimpleNamespace(point=0.0001, trade_stops_level=10, volume_min=0.01, volume_step=0.01)

        def symbol_info_tick(self, symbol: str) -> SimpleNamespace:
            return SimpleNamespace(ask=1.1000, bid=1.0990)

        def order_send(self, request: dict) -> SimpleNamespace:
            captured.append(request)
            return SimpleNamespace(retcode=self.TRADE_RETCODE_DONE, comment="ok", ticket=123)

        def positions_get(self, ticket=None):
            return [SimpleNamespace(ticket=123, symbol="EURUSD", volume=0.01, price_open=1.1000, price_current=1.1001, sl=1.0950, tp=1.1050, profit=0.0)]

    monkeypatch.setattr("execution.mt5_client.mt5", FakeMT5())

    client = MT5Client(account=123456, password="secret", server="Demo")
    result = client.place_order("EURUSD", "buy", 0.01, stop_loss=1.0950, take_profit=1.1050)

    assert result["status"] == "accepted"
    assert len(captured) == 1
    assert captured[0]["sl"] == 1.0950
    assert captured[0]["tp"] == 1.1050


def test_mt5_client_verifies_position_after_order_acceptance(monkeypatch) -> None:
    class FakeMT5:
        ORDER_TYPE_BUY = 0
        ORDER_TYPE_SELL = 1
        TRADE_ACTION_DEAL = 1
        ORDER_TIME_GTC = 0
        ORDER_FILLING_IOC = 0
        TRADE_RETCODE_DONE = 10009

        def initialize(self, **kwargs) -> bool:
            return True

        def last_error(self) -> str:
            return "ok"

        def shutdown(self) -> None:
            return None

        def account_info(self) -> SimpleNamespace:
            return SimpleNamespace(balance=1000.0)

        def symbol_info(self, symbol: str) -> SimpleNamespace:
            return SimpleNamespace(point=0.0001, trade_stops_level=10, volume_min=0.01, volume_step=0.01)

        def symbol_info_tick(self, symbol: str) -> SimpleNamespace:
            return SimpleNamespace(ask=1.1000, bid=1.0990)

        def order_send(self, request: dict) -> SimpleNamespace:
            return SimpleNamespace(retcode=self.TRADE_RETCODE_DONE, comment="ok", ticket=456)

        def positions_get(self, ticket=None):
            return [SimpleNamespace(ticket=456, symbol="EURUSD", volume=0.01, price_open=1.1000, price_current=1.1001, sl=1.0950, tp=1.1050, profit=0.0)]

    monkeypatch.setattr("execution.mt5_client.mt5", FakeMT5())
    client = MT5Client(account=123456, password="secret", server="Demo")
    result = client.place_order("EURUSD", "buy", 0.01, stop_loss=1.0950, take_profit=1.1050)

    assert result["status"] == "accepted"
    assert result["ticket"] == 456
    assert result["position"]["symbol"] == "EURUSD"


def test_mt5_client_adjusts_tight_sl_tp_distance(monkeypatch) -> None:
    captured: list[dict] = []

    class FakeMT5:
        ORDER_TYPE_BUY = 0
        ORDER_TYPE_SELL = 1
        TRADE_ACTION_DEAL = 1
        ORDER_TIME_GTC = 0
        ORDER_FILLING_IOC = 0
        TRADE_RETCODE_DONE = 10009

        def initialize(self, **kwargs) -> bool:
            return True

        def last_error(self) -> str:
            return "ok"

        def shutdown(self) -> None:
            return None

        def account_info(self) -> SimpleNamespace:
            return SimpleNamespace(balance=1000.0)

        def symbol_info(self, symbol: str) -> SimpleNamespace:
            return SimpleNamespace(point=0.0001, trade_stops_level=10, volume_min=0.01, volume_step=0.01)

        def symbol_info_tick(self, symbol: str) -> SimpleNamespace:
            return SimpleNamespace(ask=1.1000, bid=1.0990)

        def order_send(self, request: dict) -> SimpleNamespace:
            captured.append(request)
            return SimpleNamespace(retcode=self.TRADE_RETCODE_DONE, comment="ok", ticket=123)

        def positions_get(self, ticket=None):
            return [SimpleNamespace(ticket=123, symbol="EURUSD", volume=0.01, price_open=1.1000, price_current=1.1001, sl=1.0990, tp=1.1010, profit=0.0)]

    monkeypatch.setattr("execution.mt5_client.mt5", FakeMT5())

    client = MT5Client(account=123456, password="secret", server="Demo")
    result = client.place_order("EURUSD", "buy", 0.01, stop_loss=1.0999, take_profit=1.1001)

    assert result["status"] == "accepted"
    assert len(captured) == 1
    assert captured[0]["sl"] == 1.0990
    assert captured[0]["tp"] == 1.1010
