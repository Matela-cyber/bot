from __future__ import annotations

import logging
from typing import Any, Optional

import numpy as np
import pandas as pd
from config import settings

logger = logging.getLogger(__name__)

# Constants (no hardcoded magic numbers inline)
MIN_FVG_SIZE = getattr(settings, "smc_min_fvg_size", 0.00025)
DEFAULT_ATR_PERIOD = getattr(settings, "smc_atr_period", 20)
IMPULSE_MULTIPLIER = getattr(settings, "smc_impulse_multiplier", 2.0)
ORDER_BLOCK_CANDLES = getattr(settings, "smc_order_block_candles", 3)


class SmartMoneyConcepts:
    """Detect Smart Money Concepts (SMC) like BOS, CHoCH, Order Blocks, FVGs, and Liquidity.

    All public methods return a dict. If no detection, the returned dict contains
    'status': None and other fields set to None or sensible defaults.
    """

    def __init__(self) -> None:
        self.logger = logger

    # --- Helper methods
    def _calculate_atr(self, frame: pd.DataFrame, period: int = DEFAULT_ATR_PERIOD) -> float:
        """Calculate a simple ATR-like average true range over the frame."""
        if frame is None or len(frame) == 0:
            return 0.0
        tr = (frame["high"] - frame["low"]).abs()
        if len(tr) < period:
            return float(tr.mean()) if not tr.empty else 0.0
        return float(tr.rolling(period).mean().dropna().iloc[-1])

    def _infer_timeframe(self, frame: pd.DataFrame) -> Optional[str]:
        """Infer timeframe string like '15min' or '1H' from frame index."""
        if not isinstance(frame.index, pd.DatetimeIndex):
            return None
        freq = pd.infer_freq(frame.index)
        if freq:
            return freq
        diffs = frame.index.to_series().diff().dropna()
        if diffs.empty:
            return None
        mode = diffs.mode()
        if mode.empty:
            return None
        return str(mode.iloc[0])

    def _timeframe_minutes(self, frame: pd.DataFrame) -> int:
        tf = self._infer_timeframe(frame)
        if tf is None:
            return 15
        # crude parse: e.g. '15T' or '15min' or 'H'
        if tf.endswith("T") or tf.lower().endswith("min"):
            num = ''.join(ch for ch in tf if ch.isdigit())
            return int(num) if num else 1
        if tf.upper().endswith("H"):
            num = ''.join(ch for ch in tf if ch.isdigit())
            return int(num) * 60 if num else 60
        return 15

    def _find_recent_swings(self, swings: dict[str, list[Any]], count: int = 3) -> dict[str, list[Any]]:
        """Return the last `count` swings for highs and lows.

        Swings is expected to be {'highs': [...], 'lows': [...]} where items may be dicts
        containing 'price' and 'index' or objects with corresponding attributes.
        """
        highs = swings.get("highs", []) if swings else []
        lows = swings.get("lows", []) if swings else []
        return {"highs": highs[-count:], "lows": lows[-count:]} if highs or lows else {"highs": [], "lows": []}

    def _is_break_confirmed(self, frame: pd.DataFrame, level: float, direction: str, lookback: int = 3) -> bool:
        """Confirm a break by requiring a close beyond `level` within the last `lookback` candles."""
        if frame is None or len(frame) == 0:
            return False
        recent = frame["close"].iloc[-lookback:]
        if direction == "bull":
            return bool((recent > level).any())
        return bool((recent < level).any())

    def _get_average_candle_size(self, frame: pd.DataFrame, lookback: int = 20) -> float:
        if frame is None or len(frame) == 0:
            return 0.0
        rng = (frame["high"] - frame["low"]).abs()
        if len(rng) < lookback:
            return float(rng.mean()) if not rng.empty else 0.0
        return float(rng.iloc[-lookback:].mean())

    def _clamp(self, value: float, min_val: float, max_val: float) -> float:
        return max(min_val, min(max_val, value))

    # --- Detectors
    def detect_bos(self, frame: pd.DataFrame, swings: dict) -> dict:
        """Detect Break of Structure (BOS).

        Returns dict with keys: status, level, strength, description
        """
        result = {"status": None, "level": None, "strength": 0.0, "description": "No BOS detected"}
        if frame is None or len(frame) == 0:
            return result
        recent = self._find_recent_swings(swings, 3)
        highs = recent.get("highs", [])
        lows = recent.get("lows", [])
        if len(highs) < 2 and len(lows) < 2:
            return result

        # scale constants by timeframe: larger timeframes => larger gaps and impulses
        minutes = self._timeframe_minutes(frame)
        tf_scale = max(1.0, (minutes / 15.0) ** 0.5)
        atr = self._calculate_atr(frame)
        last_close = float(frame["close"].iloc[-1])

        # Bullish BOS: break above previous swing high
        if len(highs) >= 2:
            prev_high = highs[-2]["price"] if isinstance(highs[-2], dict) else getattr(highs[-2], "price", None)
            if prev_high is not None and last_close > prev_high and self._is_break_confirmed(frame, prev_high, "bull"):
                strength = abs(last_close - prev_high) / max(atr, 1e-8)
                strength = self._clamp(strength, 0.0, 1.0)
                result.update({"status": "bull", "level": float(prev_high), "strength": float(strength), "description": "Bullish BOS: close above prior swing high"})
                self.logger.info("Detected Bull BOS at %.5f (strength=%.2f)", prev_high, strength)
                return result

        # Bearish BOS: break below previous swing low
        if len(lows) >= 2:
            prev_low = lows[-2]["price"] if isinstance(lows[-2], dict) else getattr(lows[-2], "price", None)
            if prev_low is not None and last_close < prev_low and self._is_break_confirmed(frame, prev_low, "bear"):
                strength = abs(last_close - prev_low) / max(atr, 1e-8)
                strength = self._clamp(strength, 0.0, 1.0)
                result.update({"status": "bear", "level": float(prev_low), "strength": float(strength), "description": "Bearish BOS: close below prior swing low"})
                self.logger.info("Detected Bear BOS at %.5f (strength=%.2f)", prev_low, strength)
                return result

        return result

    def detect_choch(self, frame: pd.DataFrame, swings: dict) -> dict:
        """Detect Change of Character (CHoCH) indicating reversal."""
        result = {"status": None, "level": None, "strength": 0.0, "description": "No CHoCH detected"}
        if frame is None or len(frame) == 0:
            return result
        recent = self._find_recent_swings(swings, 3)
        highs = recent.get("highs", [])
        lows = recent.get("lows", [])
        if len(highs) < 3 or len(lows) < 3:
            return result

        # Extract numeric lists
        high_prices = [h["price"] if isinstance(h, dict) else getattr(h, "price", None) for h in highs]
        low_prices = [l["price"] if isinstance(l, dict) else getattr(l, "price", None) for l in lows]
        if any(v is None for v in high_prices + low_prices):
            return result

        # Detect bullish CHoCH: prior lower lows then break above a swing high
        # Check pattern: low_prices should show lower lows before bounce
        if low_prices[0] > low_prices[1] > low_prices[2]:
            # now a break above recent swing high
            prev_high = highs[-2]["price"] if isinstance(highs[-2], dict) else getattr(highs[-2], "price", None)
            last_close = float(frame["close"].iloc[-1])
            if prev_high is not None and last_close > prev_high and self._is_break_confirmed(frame, prev_high, "bull"):
                vol = frame.get("volume")
                strength = 0.0
                if vol is not None and len(vol) > 0:
                    strength = float(frame["volume"].iloc[-1]) / max(float(frame["volume"].iloc[-20:].mean()), 1.0)
                    strength = self._clamp(strength, 0.0, 1.0)
                else:
                    atr = self._calculate_atr(frame)
                    strength = self._clamp(abs(last_close - prev_high) / max(atr, 1e-8), 0.0, 1.0)
                result.update({"status": "bull", "level": float(prev_high), "strength": strength, "description": "Bullish CHoCH: reversal to bull"})
                self.logger.info("Detected Bull CHoCH at %.5f (strength=%.2f)", prev_high, strength)
                return result

        # Detect bearish CHoCH: prior higher highs then break below a swing low
        if high_prices[0] < high_prices[1] < high_prices[2]:
            prev_low = lows[-2]["price"] if isinstance(lows[-2], dict) else getattr(lows[-2], "price", None)
            last_close = float(frame["close"].iloc[-1])
            if prev_low is not None and last_close < prev_low and self._is_break_confirmed(frame, prev_low, "bear"):
                vol = frame.get("volume")
                strength = 0.0
                if vol is not None and len(vol) > 0:
                    strength = float(frame["volume"].iloc[-1]) / max(float(frame["volume"].iloc[-20:].mean()), 1.0)
                    strength = self._clamp(strength, 0.0, 1.0)
                else:
                    atr = self._calculate_atr(frame)
                    strength = self._clamp(abs(last_close - prev_low) / max(atr, 1e-8), 0.0, 1.0)
                result.update({"status": "bear", "level": float(prev_low), "strength": strength, "description": "Bearish CHoCH: reversal to bear"})
                self.logger.info("Detected Bear CHoCH at %.5f (strength=%.2f)", prev_low, strength)
                return result

        return result

    def detect_order_block(self, frame: pd.DataFrame, swings: dict) -> dict:
        """Detect Order Blocks as the candle range immediately preceding a strong impulse."""
        result = {"status": None, "zone_high": None, "zone_low": None, "midpoint": None, "strength": 0.0, "description": "No order block"}
        if frame is None or len(frame) == 0:
            return result

        # timeframe scale
        minutes = self._timeframe_minutes(frame)
        tf_scale = max(1.0, (minutes / 15.0) ** 0.5)

        avg_candle = self._get_average_candle_size(frame)
        if avg_candle <= 0:
            return result

        # Find impulse: candle or run where move > IMPULSE_MULTIPLIER * avg_candle * timeframe_scale
        rng = (frame["close"] - frame["open"]).abs()
        threshold = avg_candle * IMPULSE_MULTIPLIER * tf_scale
        impulses = rng[rng > threshold]
        if impulses.empty:
            return result

        # Use the last impulse found
        try:
            pos = int(frame.index.get_loc(impulses.index[-1]))
        except Exception:
            pos = len(frame) - 1

        # The order block is the candle(s) BEFORE the impulse
        ob_pos = max(0, pos - 1)
        # extend to multiple candles per settings
        ob_start = max(0, ob_pos - (ORDER_BLOCK_CANDLES - 1))
        ob_slice = frame.iloc[ob_start : ob_pos + 1]
        if ob_pos >= len(frame):
            return result

        zone_high = float(ob_slice["high"].max())
        zone_low = float(ob_slice["low"].min())
        midpoint = (zone_high + zone_low) / 2.0
        strength = float(rng.iloc[pos]) / max(avg_candle * tf_scale, 1e-8)
        strength = self._clamp(strength / (IMPULSE_MULTIPLIER * 2.0), 0.0, 1.0)
        direction = "bull" if frame["close"].iloc[pos] > frame["open"].iloc[pos] else "bear"
        result.update({"status": direction, "zone_high": zone_high, "zone_low": zone_low, "midpoint": midpoint, "strength": strength, "description": "Order block identified", "candles": int(len(ob_slice))})
        self.logger.info("Order block %s zone %.5f-%.5f (strength=%.2f)", direction, zone_high, zone_low, strength)
        return result

    def detect_fvg(self, frame: pd.DataFrame) -> dict:
        """Detect Fair Value Gaps (FVG) by comparing candle n and n+2."""
        result = {"status": None, "gap_high": None, "gap_low": None, "filled": False, "size_pips": 0.0, "distance_from_price": 0.0, "description": "No FVG"}
        if frame is None or len(frame) < 3:
            return result

        # timeframe scaling
        minutes = self._timeframe_minutes(frame)
        tf_scale = max(1.0, (minutes / 15.0) ** 0.5)

        gaps = []
        # iterate over triplets where we compare candle i and i+2
        for i in range(len(frame) - 2):
            c0_high = float(frame["high"].iloc[i])
            c0_low = float(frame["low"].iloc[i])
            c2_high = float(frame["high"].iloc[i + 2])
            c2_low = float(frame["low"].iloc[i + 2])
            # Bullish gap: low of candle2 > high of candle0
            if c2_low > c0_high:
                gap_low = c0_high
                gap_high = c2_low
                size = gap_high - gap_low
                if size >= MIN_FVG_SIZE * tf_scale:
                    gaps.append((i, "bull", gap_high, gap_low, size))
            # Bearish gap: high of candle2 < low of candle0
            if c2_high < c0_low:
                gap_high = c0_low
                gap_low = c2_high
                size = gap_high - gap_low
                if size >= MIN_FVG_SIZE * tf_scale:
                    gaps.append((i, "bear", gap_high, gap_low, size))

        if not gaps:
            return result

        # choose nearest gap to current price
        last_close = float(frame["close"].iloc[-1])
        def gap_distance(g):
            _, _, gap_high, gap_low, _ = g
            center = (gap_high + gap_low) / 2.0
            return abs(last_close - center)

        gaps.sort(key=gap_distance)
        idx, status, gap_high, gap_low, size = gaps[0]
        # include list of nearby gaps for cluster analysis
        all_gaps = [{"index": g[0], "status": g[1], "gap_high": float(g[2]), "gap_low": float(g[3]), "size": float(g[4])} for g in gaps]
        filled = (gap_low <= last_close <= gap_high) or (status == "bull" and last_close <= gap_low) or (status == "bear" and last_close >= gap_high)
        distance = abs(((gap_high + gap_low) / 2.0) - last_close)
        result.update({"status": status, "gap_high": float(gap_high), "gap_low": float(gap_low), "filled": bool(filled), "size_pips": float(size), "distance_from_price": float(distance), "description": "FVG detected", "all_gaps": all_gaps})
        self.logger.info("Detected FVG %s %.5f-%.5f size=%.5f filled=%s", status, gap_high, gap_low, size, filled)
        return result

    def detect_liquidity(self, frame: pd.DataFrame, swings: dict) -> dict:
        """Detect buy/sell liquidity zones from swings."""
        result = {"buy_liquidity": None, "sell_liquidity": None, "nearest_high": None, "nearest_low": None, "description": "No liquidity"}
        if frame is None or len(frame) == 0:
            return result
        highs = swings.get("highs", []) if swings else []
        lows = swings.get("lows", []) if swings else []
        last_close = float(frame["close"].iloc[-1])
        atr = self._calculate_atr(frame)

        # Find nearest swing high above price
        highs_above = [h["price"] if isinstance(h, dict) else getattr(h, "price", None) for h in highs if (h["price"] if isinstance(h, dict) else getattr(h, "price", None)) is not None and (h["price"] if isinstance(h, dict) else getattr(h, "price", None)) > last_close]
        lows_below = [l["price"] if isinstance(l, dict) else getattr(l, "price", None) for l in lows if (l["price"] if isinstance(l, dict) else getattr(l, "price", None)) is not None and (l["price"] if isinstance(l, dict) else getattr(l, "price", None)) < last_close]

        nearest_high = min(highs_above) if highs_above else None
        nearest_low = max(lows_below) if lows_below else None

        buy_liquidity = (nearest_low - (atr * 0.5)) if nearest_low is not None else None
        sell_liquidity = (nearest_high + (atr * 0.5)) if nearest_high is not None else None

        result.update({"buy_liquidity": float(buy_liquidity) if buy_liquidity is not None else None, "sell_liquidity": float(sell_liquidity) if sell_liquidity is not None else None, "nearest_high": float(nearest_high) if nearest_high is not None else None, "nearest_low": float(nearest_low) if nearest_low is not None else None, "description": "Liquidity zones computed"})
        self.logger.info("Liquidity nearest_high=%s nearest_low=%s", nearest_high, nearest_low)
        return result

    def analyze(self, frame: pd.DataFrame, swings: dict) -> dict:
        """Run all detectors and compute a combined SMC score and summary."""
        bos = self.detect_bos(frame, swings)
        choch = self.detect_choch(frame, swings)
        order_block = self.detect_order_block(frame, swings)
        fvg = self.detect_fvg(frame)
        liquidity = self.detect_liquidity(frame, swings)

        score = 0.5
        if bos.get("status"):
            score += 0.15
        if choch.get("status"):
            score += 0.15
        if order_block.get("status"):
            score += 0.10
        if fvg.get("status"):
            score += 0.10
        score = float(self._clamp(score, 0.0, 1.0))

        summary_parts = []
        if bos.get("status"):
            summary_parts.append(f"BOS={bos.get('status')}")
        if choch.get("status"):
            summary_parts.append(f"CHoCH={choch.get('status')}")
        if order_block.get("status"):
            summary_parts.append(f"OB={order_block.get('status')}")
        if fvg.get("status"):
            summary_parts.append(f"FVG={fvg.get('status')}")

        summary = ", ".join(summary_parts) if summary_parts else "No significant SMC signals"

        return {"bos": bos, "choch": choch, "order_block": order_block, "fvg": fvg, "liquidity": liquidity, "score": score, "summary": summary}
