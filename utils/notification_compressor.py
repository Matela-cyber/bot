"""Rate-limit repetitive Telegram notifications."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from notifications.telegram_sender import TelegramSender


def _new_last_sent() -> dict[str, datetime]:
    """Create an empty per-category send-time map."""
    return {}


def _new_counter() -> dict[str, int]:
    """Create an empty per-category counter map."""
    return {}


@dataclass
class NotificationCompressor:
    """Count repeated category messages and send periodic summaries."""

    telegram: TelegramSender
    reset_interval_seconds: int = 300
    _last_sent: dict[str, datetime] = field(default_factory=_new_last_sent)
    _counter: dict[str, int] = field(default_factory=_new_counter)

    def send_compressed(self, category: str, message: str, force: bool = False) -> bool:
        """Send immediately when forced or after the category interval."""
        now = datetime.now(timezone.utc)
        self._counter[category] = self._counter.get(category, 0) + 1
        last_sent = self._last_sent.get(category, now)
        elapsed = (now - last_sent).total_seconds()
        if not force and elapsed < self.reset_interval_seconds:
            return True
        count = self._counter[category]
        payload = f"{message} (repeated {count}x in {int(elapsed)}s)" if count > 1 else message
        sent = self.telegram.send(payload)
        if sent:
            self._counter[category] = 0
            self._last_sent[category] = now
        return sent

    def reset(self) -> None:
        """Clear all pending notification counters."""
        self._last_sent.clear()
        self._counter.clear()
