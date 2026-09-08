"""Conservative position sizing and account-level risk controls."""

from __future__ import annotations

import logging
import math
from typing import Any


class RiskManager:
    MAX_RISK_PER_TRADE = 0.01

    def __init__(self, config: Any) -> None:
        if config is None:
            raise ValueError("config is required")
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.starting_balance = float(
            getattr(config, "account_balance", 1000.0))
        if self.starting_balance <= 0:
            raise ValueError("account balance must be positive")
        self.current_balance = self.starting_balance
        self.peak_balance = self.starting_balance
        self._daily_loss = 0.0
        self._daily_trades = 0
        self._max_drawdown = 0.0

    @property
    def daily_loss(self) -> float:
        return self._daily_loss

    @property
    def daily_trades(self) -> int:
        return self._daily_trades

    @property
    def max_drawdown(self) -> float:
        return self._max_drawdown

    def can_open_position(self) -> bool:
        max_open = int(getattr(self.config, "max_open_trades", 3))
        open_trades = int(getattr(self.config, "open_trades",
                          getattr(self.config, "current_open_trades", 0)))
        max_daily = int(getattr(self.config, "max_daily_trades", 15))
        daily_limit = self.starting_balance * \
            abs(float(getattr(self.config, "max_daily_loss", 0.015)))
        return (
            open_trades < max_open
            and self._daily_trades < max_daily
            and self._daily_loss < daily_limit
            and not self.check_drawdown()
        )

    def calculate_position_size(self, account_balance: float, risk_percent: float, sl_pips: float, pip_value: float) -> float:
        values = (account_balance, risk_percent, sl_pips, pip_value)
        if not all(math.isfinite(float(value)) for value in values):
            raise ValueError("position sizing inputs must be finite")
        if account_balance <= 0 or risk_percent <= 0 or sl_pips <= 0 or pip_value <= 0:
            raise ValueError("position sizing inputs must be positive")
        capped_risk = min(float(risk_percent), self.MAX_RISK_PER_TRADE)
        raw_size = account_balance * capped_risk / (sl_pips * pip_value)
        return math.floor(raw_size * 100) / 100

    def update_daily_stats(self, profit: float) -> None:
        if not math.isfinite(float(profit)):
            raise ValueError("profit must be finite")
        self.current_balance += float(profit)
        self._daily_trades += 1
        if profit < 0:
            self._daily_loss += abs(float(profit))
        self.peak_balance = max(self.peak_balance, self.current_balance)
        if self.peak_balance > 0:
            drawdown = max(0.0, (self.peak_balance -
                           self.current_balance) / self.peak_balance)
            self._max_drawdown = max(self._max_drawdown, drawdown)

    def reset_daily_stats(self) -> None:
        self._daily_loss = 0.0
        self._daily_trades = 0
        self._max_drawdown = 0.0
        self.peak_balance = self.current_balance

    def check_drawdown(self) -> bool:
        limit = abs(float(getattr(self.config, "drawdown_limit", 0.10)))
        if self.peak_balance <= 0:
            return True
        current_drawdown = max(
            0.0, (self.peak_balance - self.current_balance) / self.peak_balance)
        self._max_drawdown = max(self._max_drawdown, current_drawdown)
        return current_drawdown >= limit or self._max_drawdown >= limit
