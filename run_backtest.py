"""Entry point for running the Mean Reversion backtest (3% only)."""

from datetime import datetime, timezone
import json
import pandas as pd
import os
from pathlib import Path
from typing import Any

from core.data_models import BacktestConfig
from data.mt5_loader import MT5DataLoader
from backtest.engine import BacktestEngine
from backtest.report import ReportGenerator


def _json_default(value: Any) -> Any:
    """Serialize pandas, NumPy, Enum, and datetime values in checkpoints."""
    if hasattr(value, "value"):
        return value.value
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if hasattr(value, "item"):
        return value.item()
    raise TypeError(
        f"Object of type {type(value).__name__} is not JSON serializable")


def _load_checkpoint(path: Path) -> dict[str, Any]:
    """Load a compatible checkpoint or return an empty run state."""
    if not path.exists():
        return {"completed_pairs": [], "results": {}}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("start_date") != "2025-06-01T00:00:00+00:00":
        return {"completed_pairs": [], "results": {}}
    return payload


def _write_checkpoint(path: Path, config: BacktestConfig,
                      completed_pairs: list[str], results: dict[str, Any]) -> None:
    """Atomically persist completed pair results after each pair."""
    payload = {
        "start_date": config.start_date.isoformat(),
        "end_date": config.end_date.isoformat(),
        "pairs": config.pairs,
        "strategies": config.strategies,
        "risk_percents": config.risk_percents,
        "completed_pairs": completed_pairs,
        "results": results,
    }
    temporary = path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, default=_json_default), encoding="utf-8")
    os.replace(temporary, path)


def main():
    """Run backtest and generate reports."""
    print("=" * 70)
    print("MEAN REVERSION BACKTEST - 15 MONTHS (3% RISK ONLY)")
    print("=" * 70)

    # Configuration (7 pairs, ONLY 3% risk)
    config = BacktestConfig(
        start_date=datetime(2025, 6, 1, tzinfo=timezone.utc),
        end_date=datetime(2026, 9, 5, tzinfo=timezone.utc),
        pairs=[
            "AUDCAD", "GBPJPY", "EURJPY", "EURUSD", "EURGBP", "USDJPY", "USDCAD"
        ],
        strategies=["mean_reversion"],
        risk_percents=[3],  # ✅ ONLY 3% (SWEET SPOT)
        timeframe="15m",
        initial_balance=100.0,
        max_open_positions=4,
        commission_per_lot=6.0,
        slippage_pips=0.5,
        output_dir="results",
    )

    print(f"\n📊 Configuration:")
    print(
        f"  - Period: {config.start_date.strftime('%Y-%m-%d')} to {config.end_date.strftime('%Y-%m-%d')}")
    print(f"  - Pairs: {len(config.pairs)}")
    print(f"  - Strategy: Mean Reversion ONLY")
    print(f"  - Risk Level: 3% (CONTRACT - SWEET SPOT)")
    print(f"  - Initial Balance: ${config.initial_balance:.2f}")
    print(f"  - Commission: ${config.commission_per_lot:.2f}/lot")
    print(f"  - Slippage: {config.slippage_pips} pips")

    # Load data
    print("\n📥 Loading market data...")
    data_dir = "data/backtest_data"
    data = {}
    use_existing = True

    for pair in config.pairs:
        filename = f"{data_dir}/{pair}_15m_2025-2026.csv"
        if os.path.exists(filename):
            df = pd.read_csv(filename, index_col='time', parse_dates=True)
            df.index = pd.to_datetime(df.index, utc=True, errors='coerce')
            df = df.loc[(df.index >= config.start_date) &
                        (df.index < config.end_date)]
            if not df.empty:
                data[pair] = df
                print(f"  ✅ Loaded {pair} from CSV ({len(df)} candles)")
            else:
                use_existing = False
                break
        else:
            use_existing = False
            break

    if not use_existing or len(data) != len(config.pairs):
        print("  ⚠️ Some data missing, fetching from MT5...")
        loader = MT5DataLoader()
        data = loader.fetch_all(
            pairs=config.pairs,
            timeframe=config.timeframe,
            start_date=config.start_date,
            end_date=config.end_date,
        )
        loader.save_to_csv(data)
        loader.disconnect()

    if not data:
        print("  ❌ No data available. Exiting.")
        return

    print(f"\n  ✅ Data loaded for {len(data)} pairs")

    # Run backtest
    print("\n🚀 Running backtest (3% risk only)...")
    checkpoint_path = Path(config.output_dir) / "backtest_checkpoint.json"
    checkpoint = _load_checkpoint(checkpoint_path)
    results = checkpoint.get("results", {})
    completed_pairs = set(checkpoint.get("completed_pairs", []))
    daily_pnl = {}
    all_trades = []

    for pair in config.pairs:
        if pair in completed_pairs:
            print(f"  ✅ Resuming completed pair: {pair}")
            continue

        print(
            f"\n  ▶ Testing pair {pair} ({len(completed_pairs) + 1}/{len(config.pairs)})")

        # Run Mean Reversion at 3%
        engine = BacktestEngine(config)
        pair_results = engine.run({pair: data[pair]})
        results.update(pair_results)

        # Collect trades
        for pair_key, strategies in pair_results.items():
            for strategy_name, risk_results in strategies.items():
                for result in risk_results:
                    if result.get('trades_data'):
                        all_trades.extend(result['trades_data'])

        for day, pnl in engine.daily_pnl.items():
            daily_pnl[day] = daily_pnl.get(day, 0) + pnl

        completed_pairs.add(pair)
        _write_checkpoint(checkpoint_path, config,
                          sorted(completed_pairs), results)

    if len(completed_pairs) != len(config.pairs):
        raise RuntimeError(
            f"Backtest incomplete: {len(completed_pairs)}/{len(config.pairs)} pairs completed")

    # Generate reports
    print("\n📄 Generating reports...")
    report = ReportGenerator("results")

    summary_file = report.generate_summary(results)
    print(f"  ✅ Summary: {summary_file}")

    if all_trades:
        trade_log_file = report.generate_trade_log(all_trades)
        print(f"  ✅ Trade Log: {trade_log_file}")

    pair_ranking_file = report.generate_pair_ranking(results)
    print(f"  ✅ Pair Ranking: {pair_ranking_file}")

    if daily_pnl:
        monthly_file = report.generate_monthly_returns(daily_pnl)
        print(f"  ✅ Monthly Returns: {monthly_file}")

    print("\n" + "=" * 70)
    print("✅ BACKTEST COMPLETE!")
    print("=" * 70)

    # Print results
    print("\n📊 RESULTS (3% RISK):")

    best_results = []
    for pair, strategies in results.items():
        for strategy_name, risk_results in strategies.items():
            for result in risk_results:
                if result['trades'] >= 1:
                    best_results.append({
                        'pair': pair,
                        'strategy': strategy_name,
                        'trades': result['trades'],
                        'win_rate': result['win_rate'],
                        'profit': result['net_profit'],
                        'pf': result['profit_factor'],
                    })

    best_results.sort(key=lambda x: x['profit'], reverse=True)

    print("\n  Pair Performance (3% Risk):")
    print("  ─" * 40)
    for r in best_results:
        print(
            f"  {r['pair']}: {r['trades']} trades, {r['win_rate']:.1f}% WR, +${r['profit']:.2f}, PF={r['pf']:.2f}")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()
