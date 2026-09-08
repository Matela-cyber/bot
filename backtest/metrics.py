"""Performance metrics calculator."""

from typing import List, Dict, Any
import numpy as np

from core.data_models import Trade


class MetricsCalculator:
    """Calculate performance metrics from trade history."""

    @staticmethod
    def calculate(trades: List[Trade], initial_balance: float) -> Dict[str, Any]:
        """Calculate all performance metrics."""
        if not trades:
            return MetricsCalculator._empty_metrics(initial_balance)

        wins = [t for t in trades if t.profit and t.profit > 0]
        losses = [t for t in trades if t.profit and t.profit < 0]

        total_profit = sum(t.profit for t in wins) if wins else 0
        total_loss = abs(sum(t.profit for t in losses)) if losses else 0

        # Calculate drawdown
        equity_curve = MetricsCalculator._calculate_equity_curve(
            trades, initial_balance)
        max_drawdown = MetricsCalculator._calculate_max_drawdown(equity_curve)

        # Sharpe ratio
        returns = [t.profit for t in trades if t.profit is not None]
        sharpe = 0
        if len(returns) > 1:
            mean_return = np.mean(returns)
            std_return = np.std(returns)
            if std_return > 0:
                sharpe = mean_return / std_return * np.sqrt(252)

        return {
            'trades': len(trades),
            'wins': len(wins),
            'losses': len(losses),
            'win_rate': len(wins) / len(trades) * 100 if trades else 0,
            'net_profit': sum(t.profit for t in trades) if trades else 0,
            'gross_profit': total_profit,
            'gross_loss': total_loss,
            'profit_factor': total_profit / total_loss if total_loss > 0 else float('inf'),
            'max_drawdown': max_drawdown * 100,
            'avg_win': sum(t.profit for t in wins) / len(wins) if wins else 0,
            'avg_loss': sum(t.profit for t in losses) / len(losses) if losses else 0,
            'best_trade': max(t.profit for t in trades) if trades else 0,
            'worst_trade': min(t.profit for t in trades) if trades else 0,
            'final_balance': initial_balance + sum(t.profit for t in trades),
            'total_return': (sum(t.profit for t in trades) / initial_balance) * 100,
            'sharpe_ratio': sharpe,
        }

    @staticmethod
    def _calculate_equity_curve(trades: List[Trade], initial_balance: float) -> List[float]:
        """Calculate equity curve from trade history."""
        equity = [initial_balance]
        for trade in trades:
            equity.append(equity[-1] + (trade.profit or 0))
        return equity

    @staticmethod
    def _calculate_max_drawdown(equity_curve: List[float]) -> float:
        """Calculate maximum drawdown percentage."""
        if not equity_curve:
            return 0.0

        peak = equity_curve[0]
        max_dd = 0.0

        for value in equity_curve:
            if value > peak:
                peak = value
            if peak > 0:
                dd = (peak - value) / peak
                max_dd = max(max_dd, dd)

        return max_dd

    @staticmethod
    def _empty_metrics(initial_balance: float) -> Dict[str, Any]:
        """Return empty metrics."""
        return {
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
            'final_balance': initial_balance,
            'total_return': 0,
            'sharpe_ratio': 0,
        }
