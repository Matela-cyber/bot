"""Main entry point for the Mean Reversion bot."""

from __future__ import annotations

import logging
import time
import pandas as pd
from datetime import date, datetime, timezone, timedelta
from typing import Any

from config import config
from db.models import Trade, init_db
from db.repository import TradeRepository
from execution.mt5_client import MT5Client
from execution.order_handler import OrderHandler
from filter.trading_filter import TradingFilter
from notifications.telegram_sender import TelegramSender
from risk.manager import RiskManager
from strategies.trinity_strategy import TrinityStrategy
from utils.helpers import calculate_pip_value, utc_now
from utils.logger import setup_logger


class MeanReversionBot:
    """Mean Reversion bot - 7 pairs, 3% risk, Monday/Thursday, 0,5,11 UTC."""

    def __init__(self) -> None:
        self.config = config
        self.logger = self._setup_logging()

        self.logger.info("=" * 60)
        self.logger.info("MEAN REVERSION BOT v2.0")
        self.logger.info("=" * 60)
        self.logger.info(f"Pairs: {self.config.trading_pairs}")
        self.logger.info(f"Risk: {self.config.risk_per_trade * 100:.1f}%")
        self.logger.info(f"Timeframe: {self.config.timeframe}")
        self.logger.info(f"Cycle: {self.config.cycle_interval}s")
        self.logger.info("=" * 60)

        # Database
        self.db_engine = init_db(self.config.db_path)
        self.repository = TradeRepository(engine=self.db_engine)

        # MT5
        self.mt5_client = MT5Client()
        self.order_handler = OrderHandler(self.mt5_client)

        # Risk
        self.risk_manager = RiskManager(self.config)

        # Filters
        self.trading_filter = TradingFilter(self.config, self.mt5_client)

        # Telegram
        self.telegram = TelegramSender(
            self.config.telegram_token,
            self.config.telegram_chat_id
        )

        # State
        self.performance: dict[str, Any] = {
            "cycles": 0,
            "signals": 0,
            "trades": 0,
            "wins": 0,
            "losses": 0,
            "pnl": 0.0,
            "win_rate": 0.0,
            "errors": 0,
            "started_at": None,
        }
        self.last_reset_date = datetime.now(timezone.utc).date()
        self.trading_enabled = True
        self.running = False
        self.active_pairs = self.config.trading_pairs
        self._tracked_trade_ids: dict[int, int] = {}

    def _setup_logging(self) -> logging.Logger:
        return setup_logger("trinity", self.config.log_level)

    def run(self) -> None:
        """Main bot loop."""
        self.running = True
        self.performance["started_at"] = datetime.now().isoformat()

        try:
            # Connect to MT5
            if not self.mt5_client.initialize(self.config.mt5_path):
                self.logger.error("MT5 connection failed")
                self._notify("❌ Bot failed: MT5 connection error")
                return

            self.logger.info("✅ MT5 connection established")
            self._notify(
                f"<b>MEAN REVERSION BOT STARTED</b>\n"
                f"Pairs: {len(self.config.trading_pairs)}\n"
                f"Risk: {self.config.risk_per_trade * 100:.1f}%\n"
                f"Timeframe: {self.config.timeframe}"
            )

            while self.running:
                self._check_daily_reset()

                # Sleep on non-trading days
                if not self._is_trading_day():
                    sleep_seconds = self._get_sleep_until_next_trading_day()
                    self.logger.info(f"💤 Non-trading day. Sleeping {sleep_seconds/3600:.1f}h")
                    time.sleep(sleep_seconds)
                    continue

                # Sleep outside active hours
                if not self._is_active_hour():
                    sleep_seconds = self._get_sleep_until_next_active_hour()
                    if sleep_seconds > 60:
                        self.logger.info(f"💤 Outside active hours. Sleeping {sleep_seconds/60:.0f}m")
                        time.sleep(sleep_seconds)
                        continue

                try:
                    self._process_cycle()
                except Exception as exc:
                    self.performance["errors"] += 1
                    self.logger.exception("Cycle failed: %s", exc)
                    self._notify(f"❌ Cycle error: {str(exc)[:200]}")

                if self.running:
                    time.sleep(self.config.cycle_interval)

        except KeyboardInterrupt:
            self.logger.info("Keyboard interrupt received")
        except Exception as exc:
            self.performance["errors"] += 1
            self.logger.exception("Bot crashed: %s", exc)
            self._notify(f"❌ Bot crashed: {str(exc)[:200]}")
        finally:
            self.running = False
            self.mt5_client.shutdown()
            self.repository.close()
            self._notify(
                f"<b>Bot stopped</b>\n"
                f"Trades: {self.performance['trades']}\n"
                f"PnL: ${self.performance['pnl']:.2f}\n"
                f"Win Rate: {self.performance['win_rate']:.1f}%"
            )
            self.logger.info("Bot shutdown complete")

    def _process_cycle(self) -> None:
        """Process one trading cycle."""
        self.performance["cycles"] += 1

        # Manage existing positions
        self._manage_positions()

        # Check risk limits
        if not self._check_risk_limits():
            return

        # Process each pair
        for pair in self.active_pairs:
            try:
                self._process_pair(pair)
            except Exception as exc:
                self.performance["errors"] += 1
                self.logger.exception("Pair %s failed: %s", pair, exc)

    def _process_pair(self, pair: str) -> None:
        """Process a single pair."""
        # Fetch data
        data = self._fetch_data(pair)
        if data.empty:
            return

        # Apply filters
        if not self.trading_filter.should_trade(data):
            return

        # Generate signal
        strategy = TrinityStrategy(
            frame=data,
            higher_tf=None,
            structure={},
            current_time=utc_now(),
            config=self.config,
        )
        strategy.pair = pair

        signal = strategy.generate_signal()

        if signal.get("signal") in ["buy", "sell"]:
            self.performance["signals"] += 1
            self._handle_signal(signal, pair, data)

    def _fetch_data(self, pair: str) -> pd.DataFrame:
        try:
            return self.mt5_client.get_rates(
                symbol=pair,
                timeframe=self.config.timeframe,
                bars=500
            )
        except Exception as exc:
            self.logger.error("Failed to fetch %s: %s", pair, exc)
            return pd.DataFrame()

    def _handle_signal(self, signal: dict[str, Any], pair: str, data: pd.DataFrame) -> bool:
        try:
            direction = signal.get("signal")
            trade_plan = signal.get("trade")

            if not direction or not trade_plan:
                return False

            positions = self.mt5_client.get_open_positions(pair)
            if len(positions) >= self.config.max_positions_per_pair:
                return False

            all_positions = self.mt5_client.get_open_positions()
            if len(all_positions) >= self.config.max_total_positions:
                return False

            if not self.risk_manager.can_open_position():
                return False

            confidence = signal.get("confidence", 0.0)
            if confidence < self.config.mr_min_confidence:
                return False

            entry = float(trade_plan["entry"])
            stop_loss = float(trade_plan["stop_loss"])
            take_profit = float(trade_plan["take_profit"])

            account_balance = self.mt5_client.get_account_balance()
            risk_amount = account_balance * self.config.risk_per_trade
            sl_pips = abs(entry - stop_loss) / 0.0001

            if sl_pips <= 0:
                return False

            pip_value = calculate_pip_value(entry)
            position_size = risk_amount / (sl_pips * pip_value)
            position_size = max(0.01, min(10, round(position_size, 2)))

            result = self.order_handler.place_order(
                pair, direction, entry, stop_loss, take_profit, position_size
            )

            if not result.get("success"):
                self.logger.error("Order failed for %s: %s", pair, result.get("error"))
                return False

            order_id = result.get("order_id")
            saved_trade = self.repository.save_trade(Trade(
                symbol=pair,
                direction=direction,
                entry_price=result.get("price", entry),
                stop_loss=stop_loss,
                take_profit=take_profit,
                position_size=result.get("volume", position_size),
                entry_time=utc_now(),
                strategy="mean_reversion",
                confidence=confidence,
                notes=f"order_id={order_id}",
            ))

            if order_id is not None:
                self._tracked_trade_ids[int(order_id)] = saved_trade.id

            self.performance["trades"] += 1

            self._notify_trade(signal, pair, position_size)
            self.logger.info(
                "✅ %s %s at %.5f (SL: %.5f, TP: %.5f, Size: %.2f)",
                direction.upper(), pair, entry, stop_loss, take_profit, position_size
            )

            return True

        except Exception as exc:
            self.performance["errors"] += 1
            self.logger.exception("Signal handling failed for %s: %s", pair, exc)
            return False

    def _manage_positions(self) -> None:
        try:
            positions = self.mt5_client.get_open_positions()

            for position in positions:
                ticket = int(getattr(position, "ticket"))
                entry = float(getattr(position, "price_open"))
                current = float(getattr(position, "price_current"))
                is_buy = self._is_buy_position(position)

                if is_buy:
                    profit_pips = (current - entry) / 0.0001
                else:
                    profit_pips = (entry - current) / 0.0001

                if profit_pips >= 15:
                    self.order_handler.modify_stop_loss(position.symbol, entry, ticket)

                if profit_pips >= 30:
                    if self.order_handler.close_partial(position.symbol, 50.0, ticket):
                        self.logger.info("Partial exit (50%%) at %.1f pips", profit_pips)

        except Exception as exc:
            self.logger.exception("Position management failed: %s", exc)

    def _check_risk_limits(self) -> bool:
        daily_limit = self.risk_manager.starting_balance * abs(self.config.max_daily_loss)
        exceeded = self.risk_manager.daily_loss >= daily_limit or self.risk_manager.check_drawdown()

        if exceeded:
            if self.trading_enabled:
                self.logger.error("Risk limit exceeded; trading disabled")
                self._notify("⚠️ Risk limit exceeded; trading disabled")
            self.trading_enabled = False
            return False

        return self.trading_enabled

    def _check_daily_reset(self) -> None:
        today = datetime.now(timezone.utc).date()
        if today != self.last_reset_date:
            self.logger.info(
                "Previous day: trades=%d, loss=%.2f, drawdown=%.4f",
                self.risk_manager.daily_trades,
                self.risk_manager.daily_loss,
                self.risk_manager.max_drawdown,
            )
            self.risk_manager.reset_daily_stats()
            self.last_reset_date = today
            self.trading_enabled = True
            self.logger.info("Daily stats reset for %s", today)

    def _is_trading_day(self) -> bool:
        """Monday (0) or Thursday (3)."""
        return datetime.now(timezone.utc).weekday() in [0, 3]

    def _is_active_hour(self) -> bool:
        """00:00, 05:00, or 11:00 UTC."""
        return datetime.now(timezone.utc).hour in [0, 5, 11]

    def _get_sleep_until_next_trading_day(self) -> int:
        """Calculate seconds until the next trading day."""
        now = datetime.now(timezone.utc)
        weekday = now.weekday()

        days_until = {
            0: 3,  # Mon → Thu
            1: 2,  # Tue → Thu
            2: 1,  # Wed → Thu
            3: 4,  # Thu → Mon
            4: 3,  # Fri → Mon
            5: 2,  # Sat → Mon
            6: 1,  # Sun → Mon
        }

        next_day = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(
            days=days_until.get(weekday, 1)
        )
        seconds = int((next_day - now).total_seconds())
        return max(60, seconds)

    def _get_sleep_until_next_active_hour(self) -> int:
        """Calculate seconds until the next active hour (FIXED)."""
        now = datetime.now(timezone.utc)
        current_hour = now.hour
        active_hours = [0, 5, 11]

        # Find next active hour today
        next_hour = None
        for hour in active_hours:
            if hour > current_hour:
                next_hour = hour
                break

        if next_hour is None:
            # No active hour left today → next day at 00:00 UTC
            next_time = (now + timedelta(days=1)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
        else:
            # Active hour later today
            next_time = now.replace(
                hour=next_hour, minute=0, second=0, microsecond=0
            )

        seconds = int((next_time - now).total_seconds())
        return max(60, seconds)

    @staticmethod
    def _is_buy_position(position: Any) -> bool:
        return getattr(position, "type", None) == 0

    def _notify(self, message: str) -> None:
        if self.config.is_telegram_enabled():
            self.telegram.send_message(message)

    def _notify_trade(self, signal: dict, pair: str, size: float) -> None:
        if self.config.is_telegram_enabled():
            self.telegram.send_trade_signal({
                **signal,
                "symbol": pair,
                "size": size,
            })


if __name__ == "__main__":
    MeanReversionBot().run()