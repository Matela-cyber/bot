"""SMC Market Structure Detector (BOS, CHoCH, HH, HL, LH, LL, Order Blocks, FVG, Liquidity)."""
from __future__ import annotations

import builtins
import logging
from typing import Any, cast, Optional

import numpy as np
import pandas as pd
from config import settings

logger = logging.getLogger("smc.structure")

# Constants (configuration-based)
MIN_FVG_SIZE = getattr(settings, "smc_min_fvg_size", 0.00025)
DEFAULT_ATR_PERIOD = getattr(settings, "smc_atr_period", 20)
IMPULSE_MULTIPLIER = getattr(settings, "smc_impulse_multiplier", 2.0)
ORDER_BLOCK_CANDLES = getattr(settings, "smc_order_block_candles", 3)


class SmartMoneyConcepts:
    """Backward-compatible SMC facade used by the test suite."""

    def detect_bos(self, frame: pd.DataFrame, swings: dict[str, Any]) -> dict[str, Any]:
        detector = StructureDetector(swings, frame)
        return detector.detect_bos()

    def detect_choch(self, frame: pd.DataFrame, swings: dict[str, Any]) -> dict[str, Any]:
        detector = StructureDetector(swings, frame)
        return detector.detect_choch()

    def detect_order_block(self, frame: pd.DataFrame, swings: dict[str, Any]) -> dict[str, Any]:
        detector = StructureDetector(swings or {}, frame)
        return detector.detect_order_block()

    def detect_fvg(self, frame: pd.DataFrame) -> dict[str, Any]:
        detector = StructureDetector({}, frame)
        return detector.detect_fvg()

    def detect_liquidity(self, frame: pd.DataFrame, swings: dict[str, Any]) -> dict[str, Any]:
        detector = StructureDetector(swings or {}, frame)
        return detector.detect_liquidity()

    def analyze(self, frame: pd.DataFrame, swings: dict[str, Any]) -> dict[str, Any]:
        if frame is None or frame.empty:
            return {"score": 0.5, "signals": [], "status": "empty"}

        result: dict[str, Any] = {
            "score": 0.5,
            "signals": [],
            "status": "neutral",
        }
        bos = self.detect_bos(frame, swings)
        choch = self.detect_choch(frame, swings)
        if bos.get("status"):
            result["signals"].append({"name": "bos", "status": bos["status"]})
            result["score"] += 0.2
        if choch.get("status"):
            result["signals"].append({"name": "choch", "status": choch["status"]})
            result["score"] += 0.2
        if self.detect_fvg(frame).get("status"):
            result["signals"].append({"name": "fvg", "status": self.detect_fvg(frame)["status"]})
            result["score"] += 0.1
        if result["score"] > 0.75:
            result["status"] = "bullish"
        elif result["score"] < 0.25:
            result["status"] = "bearish"
        return result


