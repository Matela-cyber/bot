from __future__ import annotations

from typing import Any


import pandas as pd


class FalconQuestionnaire:
    """Layer 2 Falcon questionnaire for mindset-ready trade scoring."""

    def __init__(self, frame: pd.DataFrame, pattern: dict[str, Any], entry_price: float, stop_loss: float, take_profit: float) -> None:
        self.frame = frame
        self.pattern = pattern
        self.entry_price = entry_price
        self.stop_loss = stop_loss
        self.take_profit = take_profit

    def evaluate(self) -> dict[str, Any]:
        structure_score = self._score_structure()
        confirmation_score = self._score_confirmation()
        trend_score = self._score_trend_alignment()
        volatility_score = self._score_volatility()
        risk_reward_score = self._score_risk_reward()
        mindset_score = self._score_mindset(
            structure_score,
            confirmation_score,
            trend_score,
            volatility_score,
            risk_reward_score,
        )

        overall_score = min(1.0, max(0.0, (
            structure_score * 0.20
            + confirmation_score * 0.20
            + trend_score * 0.18
            + volatility_score * 0.12
            + risk_reward_score * 0.18
            + mindset_score * 0.12
        )))

        return {
            "structure_score": round(structure_score, 2),
            "confirmation_score": round(confirmation_score, 2),
            "trend_score": round(trend_score, 2),
            "volatility_score": round(volatility_score, 2),
            "risk_reward_score": round(risk_reward_score, 2),
            "mindset_score": round(mindset_score, 2),
            "overall_score": round(overall_score, 2),
            "questionnaire": {
                "layers": [
                    "Structure",
                    "Confirmation",
                    "Trend Alignment",
                    "Volatility",
                    "Risk/Reward",
                    "Mindset",
                ],
                "meta": {
                    "pattern_confidence": float(self.pattern.get("confidence", 0.0)),
                    "breakout_strength": float(self.pattern.get("breakout_strength", 0.0)),
                    "candlestick_strength": float(self.pattern.get("candlestick_strength", 0.0)),
                    "trend_strength": float(self.pattern.get("trend_strength", 0.0)),
                    "range_contraction": float(self.pattern.get("range_contraction", 0.0)),
                },
            },
        }

    def _score_structure(self) -> float:
        quality = float(self.pattern.get("confidence", 0.0))
        metadata = self.pattern.get("metadata", {})
        if isinstance(metadata, dict):
            quality += float(metadata.get("quality", 0.0)) * 0.10
        return min(1.0, max(0.0, quality))

    def _score_confirmation(self) -> float:
        confirmation = float(self.pattern.get("candlestick_strength", 0.0))
        if self.pattern.get("candlestick_bonus"):
            confirmation += 0.08
        return min(1.0, max(0.0, confirmation))

    def _score_trend_alignment(self) -> float:
        trend_strength = float(self.pattern.get("trend_strength", 0.0))
        direction = self.pattern.get("direction")
        if direction == "bull":
            score = 0.5 + min(0.5, max(0.0, trend_strength * 20.0))
        elif direction == "bear":
            score = 0.5 + min(0.5, max(0.0, -trend_strength * 20.0))
        else:
            score = 0.5
        return min(1.0, max(0.0, score))

    def _score_volatility(self) -> float:
        contraction = float(self.pattern.get("range_contraction", 0.0))
        if contraction <= 0.0:
            return 0.35
        if contraction >= 0.15:
            return 1.0
        return min(1.0, 0.35 + contraction * 4.0)

    def _score_risk_reward(self) -> float:
        if self.stop_loss == self.entry_price or self.take_profit == self.entry_price:
            return 0.0

        risk = abs(self.entry_price - self.stop_loss)
        reward = abs(self.take_profit - self.entry_price)
        if risk <= 0 or reward <= 0:
            return 0.0

        ratio = reward / risk
        if ratio >= 3.0:
            return 1.0
        return min(1.0, ratio / 3.0 + 0.2)

    def _score_mindset(
        self,
        structure_score: float,
        confirmation_score: float,
        trend_score: float,
        volatility_score: float,
        risk_reward_score: float,
    ) -> float:
        base = (
            structure_score * 0.22
            + confirmation_score * 0.20
            + trend_score * 0.18
            + volatility_score * 0.15
            + risk_reward_score * 0.25
        )

        if float(self.pattern.get("breakout_strength", 0.0)) > 0.75:
            base += 0.05
        if float(self.pattern.get("candlestick_bonus", False)):
            base += 0.03
        base += min(0.05, float(self.pattern.get("candlestick_priority_bonus", 0.0)))

        return min(1.0, max(0.0, base))
