from __future__ import annotations

import logging
from typing import Any, Optional

import pandas as pd

from config import settings
from structure.patterns import detect_patterns
from falcon.engine import FalconEngine
from structure.smart_money import SmartMoneyConcepts
from structure.confluence import ConfluenceEngine, CONFLUENCE_THRESHOLD
from risk.manager import RiskManager

logger = logging.getLogger(__name__)


CONFLUENCE_THRESHOLD_LOCAL = CONFLUENCE_THRESHOLD
MIN_PATTERN_CONFIDENCE = getattr(settings, "min_entry_confidence", 0.65)


class StrategicDecisionEngine:
    """Decision engine that runs 5 cycles to validate and execute trades."""

    def __init__(self) -> None:
        self.logger = logger
        self.falcon = FalconEngine()
        self.confluence = ConfluenceEngine()
        self.smc = SmartMoneyConcepts()

    def think(
        self,
        frame: pd.DataFrame,
        swings: dict,
        mt5_client,
        symbol: str,
        risk_multiplier: float = 1.0,
    ) -> dict[str, Any]:
        """Run the 5-cycle decision process and return an action dict for a specific pair."""
        cycles_passed = 0

        # Cycle 1: Pattern Detection
        pattern = self._detect_pattern(frame, swings)
        if not pattern:
            self.logger.info("Cycle 1: No pattern detected")
            return {"action": "SKIP", "reason": "no_pattern", "cycles_passed": cycles_passed, "pattern": None, "smc_data": None, "confluence": 0.0, "trade_plan": {}}
        cycles_passed = 1
        self.logger.info("Cycle 1: Pattern detected %s (%.2f)", pattern.get("pattern_name"), pattern.get("confidence", 0.0))

        # Build initial trade plan via Falcon engine
        trade_plan = self.falcon.generate_trade_plan(frame, pattern)

        # Cycle 2: SMC Confirmation
        smc_data = self._analyze_smc(frame, swings)
        if not smc_data or smc_data.get("score", 0.0) < settings.min_smc_score:
            self.logger.info("Cycle 2: SMC not supportive (score=%.2f)", smc_data.get("score", 0.0) if smc_data else 0.0)
            return {"action": "SKIP", "reason": "smc_not_supported", "cycles_passed": cycles_passed, "pattern": pattern, "smc_data": smc_data, "confluence": 0.0, "trade_plan": trade_plan}
        cycles_passed = 2
        self.logger.info("Cycle 2: SMC confirmed score=%.2f", smc_data.get("score", 0.0))

        # Cycle 3: Confluence Check
        conf = self._calculate_confluence(pattern, smc_data)
        if conf.get("score", 0.0) < CONFLUENCE_THRESHOLD_LOCAL:
            self.logger.info("Cycle 3: Confluence below threshold (%.2f)", conf.get("score", 0.0))
            return {"action": "SKIP", "reason": "low_confluence", "cycles_passed": cycles_passed, "pattern": pattern, "smc_data": smc_data, "confluence": conf.get("score", 0.0), "trade_plan": trade_plan}
        cycles_passed = 3
        self.logger.info("Cycle 3: Confluence passed score=%.2f", conf.get("score", 0.0))

        # Cycle 4: Timing Check
        timing = self._check_timing(frame, pattern, smc_data)
        if not timing.get("ready"):
            self.logger.info("Cycle 4: Timing not ready: %s", timing.get("reason"))
            return {"action": "HOLD", "reason": timing.get("reason"), "cycles_passed": cycles_passed, "pattern": pattern, "smc_data": smc_data, "confluence": conf.get("score", 0.0), "trade_plan": trade_plan}
        cycles_passed = 4
        self.logger.info("Cycle 4: Timing ready: %s", timing.get("reason"))

        # Cycle 5: Risk Check
        risk_out = self._check_risk(pattern.get("direction"), mt5_client)
        if not risk_out.get("approved"):
            self.logger.info("Cycle 5: Risk check failed: %s", risk_out.get("reason"))
            return {"action": "SKIP", "reason": f"risk_rejected:{risk_out.get('reason')}", "cycles_passed": cycles_passed, "pattern": pattern, "smc_data": smc_data, "confluence": conf.get("score", 0.0), "trade_plan": trade_plan}
        cycles_passed = 5
        self.logger.info("Cycle 5: Risk approved")

        # All cycles passed -> build final trade plan and EXECUTE
        final_plan = self._build_trade_plan(
            pattern,
            smc_data,
            conf.get("score", 0.0),
            symbol,
            risk_multiplier,
        )
        final_plan["confluence_score"] = conf.get("score", 0.0)
        return {
            "action": "EXECUTE",
            "reason": "all_checks_passed",
            "cycles_passed": cycles_passed,
            "pattern": pattern,
            "smc_data": smc_data,
            "confluence": conf.get("score", 0.0),
            "trade_plan": final_plan,
        }

    def _detect_pattern(self, frame: pd.DataFrame, swings: dict) -> Optional[dict[str, Any]]:
        """Detect patterns and return the best by confidence."""
        patterns = detect_patterns(frame, swings)
        if not patterns:
            return None
        best = max(patterns, key=lambda p: p.get("confidence", 0.0))
        if best.get("confidence", 0.0) < MIN_PATTERN_CONFIDENCE:
            return None
        return best

    def _analyze_smc(self, frame: pd.DataFrame, swings: dict) -> dict:
        """Return SMC analysis results."""
        return self.smc.analyze(frame, swings)

    def _calculate_confluence(self, pattern: dict, smc_data: dict) -> dict:
        """Wrap ConfluenceEngine.calculate_confluence."""
        return self.confluence.calculate_confluence(pattern, smc_data)

    def _check_timing(self, frame: pd.DataFrame, pattern: dict, smc_data: dict) -> dict:
        """Decide whether current price action satisfies timing criteria.

        This is intentionally conservative: prefer holding until clear retest/entry.
        """
        last = float(frame["close"].iloc[-1]) if frame is not None and len(frame) > 0 else 0.0

        # If BOS required, ensure it's confirmed in smc_data
        bos = smc_data.get("bos", {})
        if bos.get("status") and bos.get("strength", 0.0) < 0.1:
            return {"ready": False, "reason": "waiting_for_bos_confirmation", "wait_for": "bos"}

        # If FVG present, prefer price to be close or filling
        fvg = smc_data.get("fvg", {})
        if fvg.get("status"):
            cluster = fvg.get("all_gaps", [])
            distance = fvg.get("distance_from_price", float("inf"))
            size = fvg.get("size_pips", 0.0)
            cluster_bonus = min(0.5, 0.1 * len(cluster))
            if distance > (size * 2 + 0.0005) and cluster_bonus < 0.4:
                return {"ready": False, "reason": "waiting_for_fvg_fill", "wait_for": "fvg"}

        # If order block present, wait for retest within zone +/- buffer
        ob = smc_data.get("order_block", {})
        if ob.get("zone_high") and ob.get("zone_low"):
            zone_width = abs(ob.get("zone_high") - ob.get("zone_low"))
            buffer = zone_width * 0.5 + 0.0001
            retest_count = ob.get("candles", 1)
            if not (ob.get("zone_low") - buffer <= last <= ob.get("zone_high") + buffer):
                return {"ready": False, "reason": "waiting_for_order_block_retest", "wait_for": f"order_block_{retest_count}_candles"}
            if retest_count > 1 and zone_width > 0 and abs(last - ((ob.get("zone_high") + ob.get("zone_low")) / 2)) > zone_width * 0.75:
                return {"ready": False, "reason": "waiting_for_multi_candle_ob_retest", "wait_for": "order_block"}

        # Liquidity sweeps: accept if price has approached a liquidity zone
        liq = smc_data.get("liquidity", {})
        nearest_high = liq.get("nearest_high")
        nearest_low = liq.get("nearest_low")
        if nearest_high is not None and pattern.get("direction") == "bear":
            if last > nearest_high - 0.0005:
                return {"ready": True, "reason": "liquidity_above_scanned", "wait_for": "liquidity"}
            return {"ready": False, "reason": "waiting_for_liquidity_sweep", "wait_for": "liquidity"}
        if nearest_low is not None and pattern.get("direction") == "bull":
            if last < nearest_low + 0.0005:
                return {"ready": True, "reason": "liquidity_below_scanned", "wait_for": "liquidity"}
            return {"ready": False, "reason": "waiting_for_liquidity_sweep", "wait_for": "liquidity"}

        return {"ready": True, "reason": "timing_ok", "wait_for": None}

    def _check_risk(self, direction: str, mt5_client) -> dict:
        """Request approval from RiskManager."""
        rm = RiskManager(account_balance=float(settings.account_balance), daily_loss=0.0, current_equity=None, peak_equity=None)
        approved, reason = rm.approve_trade(direction, mt5_client)
        return {"approved": approved, "reason": reason}

    def _build_trade_plan(
        self,
        pattern: dict,
        smc_data: dict,
        confluence: float,
        symbol: str,
        risk_multiplier: float = 1.0,
    ) -> dict:
        """Compose the final trade plan for execution."""
        direction = pattern.get("direction", "neutral")
        entry = pattern.get("breakout_level") or float(smc_data.get("fvg", {}).get("gap_low", 0.0)) or float(pattern.get("entry_price", 0.0))
        if not entry:
            entry = float(pattern.get("entry_price") or 0.0)
        if not entry:
            entry = 0.0

        # stop loss / take profit heuristics if not provided
        sl = pattern.get("stop_loss") or pattern.get("stop_loss_zone") or (entry - 0.001 if direction == "bull" else entry + 0.001)
        tp = pattern.get("take_profit") or (entry + abs(entry - sl) * 2 if direction == "bull" else entry - abs(entry - sl) * 2)

        risk_allocation = float(settings.pair_risk_allocation.get(symbol, settings.risk_per_trade))
        risk_amount = float(settings.account_balance) * risk_allocation * float(risk_multiplier)
        distance = abs(float(entry) - float(sl))
        position_size = 0.0
        if distance > 0:
            position_size = risk_amount / distance

        return {
            "symbol": symbol,
            "pattern_name": pattern.get("pattern_name"),
            "direction": direction,
            "entry_price": float(entry),
            "stop_loss": float(sl),
            "take_profit": float(tp),
            "confluence_score": float(confluence),
            "falcon_score": float(pattern.get("confidence", 0.0)),
            "smc_data": smc_data,
            "risk_multiplier": float(risk_multiplier),
            "quality": float(pattern.get("confidence", 0.0)),
            "position_size": float(round(position_size, 4)),
            "risk_amount": float(risk_amount),
        }
