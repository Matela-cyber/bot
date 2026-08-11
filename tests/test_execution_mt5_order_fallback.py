from __future__ import annotations

from types import SimpleNamespace

from execution.mt5_client import MT5Client


def test_mt5_client_rejects_order_without_position(monkeypatch) -> None:
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
            return SimpleNamespace(retcode=self.TRADE_RETCODE_DONE, comment="ok", ticket=789)

        def positions_get(self, ticket=None):
            return []

    monkeypatch.setattr("execution.mt5_client.mt5", FakeMT5())
    client = MT5Client(account=123456, password="secret", server="Demo")

    try:
        client.place_order("EURUSD", "buy", 0.01, stop_loss=1.0950, take_profit=1.1050)
        assert False, "Expected RuntimeError when position verification fails"
    except RuntimeError as exc:
        assert "position not found" in str(exc)
