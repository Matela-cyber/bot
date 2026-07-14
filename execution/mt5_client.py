from __future__ import annotations

import logging
from typing import Any

mt5: Any = None
try:
    import MetaTrader5 as mt5  # type: ignore[import]
except ImportError:  # pragma: no cover - optional dependency in test environments
    pass


logger = logging.getLogger("mt5_client")


class MT5Client:
    """Thin wrapper for local MetaTrader 5 execution via the desktop terminal."""

    def __init__(self, account: int | None = None, password: str | None = None, server: str | None = None) -> None:
        self.account = int(account) if account not in (None, "", 0) else None
        self.password = password
        self.server = server
        self.connected = False

    def is_configured(self) -> bool:
        return bool(self.account and self.password and self.server)

    def _require_mt5(self) -> Any:
        if mt5 is None:
            raise RuntimeError("MetaTrader5 is not installed. Install it with 'pip install MetaTrader5'.")
        return mt5

    def connect(self) -> bool:
        mt5_module = self._require_mt5()
        if self.connected:
            return True
        if not self.account or not self.password or not self.server:
            raise RuntimeError("MT5 account, password, and server must be configured in .env")

        initialized = mt5_module.initialize(login=self.account, password=self.password, server=self.server)
        if not initialized:
            raise RuntimeError(f"MT5 initialization failed: {mt5_module.last_error()}")

        self.connected = True
        return True

    def disconnect(self) -> None:
        if mt5 is None:
            return
        if self.connected:
            mt5.shutdown()
            self.connected = False

    def get_balance(self) -> float:
        self.connect()
        mt5_module = self._require_mt5()
        account_info = mt5_module.account_info()
        if account_info is None:
            raise RuntimeError("MT5 account_info returned no data")
        return float(account_info.balance)

    def get_equity(self) -> float:
        self.connect()
        mt5_module = self._require_mt5()
        account_info = mt5_module.account_info()
        if account_info is None:
            raise RuntimeError("MT5 account_info returned no data")
        return float(account_info.equity)

    def get_price(self, symbol: str) -> dict[str, float]:
        self.connect()
        mt5_module = self._require_mt5()
        tick = mt5_module.symbol_info_tick(symbol)
        if tick is None:
            raise RuntimeError(f"MT5 could not fetch tick data for {symbol}")
        return {"bid": float(tick.bid), "ask": float(tick.ask)}

    def _round_price_to_point(self, price: float, point: float, digits: int | None = None) -> float:
        if point <= 0:
            return round(price, digits or 10)
        normalized = round(price / point) * point
        return round(normalized, digits if digits is not None else 10)

    def _normalize_volume(self, lots: float, min_lot: float, volume_step: float | None) -> float:
        if lots < min_lot:
            lots = min_lot
        if volume_step and volume_step > 0:
            lots = round(round(lots / volume_step) * volume_step, 2)
        return max(min_lot, round(lots, 2))

    def place_order(
        self,
        symbol: str,
        order_type: str,
        lots: float,
        stop_loss: float | None = None,
        take_profit: float | None = None,
        reference_entry_price: float | None = None,
        comment: str | None = None,
    ) -> dict[str, Any]:
        """Place a market order with valid SL/TP using symbol info."""
        self.connect()
        mt5_module = self._require_mt5()

        # Get symbol info
        symbol_info = mt5_module.symbol_info(symbol)
        if not symbol_info:
            raise RuntimeError(f"Symbol {symbol} not found in MT5")

        # Get trade configuration
        point = symbol_info.point
        digits = getattr(symbol_info, "digits", None)
        min_stop = symbol_info.trade_stops_level
        min_lot = symbol_info.volume_min
        volume_step = symbol_info.volume_step

        # Validate lot size
        lots = self._normalize_volume(float(lots), float(min_lot), float(volume_step) if volume_step is not None else None)

        # Get current price
        tick = mt5_module.symbol_info_tick(symbol)
        if tick is None:
            raise RuntimeError(f"MT5 could not fetch tick data for {symbol}")

        # Determine order type and entry price
        order_type_upper = order_type.lower()
        if order_type_upper == "buy":
            trade_type = mt5_module.ORDER_TYPE_BUY
            entry_price = float(tick.ask)
        elif order_type_upper == "sell":
            trade_type = mt5_module.ORDER_TYPE_SELL
            entry_price = float(tick.bid)
        else:
            raise ValueError("order_type must be 'buy' or 'sell'")

        # If the trade plan was generated from a stale frame price, preserve the intended risk distances against the live entry price.
        if reference_entry_price is not None and stop_loss is not None:
            stop_distance = abs(reference_entry_price - float(stop_loss))
            stop_loss = entry_price - stop_distance if order_type_upper == "buy" else entry_price + stop_distance
        if reference_entry_price is not None and take_profit is not None:
            tp_distance = abs(float(take_profit) - reference_entry_price)
            take_profit = entry_price + tp_distance if order_type_upper == "buy" else entry_price - tp_distance

        # Calculate SL/TP with validation
        sl_price = 0.0
        tp_price = 0.0
        min_distance = float(min_stop) * float(point)

        if stop_loss is not None and stop_loss > 0:
            sl_price = self._round_price_to_point(float(stop_loss), float(point), digits)
            if order_type_upper == "buy" and sl_price >= entry_price:
                sl_price = self._round_price_to_point(
                    entry_price - max(min_distance, abs(sl_price - entry_price)),
                    float(point),
                    digits,
                )
            if order_type_upper == "sell" and sl_price <= entry_price:
                sl_price = self._round_price_to_point(
                    entry_price + max(min_distance, abs(sl_price - entry_price)),
                    float(point),
                    digits,
                )
            if abs(sl_price - entry_price) < min_distance:
                sl_price = self._round_price_to_point(
                    entry_price - min_distance if order_type_upper == "buy" else entry_price + min_distance,
                    float(point),
                    digits,
                )

        if take_profit is not None and take_profit > 0:
            tp_price = self._round_price_to_point(float(take_profit), float(point), digits)
            if order_type_upper == "buy" and tp_price <= entry_price:
                tp_price = self._round_price_to_point(
                    entry_price + max(min_distance, abs(tp_price - entry_price)),
                    float(point),
                    digits,
                )
            if order_type_upper == "sell" and tp_price >= entry_price:
                tp_price = self._round_price_to_point(
                    entry_price - max(min_distance, abs(tp_price - entry_price)),
                    float(point),
                    digits,
                )
            if abs(tp_price - entry_price) < min_distance:
                tp_price = self._round_price_to_point(
                    entry_price + min_distance if order_type_upper == "buy" else entry_price - min_distance,
                    float(point),
                    digits,
                )

        request: dict[str, Any] = {
            "action": mt5_module.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": float(lots),
            "type": trade_type,
            "price": entry_price,
            "deviation": 30,
            "magic": 123456,
            "comment": comment or "Bot Trade",
            "type_time": mt5_module.ORDER_TIME_GTC,
            "type_filling": mt5_module.ORDER_FILLING_IOC,
        }
        if sl_price > 0 and sl_price != entry_price:
            request["sl"] = sl_price
        if tp_price > 0 and tp_price != entry_price:
            request["tp"] = tp_price

        logger.info("MT5 order request=%s", request)
        result = mt5_module.order_send(request)
        logger.info("MT5 order response=%s", getattr(result, "__dict__", result))
        if result is None:
            raise RuntimeError("MT5 order_send returned no result")

        if result.retcode != mt5_module.TRADE_RETCODE_DONE:
            error_comment = getattr(result, "comment", None)
            raise RuntimeError(
                f"MT5 order failed with code {result.retcode}"
                + (f", comment={error_comment}" if error_comment else "")
            )

        # Try multiple fields for order ID (ticket, deal, order)
        ticket = getattr(result, "ticket", None) or getattr(result, "deal", None) or getattr(result, "order", None)
        if ticket is None:
            raise RuntimeError("MT5 order accepted but no ticket/deal/order ID found")

        return {
            "status": "accepted",
            "order_id": str(ticket),
            "comment": getattr(result, "comment", ""),
            "entry_price": entry_price,
        }

    def draw_analysis(self, symbol: str, trade_plan: dict[str, Any]) -> None:
        """Attempt to draw analysis markers in MT5 chart if the API is available."""
        if mt5 is None:
            logger.warning("MT5 is not installed; cannot draw chart analysis.")
            return

        if not hasattr(mt5, "object_create"):
            logger.warning("MT5 chart object API unavailable in installed MetaTrader5 package.")
            return

        logger.info("MT5 analysis drawing is not available in this runtime environment.")

    def close_position(self, position_id: int) -> dict[str, Any]:
        self.connect()
        mt5_module = self._require_mt5()
        positions = mt5_module.positions_get(ticket=position_id)
        if not positions:
            raise RuntimeError(f"MT5 position {position_id} was not found")

        position = positions[0]
        tick = mt5_module.symbol_info_tick(position.symbol)
        if tick is None:
            raise RuntimeError(f"MT5 could not fetch tick data for {position.symbol}")

        close_request: dict[str, Any] = {
            "action": mt5_module.TRADE_ACTION_DEAL,
            "symbol": position.symbol,
            "volume": position.volume,
            "type": mt5_module.ORDER_TYPE_SELL if position.type == mt5_module.ORDER_TYPE_BUY else mt5_module.ORDER_TYPE_BUY,
            "price": tick.ask if position.type == mt5_module.ORDER_TYPE_BUY else tick.bid,
            "deviation": 20,
            "magic": 100000,
            "comment": "bot-close",
            "type_time": mt5_module.ORDER_TIME_GTC,
            "type_filling": mt5_module.ORDER_FILLING_IOC,
        }
        result = mt5_module.order_send(close_request)
        if result is None:
            raise RuntimeError("MT5 position close returned no result")
        if result.retcode != mt5_module.TRADE_RETCODE_DONE:
            raise RuntimeError(f"MT5 position close failed with code {result.retcode}")
        return {"status": "closed", "position_id": str(position_id)}

    def get_open_positions(self) -> list[dict[str, Any]]:
        """Fetch all open positions for the account."""
        self.connect()
        mt5_module = self._require_mt5()
        positions = mt5_module.positions_get()

        if not positions:
            return []

        result: list[dict[str, Any]] = []
        for pos in positions:
            pnl_pct = (pos.profit / (pos.price_open * pos.volume * 100000)) * 100 if pos.price_open and pos.volume else 0.0
            result.append({
                "ticket": pos.ticket,
                "symbol": pos.symbol,
                "type": "buy" if pos.type == mt5_module.ORDER_TYPE_BUY else "sell",
                "volume": pos.volume,
                "entry_price": pos.price_open,
                "current_price": pos.price_current,
                "sl": pos.sl,
                "tp": pos.tp,
                "pnl": pos.profit,
                "pnl_percent": pnl_pct,
            })

        return result
