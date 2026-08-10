from __future__ import annotations

from typing import Any

import pandas as pd

from config import settings
from falcon.questionnaire import FalconQuestionnaire


class FalconEngine:
    """Falcon assessment engine with fuller questionnaire scoring."""

    def generate_trade_plan(self, frame: pd.DataFrame, pattern: dict[str, Any]) -> dict[str, Any]:
        direction = pattern.get("direction", "neutral")
        entry_price = float(frame["close"].iloc[-1])
        if direction == "bull":
            stop_loss = float(pattern.get("stop_loss_zone", entry_price - 0.0005))
            take_profit = float(entry_price + abs(entry_price - stop_loss) * 2)
        elif direction == "bear":
            stop_loss = float(pattern.get("stop_loss_zone", entry_price + 0.0005))
            take_profit = float(entry_price - abs(entry_price - stop_loss) * 2)
        else:
            stop_loss = entry_price
            take_profit = entry_price

        questionnaire = FalconQuestionnaire(
            frame=frame,
            pattern=pattern,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
        ).evaluate()

        quality = questionnaire["overall_score"]
        confirmation_score = questionnaire["confirmation_score"]
        eligible = self._is_trade_eligible(quality, confirmation_score)
        status = self._grade_quality(quality, confirmation_score, eligible)

        return {
            "pattern_name": pattern.get("pattern_name"),
            "direction": direction,
            "quality": round(min(1.0, quality), 2),
            "status": status,
            "breakout_level": pattern.get("breakout_level"),
            "entry_price": entry_price,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "falcon_scores": questionnaire,
        }

    def _is_trade_eligible(self, quality: float, confirmation_score: float) -> bool:
        return (
            quality >= settings.min_overall_score
            and confirmation_score >= settings.min_confirmation
        )

    def _grade_quality(self, quality: float, confirmation_score: float, eligible: bool) -> str:
        if not eligible:
            return "Rejected"

        if quality >= 0.80 and confirmation_score >= settings.min_confirmation:
            return "High Confidence"
        if quality >= settings.min_overall_score:
            return "Moderate Confidence"
        return "Risk Entry"
