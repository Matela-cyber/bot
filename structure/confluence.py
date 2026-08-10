from __future__ import annotations

import logging
from typing import Any

from config import settings

logger = logging.getLogger(__name__)


CONFLUENCE_THRESHOLD = 0.70
MIN_PATTERN_CONFIDENCE = 0.65
MIN_SMC_SCORE = 0.30


class ConfluenceEngine:
    """Compute confluence between Falcon pattern signals and SMC/ICT detectors."""

    def __init__(self) -> None:
        self.logger = logger

    def get_grade(self, confluence: float) -> str:
        """Return a human grade string for a confluence score.

        Args:
            confluence: float score in 0..1

        Returns:
            Grade string
        """
        if confluence >= 0.80:
            return "Very High"
        if confluence >= 0.70:
            return "High"
        if confluence >= 0.60:
            return "Medium"
        return "Low"

    def calculate_confluence(self, pattern: dict[str, Any], smc_data: dict[str, Any]) -> dict[str, Any]:
        """Calculate confluence score and contributors.

        The returned dict contains keys described in the project spec.
        """
        falcon_score = float(pattern.get("confidence", 0.0)) if pattern else 0.0

        timeframe = pattern.get("timeframe", "15min").lower() if pattern else "15min"
        asset = pattern.get("symbol", "generic").lower() if pattern else "generic"
        tf_scale = settings.confluence_timeframe_scales.get(timeframe, 1.0)
        asset_scale = settings.confluence_asset_scales.get(asset, 1.0)
        total_scale = tf_scale * asset_scale

        # contributors initialized
        contributors = {"bos": 0.0, "choch": 0.0, "order_block": 0.0, "fvg": 0.0, "liquidity": 0.0}
        smc_score = 0.0

        pat_dir = pattern.get("direction") if pattern else None

        # BOS
        bos = smc_data.get("bos", {}) if smc_data else {}
        if bos.get("status") in ("bull", "bear"):
            if pat_dir and bos.get("status") == pat_dir:
                contributors["bos"] = 0.25 * total_scale
                smc_score += contributors["bos"]

        # CHoCH
        choch = smc_data.get("choch", {}) if smc_data else {}
        if choch.get("status") in ("bull", "bear"):
            if pat_dir and choch.get("status") == pat_dir:
                contributors["choch"] = 0.25 * total_scale
                smc_score += contributors["choch"]

        # Order Block
        ob = smc_data.get("order_block", {}) if smc_data else {}
        if ob.get("status") in ("bull", "bear"):
            contributors["order_block"] = 0.20 * total_scale
            smc_score += contributors["order_block"]

        # FVG
        fvg = smc_data.get("fvg", {}) if smc_data else {}
        if fvg.get("status") in ("bull", "bear"):
            contributors["fvg"] = 0.15 * total_scale
            smc_score += contributors["fvg"]

        # Liquidity
        liq = smc_data.get("liquidity", {}) if smc_data else {}
        if liq.get("nearest_high") or liq.get("nearest_low"):
            contributors["liquidity"] = 0.15 * total_scale
            smc_score += contributors["liquidity"]

        # clamp smc_score to 0..1
        smc_score = max(0.0, min(1.0, smc_score))

        # final weighted average
        confluence = (falcon_score * 0.50) + (smc_score * 0.50)
        confluence = float(max(0.0, min(1.0, confluence)))

        aligned = False
        if pat_dir and (bos.get("status") == pat_dir or choch.get("status") == pat_dir):
            aligned = True

        reason_parts = []
        if aligned:
            reason_parts.append("Direction aligned between Falcon and SMC")
        if smc_score <= 0:
            reason_parts.append("No supporting SMC signals")
        if falcon_score <= 0:
            reason_parts.append("Low Falcon confidence")

        reason = ", ".join(reason_parts) if reason_parts else "Confluence computed"

        grade = self.get_grade(confluence)

        result = {
            "score": confluence,
            "grade": grade,
            "falcon_score": falcon_score,
            "smc_score": smc_score,
            "aligned": aligned,
            "contributors": contributors,
            "reason": reason,
        }

        self.logger.info("Confluence: score=%.2f grade=%s falcon=%.2f smc=%.2f", confluence, grade, falcon_score, smc_score)
        return result
