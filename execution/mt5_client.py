from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any, cast

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
            raise RuntimeError(
                "MetaTrader5 is not installed. Install it with 'pip install MetaTrader5'.")
        return mt5

    def _connection_is_alive(self, mt5_module: Any) -> bool:
        """Check whether the terminal session behind the cached flag is still usable."""
        if not self.connected:
            return False

        terminal_info = getattr(mt5_module, "terminal_info", None)
        if callable(terminal_info):
            try:
                return terminal_info() is not None
            except Exception:
                return False

        account_info = getattr(mt5_module, "account_info", None)
        if callable(account_info):
            try:
                return account_info() is not None
            except Exception:
                return False

        return True

    def connect(self) -> bool:
        mt5_module = self._require_mt5()
        if self._connection_is_alive(mt5_module):
            return True
        self.connected = False
        if not self.account or not self.password or not self.server:
            raise RuntimeError(
                "MT5 account, password, and server must be configured in .env")

        initialized = mt5_module.initialize(
            login=self.account, password=self.password, server=self.server)
        if not initialized:
            raise RuntimeError(
                f"MT5 initialization failed: {mt5_module.last_error()}")

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

    def get_symbol_spec(self, symbol: str) -> dict[str, float | str]:
        """Return broker symbol economics required for risk sizing."""
        self.connect()
        mt5_module = self._require_mt5()
        resolved_symbol = self.resolve_symbol(symbol)
        info = mt5_module.symbol_info(resolved_symbol)
        if info is None:
            raise RuntimeError(f"Symbol {resolved_symbol} not found in MT5")
        return {
            "symbol": resolved_symbol,
            "point": float(getattr(info, "point", 0.0) or 0.0),
            "tick_size": float(getattr(info, "trade_tick_size", 0.0) or getattr(info, "point", 0.0) or 0.0),
            "tick_value": float(getattr(info, "trade_tick_value", 0.0) or 0.0),
            "volume_min": float(getattr(info, "volume_min", 0.0) or 0.0),
            "volume_max": float(getattr(info, "volume_max", 0.0) or 0.0),
            "volume_step": float(getattr(info, "volume_step", 0.0) or 0.0),
        }

    def check_spread(self, symbol: str) -> tuple[bool, float]:
        """Check the live spread against the broker's typical spread in points."""
        self.connect()
        mt5_module = self._require_mt5()
        resolved_symbol = self.resolve_symbol(symbol)
        info = mt5_module.symbol_info(resolved_symbol)
        tick = mt5_module.symbol_info_tick(resolved_symbol)
        point = float(getattr(info, "point", 0.0)
                      or 0.0) if info is not None else 0.0
        if info is None or tick is None or point <= 0:
            return False, 0.0

        current_spread = round((float(tick.ask) - float(tick.bid)) / point, 8)
        average_spread = float(getattr(info, "spread", 0.0) or 0.0)
        if current_spread < 0:
            return False, current_spread
        if average_spread <= 0:
            logger.warning(
                "No broker spread baseline for %s; allowing current spread %.2f", resolved_symbol, current_spread)
            return True, current_spread
        if current_spread > average_spread * 2:
            return False, current_spread
        if current_spread > average_spread * 1.5:
            logger.warning(
                "Spread widening for %s: %.2f points (average: %.2f)",
                resolved_symbol,
                current_spread,
                average_spread,
            )
        return True, current_spread

    def calculate_risk_lots(self, symbol: str, risk_amount: float, stop_distance: float) -> float:
        """Calculate volume from live broker tick economics and stop distance."""
        if risk_amount <= 0 or stop_distance <= 0:
            raise ValueError("risk_amount and stop_distance must be positive")
        spec = self.get_symbol_spec(symbol)
        tick_size = float(spec["tick_size"])
        tick_value = float(spec["tick_value"])
        if tick_size <= 0 or tick_value <= 0:
            raise RuntimeError(
                f"Broker returned invalid tick economics for {spec['symbol']}")
        raw_lots = risk_amount / ((stop_distance / tick_size) * tick_value)
        volume_min = float(spec["volume_min"])
        volume_max = float(spec["volume_max"])
        volume_step = float(spec["volume_step"])
        if volume_min <= 0 or volume_step <= 0:
            raise RuntimeError(
                f"Broker returned invalid volume settings for {spec['symbol']}")
        if raw_lots < volume_min:
            raise RuntimeError(
                f"Minimum volume {volume_min} exceeds risk budget for {spec['symbol']}")
        lots = min(raw_lots, volume_max) if volume_max > 0 else raw_lots
        lots = (lots // volume_step) * volume_step
        return round(max(volume_min, lots), 8)

    def resolve_symbol(self, symbol: str) -> str:
        """Resolve a configured pair to the broker's exact MT5 symbol name."""
        self.connect()
        mt5_module = self._require_mt5()
        requested = symbol.strip().upper()
        if not requested:
            raise ValueError("MT5 symbol cannot be empty")

        exact_info = mt5_module.symbol_info(requested)
        if exact_info is not None:
            if hasattr(mt5_module, "symbol_select"):
                mt5_module.symbol_select(requested, True)
            return requested

        symbols_get = getattr(mt5_module, "symbols_get", None)
        if symbols_get is None:
            raise RuntimeError(
                f"Symbol {requested} not found in MT5 and symbol discovery is unavailable")

        candidates = cast(list[Any], symbols_get() or [])
        normalized_requested = "".join(
            character for character in requested if character.isalnum())
        matches: list[str] = []
        for candidate in candidates:
            candidate_name = str(getattr(candidate, "name", candidate))
            normalized_candidate = "".join(
                character for character in candidate_name.upper() if character.isalnum())
            if normalized_candidate == normalized_requested or normalized_candidate.startswith(normalized_requested):
                matches.append(candidate_name)

        if not matches:
            raise RuntimeError(
                f"Symbol {requested} not found in MT5; configure the broker symbol name")

        resolved = sorted(matches, key=lambda name: (len(name), name))[0]
        if hasattr(mt5_module, "symbol_select") and not mt5_module.symbol_select(resolved, True):
            raise RuntimeError(
                f"MT5 could not select resolved symbol {resolved} for {requested}")
        logger.info("Resolved broker symbol %s -> %s", requested, resolved)
        return resolved

    def get_price(self, symbol: str) -> dict[str, float]:
        self.connect()
        mt5_module = self._require_mt5()
        resolved_symbol = self.resolve_symbol(symbol)
        tick = mt5_module.symbol_info_tick(resolved_symbol)
        if tick is None:
            raise RuntimeError(
                f"MT5 could not fetch tick data for {resolved_symbol}")
        return {"bid": float(tick.bid), "ask": float(tick.ask)}

    @staticmethod
    def _rate_value(rate: Any, field: str) -> float:
        """Read a rate field from an MT5 structured record or object row."""
        try:
            return float(getattr(rate, field))
        except AttributeError:
            try:
                return float(rate[field])
            except (KeyError, IndexError, TypeError) as exc:
                raise RuntimeError(
                    f"MT5 rate row is missing field '{field}'") from exc

    def get_atr(self, symbol: str, period: int = 14) -> float:
        self.connect()
        mt5_module = self._require_mt5()
        resolved_symbol = self.resolve_symbol(symbol)

        ticks = mt5_module.copy_rates_from_pos(
            resolved_symbol, mt5_module.TIMEFRAME_M15, 0, period + 1)
        if ticks is None or len(ticks) < period + 1:
            raise RuntimeError(
                f"MT5 could not fetch enough OHLCV bars for ATR on {resolved_symbol}")

        true_ranges: list[float] = []
        for i in range(1, len(ticks)):
            high = self._rate_value(ticks[i], "high")
            low = self._rate_value(ticks[i], "low")
            prev_close = self._rate_value(ticks[i - 1], "close")
            true_range = max(high - low, abs(high - prev_close),
                             abs(low - prev_close))
            true_ranges.append(true_range)

        if not true_ranges:
            raise RuntimeError(
                "ATR calculation failed due to missing range data")

        return sum(true_ranges[-period:]) / float(period)

    def validate_price_levels(
        self,
        entry: float,
        sl: float,
        tp: float,
        direction: str,
        symbol: str,
    ) -> tuple[float, float, float]:
        self.connect()
        mt5_module = self._require_mt5()
        resolved_symbol = self.resolve_symbol(symbol)
        tick = mt5_module.symbol_info_tick(resolved_symbol)
        if tick is None:
            raise RuntimeError(
                f"MT5 could not fetch tick data for {resolved_symbol}")

        live_price = float(tick.ask) if direction.lower(
        ) == "buy" else float(tick.bid)
        if abs(entry - live_price) <= 0.0005:
            return entry, sl, tp

        atr = self.get_atr(resolved_symbol)
        if direction.lower() == "buy":
            new_sl = live_price - atr * 1.5
            new_tp = live_price + atr * 3.0
        else:
            new_sl = live_price + atr * 1.5
            new_tp = live_price - atr * 3.0

        logger.info(
            "Validating stale price levels for %s: live=%s entry=%s sl=%s tp=%s recalculated_sl=%s recalculated_tp=%s",
            symbol,
            live_price,
            entry,
            sl,
            tp,
            new_sl,
            new_tp,
        )
        return live_price, new_sl, new_tp

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

    def _mt5_error_message(self, result: Any) -> str:
        if result is None:
            return "no_result"

        known_codes: dict[int, str] = {
            -6: "Authorization failed",
            -7: "Terminal not found",
            -8: "Not enough rights",
            -100: "No connection",
            -10001: "Market closed",
            -10002: "Invalid symbol",
            -10004: "Invalid volume",
            -10007: "Invalid price",
        }
        code = getattr(result, "retcode", None)
        comment = getattr(result, "comment", None)
        message: str = known_codes.get(
            int(code) if code is not None else 0, "unknown_error")
        if comment:
            message = f"{message}: {comment}"
        return message

    def _position_dict(self, position: Any) -> dict[str, Any]:
        """Convert an MT5 position record into the bot's canonical shape."""
        position_type = getattr(
            position, "type", self._require_mt5().ORDER_TYPE_BUY)
        return {
            "ticket": int(position.ticket),
            "symbol": str(position.symbol),
            "type": "buy" if position_type == self._require_mt5().ORDER_TYPE_BUY else "sell",
            "volume": float(position.volume),
            "entry_price": float(position.price_open),
            "current_price": float(position.price_current),
            "sl": float(position.sl),
            "tp": float(position.tp),
            "profit": float(position.profit),
            "magic": int(getattr(position, "magic", 0) or 0),
        }

    def _verify_position(
        self,
        ticket: int,
        symbol: str,
        entry_price: float | None = None,
        point: float = 0.0,
        position_id: int | None = None,
    ) -> dict[str, Any] | None:
        mt5_module = self._require_mt5()

        lookup_ticket = position_id or ticket
        positions = mt5_module.positions_get(ticket=lookup_ticket)
        if positions:
            return self._position_dict(positions[0])

        positions = mt5_module.positions_get()
        if positions:
            for position in positions:
                if position.symbol != symbol:
                    continue
                if entry_price is None:
                    return self._position_dict(position)
                if abs(float(position.price_open) - entry_price) <= max(3.0 * point, 1e-5):
                    return self._position_dict(position)

        return None

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
        symbol = self.resolve_symbol(symbol)

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
        lots = self._normalize_volume(float(lots), float(min_lot), float(
            volume_step) if volume_step is not None else None)

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
            stop_loss = entry_price - \
                stop_distance if order_type_upper == "buy" else entry_price + stop_distance
        if reference_entry_price is not None and take_profit is not None:
            tp_distance = abs(float(take_profit) - reference_entry_price)
            take_profit = entry_price + \
                tp_distance if order_type_upper == "buy" else entry_price - tp_distance

        # Calculate SL/TP with validation
        sl_price = 0.0
        tp_price = 0.0
        min_distance = float(min_stop) * float(point)

        if stop_loss is not None and stop_loss > 0:
            sl_price = self._round_price_to_point(
                float(stop_loss), float(point), digits)
            if order_type_upper == "buy" and sl_price >= entry_price:
                sl_price = self._round_price_to_point(
                    entry_price - max(min_distance,
                                      abs(sl_price - entry_price)),
                    float(point),
                    digits,
                )
            if order_type_upper == "sell" and sl_price <= entry_price:
                sl_price = self._round_price_to_point(
                    entry_price + max(min_distance,
                                      abs(sl_price - entry_price)),
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
            tp_price = self._round_price_to_point(
                float(take_profit), float(point), digits)
            if order_type_upper == "buy" and tp_price <= entry_price:
                tp_price = self._round_price_to_point(
                    entry_price + max(min_distance,
                                      abs(tp_price - entry_price)),
                    float(point),
                    digits,
                )
            if order_type_upper == "sell" and tp_price >= entry_price:
                tp_price = self._round_price_to_point(
                    entry_price - max(min_distance,
                                      abs(tp_price - entry_price)),
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
        logger.info("MT5 order response=%s",
                    getattr(result, "__dict__", result))
        if result is None:
            raise RuntimeError("MT5 order_send returned no result")

        if result.retcode != mt5_module.TRADE_RETCODE_DONE:
            raise RuntimeError(self._mt5_error_message(result))

        # Try multiple fields for order ID (ticket, deal, order)
        ticket = getattr(result, "ticket", None) or getattr(
            result, "deal", None) or getattr(result, "order", None)
        if ticket is None:
            raise RuntimeError(
                "MT5 order accepted but no ticket/deal/order ID found")

        position_id = getattr(result, "position", None) or getattr(
            result, "position_id", None)

        # After order_send returns, the terminal may need a short moment to register the position.
        # Poll `positions_get` and `history_deals_get` for a few seconds to locate the resulting position/deal.
        import time

        position = self._verify_position(
            int(ticket),
            symbol,
            entry_price=entry_price,
            point=point,
            position_id=int(position_id) if position_id else None,
        )
        if position is None:
            # try polling briefly (total ~5s)
            for _ in range(10):
                time.sleep(0.5)
                position = self._verify_position(
                    int(ticket),
                    symbol,
                    entry_price=entry_price,
                    point=point,
                    position_id=int(position_id) if position_id else None,
                )
                if position is not None:
                    break

        # as a final resort, check recent deals and history orders to correlate the ticket
        if position is None and hasattr(mt5_module, "history_deals_get"):
            now_ts = int(time.time())
            try:
                deals: list[Any] = mt5_module.history_deals_get(
                    0, now_ts, 20) or []
                for d in deals:
                    if (
                        getattr(d, "order", None) == ticket
                        or getattr(d, "deal", None) == ticket
                        or (position_id is not None and getattr(d, "position_id", None) == position_id)
                    ):
                        position_id = position_id or getattr(
                            d, "position_id", None)
                        position = self._verify_position(
                            int(ticket),
                            symbol,
                            entry_price=entry_price,
                            point=point,
                            position_id=int(
                                position_id) if position_id else None,
                        )
                        break
            except Exception:
                # ignore history errors during verification
                pass

        return {
            "status": "accepted" if position is not None else "accepted_unreconciled",
            "order_id": str(ticket),
            "ticket": ticket,
            "position_id": position.get("ticket") if position else position_id,
            "comment": getattr(result, "comment", ""),
            "entry_price": entry_price,
            "position": position,
        }

    def draw_analysis(self, symbol: str, trade_plan: dict[str, Any]) -> None:
        """Attempt to draw analysis markers in MT5 chart if the API is available."""
        if mt5 is None:
            logger.warning("MT5 is not installed; cannot draw chart analysis.")
            return

        if not hasattr(mt5, "object_create"):
            logger.warning(
                "MT5 chart object API unavailable in installed MetaTrader5 package.")
            return

        logger.info(
            "MT5 analysis drawing is not available in this runtime environment.")

    def modify_position(self, position_id: int, stop_loss: float | None = None, take_profit: float | None = None) -> dict[str, Any]:
        """Modify SL/TP on an existing position."""
        self.connect()
        mt5_module = self._require_mt5()
        positions = mt5_module.positions_get(ticket=position_id)
        if not positions:
            raise RuntimeError(f"MT5 position {position_id} was not found")
        position = positions[0]
        request: dict[str, Any] = {
            "action": mt5_module.TRADE_ACTION_SLTP,
            "symbol": position.symbol,
            "position": position.ticket,
            "sl": float(stop_loss if stop_loss is not None else position.sl),
            "tp": float(take_profit if take_profit is not None else position.tp),
            "magic": 123456,
        }
        result = mt5_module.order_send(request)
        if result is None or result.retcode != mt5_module.TRADE_RETCODE_DONE:
            raise RuntimeError(
                f"MT5 position modification failed: {self._mt5_error_message(result)}")
        return {"status": "modified", "position_id": position_id, "sl": request["sl"], "tp": request["tp"]}

    def close_position(self, position_id: int, volume: float | None = None) -> dict[str, Any]:
        self.connect()
        mt5_module = self._require_mt5()
        positions = mt5_module.positions_get(ticket=position_id)
        if not positions:
            raise RuntimeError(f"MT5 position {position_id} was not found")

        position = positions[0]
        tick = mt5_module.symbol_info_tick(position.symbol)
        if tick is None:
            raise RuntimeError(
                f"MT5 could not fetch tick data for {position.symbol}")

        close_request: dict[str, Any] = {
            "action": mt5_module.TRADE_ACTION_DEAL,
            "symbol": position.symbol,
            "volume": float(volume if volume is not None else position.volume),
            "type": mt5_module.ORDER_TYPE_SELL if position.type == mt5_module.ORDER_TYPE_BUY else mt5_module.ORDER_TYPE_BUY,
            "price": tick.ask if position.type == mt5_module.ORDER_TYPE_BUY else tick.bid,
            "deviation": 20,
            "magic": 123456,
            "comment": "bot-close",
            "type_time": mt5_module.ORDER_TIME_GTC,
            "type_filling": mt5_module.ORDER_FILLING_IOC,
        }
        result = mt5_module.order_send(close_request)
        if result is None:
            raise RuntimeError("MT5 position close returned no result")
        if result.retcode != mt5_module.TRADE_RETCODE_DONE:
            raise RuntimeError(
                f"MT5 position close failed with code {result.retcode}")
        return {"status": "closed", "position_id": str(position_id)}

    def get_open_positions(self, bot_only: bool = False) -> list[dict[str, Any]]:
        """Fetch open positions, optionally limited to this bot's magic number."""
        self.connect()
        mt5_module = self._require_mt5()
        positions = mt5_module.positions_get()

        if not positions:
            return []

        result: list[dict[str, Any]] = []
        for pos in positions:
            magic = int(getattr(pos, "magic", 0) or 0)
            if bot_only and magic != 123456:
                continue
            comment = str(getattr(pos, "comment", "") or "")
            score_match = re.search(r"score:(\d+(?:\.\d+)?)", comment)
            score = float(score_match.group(1)) if score_match else 0.0
            pnl_pct = (pos.profit / (pos.price_open * pos.volume * 100000)
                       ) * 100 if pos.price_open and pos.volume else 0.0
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
                "magic": magic,
                "score": score,
                "open_time": (
                    datetime.fromtimestamp(int(pos.time), tz=timezone.utc)
                    if getattr(pos, "time", None)
                    else None
                ),
            })

        return result
