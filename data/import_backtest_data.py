"""Import the canonical seven-pair 15-minute backtest dataset from MT5."""

from __future__ import annotations

from datetime import datetime, timezone

from data.mt5_loader import MT5DataLoader


PAIRS = ["EURUSD", "USDCAD", "EURGBP", "GBPJPY", "AUDCAD", "EURJPY", "USDJPY"]
MT5_TERMINAL = r"C:\Program Files\Pepperstone KE MetaTrader 5 Terminal\terminal64.exe"


def main() -> None:
    loader = MT5DataLoader(MT5_TERMINAL)
    try:
        if not loader.connect():
            raise RuntimeError("MT5 connection failed")
        data = loader.fetch_all(
            pairs=PAIRS,
            timeframe="15m",
            start_date=datetime(2025, 5, 5, tzinfo=timezone.utc),
            end_date=datetime(2026, 9, 5, tzinfo=timezone.utc),
        )
        missing = [pair for pair in PAIRS if pair not in data or data[pair].empty]
        if missing:
            raise RuntimeError(
                f"No MT5 history returned for: {', '.join(missing)}")
        loader.save_to_csv(data, "data/backtest_data")
        print(f"Exported {len(data)}/{len(PAIRS)} pairs")
    finally:
        loader.disconnect()


if __name__ == "__main__":
    main()
