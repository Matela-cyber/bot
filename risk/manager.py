from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from config import settings


@dataclass
class RiskAssessment:
    """Structured outcome for a proposed trade plan."""

    allowed: bool
    reason: str
    risk_amount: float
    position_size: float
    max_position_size: float
    drawdown_fraction: float


@dataclass
class RiskManager:
    account_balance: float
    daily_loss: float = 0.0
    consecutive_losses: int = 0

    def check_trade_limits(self, trade_plan: dict[str, Any]) -> bool:
        assessment = self.assess_trade(trade_plan)
        return assessment.allowed

    def assess_trade(self, trade_plan: dict[str, Any]) -> RiskAssessment:
        entry_price = float(trade_plan.get("entry_price", 0.0))
        stop_loss_price = float(trade_plan.get("stop_loss", 0.0))
        if self.account_balance <= 0:
            return RiskAssessment(False, "invalid_balance", 0.0, 0.0, 0.0, 0.0)
        if entry_price <= 0 or stop_loss_price <= 0:
            return RiskAssessment(False, "invalid_prices", 0.0, 0.0, 0.0, 0.0)

        distance = abs(entry_price - stop_loss_price)
        if distance <= 0:
            return RiskAssessment(False, "invalid_risk_distance", 0.0, 0.0, 0.0, 0.0)

        risk_amount = self.account_balance * settings.risk_per_trade
        max_position_size = risk_amount / distance
        position_size = min(max_position_size, self.account_balance * 0.25)
        position_size = max(0.0, position_size)

        daily_loss_limit = settings.daily_loss_limit * self.account_balance
        drawdown_limit = settings.drawdown_limit * self.account_balance

        if self.daily_loss >= drawdown_limit:
            drawdown_fraction = 0.0
            return RiskAssessment(False, "drawdown_limit", risk_amount, position_size, max_position_size, drawdown_fraction)

        if self.daily_loss >= daily_loss_limit:
            drawdown_fraction = max(0.0, (drawdown_limit - self.daily_loss) / self.account_balance)
            return RiskAssessment(False, "daily_loss_limit", risk_amount, position_size, max_position_size, drawdown_fraction)

        drawdown_fraction = max(0.0, (drawdown_limit - self.daily_loss) / self.account_balance)
        return RiskAssessment(True, "ok", risk_amount, position_size, max_position_size, drawdown_fraction)

    def position_size(self, entry_price: float, stop_loss_price: float) -> float:
        assessment = self.assess_trade({"entry_price": entry_price, "stop_loss": stop_loss_price})
        return assessment.position_size
