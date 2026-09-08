"""MT5 data loader for backtest."""

from datetime import datetime
from typing import Dict, List, Optional
import pandas as pd
import MetaTrader5 as mt5


class MT5DataLoader:
    """Load historical data from MT5 for backtesting."""

    TIMEFRAME_MAP = {
        "1m": mt5.TIMEFRAME_M1,
        "5m": mt5.TIMEFRAME_M5,
        "15m": mt5.TIMEFRAME_M15,
        "30m": mt5.TIMEFRAME_M30,
        "1h": mt5.TIMEFRAME_H1,
        "4h": mt5.TIMEFRAME_H4,
        "1d": mt5.TIMEFRAME_D1,
    }

    def __init__(self, terminal_path: str = ""):
        self.terminal_path = terminal_path
        self.connected = False

    def connect(self) -> bool:
        """Connect to MT5."""
        if not mt5.initialize(self.terminal_path):
            print(f"MT5 initialize failed: {mt5.last_error()}")
            return False
        self.connected = True
        return True

    def disconnect(self):
        """Disconnect from MT5."""
        if self.connected:
            mt5.shutdown()
            self.connected = False

    def fetch_all(
        self,
        pairs: List[str],
        timeframe: str,
        start_date: datetime,
        end_date: datetime,
    ) -> Dict[str, pd.DataFrame]:
        """Fetch data for all pairs."""
        if not self.connected:
            if not self.connect():
                return {}

        data = {}
        total = len(pairs)

        for idx, pair in enumerate(pairs, 1):
            print(f"  [{idx}/{total}] Fetching {pair}...")
            df = self.fetch_pair(pair, timeframe, start_date, end_date)

            if df is not None and not df.empty:
                data[pair] = df
                print(f"    - {len(df)} candles")
            else:
                print(f"    - No data for {pair}")

        return data

    def fetch_pair(
        self,
        pair: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime,
    ) -> Optional[pd.DataFrame]:
        """Fetch data for a single pair."""
        tf = self.TIMEFRAME_MAP.get(timeframe.lower())
        if tf is None:
            raise ValueError(f"Invalid timeframe: {timeframe}")

        rates = mt5.copy_rates_range(pair, tf, start_date, end_date)

        if rates is None or len(rates) == 0:
            return None

        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s', utc=True)
        df.set_index('time', inplace=True)

        # Rename columns
        df.columns = ['open', 'high', 'low', 'close',
                      'tick_volume', 'spread', 'real_volume']
        df = df[['open', 'high', 'low', 'close', 'tick_volume']]

        return df

    def save_to_csv(self, data: Dict[str, pd.DataFrame], output_dir: str = "data/backtest_data"):
        """Save fetched data to CSV files."""
        import os
        os.makedirs(output_dir, exist_ok=True)

        for pair, df in data.items():
            filename = f"{output_dir}/{pair}_15m_2025-2026.csv"
            df.to_csv(filename)
            print(f"  Saved {pair} to {filename}")
