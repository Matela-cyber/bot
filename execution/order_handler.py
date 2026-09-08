"""Order lifecycle operations built on top of mt5_client."""

from __future__ import annotations

import logging
from typing import Any

from execution.mt5_client import MT5Client


class OrderHandler:
    DEVIATION = 20

    def __init__(self, mt5_client: MT5Client) -> None:
        if mt5_client is None:
            raise ValueError("mt5_client is required")
        self.mt5_client = mt5_client
        self.logger = logging.getLogger(__name__)

    def place_order(
        self,
        symbol: str,
        direction: str,
        entry: float,
        stop_loss: float,
        take_profit: float,
        size: float,
    ) -> dict[str, Any]:
        try:
            normalized = direction.lower().strip()
            if normalized not in {"buy", "sell"}:
                raise ValueError("direction must be 'buy' or 'sell'")
            result = self.mt5_client.place_order(
                symbol, normalized, size, entry, stop_loss, take_profit, "mean_reversion")
            return {
                "success": True,
                "order_id": getattr(result, "order", None) or getattr(result, "deal", None),
                "price": float(getattr(result, "price", entry)),
                "volume": float(getattr(result, "volume", size)),
                "symbol": symbol,
            }
        except Exception as exc:
            self.logger.exception(
                "Could not place %s order for %s", direction, symbol)
            return {"success": False, "order_id": None, "price": None, "volume": None, "symbol": symbol, "error": str(exc)}

    def modify_stop_loss(self, symbol: str, new_sl: float, order_id: int | None = None) -> bool:
        try:
            position = self._select_position(symbol, order_id)
            if position is None or new_sl <= 0:
                return False
            api = self.mt5_client._api()
            request = {
                "action": getattr(api, "TRADE_ACTION_SLTP", 6),
                "symbol": symbol,
                "position": self._ticket(position),
                "sl": new_sl,
                "tp": float(getattr(position, "tp", 0.0)),
            }
            return self._send_success(api, request, "stop-loss modification")
        except Exception as exc:
            self.logger.exception("Could not modify stop loss for %s", symbol)
            return False

    def close_order(self, symbol: str, order_id: int | None = None) -> bool:
        return self.close_partial(symbol, 100.0, order_id)

    def close_partial(self, symbol: str, percentage: float, order_id: int | None = None) -> bool:
        try:
            if not 0 < percentage <= 100:
                raise ValueError(
                    "percentage must be greater than 0 and at most 100")
            position = self._select_position(symbol, order_id)
            if position is None:
                return False
            api = self.mt5_client._api()
            position_type = getattr(position, "type", None)
            buy_type = getattr(api, "POSITION_TYPE_BUY", 0)
            close_type = getattr(api, "ORDER_TYPE_SELL", 1) if position_type == buy_type else getattr(
                api, "ORDER_TYPE_BUY", 0)
            volume = round(float(getattr(position, "volume"))
                           * percentage / 100.0, 2)
            if volume <= 0:
                return False
            price = self._close_price(api, symbol, position_type, position)
            request = {
                "action": getattr(api, "TRADE_ACTION_DEAL", 1),
                "symbol": symbol,
                "volume": volume,
                "type": close_type,
                "position": self._ticket(position),
                "price": price,
                "deviation": self.DEVIATION,
                "magic": 20260903,
                "comment": "partial close",
                "type_time": getattr(api, "ORDER_TIME_GTC", 0),
                "type_filling": getattr(api, "ORDER_FILLING_IOC", 1),
            }
            return self._send_success(api, request, "position close")
        except Exception as exc:
            self.logger.exception("Could not close %s position", symbol)
            return False

    def get_order_status(self, order_id: int) -> Any:
        try:
            return self.mt5_client.get_order_info(order_id)
        except Exception as exc:
            self.logger.exception("Could not retrieve order %s", order_id)
            return None

    def _select_position(self, symbol: str, order_id: int | None) -> Any | None:
        positions = self.mt5_client.get_open_positions(symbol)
        if order_id is not None:
            return next((position for position in positions if self._ticket(position) == order_id), None)
        return positions[0] if positions else None

    @staticmethod
    def _ticket(position: Any) -> int:
        ticket = getattr(position, "ticket", None)
        if ticket is None:
            raise ValueError("position has no ticket")
        return int(ticket)

    @staticmethod
    def _close_price(api: Any, symbol: str, position_type: Any, position: Any) -> float:
        tick = api.symbol_info_tick(symbol)
        if tick is not None:
            buy_type = getattr(api, "POSITION_TYPE_BUY", 0)
            value = getattr(tick, "bid", None) if position_type == buy_type else getattr(
                tick, "ask", None)
            if value is not None and float(value) > 0:
                return float(value)
        current = getattr(position, "price_current", None) or getattr(
            position, "price_open", None)
        if current is None or float(current) <= 0:
            raise ValueError("no valid market close price")
        return float(current)

    def _send_success(self, api: Any, request: dict[str, Any], operation: str) -> bool:
        result = api.order_send(request)
        success_code = getattr(api, "TRADE_RETCODE_DONE", 10009)
        if result is None or getattr(result, "retcode", None) != success_code:
            self.logger.error("MT5 %s failed: %s", operation,
                              self._last_error(api))
            return False
        return True

    @staticmethod
    def _last_error(api: Any) -> Any:
        try:
            return api.last_error()
        except Exception:
            return "unknown MT5 error"
