from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from config import settings

try:
    import MetaTrader5 as mt5  # type: ignore[import]
except ImportError:
    mt5 = None

LOG_FILE = Path(__file__).resolve().parent / "mt5_diagnostic.log"

logger = logging.getLogger("diagnose_mt5")
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
file_handler = logging.FileHandler(LOG_FILE)
file_handler.setFormatter(formatter)
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)
logger.addHandler(file_handler)
logger.addHandler(stream_handler)


def log_and_print(message: str, level: str = "info") -> None:
    getattr(logger, level)(message)


def _check_mt5_import() -> bool:
    if mt5 is None:
        log_and_print("MetaTrader5 package is not installed.", "error")
        return False
    log_and_print("MetaTrader5 package imported successfully.", "info")
    return True


def _initialize_mt5() -> bool:
    try:
        initialized = mt5.initialize(login=settings.mt5_account, password=settings.mt5_password, server=settings.mt5_server)
    except Exception as exc:
        log_and_print(f"MT5 initialization threw an exception: {exc}", "error")
        return False

    if not initialized:
        err = mt5.last_error()
        log_and_print(f"MT5 initialization failed: {err}", "error")
        return False

    log_and_print("MT5 initialized successfully.", "info")
    return True


def _check_account_info() -> bool:
    account_info = mt5.account_info()
    if account_info is None:
        err = mt5.last_error()
        log_and_print(f"Account info unavailable: {err}", "error")
        return False

    info = {
        "login": account_info.login,
        "balance": float(account_info.balance),
        "equity": float(account_info.equity),
        "margin": float(account_info.margin),
        "margin_free": float(account_info.margin_free),
        "leverage": int(account_info.leverage),
        "server": account_info.server,
        "name": getattr(account_info, "name", None),
    }
    log_and_print(f"Account info: {json.dumps(info, default=str)}", "info")
    return True


def _check_symbol(symbol: str) -> bool:
    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        log_and_print(f"Symbol {symbol} not available in MT5.", "error")
        return False

    details = {
        "symbol": symbol,
        "digits": getattr(symbol_info, "digits", None),
        "point": float(getattr(symbol_info, "point", 0.0)),
        "min_lot": float(getattr(symbol_info, "volume_min", 0.0)),
        "max_lot": float(getattr(symbol_info, "volume_max", 0.0)),
        "step": float(getattr(symbol_info, "volume_step", 0.0)),
        "trade_stops_level": float(getattr(symbol_info, "trade_stops_level", 0.0)),
        "trade_mode": getattr(symbol_info, "trade_mode", None),
    }
    log_and_print(f"Symbol info: {json.dumps(details, default=str)}", "info")
    return True


def _check_symbol_tick(symbol: str) -> bool:
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        log_and_print(f"Tick info unavailable for {symbol}.", "error")
        return False

    log_and_print(f"Tick for {symbol}: bid={tick.bid}, ask={tick.ask}", "info")
    return True


def _test_order(symbol: str, volume: float) -> bool:
    log_and_print(f"Attempting test order for {symbol} at {volume} lots", "info")
    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        log_and_print(f"Cannot place order; symbol {symbol} missing.", "error")
        return False

    if not symbol_info.visible:
        mt5.symbol_select(symbol, True)
        log_and_print(f"Selected symbol {symbol} for trading.", "debug")

    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        log_and_print(f"Cannot fetch tick for {symbol}", "error")
        return False

    order_type = mt5.ORDER_TYPE_BUY
    price = float(tick.ask)
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": float(volume),
        "type": order_type,
        "price": price,
        "deviation": 30,
        "magic": 999999,
        "comment": "diagnostic-test",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    log_and_print(f"Order request: {request}", "debug")
    result = mt5.order_send(request)
    if result is None:
        log_and_print("MT5 order_send returned no result.", "error")
        return False

    log_and_print(f"Order response retcode={result.retcode}, comment={getattr(result, 'comment', None)}, ticket={getattr(result, 'ticket', None)}", "info")
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        log_and_print(f"Order failed: retcode={result.retcode}, comment={getattr(result, 'comment', None)}", "error")
        return False

    ticket = getattr(result, "ticket", None) or getattr(result, "deal", None) or getattr(result, "order", None)
    if ticket is None:
        log_and_print("Order accepted but no ticket was returned.", "error")
        return False

    positions = mt5.positions_get(ticket=ticket)
    if not positions:
        log_and_print(f"Order {ticket} placed but no position found in positions_get().", "error")
        return False

    position = positions[0]
    details = {
        "ticket": position.ticket,
        "symbol": position.symbol,
        "volume": position.volume,
        "price_open": position.price_open,
        "sl": position.sl,
        "tp": position.tp,
        "profit": position.profit,
    }
    log_and_print(f"Position verified: {json.dumps(details, default=str)}", "info")
    return True


def main() -> None:
    success = _check_mt5_import()
    if not success:
        return

    success = _initialize_mt5()
    if not success:
        return

    try:
        _check_account_info()
        _check_symbol("GBPUSD")
        _check_symbol_tick("GBPUSD")

        order_success = _test_order("GBPUSD", 0.01)
        if order_success:
            log_and_print("MT5 diagnostic passed.", "info")
        else:
            log_and_print("MT5 diagnostic failed. See logs for details.", "error")
    finally:
        try:
            mt5.shutdown()
            log_and_print("MT5 shutdown cleanly.", "info")
        except Exception as exc:
            log_and_print(f"Error shutting down MT5: {exc}", "warning")


if __name__ == "__main__":
    main()
