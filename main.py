"""New orchestrator for regime-based bot with multi-pair support."""
from __future__ import annotations

import time
from datetime import datetime
from typing import Any

import pytz
from sqlalchemy import text

from config import settings
from data.ingestor import fetch_mt5_ohlcv
from data.preprocessor import prepare_ohlcv
from structure.swing_detector import detect_swings
from regime.market_regime import MarketRegime
from strategies.trend_strategy import TrendStrategy
from strategies.mean_reversion import MeanReversionStrategy
from strategies.breakout_strategy import BreakoutStrategy
from signals.signal_engine import SignalEngine
from smc.structure import StructureDetector
from execution.mt5_client import MT5Client
from risk.manager import RiskManager
from notifications.telegram_sender import TelegramSender
from db.repository import Repository
from utils.logger import get_logger
from filter.trading_filter import TradingFilter
from filter.news_filter import NewsFilter
from filter.weekend_filter import WeekendFilter
from filter.liquidity_filter import LowLiquidityFilter
from core.portfolio_manager import PortfolioManager

logger = get_logger("bot")


class RegimeBasedBot:
    """Regime-adaptive trading bot with multi-pair support."""

    def __init__(self) -> None:
        """Initialize bot components."""
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
        self.repository = Repository(settings.database_url)
        self.portfolio_manager = PortfolioManager({"TRADING_PAIRS": settings.trading_pairs})

        # Trading pairs and their timeframes from settings
        self.trading_pairs = settings.trading_pairs
        self.pair_timeframes = settings.pair_timeframes
        self.pair_risk_allocation = settings.pair_risk_allocation

        # Track daily reset
        self._last_reset_date = None

    def health_check(self) -> tuple[bool, str]:
        """Verify bot can connect to MT5 and fetch data."""
        try:
            # Check MT5
            if settings.use_mt5_execution and not self.mt5_client.is_configured():
                return False, "MT5 not configured"

            # Check database
            with self.repository.session() as session:
                session.execute(text("SELECT 1"))

            # Check recent data
            data = fetch_mt5_ohlcv(days=1, timeframe="15m", symbol="EURUSD")
            if data.empty:
                return False, "No market data available"

            logger.info("Health check passed")
            return True, "Healthy"

        except Exception as e:
            return False, str(e)

    def _reset_daily_stats(self, current_time: datetime) -> None:
        """Reset daily PnL at midnight UTC."""
        current_date = current_time.date()
        if self._last_reset_date != current_date:
            if self._last_reset_date is not None:
                logger.info(f"Daily reset: clearing daily PnL (was ${self.portfolio_manager.global_daily_pnl:.2f})")
                self.portfolio_manager.global_daily_pnl = 0.0
            self._last_reset_date = current_date

    def run_cycle(self) -> None:
        """Run one complete trading cycle across all pairs."""
        logger.info("Starting bot cycle")

        # 0. Reset daily stats at midnight
        current_time = datetime.now(pytz.UTC)
        self._reset_daily_stats(current_time)

        # 1. Market safety gates
        filter_result = self.trading_filter.should_trade(current_time)
        if not filter_result["trade"]:
            logger.info("Trading blocked: %s", filter_result["reason"])
            return

        # 2. Check portfolio limits
        if not self.portfolio_manager.check_global_limits()[0]:
            logger.warning("Global limit hit: %s", self.portfolio_manager.check_global_limits()[1])
            return

        # 3. Loop through all trading pairs
        for symbol in self.trading_pairs:
            try:
                self._process_pair(symbol, current_time)
            except Exception as e:
                logger.error(f"Error processing {symbol}: {e}")
                self.telegram_sender.send(f"⚠️ Error on {symbol}: {str(e)[:100]}")

        # 4. Portfolio summary
        logger.info(f"Portfolio summary: {self.portfolio_manager.total_open_positions} positions, Daily PnL: ${self.portfolio_manager.global_daily_pnl:.2f}")

    def _process_pair(self, symbol: str, current_time: datetime) -> None:
        """Process a single trading pair."""
        # Get timeframe for this pair
        timeframe = self.pair_timeframes.get(symbol, "15m")
        risk_allocation = self.pair_risk_allocation.get(symbol, 0.005)

        # 1. Fetch market data
        try:
            data = fetch_mt5_ohlcv(days=90, timeframe=timeframe, symbol=symbol)
            frame = prepare_ohlcv(data)
            if frame.empty:
                logger.warning(f"No OHLCV data fetched for {symbol}")
                return
        except Exception as exc:
            logger.exception(f"Failed to fetch market data for {symbol}: %s", exc)
            return

        # 2. Analyze market structure
        swings = detect_swings(frame)
        structure = StructureDetector(swings, frame)

        # 3. Detect market regime
        regime = MarketRegime(frame).get_regime()
        logger.info(f"{symbol}: Market regime: {regime['regime']} (ADX={regime['adx']:.2f})")

        if regime["regime"] == "mixed":
            logger.info(f"{symbol}: Mixed regime detected, skipping")
            return

        # 4. Select strategy based on regime
        signal = self._select_strategy_and_signal(frame, regime)
        if signal["signal"] == "none":
            logger.info(f"{symbol}: No signal generated")
            return

        # 5. Score signal
        struct_dict: dict[str, Any] = {
            "bos": structure.detect_bos(),
            "choch": structure.detect_choch(),
        }
        scored = self.signal_engine.score(signal, regime, struct_dict)
        logger.info(f"{symbol}: Signal scored: {scored['score']} (grade={scored['grade']})")

        # 6. Risk check
        if scored["score"] < settings.min_score:
            logger.info(f"{symbol}: Score {scored['score']} < {settings.min_score} threshold, skipping")
            return

        # 7. SIGNAL VALIDATION (CRITICAL FIX)
        entry = signal.get("entry", 0.0)
        sl = signal.get("stop_loss", 0.0)
        tp = signal.get("take_profit", 0.0)

        if not all([entry > 0, sl > 0, tp > 0]):
            logger.warning(f"{symbol}: Invalid signal prices (entry={entry}, sl={sl}, tp={tp})")
            return

        if signal["signal"] == "buy":
            if not (entry > sl and entry < tp):
                logger.warning(f"{symbol}: Invalid BUY levels (SL={sl} not below entry={entry} or TP={tp} not above)")
                return
        elif signal["signal"] == "sell":
            if not (entry < sl and entry > tp):
                logger.warning(f"{symbol}: Invalid SELL levels (SL={sl} not above entry={entry} or TP={tp} not below)")
                return

        # 8. Check pair-specific risk
        pair_state = self.portfolio_manager.get_pair_state(symbol)
        if pair_state.consecutive_losses >= 3:
            logger.info(f"{symbol}: Paused due to 3 consecutive losses")
            return

        # 9. Check global position limit
        if self.portfolio_manager.total_open_positions >= settings.global_max_concurrent_positions:
            logger.info(f"{symbol}: Global max positions reached ({self.portfolio_manager.total_open_positions})")
            return

        # 10. Execute trade with risk allocation
        self._execute_trade(symbol, signal, scored, regime, risk_allocation)

    def _select_strategy_and_signal(self, frame: Any, regime: dict[str, Any]) -> dict[str, Any]:
        """Select appropriate strategy based on regime and generate signal."""
        if regime["regime"] == "trending":
            strategy = TrendStrategy(frame, regime)
        elif regime["regime"] == "ranging":
            strategy = MeanReversionStrategy(frame, regime)
        else:
            strategy = BreakoutStrategy(frame, regime)

        return strategy.generate_signal()

    def _execute_trade(self, symbol: str, signal: dict[str, Any], scored: dict[str, Any], regime: dict[str, Any], risk_allocation: float) -> None:
        """Execute trade if all checks pass."""
        if signal["signal"] not in ("buy", "sell"):
            logger.warning(f"{symbol}: Invalid signal: {signal['signal']}")
            return

        try:
            order_type = signal["signal"]
            logger.info(f"{symbol}: Executing {order_type} order: score={scored['score']}")

            if not settings.use_mt5_execution or not self.mt5_client.is_configured():
                logger.warning(f"{symbol}: MT5 execution disabled or not configured")
                return

            # Calculate position size based on risk allocation
            account_balance = float(settings.account_balance)
            risk_amount = account_balance * risk_allocation
            entry_price = signal.get("entry", 0.0)
            stop_loss = signal.get("stop_loss", 0.0)

            # CRITICAL FIX: Prevent division by zero
            risk_per_unit = abs(entry_price - stop_loss)
            if risk_per_unit <= 0:
                logger.warning(f"{symbol}: Invalid risk distance (entry={entry_price}, SL={stop_loss})")
                return

            lots = risk_amount / (risk_per_unit * 100000)
            lots = round(max(0.01, min(lots, 1.0)), 2)

            order_result = self.mt5_client.place_order(
                symbol=symbol,
                order_type=order_type,
                lots=lots,
                stop_loss=signal.get("stop_loss"),
                take_profit=signal.get("take_profit"),
                comment=f"regime:{regime['regime']}|score:{scored['score']}",
            )

            # CRITICAL FIX: Check order result
            if order_result.get("status") != "accepted":
                logger.error(f"{symbol}: Order rejected: {order_result}")
                self.repository.add_failed_order({
                    "symbol": symbol,
                    "order_type": order_type,
                    "volume": lots,
                    "error_code": order_result.get("error_code"),
                    "error_message": str(order_result),
                })
                self.telegram_sender.send(f"⚠️ Order failed on {symbol}: {order_result.get('error_message', 'Unknown error')}")
                return

            logger.info(f"{symbol}: Order placed: ticket={order_result.get('ticket')} status={order_result.get('status')}")

            # Update portfolio manager
            self.portfolio_manager.update_position_state(symbol, {
                "ticket": order_result.get("ticket"),
                "symbol": symbol,
                "direction": order_type,
                "entry_price": signal.get("entry"),
                "stop_loss": signal.get("stop_loss"),
                "take_profit": signal.get("take_profit"),
                "volume": lots,
            })

            # Send Telegram alert
            msg = (
                f"🟢 Trade Opened\n"
                f"Symbol: {symbol}\n"
                f"Side: {order_type.upper()}\n"
                f"Score: {scored['score']}/100 ({scored['grade']})\n"
                f"Regime: {regime['regime']}\n"
                f"Size: {lots:.2f} lots\n"
                f"Ticket: {order_result.get('ticket')}"
            )
            self.telegram_sender.send(msg)

        except Exception as exc:
            logger.exception(f"{symbol}: Trade execution failed: %s", exc)
            self.telegram_sender.send(f"❌ Trade failed on {symbol}: {str(exc)[:100]}")


