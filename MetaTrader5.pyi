from __future__ import annotations

from typing import Any

ORDER_TYPE_BUY: int
ORDER_TYPE_SELL: int
TRADE_ACTION_DEAL: int
ORDER_TIME_GTC: int
ORDER_FILLING_IOC: int
TRADE_RETCODE_DONE: int
TIMEFRAME_M1: int


class AccountInfo:
    balance: float
    equity: float
    profit: float
    leverage: int
    currency: str


class Tick:
    bid: float
    ask: float


class Position:
    ticket: int
    symbol: str
    volume: float
    type: int


class OrderResult:
    retcode: int
    ticket: int
    price: float
    volume: float
    comment: str


def initialize(path: str | None = None) -> bool: ...

def shutdown() -> None: ...

def last_error() -> str: ...

def login(login: int | None = None, password: str | None = None, server: str | None = None) -> bool: ...

def account_info() -> AccountInfo | None: ...

def symbol_info_tick(symbol: str) -> Tick | None: ...

def order_send(request: dict[str, Any]) -> OrderResult | None: ...

def positions_get(ticket: int) -> list[Position] | tuple[Position, ...] | None: ...

def copy_rates_from_pos(symbol: str, timeframe: int, start_pos: int, count: int) -> list[tuple[Any, ...]] | None: ...