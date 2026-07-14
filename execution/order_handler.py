from __future__ import annotations

from typing import Any


class OrderHandler:
    """Handles order placement with basic idempotency support."""

    def __init__(self) -> None:
        self._last_order_id: str | None = None

    def place_order(self, payload: dict[str, Any]) -> dict[str, Any]:
        order_id = payload.get("client_order_id") or "order-001"
        if order_id == self._last_order_id:
            return {"status": "duplicate", "order_id": order_id}
        self._last_order_id = order_id
        return {"status": "accepted", "order_id": order_id}
