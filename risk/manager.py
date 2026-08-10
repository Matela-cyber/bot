from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from config import settings
from execution.mt5_client import MT5Client

MAX_CONCURRENT_POSITIONS = 2
MAX_SAME_DIRECTION_POSITIONS = 2
MAX_TOTAL_RISK_PERCENT = 0.03
DAILY_LOSS_LIMIT = 0.03
OVERALL_DRAWDOWN_LIMIT = 0.15
CONTRACT_SIZE = 100000.0


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
    current_equity: float | None = None
    peak_equity: float | None = None

    def get_open_positions(self, mt5_client: MT5Client) -> list[dict[str, Any]]:
        positions = mt5_client.get_open_positions()
        result: list[dict[str, Any]] = []
        for pos in positions:
            result.append(
                {
                    "ticket": pos["ticket"],
                    "symbol": pos["symbol"],
                    "direction": "bull" if pos["type"] == "buy" else "bear",
                    "entry": float(pos.get("entry_price", 0.0) or 0.0),
                    "sl": float(pos.get("sl", 0.0) or 0.0),
                    "tp": float(pos.get("tp", 0.0) or 0.0),
                    "current_price": float(pos.get("current_price", 0.0) or 0.0),
                    "pnl": float(pos.get("pnl", 0.0) or 0.0),
                    "pnl_percent": float(pos.get("pnl_percent", 0.0) or 0.0),
                    "volume": float(pos.get("volume", 0.0) or 0.0),
                }
            )
        return result

    def calculate_total_risk(self, mt5_client: MT5Client) -> float:
        positions = self.get_open_positions(mt5_client)
        total_risk_amount = 0.0
        for pos in positions:
            entry = pos.get("entry", 0.0)
            sl = pos.get("sl", 0.0)
            volume = pos.get("volume", 0.0)
            if entry and sl and volume:
                total_risk_amount += abs(entry - sl) * volume * CONTRACT_SIZE

        equity = mt5_client.get_equity()
        if equity <= 0:
            return 0.0

        return total_risk_amount / equity

    def approve_trade(self, direction: str, mt5_client: MT5Client) -> tuple[bool, str]:
        try:
            positions = self.get_open_positions(mt5_client)
        except Exception as exc:
            return False, f"open_positions_failed:{exc}"

        if len(positions) >= MAX_CONCURRENT_POSITIONS:
            return False, "max_concurrent_positions"

        same_direction_count = sum(1 for pos in positions if pos["direction"] == direction)
        if same_direction_count >= MAX_SAME_DIRECTION_POSITIONS:
            return False, "max_same_direction_positions"

        total_risk_pct = self.calculate_total_risk(mt5_client)
        if total_risk_pct >= MAX_TOTAL_RISK_PERCENT:
            return False, "max_total_risk_percent"

        return True, "approved"

    def check_limits(
        self,
        current_equity: float | None = None,
        peak_equity: float | None = None,
    ) -> tuple[bool, str]:
        if self.daily_loss >= DAILY_LOSS_LIMIT * self.account_balance:
            return False, "daily_loss_limit"

        effective_current_equity = (
            current_equity
            if current_equity is not None and current_equity > 0
            else self.account_balance
        )
        effective_peak_equity = (
            peak_equity
            if peak_equity is not None and peak_equity > 0
            else self.peak_equity
            if self.peak_equity is not None and self.peak_equity > 0
            else effective_current_equity
        )

        if effective_peak_equity <= 0:
            return True, "ok"

        drawdown = (effective_peak_equity - effective_current_equity) / effective_peak_equity
        if drawdown >= OVERALL_DRAWDOWN_LIMIT:
            return False, "overall_drawdown_limit"

        return True, "ok"

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
