"""Simplified signal orchestration - Mean Reversion only."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional

import pandas as pd

from strategies.mean_reversion import MeanReversion
from core.data_models import Signal


class TrinityStrategy:
    """Mean Reversion only strategy orchestration."""

    def __init__(
        self,
        frame: pd.DataFrame,
        higher_tf: pd.DataFrame | None,
        structure: Any,
        current_time: datetime,
        config: Any,
    ) -> None:
        self.frame = frame
        self.higher_tf = higher_tf
        self.structure = structure
        self.current_time = current_time
        self.config = config
        self.pair = getattr(config, 'symbol', 'EURUSD')
        self.logger = logging.getLogger(__name__)

    def generate_signal(self) -> dict[str, Any]:
        try:
            if not isinstance(self.frame, pd.DataFrame) or self.frame.empty:
                return self._no_signal("Insufficient market data")

            required = {"open", "high", "low", "close"}
            missing = required.difference(self.frame.columns)
            if missing:
                return self._no_signal(f"Missing columns: {', '.join(sorted(missing))}")

            # Check if pair is in MR list
            if self.pair.upper() not in self.config.trading_pairs:
                return self._no_signal(f"Pair {self.pair} not in MR list")

            # Create Mean Reversion strategy
            strategy = MeanReversion({
                'pair': self.pair,
                'hours': [0, 5, 11],
                'days': [0, 3],
                'rsi_threshold': 25,
                'tp_ratio': 1.5,
                'sl_pips': 20,
                'use_atr_sl': True,
                'atr_multiplier': 1.0,
                'min_confidence': 60,
                'risk_percent': 3.0,
            })

            signal = strategy.generate_signal(self.frame, self.current_time)

            if signal is None:
                return self._no_signal("Mean Reversion no signal")

            return self._format_signal(signal)

        except Exception as exc:
            self.logger.exception("Signal evaluation failed")
            return self._no_signal(f"Error: {exc}")

    def _format_signal(self, signal: Signal) -> dict[str, Any]:
        return {
            'signal': signal.direction.value,
            'strategy': signal.strategy,
            'confidence': signal.confidence,
            'reason': signal.reason,
            'trade': {
                'entry': signal.entry,
                'stop_loss': signal.stop_loss,
                'take_profit': signal.take_profit,
                'risk_reward': self._calculate_risk_reward(
                    signal.entry, signal.stop_loss, signal.take_profit
                ),
            },
            'metadata': signal.metadata,
        }

    def _calculate_risk_reward(self, entry: float, stop_loss: float, take_profit: float) -> float:
        risk = abs(entry - stop_loss)
        reward = abs(take_profit - entry)
        return round(reward / risk, 2) if risk > 0 else 0

    def _no_signal(self, reason: str) -> dict[str, Any]:
        return {
            'signal': None,
            'strategy': None,
            'confidence': 0.0,
            'reason': reason,
            'trade': None,
        }