class StructureDetector:
    """Smart Money Concepts market structure detector."""

    def __init__(self, swings: dict[str, Any], frame: pd.DataFrame | None = None) -> None:
        """Initialize structure detector."""
        self.highs: list[Any] = list(swings.get("highs", []))
        self.lows: list[Any] = list(swings.get("lows", []))
        self.frame = frame
        self._log_debug()

    def _log_debug(self) -> None:
        logger.debug("StructureDetector: highs=%s, lows=%s", len(self.highs), len(self.lows))

    def _get_price(self, point: Any) -> float:
        """Return the price value from either a dict or object point."""
        if isinstance(point, dict):
            point_map = cast(dict[str, Any], point)
            value = point_map.get("price", 0.0)
            if value is None:
                return 0.0
            return float(value)

        value = getattr(point, "price", 0.0)
        if value is None:
            return 0.0
        return float(value)

    def _get_index(self, point: Any) -> int:
        """Return the index value from either a dict or object point."""
        if isinstance(point, dict):
            point_map = cast(dict[str, Any], point)
            value = point_map.get("index", 0)
            if value is None:
                return 0
            return int(value)

        value = getattr(point, "index", 0)
        if value is None:
            return 0
        return int(value)

    def _get_current_price(self) -> float:
        """Get current price from frame, fallback to latest swing."""
        if self.frame is not None and not self.frame.empty:
            return float(self.frame["close"].iloc[-1])
        if self.highs:
            return self._get_price(self.highs[-1])
        return 0.0

    def _get_recent_swing(self, swings: list[Any], lookback: int = 3) -> list[Any]:
        """Get the most recent swing points with a lookback window."""
        if len(swings) < lookback:
            return swings
        return swings[-lookback:]

    def _is_confirmed_break(self, level: float, direction: str) -> bool:
        """Check if price has confirmed a break with candle close."""
        if self.frame is None or self.frame.empty or len(self.frame) < 3:
            return False

        last_candles = self.frame.tail(3)
        current_close = float(last_candles["close"].iloc[-1])
        current_high = float(last_candles["high"].iloc[-1])
        current_low = float(last_candles["low"].iloc[-1])
        prev_close = float(last_candles["close"].iloc[-2])

        atr = self._calculate_atr()
        min_move = atr * 0.3 if atr > 0 else 0.0005

        if direction == "bull":
            if current_close > level and current_high > level:
                if current_close - prev_close > min_move:
                    return True
        else:
            if current_close < level and current_low < level:
                if prev_close - current_close > min_move:
                    return True

        return False

    def _calculate_atr(self, period: int = 14) -> float:
        """Calculate ATR for momentum filtering."""
        if self.frame is None or self.frame.empty or len(self.frame) < period:
            return 0.001

        high = self.frame["high"].tail(period + 1)
        low = self.frame["low"].tail(period + 1)
        close = self.frame["close"].tail(period + 1)

        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        return float(tr.mean())

    def detect_bos(self) -> dict[str, Any]:
        """Detect Break of Structure (BOS) with confirmation."""
        result: dict[str, Any] = {
            "status": None,
            "level": 0.0,
            "strength": 0.0,
            "confirmed": False,
            "timestamp": None,
        }

        current_price = self._get_current_price()

        if len(self.highs) >= 2:
            previous_high = self._get_price(self.highs[-2])
            current_high = self._get_price(self.highs[-1])
            if current_price > previous_high or current_high > previous_high:
                confirmed = self._is_confirmed_break(previous_high, "bull") or current_price > previous_high
                strength = self._calculate_break_strength(previous_high, "bull")
                result.update({
                    "status": "bull",
                    "level": previous_high,
                    "strength": strength,
                    "confirmed": confirmed,
                    "timestamp": pd.Timestamp.now(),
                })
                logger.info("Bullish BOS detected at %.5f (confirmed=%s)", previous_high, confirmed)
                return result

        if len(self.lows) >= 2:
            previous_low = self._get_price(self.lows[-2])
            current_low = self._get_price(self.lows[-1])
            if current_price < previous_low or current_low < previous_low:
                confirmed = self._is_confirmed_break(previous_low, "bear") or current_price < previous_low
                strength = self._calculate_break_strength(previous_low, "bear")
                result.update({
                    "status": "bear",
                    "level": previous_low,
                    "strength": strength,
                    "confirmed": confirmed,
                    "timestamp": pd.Timestamp.now(),
                })
                logger.info("Bearish BOS detected at %.5f (confirmed=%s)", previous_low, confirmed)
                return result

        recent_highs = self._get_recent_swing(self.highs, 4)
        recent_lows = self._get_recent_swing(self.lows, 4)

        if len(recent_highs) >= 2:
            previous_high = self._get_price(recent_highs[-2])
            current_high = self._get_price(recent_highs[-1])
            if current_high > previous_high:
                confirmed = self._is_confirmed_break(previous_high, "bull")
                strength = self._calculate_break_strength(previous_high, "bull")
                result.update({
                    "status": "bull",
                    "level": previous_high,
                    "strength": strength,
                    "confirmed": confirmed,
                    "timestamp": pd.Timestamp.now(),
                })
                return result

        if len(recent_lows) >= 2:
            previous_low = self._get_price(recent_lows[-2])
            current_low = self._get_price(recent_lows[-1])
            if current_low < previous_low:
                confirmed = self._is_confirmed_break(previous_low, "bear")
                strength = self._calculate_break_strength(previous_low, "bear")
                result.update({
                    "status": "bear",
                    "level": previous_low,
                    "strength": strength,
                    "confirmed": confirmed,
                    "timestamp": pd.Timestamp.now(),
                })
                return result

        return result

    def _calculate_break_strength(self, level: float, direction: str) -> float:
        """Calculate strength of a break based on distance and ATR."""
        if self.frame is None or self.frame.empty:
            return 0.5

        current_price = self._get_current_price()
        atr = self._calculate_atr()
        if atr <= 0:
            return 0.5

        distance = abs(current_price - level)
        raw_strength = distance / atr
        return min(1.0, raw_strength * 0.5)

    def detect_choch(self) -> dict[str, Any]:
        """Detect Change of Character (CHoCH) with confirmation."""
        result: dict[str, Any] = {
            "status": None,
            "level": 0.0,
            "strength": 0.0,
            "confirmed": False,
            "timestamp": None,
        }

        if len(self.highs) < 2 or len(self.lows) < 2:
            return result

        current_price = self._get_current_price()
        last_high = self._get_price(self.highs[-1])
        prev_high = self._get_price(self.highs[-2])
        last_low = self._get_price(self.lows[-1])
        prev_low = self._get_price(self.lows[-2])

        if last_low <= prev_low and current_price > prev_high:
            level = prev_high
            confirmed = self._is_confirmed_break(level, "bull") or current_price > prev_high
            strength = self._calculate_break_strength(level, "bull")
            result.update({
                "status": "bull",
                "level": level,
                "strength": strength,
                "confirmed": confirmed,
                "timestamp": pd.Timestamp.now(),
            })
            logger.info("Bullish CHoCH detected at %.5f (confirmed=%s)", level, confirmed)
            return result

        if last_high >= prev_high and current_price < prev_low:
            level = prev_low
            confirmed = self._is_confirmed_break(level, "bear") or current_price < prev_low
            strength = self._calculate_break_strength(level, "bear")
            result.update({
                "status": "bear",
                "level": level,
                "strength": strength,
                "confirmed": confirmed,
                "timestamp": pd.Timestamp.now(),
            })
            logger.info("Bearish CHoCH detected at %.5f (confirmed=%s)", level, confirmed)
            return result

        if len(self.highs) >= 4 and len(self.lows) >= 4:
            if (self._get_price(self.lows[-1]) < self._get_price(self.lows[-2]) and
                self._get_price(self.highs[-1]) > self._get_price(self.highs[-2])):
                level = self._get_price(self.highs[-2])
                confirmed = self._is_confirmed_break(level, "bull")
                strength = self._calculate_break_strength(level, "bull")
                result.update({
                    "status": "bull",
                    "level": level,
                    "strength": strength,
                    "confirmed": confirmed,
                    "timestamp": pd.Timestamp.now(),
                })
                return result

            if (self._get_price(self.highs[-1]) > self._get_price(self.highs[-2]) and
                self._get_price(self.lows[-1]) < self._get_price(self.lows[-2])):
                level = self._get_price(self.lows[-2])
                confirmed = self._is_confirmed_break(level, "bear")
                strength = self._calculate_break_strength(level, "bear")
                result.update({
                    "status": "bear",
                    "level": level,
                    "strength": strength,
                    "confirmed": confirmed,
                    "timestamp": pd.Timestamp.now(),
                })
                return result

        return result

    def detect_hh_hl(self) -> dict[str, Any]:
        """Detect Higher Highs (HH) and Higher Lows (HL) - Bullish structure."""
        result: dict[str, Any] = {"hh": False, "hl": False, "strength": 0.0}

        if len(self.highs) >= 3:
            result["hh"] = (self._get_price(self.highs[-1]) > self._get_price(self.highs[-2]) and
                            self._get_price(self.highs[-2]) > self._get_price(self.highs[-3]))

        if len(self.lows) >= 3:
            result["hl"] = (self._get_price(self.lows[-1]) > self._get_price(self.lows[-2]) and
                            self._get_price(self.lows[-2]) > self._get_price(self.lows[-3]))

        if result["hh"] and result["hl"]:
            result["strength"] = 1.0
        elif result["hh"] or result["hl"]:
            result["strength"] = 0.5

        return result

    def detect_lh_ll(self) -> dict[str, Any]:
        """Detect Lower Highs (LH) and Lower Lows (LL) - Bearish structure."""
        result: dict[str, Any] = {"lh": False, "ll": False, "strength": 0.0}

        if len(self.highs) >= 3:
            result["lh"] = (self._get_price(self.highs[-1]) < self._get_price(self.highs[-2]) and
                            self._get_price(self.highs[-2]) < self._get_price(self.highs[-3]))

        if len(self.lows) >= 3:
            result["ll"] = (self._get_price(self.lows[-1]) < self._get_price(self.lows[-2]) and
                            self._get_price(self.lows[-2]) < self._get_price(self.lows[-3]))

        if result["lh"] and result["ll"]:
            result["strength"] = 1.0
        elif result["lh"] or result["ll"]:
            result["strength"] = 0.5

        return result

    def _clamp(self, value: float, min_val: float, max_val: float) -> float:
        """Clamp value between min and max."""
        return max(min_val, min(max_val, value))

    def _get_average_candle_size(self, lookback: int = 20) -> float:
        """Calculate average candle size (range) over lookback period."""
        if self.frame is None or self.frame.empty or len(self.frame) < lookback:
            if self.frame is not None and not self.frame.empty and len(self.frame) > 0:
                rng = (self.frame["high"] - self.frame["low"]).abs()
                return float(rng.mean()) if not rng.empty else 0.0
            return 0.0
        rng = (self.frame["high"] - self.frame["low"]).abs()
        return float(rng.iloc[-lookback:].mean())

    def detect_order_block(self) -> dict[str, Any]:
        """Detect Order Blocks as the candle range preceding a strong impulse."""
        result: dict[str, Any] = {
            "status": None,
            "zone_high": None,
            "zone_low": None,
            "midpoint": None,
            "strength": 0.0,
            "description": "No order block",
        }
        if self.frame is None or self.frame.empty or len(self.frame) < 5:
            return result

        avg_candle = self._get_average_candle_size()
        if avg_candle <= 0:
            return result

        # Find impulse: candle or run where move > IMPULSE_MULTIPLIER * avg_candle
        rng = (self.frame["close"] - self.frame["open"]).abs()
        threshold = avg_candle * IMPULSE_MULTIPLIER
        impulses = rng[rng > threshold]
        if impulses.empty:
            return result

        # Use the last impulse found
        try:
            loc_result = self.frame.index.get_loc(impulses.index[-1])
            pos = int(loc_result) if isinstance(loc_result, (int, np.integer)) else len(self.frame) - 1
        except Exception:
            pos = len(self.frame) - 1

        # The order block is the candle(s) BEFORE the impulse
        ob_pos = max(0, pos - 1)
        ob_start = max(0, ob_pos - (ORDER_BLOCK_CANDLES - 1))
        ob_slice = self.frame.iloc[ob_start : ob_pos + 1]
        if ob_pos >= len(self.frame) or ob_slice.empty:
            return result

        zone_high = float(ob_slice["high"].max())
        zone_low = float(ob_slice["low"].min())
        midpoint = (zone_high + zone_low) / 2.0
        strength = float(rng.iloc[pos]) / max(avg_candle, 1e-8)
        strength = self._clamp(strength / (IMPULSE_MULTIPLIER * 2.0), 0.0, 1.0)
        direction = "bull" if self.frame["close"].iloc[pos] > self.frame["open"].iloc[pos] else "bear"
        
        result.update({
            "status": direction,
            "zone_high": zone_high,
            "zone_low": zone_low,
            "midpoint": midpoint,
            "strength": strength,
            "description": "Order block identified",
            "candles": int(len(ob_slice)),
        })
        logger.debug("Order block %s zone %.5f-%.5f (strength=%.2f)", direction, zone_high, zone_low, strength)
        return result

    def detect_fvg(self) -> dict[str, Any]:
        """Detect Fair Value Gaps (FVG) by comparing candle n and n+2."""
        result: dict[str, Any] = {
            "status": None,
            "gap_high": None,
            "gap_low": None,
            "filled": False,
            "size_pips": 0.0,
            "distance_from_price": 0.0,
            "description": "No FVG",
        }
        if self.frame is None or self.frame.empty or len(self.frame) < 3:
            return result

        gaps: list[tuple[int, str, float, float, float]] = []
        # Iterate over triplets where we compare candle i and i+2
        for i in range(len(self.frame) - 2):
            c0_high = float(self.frame["high"].iloc[i])
            c0_low = float(self.frame["low"].iloc[i])
            c2_high = float(self.frame["high"].iloc[i + 2])
            c2_low = float(self.frame["low"].iloc[i + 2])
            
            # Bullish gap: low of candle2 > high of candle0
            if c2_low > c0_high:
                gap_low = c0_high
                gap_high = c2_low
                size = gap_high - gap_low
                if size >= MIN_FVG_SIZE:
                    gaps.append((i, "bull", gap_high, gap_low, size))
            
            # Bearish gap: high of candle2 < low of candle0
            if c2_high < c0_low:
                gap_high = c0_low
                gap_low = c2_high
                size = gap_high - gap_low
                if size >= MIN_FVG_SIZE:
                    gaps.append((i, "bear", gap_high, gap_low, size))

        if not gaps:
            return result

        # Choose nearest gap to current price
        last_close = self._get_current_price()
        
        def gap_distance(g: tuple[int, str, float, float, float]) -> float:
            _, _, gap_high, gap_low, _ = g
            center = (gap_high + gap_low) / 2.0
            return abs(last_close - center)

        gaps.sort(key=gap_distance)
        _gap_idx, status, gap_high, gap_low, size = gaps[0]
        
        # Include list of nearby gaps for cluster analysis
        all_gaps: list[dict[str, Any]] = [
            {
                "index": g[0],
                "status": g[1],
                "gap_high": float(g[2]),
                "gap_low": float(g[3]),
                "size": float(g[4]),
            }
            for g in gaps
        ]
        
        filled = ((gap_low <= last_close <= gap_high) or
                  (status == "bull" and last_close <= gap_low) or
                  (status == "bear" and last_close >= gap_high))
        distance = abs(((gap_high + gap_low) / 2.0) - last_close)
        
        result.update({
            "status": status,
            "gap_high": float(gap_high),
            "gap_low": float(gap_low),
            "filled": bool(filled),
            "size_pips": float(size),
            "distance_from_price": float(distance),
            "description": "FVG detected",
            "all_gaps": all_gaps,
        })
        logger.debug("Detected FVG %s %.5f-%.5f size=%.5f filled=%s", status, gap_high, gap_low, size, filled)
        return result

    def detect_liquidity(self) -> dict[str, Any]:
        """Detect buy/sell liquidity zones from swings."""
        result: dict[str, Any] = {
            "buy_liquidity": None,
            "sell_liquidity": None,
            "nearest_high": None,
            "nearest_low": None,
            "description": "No liquidity",
        }
        if len(self.highs) == 0 or len(self.lows) == 0:
            return result

        last_close = self._get_current_price()
        atr = self._calculate_atr()

        # Find nearest swing high above price
        highs_above: list[float] = []
        lows_below: list[float] = []

        for h in self.highs:
            price = self._get_price(h)
            if price > last_close:
                highs_above.append(price)

        for l in self.lows:
            price = self._get_price(l)
            if price < last_close:
                lows_below.append(price)

        nearest_high: Optional[float] = min(highs_above) if highs_above else None
        nearest_low: Optional[float] = max(lows_below) if lows_below else None

        buy_liquidity: Optional[float] = (nearest_low - (atr * 0.5)) if nearest_low is not None else None
        sell_liquidity: Optional[float] = (nearest_high + (atr * 0.5)) if nearest_high is not None else None

        result.update({
            "buy_liquidity": float(buy_liquidity) if buy_liquidity is not None else None,
            "sell_liquidity": float(sell_liquidity) if sell_liquidity is not None else None,
            "nearest_high": float(nearest_high) if nearest_high is not None else None,
            "nearest_low": float(nearest_low) if nearest_low is not None else None,
            "description": "Liquidity zones computed",
        })
        logger.debug("Liquidity nearest_high=%s nearest_low=%s", nearest_high, nearest_low)
        return result

    def get_smc_summary(self) -> dict[str, Any]:
        """Return a comprehensive summary of all detected SMC features."""
        return {
            "bos": self.detect_bos(),
            "choch": self.detect_choch(),
            "hh_hl": self.detect_hh_hl(),
            "lh_ll": self.detect_lh_ll(),
            "order_block": self.detect_order_block(),
            "fvg": self.detect_fvg(),
            "liquidity": self.detect_liquidity(),
        }

    def get_structure_summary(self) -> dict[str, Any]:
        """Return a summary of all detected structures (backward compatible)."""
        return self.get_smc_summary()


# Backward compatibility for legacy tests that instantiate SmartMoneyConcepts without
# importing it directly from this module.
builtins.SmartMoneyConcepts = SmartMoneyConcepts
__all__ = ["StructureDetector", "SmartMoneyConcepts"]