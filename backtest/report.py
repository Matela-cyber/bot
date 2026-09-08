"""Report generator for backtest results."""

import csv
from typing import List, Dict, Any
from datetime import datetime
import os


class ReportGenerator:
    """Generate CSV reports from backtest results."""

    def __init__(self, output_dir: str = "results"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def generate_summary(self, results: Dict[str, Any]) -> str:
        """Generate summary report."""
        filename = f"{self.output_dir}/backtest_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

        with open(filename, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'pair', 'strategy', 'risk_pct', 'trades', 'wins', 'losses',
                'win_rate', 'net_profit', 'profit_factor', 'max_drawdown',
                'avg_win', 'avg_loss', 'best_trade', 'worst_trade',
                'final_balance', 'total_return', 'sharpe_ratio'
            ])

            for pair, strategies in results.items():
                for strategy_name, risk_results in strategies.items():
                    for result in risk_results:
                        writer.writerow([
                            pair,
                            strategy_name,
                            result['risk_percent'],
                            result['trades'],
                            result['wins'],
                            result['losses'],
                            round(result['win_rate'], 2),
                            round(result['net_profit'], 2),
                            round(result['profit_factor'], 2),
                            round(result['max_drawdown'], 2),
                            round(result['avg_win'], 2),
                            round(result['avg_loss'], 2),
                            round(result['best_trade'], 2),
                            round(result['worst_trade'], 2),
                            round(result['final_balance'], 2),
                            round(result['total_return'], 2),
                            round(result['sharpe_ratio'], 4),
                        ])

        return filename

    def generate_trade_log(self, trades_data: List[Dict]) -> str:
        """Generate trade log CSV."""
        filename = f"{self.output_dir}/trade_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

        with open(filename, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'pair', 'strategy', 'direction', 'entry_time', 'exit_time',
                'entry', 'stop_loss', 'take_profit', 'exit_price',
                'profit_pips', 'profit', 'exit_reason', 'confidence',
                'risk_pct', 'position_size', 'commission', 'slippage'
            ])

            for trade in trades_data:
                writer.writerow([
                    trade.get('pair', ''),
                    trade.get('strategy', ''),
                    trade.get('direction', ''),
                    trade.get('entry_time', ''),
                    trade.get('exit_time', ''),
                    round(trade.get('entry_price', 0), 5),
                    round(trade.get('stop_loss', 0), 5),
                    round(trade.get('take_profit', 0), 5),
                    round(trade.get('exit_price', 0), 5),
                    round(trade.get('profit_pips', 0), 2),
                    round(trade.get('profit', 0), 2),
                    trade.get('exit_reason', ''),
                    round(trade.get('confidence', 0), 1),
                    trade.get('risk_percent', 0),
                    round(trade.get('position_size', 0), 2),
                    round(trade.get('commission', 0), 2),
                    round(trade.get('slippage', 0), 2),
                ])

        return filename

    def generate_risk_comparison(self, results: Dict[str, Any]) -> str:
        """Generate risk comparison report."""
        filename = f"{self.output_dir}/risk_comparison_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

        with open(filename, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'pair', 'strategy', 'risk_1%', 'risk_2%', 'risk_3%',
                'risk_4%', 'risk_5%', 'best_risk'
            ])

            for pair, strategies in results.items():
                for strategy_name, risk_results in strategies.items():
                    profits = {}
                    for result in risk_results:
                        profits[f"risk_{result['risk_percent']}%"] = round(
                            result['net_profit'], 2)

                    # Find best risk level by net profit
                    if risk_results:
                        best_risk = max(
                            risk_results, key=lambda x: x['net_profit'])
                        best_str = f"{best_risk['risk_percent']}% ({round(best_risk['net_profit'], 2)})"
                    else:
                        best_str = "N/A"

                    writer.writerow([
                        pair,
                        strategy_name,
                        profits.get('risk_1%', 0),
                        profits.get('risk_2%', 0),
                        profits.get('risk_3%', 0),
                        profits.get('risk_4%', 0),
                        profits.get('risk_5%', 0),
                        best_str
                    ])

        return filename

    def generate_monthly_returns(self, daily_pnl: Dict[str, float]) -> str:
        """Generate monthly returns report."""
        filename = f"{self.output_dir}/monthly_returns_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

        # Group by month
        monthly = {}
        for date_str, pnl in daily_pnl.items():
            if not date_str:
                continue
            try:
                date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                month_key = date_obj.strftime('%Y-%m')
                monthly[month_key] = monthly.get(month_key, 0) + pnl
            except ValueError:
                continue

        with open(filename, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['month', 'pnl'])
            for month, pnl in sorted(monthly.items()):
                writer.writerow([month, round(pnl, 2)])

        return filename

    def generate_pair_ranking(self, results: Dict[str, Any]) -> str:
        """Generate pair ranking report."""
        filename = f"{self.output_dir}/pair_ranking_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

        rankings = []

        for pair, strategies in results.items():
            for strategy_name, risk_results in strategies.items():
                for result in risk_results:
                    if result['trades'] > 0:
                        rankings.append({
                            'pair': pair,
                            'strategy': strategy_name,
                            'risk_pct': result['risk_percent'],
                            'trades': result['trades'],
                            'win_rate': result['win_rate'],
                            'net_profit': result['net_profit'],
                            'profit_factor': result['profit_factor'],
                        })

        # Sort by net profit descending
        rankings.sort(key=lambda x: x['net_profit'], reverse=True)

        with open(filename, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'rank', 'pair', 'strategy', 'risk_pct', 'trades',
                'win_rate', 'net_profit', 'profit_factor'
            ])

            for i, r in enumerate(rankings, 1):
                writer.writerow([
                    i,
                    r['pair'],
                    r['strategy'],
                    r['risk_pct'],
                    r['trades'],
                    round(r['win_rate'], 2),
                    round(r['net_profit'], 2),
                    round(r['profit_factor'], 2),
                ])

        return filename
