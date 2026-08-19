"""Self-aware, adaptive Forex trading bot."""
from __future__ import annotations

import argparse
import time
from datetime import date, datetime
from typing import Any

import pandas as pd
import pytz
from sqlalchemy import text

from config import settings
from core.portfolio_manager import PortfolioManager
from core.self_diagnostic import CycleReport
from data.ingestor import fetch_mt5_ohlcv
from data.preprocessor import prepare_ohlcv
from db.repository import Repository
from execution.mt5_client import MT5Client
from filter.liquidity_filter import LowLiquidityFilter
from filter.news_filter import NewsFilter
from filter.trading_filter import TradingFilter
from filter.weekend_filter import WeekendFilter
from notifications.telegram_sender import TelegramSender
from regime.market_regime import MarketRegime
from risk.manager import RiskManager
from signals.signal_engine import SignalEngine
from smc.structure import StructureDetector
from strategies.breakout_strategy import BreakoutStrategy
from strategies.mean_reversion import MeanReversionStrategy
from strategies.trend_strategy import TrendStrategy
from structure.candlestick_validator import CandlestickValidator
from structure.swing_detector import detect_swings
from utils.logger import get_logger

logger = get_logger("bot")


class AdaptiveTradingBot:
    """Self-aware, adaptive trading bot with multi-cycle support."""

    def __init__(self) -> None:
        """Initialize bot components and state."""
        self.mt5_client = MT5Client(settings.mt5_account, settings.mt5_password, settings.mt5_server)
        self.risk_manager = RiskManager(
            account_balance=float(settings.account_balance),
            daily_loss=0.0,
            current_equity=None,
            peak_equity=None,
        )
        self.telegram_sender = TelegramSender(settings.telegram_token, settings.telegram_chat_id)
        self.news_filter = NewsFilter()
        self.weekend_filter = WeekendFilter()
        self.liquidity_filter = LowLiquidityFilter()
        self.trading_filter = TradingFilter(self.news_filter, self.weekend_filter, self.liquidity_filter)
        self.signal_engine = SignalEngine()
        self.candlestick_validator = CandlestickValidator()
        self.repository = Repository(settings.database_url)
        self.portfolio_manager = PortfolioManager({"TRADING_PAIRS": settings.trading_pairs})

        self.trading_pairs = settings.trading_pairs
        self.pair_timeframes = settings.pair_timeframes
        self.pair_risk_allocation = settings.pair_risk_allocation

        self.last_cycle_time: datetime | None = None
        self.open_positions: dict[int, dict[str, Any]] = {}
        self.monitoring_positions: list[int] = []
        self.diagnostic_reports: list[CycleReport] = []
        self._unavailable_symbols: set[str] = set()
        self._last_reset_date: date | None = None
        self.error_count = 0
        self.max_errors = 10
        self.last_health_check: datetime | None = None

        self.cycle_types = {
            "standard": 900,
            "micro": 120,
            "monitoring": 30,
            "emergency": 5,
        }

    def run(self) -> None:
        """Main bot loop with adaptive cycle timing."""
        logger.info("Bot starting...")

        initial_report = self.health_check()
        if not initial_report.is_healthy():
            logger.critical("Initial health check failed: %s", initial_report.summary())
            try:
                self.telegram_sender.send(f"🚨 Bot health check failed: {initial_report.summary()}")
            except Exception:
                logger.warning("Telegram health alert failed")
            return

        try:
            self.telegram_sender.send("🚀 Bot started successfully (self-aware mode)")
        except Exception:
            logger.warning("Telegram startup alert failed")

        while True:
            try:
                cycle_type = self._determine_cycle_type()
                report = self.run_cycle(cycle_type)
                self.diagnostic_reports.append(report)
                logger.info(report.summary())

                if report.errors:
                    self.error_count += 1
                    if self.error_count >= self.max_errors:
                        logger.critical("Max errors reached, shutting down")
                        try:
                            self.telegram_sender.send("🚨 CRITICAL: Max errors reached, bot shutting down")
                        except Exception:
                            pass
                        raise RuntimeError("Max errors reached")
                else:
                    self.error_count = 0

                sleep_time = self.cycle_types.get(cycle_type, 900)
                self.last_cycle_time = datetime.now(pytz.UTC)
                time.sleep(sleep_time)

            except KeyboardInterrupt:
                logger.info("Bot stopped by user")
                try:
                    self.telegram_sender.send("🛑 Bot stopped by user")
                except Exception:
                    pass
                break
            except Exception as exc:
                logger.exception("Unhandled error: %s", exc)
                try:
                    self.telegram_sender.send(f"⚠️ Bot error: {str(exc)[:100]}")
                except Exception:
                    pass
                self.error_count += 1
                time.sleep(60)

    def _determine_cycle_type(self) -> str:
        """Choose the appropriate cycle type based on market and risk conditions."""
        now = datetime.now(pytz.UTC)

        if self._has_emergency_positions():
            return "emergency"
        if self._has_open_positions():
            return "monitoring"
        if self._has_pending_signals():
            return "micro"
        if now.minute % 15 == 0:
            return "standard"
        return "micro"

    def _has_emergency_positions(self) -> bool:
        """Return true if any open position is near stop loss or risk threshold."""
        for pos in self.open_positions.values():
            if bool(pos.get("danger", False)):
                return True
        return False

    def _has_open_positions(self) -> bool:
        """Return true if there are tracked open positions."""
        return bool(self.open_positions)

    def _has_pending_signals(self) -> bool:
        """Return true if confirmation cycle should run before entry."""
        return False

    def health_check(self) -> CycleReport:
        """Run a comprehensive health check across key bot subsystems."""
        report = CycleReport(datetime.now(pytz.UTC), "health")

        try:
            if settings.use_mt5_execution and not self.mt5_client.is_configured():
                report.add_check("MT5 Configuration", False, "MT5 not configured")
            else:
                self.mt5_client.connect()
                balance = self.mt5_client.get_balance()
                report.add_check("MT5 Connection", True, f"Connected, balance: ${balance:.2f}")
                report.add_success("MT5 connected")
        except Exception as exc:
            report.add_check("MT5 Connection", False, str(exc))
            report.add_error(f"MT5 connection failed: {exc}")

        try:
            with self.repository.session() as session:
                session.execute(text("SELECT 1"))
            report.add_check("Database", True, "Connected and responsive")
            report.add_success("Database healthy")
        except Exception as exc:
            report.add_check("Database", False, str(exc))
            report.add_error(f"Database check failed: {exc}")

        try:
            data = fetch_mt5_ohlcv(days=1, timeframe="15m", symbol="EURUSD")
            if data.empty:
                report.add_check("Data Fetching", False, "No data received")
                report.add_error("Data fetching returned empty OHLCV frame")
            else:
                report.add_check("Data Fetching", True, f"Received {len(data)} candles")
                report.add_success("Market data available")
        except Exception as exc:
            report.add_check("Data Fetching", False, str(exc))
            report.add_error(f"Data fetch failed: {exc}")

        try:
            if settings.telegram_token and settings.telegram_chat_id:
                success = self.telegram_sender.send("🩺 Health check: Bot is alive")
                report.add_check("Telegram", bool(success), "Alert send status")
                if success:
                    report.add_success("Telegram alerting healthy")
            else:
                report.add_check("Telegram", True, "Not configured (skipped)")
        except Exception as exc:
            report.add_check("Telegram", False, str(exc))
            report.add_error(f"Telegram alerting failed: {exc}")

        try:
            limits_ok, limits_reason = self.portfolio_manager.check_global_limits()
            report.add_check("Portfolio Limits", limits_ok, limits_reason)
            if limits_ok:
                report.add_success("Portfolio limits valid")
        except Exception as exc:
            report.add_check("Portfolio Limits", False, str(exc))
            report.add_error(f"Portfolio limit check failed: {exc}")

        self.last_health_check = datetime.now(pytz.UTC)
        return report

    def run_cycle(self, cycle_type: str) -> CycleReport:
        """Execute a full trading cycle and return a diagnostic report."""
        report = CycleReport(datetime.now(pytz.UTC), cycle_type)
        report.add_success(f"Starting {cycle_type} cycle")

        current_time = datetime.now(pytz.UTC)
        self._reset_daily_stats(current_time)

        filter_result = self.trading_filter.should_trade(current_time)
        if not filter_result["trade"]:
            report.add_check("Safety Gates", False, filter_result["reason"])
            report.add_warning(f"Trading blocked: {filter_result['reason']}")
            return report
        report.add_check("Safety Gates", True, "All safety gates passed")
        report.add_success("Safety gates passed")

        limits_ok, limits_reason = self.portfolio_manager.check_global_limits()
        if not limits_ok:
            report.add_check("Portfolio Limits", False, limits_reason)
            report.add_warning(f"Portfolio limit hit: {limits_reason}")
            return report
        report.add_check("Portfolio Limits", True, limits_reason)

        pairs_processed = 0
        pairs_skipped = 0
        signals_generated = 0
        trades_executed = 0

        for symbol in self.trading_pairs:
            try:
                result = self._process_pair(symbol, current_time)
                if result.get("skipped"):
                    pairs_skipped += 1
                else:
                    pairs_processed += 1
                if result.get("signal_generated"):
                    signals_generated += 1
                if result.get("trade_executed"):
                    trades_executed += 1
            except Exception as exc:
                report.add_error(f"Error processing {symbol}: {exc}")

        report.pairs_processed = pairs_processed
        report.pairs_skipped = pairs_skipped
        report.signals_generated = signals_generated
        report.trades_executed = trades_executed

        if cycle_type in {"monitoring", "emergency"}:
            self._monitor_positions(report)

        return report

    def _process_pair(self, symbol: str, current_time: datetime) -> dict[str, Any]:
        """Process one symbol across multiple timeframes, validate candlesticks, and score the trade."""
        result: dict[str, Any] = {"skipped": True, "signal_generated": False, "trade_executed": False}
        risk_allocation = self.pair_risk_allocation.get(symbol, 0.005)

        if symbol in self._unavailable_symbols:
            return result

        try:
            resolved_symbol = self.mt5_client.resolve_symbol(symbol)
            frames: dict[str, pd.DataFrame] = {}
            for tf in ("4h", "1h", "15m"):
                data = fetch_mt5_ohlcv(days=180, timeframe=tf, symbol=resolved_symbol)
                frame = prepare_ohlcv(data)
                if frame.empty:
                    raise ValueError(f"No {tf} OHLCV data for {resolved_symbol}")
                frames[tf] = frame

            swings: dict[str, Any] = {}
            for tf in ("4h", "1h", "15m"):
                swings[tf] = detect_swings(frames[tf])

            structures: dict[str, Any] = {}
            for tf in ("4h", "1h", "15m"):
                structures[tf] = StructureDetector(swings[tf], frames[tf])

            regimes: dict[str, dict[str, Any]] = {}
            for tf in ("4h", "1h", "15m"):
                regimes[tf] = MarketRegime(frames[tf]).get_regime()
            logger.info(
                "%s: 4H=%s | 1H=%s | 15M=%s",
                symbol,
                regimes["4h"]["regime"],
                regimes["1h"]["regime"],
                regimes["15m"]["regime"],
            )

            signal = self._select_strategy_and_signal(frames["15m"], regimes["15m"])
            if signal["signal"] == "none":
                logger.info("%s: No signal generated", symbol)
                return result

            candle_result = self.candlestick_validator.validate(frames["15m"], signal["signal"])
            if candle_result.get("confirmed"):
                logger.info(
                    "%s: Candlestick confirmed %s (+%.0f%%)",
                    symbol,
                    candle_result.get("pattern_name"),
                    float(candle_result.get("bonus", 0.0)) * 100,
                )

            struct_dict = {
                "bos_4h": structures["4h"].detect_bos(),
                "bos_1h": structures["1h"].detect_bos(),
                "bos_15m": structures["15m"].detect_bos(),
                "choch_4h": structures["4h"].detect_choch(),
                "choch_1h": structures["1h"].detect_choch(),
                "choch_15m": structures["15m"].detect_choch(),
            }

            scored = self.signal_engine.score_multi_timeframe(
                signal=signal,
                h4_regime=regimes["4h"],
                h1_regime=regimes["1h"],
                m15_regime=regimes["15m"],
                structure=struct_dict,
                frame_15m=frames["15m"],
                candlestick_result=candle_result,
            )
            logger.info("%s: Signal scored %s (%s)", symbol, scored["score"], scored["grade"])

            if scored["score"] < settings.min_score:
                logger.info("%s: Score %s < %s threshold, skipping", symbol, scored["score"], settings.min_score)
                return result

            result["signal_generated"] = True
            entry = signal.get("entry", 0.0)
            sl = signal.get("stop_loss", 0.0)
            tp = signal.get("take_profit", 0.0)

            if not all([entry > 0, sl > 0, tp > 0]):
                logger.warning("%s: Invalid signal prices (entry=%s, sl=%s, tp=%s)", symbol, entry, sl, tp)
                return result

            if signal["signal"] == "buy":
                if not (entry > sl and entry < tp):
                    logger.warning("%s: Invalid BUY levels (SL=%s, entry=%s, TP=%s)", symbol, sl, entry, tp)
                    return result
            elif signal["signal"] == "sell":
                if not (entry < sl and entry > tp):
                    logger.warning("%s: Invalid SELL levels (SL=%s, entry=%s, TP=%s)", symbol, sl, entry, tp)
                    return result

            pair_state = self.portfolio_manager.get_pair_state(symbol)
            if pair_state.consecutive_losses >= 3:
                logger.info("%s: Paused due to 3 consecutive losses", symbol)
                return result

            if self.portfolio_manager.total_open_positions >= settings.global_max_concurrent_positions:
                logger.info("%s: Global max positions reached (%s)", symbol, self.portfolio_manager.total_open_positions)
                return result

            self._execute_trade(resolved_symbol, signal, scored, regimes["1h"], risk_allocation)
            result["trade_executed"] = True
            result["skipped"] = False
            return result

        except Exception as exc:
            message = str(exc)
            if "not found in MT5" in message or "symbol discovery is unavailable" in message:
                self._unavailable_symbols.add(symbol)
                logger.warning("%s unavailable in MT5; skipping it for this bot run", symbol)
                return result
            logger.error("%s: Error - %s", symbol, exc)
            return result

    def _monitor_positions(self, report: CycleReport) -> None:
        """Monitor live open positions and update diagnostic report."""
        try:
            positions = self.mt5_client.get_open_positions()
            self.open_positions = {pos["ticket"]: pos for pos in positions}
            if positions:
                report.add_check("Position Monitoring", True, f"Monitoring {len(positions)} positions")
                for pos in positions:
                    report.add_success(f"Position {pos['ticket']}: PnL=${pos.get('pnl', 0.0):.2f}")
            else:
                report.add_check("Position Monitoring", True, "No open positions")
        except Exception as exc:
            report.add_check("Position Monitoring", False, str(exc))
            report.add_error(f"Position monitoring failed: {exc}")

    def _reset_daily_stats(self, current_time: datetime) -> None:
        """Reset daily totals at midnight UTC."""
        if self._last_reset_date != current_time.date():
            if self._last_reset_date is not None:
                logger.info("Daily reset: clearing daily PnL (was $%.2f)", self.portfolio_manager.global_daily_pnl)
                self.portfolio_manager.global_daily_pnl = 0.0
            self._last_reset_date = current_time.date()

    def _select_strategy_and_signal(self, frame: Any, regime: dict[str, Any]) -> dict[str, Any]:
        """Select and generate the directional signal based on the active regime."""
        if regime["regime"] == "trending":
            strategy = TrendStrategy(frame, regime)
        elif regime["regime"] == "ranging":
            strategy = MeanReversionStrategy(frame, regime)
        else:
            strategy = BreakoutStrategy(frame, regime)
        return strategy.generate_signal()

    def _execute_trade(
        self,
        symbol: str,
        signal: dict[str, Any],
        scored: dict[str, Any],
        regime: dict[str, Any],
        risk_allocation: float,
    ) -> None:
        """Execute the trade only after validation, risk gating, and MT5 checks pass."""
        try:
            if signal["signal"] not in ("buy", "sell"):
                raise ValueError(f"Invalid signal: {signal['signal']}")

            if not settings.use_mt5_execution or not self.mt5_client.is_configured():
                logger.warning("%s: MT5 execution disabled or not configured", symbol)
                return

            entry_price = float(signal.get("entry", 0.0))
            stop_loss = float(signal.get("stop_loss", 0.0))
            risk_per_unit = abs(entry_price - stop_loss)
            if risk_per_unit <= 0:
                raise ValueError(f"Invalid risk distance: entry={entry_price}, SL={stop_loss}")

            account_balance = float(settings.account_balance)
            risk_amount = account_balance * risk_allocation
            lots = risk_amount / (risk_per_unit * 100000)
            lots = round(max(0.01, min(lots, 1.0)), 2)

            order_result = self.mt5_client.place_order(
                symbol=symbol,
                order_type=signal["signal"],
                lots=lots,
                stop_loss=stop_loss,
                take_profit=float(signal.get("take_profit", 0.0)),
                comment=f"score:{scored['score']}|regime:{regime['regime']}",
            )

            if order_result.get("status") != "accepted":
                logger.error("%s: Order rejected: %s", symbol, order_result)
                self.repository.add_failed_order({
                    "symbol": symbol,
                    "order_type": signal["signal"],
                    "volume": lots,
                    "error_code": order_result.get("error_code"),
                    "error_message": str(order_result),
                })
                self.telegram_sender.send(
                    f"⚠️ Order failed on {symbol}: {order_result.get('error_message', 'Unknown error')}"
                )
                return

            logger.info("%s: Order placed: ticket=%s status=%s", symbol, order_result.get("ticket"), order_result.get("status"))
            self.portfolio_manager.update_position_state(symbol, {
                "ticket": order_result.get("ticket"),
                "symbol": symbol,
                "direction": signal["signal"],
                "entry_price": entry_price,
                "stop_loss": stop_loss,
                "take_profit": signal.get("take_profit"),
                "volume": lots,
            })

            msg = (
                f"🟢 Trade Opened\n"
                f"Symbol: {symbol}\n"
                f"Side: {signal['signal'].upper()}\n"
                f"Score: {scored['score']}/100 ({scored['grade']})\n"
                f"Regime: {regime['regime']}\n"
                f"Size: {lots:.2f} lots\n"
                f"Ticket: {order_result.get('ticket')}"
            )
            try:
                self.telegram_sender.send(msg)
            except Exception:
                logger.warning("Telegram trade alert failed for %s", symbol)

        except Exception as exc:
            logger.exception("%s: Trade execution failed: %s", symbol, exc)
            try:
                self.telegram_sender.send(f"❌ Trade failed on {symbol}: {str(exc)[:100]}")
            except Exception:
                pass

    def run_test_order(self, symbol: str, direction: str, live: bool = False) -> None:
        """Validate or place one manually requested market order for testing."""
        symbol = symbol.strip().upper()
        direction = direction.strip().lower()
        if not symbol:
            raise ValueError("A symbol is required")
        if direction not in {"buy", "sell"}:
            raise ValueError("Direction must be 'buy' or 'sell'")

        if live and not settings.use_mt5_execution:
            raise RuntimeError("Live test orders require USE_MT5_EXECUTION=true")
        if live and not self.mt5_client.is_configured():
            raise RuntimeError("Live test orders require MT5_ACCOUNT, MT5_PASSWORD, and MT5_SERVER")

        self.mt5_client.connect()
        prices = self.mt5_client.get_price(symbol)
        entry = prices["ask"] if direction == "buy" else prices["bid"]
        atr = self.mt5_client.get_atr(symbol)
        if entry <= 0 or atr <= 0:
            raise RuntimeError(f"Invalid live market data for {symbol}: entry={entry}, atr={atr}")

        stop_distance = atr * 1.5
        target_distance = atr * 3.0
        stop_loss = entry - stop_distance if direction == "buy" else entry + stop_distance
        take_profit = entry + target_distance if direction == "buy" else entry - target_distance
        risk_allocation = self.pair_risk_allocation.get(symbol, settings.risk_per_trade)
        risk_amount = float(settings.account_balance) * risk_allocation
        lots = risk_amount / (stop_distance * 100000)
        lots = round(max(0.01, min(lots, 1.0)), 2)

        order_plan: dict[str, Any] = {
            "symbol": symbol,
            "direction": direction,
            "entry": entry,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "lots": lots,
            "live": live,
        }
        logger.info("Test order plan: %s", order_plan)

        if not live:
            logger.info("Dry-run only: no order was submitted")
            return

        result = self.mt5_client.place_order(
            symbol=symbol,
            order_type=direction,
            lots=lots,
            stop_loss=stop_loss,
            take_profit=take_profit,
            reference_entry_price=entry,
            comment="manual-test-order",
        )
        if result.get("status") != "accepted":
            raise RuntimeError(f"Test order was not accepted: {result}")
        logger.info("Test order accepted: %s", result)


def main() -> None:
    """Entry point for the adaptive trading bot."""
    parser = argparse.ArgumentParser(description="Run the adaptive Forex trading bot.")
    parser.add_argument(
        "--test-order",
        metavar="SYMBOL",
        help="Validate and optionally place one test market order for an MT5 symbol.",
    )
    parser.add_argument(
        "--direction",
        choices=("buy", "sell"),
        default="buy",
        help="Direction for --test-order (default: buy).",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Actually submit the test order; without this flag the command is dry-run only.",
    )
    args = parser.parse_args()

    if args.test_order:
        bot = AdaptiveTradingBot()
        bot.run_test_order(args.test_order, args.direction, live=args.live)
        return

    bot = AdaptiveTradingBot()
    bot.run()


if __name__ == "__main__":
    main()