from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from pytest import MonkeyPatch

from execution.mt5_client import MT5Client


class LifecycleMT5:
    ORDER_TYPE_BUY = 0
    ORDER_TYPE_SELL = 1
    TRADE_ACTION_DEAL = 1
    ORDER_TIME_GTC = 0
    ORDER_FILLING_IOC = 0
    TRADE_RETCODE_DONE = 10009

    def __init__(self, positions: list[SimpleNamespace] | None = None) -> None:
        self.positions = positions or []
        self.initialized = 0
        self.alive = False

    def initialize(self, **kwargs: Any) -> bool:
        self.initialized += 1
        self.alive = True
        return True

    def terminal_info(self):
        return SimpleNamespace() if self.alive else None

    def account_info(self):
        return SimpleNamespace(balance=1000.0, equity=1000.0) if self.alive else None

    def last_error(self) -> str:
        return "ok"

    def shutdown(self) -> None:
        self.alive = False

    def symbol_info(self, symbol: str) -> SimpleNamespace:
        return SimpleNamespace(
            point=0.0001,
            trade_tick_size=0.0001,
            trade_tick_value=1.0,
            trade_stops_level=10,
            volume_min=0.01,
            volume_max=100.0,
            volume_step=0.01,
        )

    def symbol_info_tick(self, symbol: str) -> SimpleNamespace:
        return SimpleNamespace(ask=1.1000, bid=1.0999)

    def positions_get(self, ticket: int | None = None) -> list[SimpleNamespace]:
        if ticket is None:
            return self.positions
        return [position for position in self.positions if position.ticket == ticket]

    def order_send(self, request: dict[str, Any]) -> SimpleNamespace:
        return SimpleNamespace(retcode=self.TRADE_RETCODE_DONE, ticket=789, comment="accepted")


def test_stale_mt5_session_reconnects(monkeypatch: MonkeyPatch) -> None:
    fake = LifecycleMT5()
    monkeypatch.setattr("execution.mt5_client.mt5", fake)
    client = MT5Client(account=1, password="secret", server="demo")

    client.connect()
    fake.shutdown()
    client.connect()

    assert fake.initialized == 2


def test_bot_owned_position_filter(monkeypatch: MonkeyPatch) -> None:
    positions = [
        SimpleNamespace(
            ticket=1,
            symbol="EURUSD",
            type=0,
            volume=0.01,
            price_open=1.1,
            price_current=1.1,
            sl=1.09,
            tp=1.12,
            profit=0.0,
            magic=123456,
        ),
        SimpleNamespace(
            ticket=2,
            symbol="GBPUSD",
            type=0,
            volume=0.01,
            price_open=1.2,
            price_current=1.2,
            sl=1.19,
            tp=1.22,
            profit=0.0,
            magic=0,
        ),
    ]
    fake = LifecycleMT5(positions)
    monkeypatch.setattr("execution.mt5_client.mt5", fake)
    client = MT5Client(account=1, password="secret", server="demo")

    result = client.get_open_positions(bot_only=True)

    assert [position["ticket"] for position in result] == [1]


def test_broker_aware_risk_sizing(monkeypatch: MonkeyPatch) -> None:
    fake = LifecycleMT5()
    monkeypatch.setattr("execution.mt5_client.mt5", fake)
    client = MT5Client(account=1, password="secret", server="demo")

    lots = client.calculate_risk_lots(
        "EURUSD", risk_amount=10.0, stop_distance=0.01)

    assert lots == 0.1


def test_spread_check_uses_live_quote_and_broker_baseline(monkeypatch: MonkeyPatch) -> None:
    fake = LifecycleMT5()
    monkeypatch.setattr("execution.mt5_client.mt5", fake)
    client = MT5Client(account=1, password="secret", server="demo")

    allowed, spread = client.check_spread("EURUSD")

    assert allowed is True
    assert spread == 1.0
