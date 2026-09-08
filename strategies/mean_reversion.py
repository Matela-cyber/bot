"""Mean Reversion strategy."""

from typing import Optional, List, Dict, Any
from datetime import datetime
import pandas as pd
import numpy as np

from strategies.base import BaseStrategy
from core.data_models import Signal, Direction
from indicators.rsi import calculate_rsi
from indicators.atr import calculate_atr


class MeanReversion(BaseStrategy):
    """Mean Reversion Strategy - 7 Pairs.

    Entry Rules:
    - Direction: BUY only
    - Session: Asia (0-8 UTC)
    - Hours: 0:00, 5:00, 11:00 UTC
    - Days: Monday (0), Thursday (3)
    - RSI: < 25
    - Bollinger Band: Price below lower band
    - TP: 1.5R
    - SL: ATR-based
    - Risk: 3%
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.min_hours = config.get('hours', [0, 5, 11])
        self.good_days = config.get('days', [0, 3])
        self.rsi_threshold = config.get('rsi_threshold', 25)
        self.bb_period = config.get('bb_period', 20)
        self.bb_std = config.get('bb_std', 2.0)
        self.tp_ratio = config.get('tp_ratio', 1.5)
        self.sl_pips = config.get('sl_pips', 20)
        self.use_atr_sl = config.get('use_atr_sl', True)
        self.atr_multiplier = config.get('atr_multiplier', 1.0)
        self.pair = config.get('pair', 'EURUSD')
        self.min_confidence = config.get('min_confidence', 60)
        self.risk_percent = config.get('risk_percent', 3.0)

    def generate_signal(self, data: pd.DataFrame, current_time: datetime) -> Optional[Signal]:
        # Session checks
        if not self._is_good_hour(current_time):
            return None
        if not self._is_good_day(current_time):
            return None
        if not self._is_asia_session(current_time):
            return None

        if len(data) < self.bb_period + 10:
            return None

        # RSI
        rsi_series = calculate_rsi(data, 14)
        if rsi_series.empty or pd.isna(rsi_series.iloc[-1]):
            return None

        rsi = rsi_series.iloc[-1]
        if rsi > self.rsi_threshold:
            return None

        # Bollinger Bands
        bb_upper, bb_middle, bb_lower = self._calculate_bollinger_bands(data)
        current_close = data['close'].iloc[-1]

        if current_close > bb_lower:
            return None

        # Build signal
        entry = current_close
        atr = self._get_atr(data)

        if self.use_atr_sl and atr > 0:
            risk = atr * self.atr_multiplier
            stop_loss = entry - risk
            take_profit = entry + risk * self.tp_ratio
        else:
            pip_size = 0.0001
            stop_loss = entry - (self.sl_pips * pip_size)
            take_profit = entry + (self.sl_pips * pip_size * self.tp_ratio)

        if stop_loss <= 0 or take_profit <= entry:
            return None

        confidence = self._calculate_confidence(rsi, current_close, bb_lower)

        if confidence < self.min_confidence:
            return None

        return Signal(
            pair=self.pair,
            strategy='mean_reversion',
            direction=Direction.BUY,
            entry=entry,
            stop_loss=stop_loss,
            take_profit=take_profit,
            confidence=confidence,
            timestamp=current_time,
            reason=f"RSI={rsi:.1f}, Price={current_close:.5f}",
            metadata={
                'rsi': rsi,
                'bb_lower': bb_lower,
                'bb_middle': bb_middle,
                'bb_upper': bb_upper,
                'atr': atr,
                'risk_percent': self.risk_percent,
                'tp_ratio': self.tp_ratio,
            }
        )

    def _is_asia_session(self, dt: datetime) -> bool:
        return 0 <= dt.hour < 8

    def _is_good_hour(self, dt: datetime) -> bool:
        return dt.hour in self.min_hours

    def _is_good_day(self, dt: datetime) -> bool:
        return dt.weekday() in self.good_days

    def _calculate_bollinger_bands(self, data: pd.DataFrame):
        close = data['close']
        period = self.bb_period

        if len(close) < period:
            return float('nan'), float('nan'), float('nan')

        middle = close.rolling(window=period).mean().iloc[-1]
        std = close.rolling(window=period).std().iloc[-1]

        if pd.isna(middle) or pd.isna(std):
            return float('nan'), float('nan'), float('nan')

        upper = middle + (std * self.bb_std)
        lower = middle - (std * self.bb_std)
        return upper, middle, lower

    def _get_atr(self, data: pd.DataFrame) -> float:
        try:
            atr = calculate_atr(data, 14)
            if atr.empty or pd.isna(atr.iloc[-1]):
                return 0.0
            return float(atr.iloc[-1])
        except Exception:
            return 0.0

    def _calculate_confidence(self, rsi: float, price: float, bb_lower: float) -> float:
        confidence = 50.0

        if rsi < 20:
            confidence += 25
        elif rsi < 25:
            confidence += 15
        elif rsi < 30:
            confidence += 5

        if pd.isna(bb_lower) or bb_lower <= 0:
            pass
        else:
            distance = (bb_lower - price) / bb_lower * 100
            if distance > 0.1:
                confidence += 20
            elif distance > 0.05:
                confidence += 10

        confidence += 5  # Asia session bonus

        return min(100, max(0, confidence))

    def get_required_indicators(self) -> List[str]:
        return ['rsi', 'bb_lower', 'bb_middle', 'bb_upper', 'atr']