def main() -> None:
    """Main entry point with resilient error handling."""
    bot = RegimeBasedBot()
    logger.info("Bot started")

    # Health check before starting
    healthy, reason = bot.health_check()
    if not healthy:
        logger.critical(f"Health check failed: {reason}")
        bot.telegram_sender.send(f"🚨 Health check failed: {reason}")
        raise RuntimeError(reason)

    bot.telegram_sender.send("🚀 Bot started successfully")

    error_count = 0
    max_consecutive_errors = 10

    while True:
        try:
            bot.run_cycle()
            error_count = 0  # Reset on success
            time.sleep(settings.loop_interval_seconds)

        except KeyboardInterrupt:
            logger.info("Bot stopped by user")
            bot.telegram_sender.send("🛑 Bot stopped by user")
            break

        except Exception as exc:
            error_count += 1
            logger.exception(f"Cycle failed (error #{error_count}): {exc}")

            # Send alert
            try:
                bot.telegram_sender.send(f"⚠️ Bot error #{error_count}: {str(exc)[:100]}")
            except:
                pass

            if error_count >= max_consecutive_errors:
                logger.critical(f"Max errors ({max_consecutive_errors}) reached, shutting down")
                try:
                    bot.telegram_sender.send("🚨 CRITICAL: Max errors reached, bot shutting down")
                except:
                    pass
                raise

            # Exponential backoff: 1min, 2min, 4min, 8min... max 5min
            backoff = min(60 * (2 ** (error_count - 1)), 300)
            logger.info(f"Waiting {backoff}s before retry...")
            time.sleep(backoff)


if __name__ == "__main__":
    main()