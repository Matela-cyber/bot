"""Safe wrapper around MetaTrader 5 Python API."""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from config import config

try:
    import MetaTrader5 as mt5
except ImportError:
    mt5 = None


class MT5ClientError(RuntimeError):
    pass


class MT5Client:
    TIMEFRAMES = {
        "1m": "TIMEFRAME_M1",
        "5m": "TIMEFRAME_M5",
        "15m": "TIMEFRAME_M15",
        "30m": "TIMEFRAME_M30",
        "1h": "TIMEFRAME_H1",
        "4h": "TIMEFRAME_H4",
        "1d": "TIMEFRAME_D1",
    }

    def __init__(self) -> None:
        self.logger = logging.getLogger(__name__)
        self.connected = False

    def initialize(self, terminal_path: str | None = None) -> bool:
        api = self._api()
        kwargs: dict[str, Any] = {}
        login = str(config.mt5_login).strip()
        if login.isdigit():
            kwargs["login"] = int(login)
        if config.mt5_password and config.mt5_password != "your_password":
            kwargs["password"] = config.mt5_password
        if config.mt5_server and config.mt5_server != "ICMarkets-Demo":
            kwargs["server"] = config.mt5_server
        path = terminal_path or config.mt5_path
        try:
            initialized = api.initialize(
                path, **kwargs) if path else api.initialize(**kwargs)
        except Exception as exc:
            raise self._error("MT5 initialization failed", exc) from exc
        if not initialized:
            raise self._error("MT5 initialization failed")
        self.connected = True
        return True

    def shutdown(self) -> None:
        if mt5 is not None:
            mt5.shutdown()
        self.connected = False

    def get_rates(self, symbol: str, timeframe: str, bars: int) -> pd.DataFrame:
        if not symbol or bars < 1:
            raise ValueError("symbol is required and bars must be positive")
        api = self._api()
        timeframe_value = self._timeframe(api, timeframe)
        try:
            rates = api.copy_rates_from_pos(symbol, timeframe_value, 0, bars)
        except Exception as exc:
            raise self._error("MT5 rate request failed", exc) from exc
        if rates is None:
            raise self._error("MT5 returned no rates")
        frame = pd.DataFrame(rates)
        if frame.empty:
            return frame
        if "time" not in frame.columns:
            raise MT5ClientError("MT5 rates do not contain a time column")
        frame["time"] = pd.to_datetime(
            frame["time"], unit="s", utc=True, errors="coerce")
        return frame.dropna(subset=["time"]).set_index("time").sort_index()

    def place_order(self, symbol: str, order_type: str | int, volume: float, price: float, sl: float, tp: float, comment: str) -> Any:
        if not symbol or volume <= 0 or price <= 0 or sl <= 0 or tp <= 0:
            raise ValueError(
                "symbol and order prices must be valid; volume must be positive")
        api = self._api()
        order_value = self._order_type(api, order_type)
        request = {
            "action": getattr(api, "TRADE_ACTION_DEAL", 1),
            "symbol": symbol,
            "volume": volume,
            "type": order_value,
            "price": price,
            "sl": sl,
            "tp": tp,
            "deviation": 20,
            "magic": 20260903,
            "comment": comment[:31],
            "type_time": getattr(api, "ORDER_TIME_GTC", 0),
            "type_filling": getattr(api, "ORDER_FILLING_IOC", 1),
        }
        try:
            result = api.order_send(request)
        except Exception as exc:
            raise self._error("MT5 order submission failed", exc) from exc
        if result is None:
            raise self._error("MT5 order submission failed")
        success_code = getattr(api, "TRADE_RETCODE_DONE", 10009)
        if getattr(result, "retcode", success_code) != success_code:
            raise self._error(f"MT5 order rejected (retcode={result.retcode})")
        return result

    def get_account_balance(self) -> float:
        api = self._api()
        try:
            account = api.account_info()
        except Exception as exc:
            raise self._error("MT5 account query failed", exc) from exc
        if account is None or not hasattr(account, "balance"):
            raise self._error("MT5 account query failed")
        return float(account.balance)

    def get_open_positions(self, symbol: str | None = None) -> list[Any]:
        api = self._api()
        try:
            positions = api.positions_get(
                symbol=symbol) if symbol else api.positions_get()
        except Exception as exc:
            raise self._error("MT5 positions query failed", exc) from exc
        if positions is None:
            error = self._last_error(api)
            if error[0] == 0:
                return []
            raise MT5ClientError(f"MT5 positions query failed: {error}")
        return list(positions)

    def get_order_info(self, order_id: int) -> Any:
        if order_id <= 0:
            raise ValueError("order_id must be positive")
        api = self._api()
        try:
            order = api.history_order_get(ticket=order_id)
        except Exception as exc:
            raise self._error("MT5 order query failed", exc) from exc
        if order is None:
            raise self._error(f"MT5 order {order_id} was not found")
        return order

    def get_api(self) -> Any:
        return self._api()

    @staticmethod
    def _last_error(api: Any) -> Any:
        try:
            return api.last_error()
        except Exception:
            return "unknown MT5 error"

    def _error(self, message: str, cause: Exception | None = None) -> MT5ClientError:
        detail = self._last_error(self._api())
        suffix = f": {detail}"
        if cause:
            suffix += f" ({cause})"
        return MT5ClientError(message + suffix)

    @staticmethod
    def _api() -> Any:
        if mt5 is None:
            raise MT5ClientError("MetaTrader5 package is not installed")
        return mt5

    @classmethod
    def _timeframe(cls, api: Any, timeframe: str) -> Any:
        key = timeframe.lower().strip()
        constant = cls.TIMEFRAMES.get(key)
        if constant is None or not hasattr(api, constant):
            raise ValueError(f"unsupported timeframe: {timeframe}")
        return getattr(api, constant)

    @staticmethod
    def _order_type(api: Any, order_type: str | int) -> Any:
        if isinstance(order_type, int):
            return order_type
        values = {"buy": "ORDER_TYPE_BUY", "sell": "ORDER_TYPE_SELL"}
        constant = values.get(order_type.lower().strip())
        if constant is None or not hasattr(api, constant):
            raise ValueError(f"unsupported order type: {order_type}")
        return getattr(api, constant)
