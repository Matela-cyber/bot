"""Self-diagnostic module for bot health monitoring."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger("diagnostic")


@dataclass
class CycleReport:
    """Report of a single cycle execution."""

    timestamp: datetime
    cycle_type: str
    pairs_processed: int = 0
    pairs_skipped: int = 0
    signals_generated: int = 0
    trades_executed: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    successes: list[str] = field(default_factory=list)
    checks_passed: dict[str, bool] = field(default_factory=dict)
    checks_details: dict[str, str] = field(default_factory=dict)

    def add_success(self, msg: str) -> None:
        self.successes.append(msg)
        logger.info("✅ %s", msg)

    def add_warning(self, msg: str) -> None:
        self.warnings.append(msg)
        logger.warning("⚠️ %s", msg)

    def add_error(self, msg: str) -> None:
        self.errors.append(msg)
        logger.error("❌ %s", msg)

    def add_check(self, name: str, passed: bool, detail: str = "") -> None:
        self.checks_passed[name] = passed
        self.checks_details[name] = detail
        if passed:
            logger.debug("✅ %s: %s", name, detail or "passed")
        else:
            logger.warning("❌ %s: %s", name, detail or "failed")

    def is_healthy(self) -> bool:
        if self.errors:
            return False
        if not self.checks_passed:
            return True
        return all(self.checks_passed.values())

    def summary(self) -> str:
        lines = [
            f"📊 CYCLE REPORT: {self.cycle_type}",
            f"   Time: {self.timestamp}",
            f"   Pairs: {self.pairs_processed} processed, {self.pairs_skipped} skipped",
            f"   Signals: {self.signals_generated}",
            f"   Trades: {self.trades_executed}",
            f"   Checks: {sum(1 for passed in self.checks_passed.values() if passed)}/{len(self.checks_passed)} passed",
        ]
        if self.errors:
            lines.append(f"   ❌ Errors: {len(self.errors)}")
        if self.warnings:
            lines.append(f"   ⚠️ Warnings: {len(self.warnings)}")
        if self.successes:
            lines.append(f"   ✅ Successes: {len(self.successes)}")
        return "\n".join(lines)
