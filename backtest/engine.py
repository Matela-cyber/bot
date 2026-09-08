"""Main backtest engine."""

from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

from core.data_models import Trade, Signal, BacktestConfig, Direction, ExitReason
from strategies.mean_reversion import MeanReversion
from strategies.base import BaseStrategy


class BacktestEngine:
    """Backtest engine for running strategy simulations."""

    def __init__(self, config: BacktestConfig):
        self.config = config
        self.trades: List[Trade] = []
        self.balance = config.initial_balance
        self.initial_balance = config.initial_balance
        self.equity_curve: List[Dict] = []
        self.daily_pnl: Dict[str, float] = {}
        self.open_positions: List[Trade] = []
        self.all_trade_data: List[Dict] = []

    def run(self, data: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
        """Run backtest on all pairs and strategies."""
        results = {}

        total_scenarios = len(
            data) * len(self.config.strategies) * len(self.config.risk_percents)
        scenario_count = 0

        print(f"\n📊 Running {total_scenarios} scenarios...")

        for pair, df in data.items():
            if df.empty:
                print(f"  ⚠️ No data for {pair}, skipping")
                continue

            results[pair] = {}

            for strategy_name in self.config.strategies:
                results[pair][strategy_name] = []

                for risk_pct in self.config.risk_percents:
                    scenario_count += 1
                    print(
                        f"  [{scenario_count}/{total_scenarios}] {pair} + {strategy_name} + {risk_pct}%")

                    result = self._run_scenario(
                        pair, df, strategy_name, risk_pct)
                    results[pair][strategy_name].append(result)

        return results

    def _run_scenario(
        self,
        pair: str,
        data: pd.DataFrame,
        strategy_name: str,
        risk_pct: float
    ) -> Dict[str, Any]:
        """Run a single scenario."""
        # Reset state
        self.trades = []
        self.balance = self.initial_balance
        self.open_positions = []
        self.equity_curve = []
        self.daily_pnl = {}
        self.all_trade_data = []

        # Create strategy
        strategy = self._create_strategy(strategy_name, pair, risk_pct)

        # Iterate through candles
        for i in range(len(data)):
            current_data = data.iloc[:i+1]
            current_time = data.index[i]

            # Manage open positions
            self._manage_positions(current_data, current_time)

            # Check daily loss limit
            if self._check_daily_loss_limit(current_time):
                continue

            # Generate signal
            signal = strategy.generate_signal(current_data, current_time)
            if signal:
                self._execute_signal(signal, current_time, risk_pct)

        # Calculate metrics
        return self._calculate_metrics(pair, strategy_name, risk_pct)

    def _create_strategy(self, name: str, pair: str, risk_pct: float) -> BaseStrategy:
        """Create strategy instance."""
        config = {
            'pair': pair,
            'risk_percent': risk_pct,
        }

        if name == 'mean_reversion':
            return MeanReversion({
                **config,
                'hours': [0, 5, 11],
                'days': [0, 3],
                'rsi_threshold': 25,
                'tp_ratio': 2.0,
                'sl_pips': 20,
                'use_atr_sl': True,
                'atr_multiplier': 1.0,
            })
        else:
            raise ValueError(f"Unknown strategy: {name}")

    def _execute_signal(self, signal: Signal, current_time: datetime, risk_pct: float):
        """Execute a trading signal."""
        if len(self.open_positions) >= self.config.max_open_positions:
            return

        # Calculate position size
        position_size = self._calculate_position_size(
            risk_pct, signal.entry, signal.stop_loss)

        if position_size <= 0:
            return

        # Create trade
        trade = Trade(
            pair=signal.pair,
            strategy=signal.strategy,
            direction=signal.direction,
            entry_price=signal.entry,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
            position_size=position_size,
            entry_time=current_time,
            confidence=signal.confidence,
            risk_percent=risk_pct,
        )

        self.open_positions.append(trade)

    def _manage_positions(self, data: pd.DataFrame, current_time: datetime):
        """Manage open positions."""
        if not self.open_positions:
            return

        current_price = data['close'].iloc[-1]

        for trade in self.open_positions[:]:
            # Check TP/SL
            if trade.direction == Direction.BUY:
                if current_price >= trade.take_profit:
                    self._close_trade(trade, trade.take_profit,
                                      current_time, ExitReason.TAKE_PROFIT)
                elif current_price <= trade.stop_loss:
                    self._close_trade(trade, trade.stop_loss,
                                      current_time, ExitReason.STOP_LOSS)
            else:
                if current_price <= trade.take_profit:
                    self._close_trade(trade, trade.take_profit,
                                      current_time, ExitReason.TAKE_PROFIT)
                elif current_price >= trade.stop_loss:
                    self._close_trade(trade, trade.stop_loss,
                                      current_time, ExitReason.STOP_LOSS)

    def _close_trade(self, trade: Trade, exit_price: float, exit_time: datetime, reason: ExitReason):
        """Close a trade and update P&L."""
        trade.exit_price = exit_price
        trade.exit_time = exit_time
        trade.exit_reason = reason

        # Calculate profit in pips
        pip_size = 0.0001
        if trade.direction == Direction.BUY:
            trade.profit_pips = (exit_price - trade.entry_price) / pip_size
        else:
            trade.profit_pips = (trade.entry_price - exit_price) / pip_size

        # Calculate monetary profit
        pip_value = self._calculate_pip_value(
            trade.entry_price, trade.position_size)
        raw_profit = trade.profit_pips * pip_value

        # Apply commission
        commission = self.config.commission_per_lot * trade.position_size
        trade.commission = commission

        # Apply slippage
        slippage_cost = self.config.slippage_pips * pip_value
        trade.slippage = slippage_cost

        trade.profit = raw_profit - commission - slippage_cost

        # Update balance
        self.balance += trade.profit
        self.trades.append(trade)
        self.open_positions.remove(trade)

        # Store trade data for reporting
        self.all_trade_data.append({
            'pair': trade.pair,
            'strategy': trade.strategy,
            'direction': trade.direction.value,
            'entry_time': trade.entry_time,
            'exit_time': trade.exit_time,
            'entry_price': trade.entry_price,
            'stop_loss': trade.stop_loss,
            'take_profit': trade.take_profit,
            'exit_price': trade.exit_price,
            'profit_pips': trade.profit_pips,
            'profit': trade.profit,
            'exit_reason': trade.exit_reason.value if trade.exit_reason else '',
            'confidence': trade.confidence,
            'risk_percent': trade.risk_percent,
            'position_size': trade.position_size,
            'commission': trade.commission,
            'slippage': trade.slippage,
        })

        # Update daily P&L
        day_key = exit_time.strftime('%Y-%m-%d')
        self.daily_pnl[day_key] = self.daily_pnl.get(day_key, 0) + trade.profit

        # Update equity curve
        self.equity_curve.append({
            'timestamp': exit_time,
            'equity': self.balance,
            'profit': trade.profit,
        })

    def _calculate_position_size(self, risk_pct: float, entry: float, stop_loss: float) -> float:
        """Calculate position size based on risk."""
        risk_amount = self.balance * (risk_pct / 100)
        risk_pips = abs(entry - stop_loss) / 0.0001

        if risk_pips <= 0:
            return 0

        pip_value = self._calculate_pip_value(entry, 1.0)
        position_size = risk_amount / (risk_pips * pip_value)

        # Round to 2 decimals, min 0.01
        return round(max(0.01, position_size), 2)

    def _calculate_pip_value(self, price: float, lot_size: float) -> float:
        """Calculate pip value for a position."""
        contract_size = 100000
        pip_size = 0.0001
        return contract_size * lot_size * pip_size / price

    def _check_daily_loss_limit(self, current_time: datetime) -> bool:
        """Check if daily loss limit has been reached."""
        day_key = current_time.strftime('%Y-%m-%d')
        today_pnl = self.daily_pnl.get(day_key, 0)
        daily_loss_limit = -abs(self.initial_balance * 0.05)  # 5% daily loss

        return today_pnl < daily_loss_limit

    def _calculate_metrics(self, pair: str, strategy: str, risk_pct: float) -> Dict[str, Any]:
        """Calculate performance metrics."""
        if not self.trades:
            return self._empty_metrics(pair, strategy, risk_pct)

        wins = [t for t in self.trades if t.profit and t.profit > 0]
        losses = [t for t in self.trades if t.profit and t.profit < 0]
        total_profit = sum(t.profit for t in wins) if wins else 0
        total_loss = abs(sum(t.profit for t in losses)) if losses else 0

        # Calculate drawdown
        equity_values = [e['equity'] for e in self.equity_curve]
        peak = self.initial_balance
        max_drawdown = 0
        for eq in equity_values:
            if eq > peak:
                peak = eq
            if peak > 0:
                dd = (peak - eq) / peak
                max_drawdown = max(max_drawdown, dd)

        # Calculate Sharpe ratio (simplified)
        returns = [e['profit'] for e in self.equity_curve]
        sharpe = 0
        if returns and len(returns) > 1:
            mean_return = np.mean(returns)
            std_return = np.std(returns)
            if std_return > 0:
                sharpe = mean_return / std_return * np.sqrt(252)

        return {
            'pair': pair,
            'strategy': strategy,
            'risk_percent': risk_pct,
            'trades': len(self.trades),
            'wins': len(wins),
            'losses': len(losses),
            'win_rate': len(wins) / len(self.trades) * 100 if self.trades else 0,
            'net_profit': self.balance - self.initial_balance,
            'gross_profit': total_profit,
            'gross_loss': total_loss,
            'profit_factor': total_profit / total_loss if total_loss > 0 else float('inf'),
            'max_drawdown': max_drawdown * 100,
            'avg_win': sum(t.profit for t in wins) / len(wins) if wins else 0,
            'avg_loss': sum(t.profit for t in losses) / len(losses) if losses else 0,
            'best_trade': max(t.profit for t in self.trades) if self.trades else 0,
            'worst_trade': min(t.profit for t in self.trades) if self.trades else 0,
            'final_balance': self.balance,
            'total_return': (self.balance - self.initial_balance) / self.initial_balance * 100,
            'sharpe_ratio': sharpe,
            'trades_data': self.all_trade_data,
        }

    def _empty_metrics(self, pair: str, strategy: str, risk_pct: float) -> Dict[str, Any]:
        """Return empty metrics."""
        return {
            'pair': pair,
            'strategy': strategy,
            'risk_percent': risk_pct,
            'trades': 0,
            'wins': 0,
            'losses': 0,
            'win_rate': 0,
            'net_profit': 0,
            'gross_profit': 0,
            'gross_loss': 0,
            'profit_factor': 0,
            'max_drawdown': 0,
            'avg_win': 0,
            'avg_loss': 0,
            'best_trade': 0,
            'worst_trade': 0,
            'final_balance': self.initial_balance,
            'total_return': 0,
            'sharpe_ratio': 0,
            'trades_data': [],
        }
