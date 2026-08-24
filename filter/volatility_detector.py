"""MT5-based volatility and unscheduled-event detection."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


class VolatilityDetector:
    """Detect volatility changes from spread, ATR, and tick volume."""

    def __init__(self, mt5_client: Any) -> None:
        self.mt5_client = mt5_client
        self.baseline_spread: dict[str, float] = {}
        self.baseline_atr: dict[str, float] = {}
        self.baseline_volume: dict[str, float] = {}
        self.last_spike_time: dict[str, datetime] = {}
        self.spike_cooldown_minutes = 30
        self._last_update_time: dict[str, datetime] = {}
        self._update_interval = timedelta(hours=1)

    def _ensure_baseline(self, symbol: str) -> None:
        now = datetime.now(timezone.utc)
        last_update = self._last_update_time.get(symbol)
        if last_update is None or now - last_update >= self._update_interval:
            self._update_baseline(symbol)
            self._last_update_time[symbol] = now

    def _update_baseline(self, symbol: str) -> None:
        resolved = self.mt5_client.resolve_symbol(symbol)
        prices = self.mt5_client.get_price(resolved)
        spec = self.mt5_client.get_symbol_spec(resolved)
        point = float(spec["point"])
        if point <= 0:
            raise RuntimeError(f"Invalid point size for {resolved}")
        current_spread = max(0.0, (prices["ask"] - prices["bid"]) / point)
        self.baseline_spread[resolved] = self._ema(
            self.baseline_spread.get(resolved), current_spread)

        frame = self._get_ohlcv(resolved, "15m", 100)
        if frame is None or len(frame) < 20:
            raise RuntimeError(f"Insufficient 1m data for {resolved}")
        current_atr = float(
            (frame["high"] - frame["low"]).abs().tail(20).mean())
        self.baseline_atr[resolved] = self._ema(
            self.baseline_atr.get(resolved), current_atr)
        if "tick_volume" in frame.columns:
            current_volume = float(frame["tick_volume"].tail(20).mean())
            self.baseline_volume[resolved] = self._ema(
                self.baseline_volume.get(resolved), current_volume)

    @staticmethod
    def _ema(previous: float | None, current: float) -> float:
        return current if previous is None else previous * 0.95 + current * 0.05

    def _get_ohlcv(self, symbol: str, timeframe: str, count: int) -> pd.DataFrame | None:
        mt5_module = self.mt5_client._require_mt5()
        resolved = self.mt5_client.resolve_symbol(symbol)
        timeframe_map: dict[str, Any] = {
            "1m": getattr(mt5_module, "TIMEFRAME_M1"),
            "5m": getattr(mt5_module, "TIMEFRAME_M5"),
            "15m": getattr(mt5_module, "TIMEFRAME_M15"),
            "1h": getattr(mt5_module, "TIMEFRAME_H1"),
        }
        rates = mt5_module.copy_rates_from_pos(
            resolved, timeframe_map[timeframe], 0, count)
        if rates is None or len(rates) == 0:
            return None
        frame = pd.DataFrame(rates)
        if len(frame) > 1:
            frame = frame.iloc[:-1].copy()
        return frame

    def detect_volatility(self, symbol: str = "EURUSD") -> dict[str, Any]:
        """Return current volatility level and component multipliers."""
        try:
            resolved = self.mt5_client.resolve_symbol(symbol)
            self._ensure_baseline(resolved)
            prices = self.mt5_client.get_price(resolved)
            spec = self.mt5_client.get_symbol_spec(resolved)
            point = float(spec["point"])
            if point <= 0:
                raise RuntimeError(f"Invalid point size for {resolved}")
            spread_multiplier = ((prices["ask"] - prices["bid"]) / point) / \
                max(self.baseline_spread.get(resolved, 0.0), 1e-12)
            frame = self._get_ohlcv(resolved, "15m", 30)
            if frame is None or len(frame) < 5:
                raise RuntimeError(
                    f"Insufficient current 1m data for {resolved}")
            current_atr = float(
                (frame["high"] - frame["low"]).abs().tail(5).mean())
            atr_multiplier = current_atr / \
                max(self.baseline_atr.get(resolved, 0.0), 1e-12)
            if spread_multiplier <= 1.5 and "tick_volume" in frame.columns:
                current_volume = float(frame["tick_volume"].tail(5).mean())
                volume_multiplier = current_volume / max(
                    self.baseline_volume.get(resolved, 0.0), 1e-12
                ) if self.baseline_volume.get(resolved, 0.0) else 1.0
            else:
                volume_multiplier = 1.0
        except Exception as exc:
            logger.error("Volatility detection failed for %s: %s", symbol, exc)
            return {"level": "unavailable", "spread_multiplier": 0.0, "atr_multiplier": 0.0, "volume_multiplier": 0.0, "reason": f"market_data_unavailable: {exc}"}

        result: dict[str, Any] = {
            "level": "normal",
            "spread_multiplier": round(spread_multiplier, 2),
            "atr_multiplier": round(atr_multiplier, 2),
            "volume_multiplier": round(volume_multiplier, 2),
            "reason": "normal_market",
        }
        last_spike = self.last_spike_time.get(resolved)
        if last_spike is not None:
            minutes_since = (datetime.now(timezone.utc) -
                             last_spike).total_seconds() / 60
            if minutes_since < self.spike_cooldown_minutes:
                result.update(
                    {"level": "cooldown", "reason": f"cooldown ({self.spike_cooldown_minutes - minutes_since:.0f}m remaining)"})
                return result
        details = f"spread: {spread_multiplier:.1f}x, atr: {atr_multiplier:.1f}x, vol: {volume_multiplier:.1f}x"
        if max(spread_multiplier, atr_multiplier, volume_multiplier) > 3.0:
            result.update({"level": "high", "reason": details})
            self.last_spike_time[resolved] = datetime.now(timezone.utc)
            logger.warning("HIGH VOLATILITY %s: %s", resolved, details)
        elif max(spread_multiplier, atr_multiplier, volume_multiplier) > 2.0:
            result.update({"level": "medium", "reason": details})
        elif spread_multiplier > 1.5:
            result.update(
                {"level": "low", "reason": f"spread: {spread_multiplier:.1f}x"})
        return result

    def should_trade(self, symbol: str = "EURUSD") -> tuple[bool, str, float]:
        """Return entry permission, reason, and volatility risk multiplier."""
        result = self.detect_volatility(symbol)
        level = result["level"]
        if level in {"high", "cooldown", "unavailable"}:
            return False, f"{level.replace('_', ' ').title()}: {result['reason']}", 0.0
        if level == "medium":
            return True, f"Medium volatility: {result['reason']} (reduce risk)", 0.5
        if level == "low":
            return True, f"Low volatility: {result['reason']} (reduce risk)", 0.8
        return True, "Normal market", 1.0

    def get_risk_multiplier(self, symbol: str = "EURUSD") -> float:
        """Return the current volatility risk multiplier."""
        return self.should_trade(symbol)[2]
