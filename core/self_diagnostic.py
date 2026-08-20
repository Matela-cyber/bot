"""Self-diagnostic module for bot health monitoring."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger("diagnostic")


@dataclass(init=False)
class CycleReport:
    """Report of a single cycle execution."""

    timestamp: datetime
    cycle_type: str
    pairs_processed: int = 0
    pairs_skipped: int = 0
    signals_generated: int = 0
    trades_executed: int = 0
    errors: list[str]
    warnings: list[str]
    successes: list[str]
    checks_passed: dict[str, bool]
    checks_details: dict[str, str]

    def __init__(self, timestamp: datetime, cycle_type: str) -> None:
        self.timestamp = timestamp
        self.cycle_type = cycle_type
        self.pairs_processed = 0
        self.pairs_skipped = 0
        self.signals_generated = 0
        self.trades_executed = 0
        self.errors = []
        self.warnings = []
        self.successes = []
        self.checks_passed = {}
        self.checks_details = {}

    def add_success(self, msg: str) -> None:
        self.successes.append(msg)
        logger.info("SUCCESS: %s", msg)

    def add_warning(self, msg: str) -> None:
        self.warnings.append(msg)
        logger.warning("WARNING: %s", msg)

    def add_error(self, msg: str) -> None:
        self.errors.append(msg)
        logger.error("ERROR: %s", msg)

    def add_check(self, name: str, passed: bool, detail: str = "") -> None:
        self.checks_passed[name] = passed
        self.checks_details[name] = detail
        if passed:
            logger.debug("CHECK PASSED: %s: %s", name, detail or "passed")
        else:
            logger.warning("CHECK FAILED: %s: %s", name, detail or "failed")

    def is_healthy(self) -> bool:
        if self.errors:
            return False
        if not self.checks_passed:
            return True
        return all(self.checks_passed.values())

    def summary(self) -> str:
        lines = [
            f"CYCLE REPORT: {self.cycle_type}",
            f"   Time: {self.timestamp}",
            f"   Pairs: {self.pairs_processed} processed, {self.pairs_skipped} skipped",
            f"   Signals: {self.signals_generated}",
            f"   Trades: {self.trades_executed}",
            f"   Checks: {sum(1 for passed in self.checks_passed.values() if passed)}/{len(self.checks_passed)} passed",
        ]
        if self.errors:
            lines.append(f"   Errors: {len(self.errors)}")
        if self.warnings:
            lines.append(f"   Warnings: {len(self.warnings)}")
        if self.successes:
            lines.append(f"   Successes: {len(self.successes)}")
        return "\n".join(lines)
