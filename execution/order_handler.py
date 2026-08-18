from __future__ import annotations

import logging
from typing import Any
from datetime import datetime

logger = logging.getLogger("execution.order_handler")


class OrderHandler:
    """
    Handles order placement with idempotency, retries, and MT5 integration.
    
    Features:
    - Idempotency: prevents duplicate orders
    - Retry logic: retries failed orders up to N times
    - Logging: tracks all order attempts
    - Validation: checks order payload before execution
    """

    def __init__(
        self,
        max_retries: int = 3,
        retry_delay_seconds: int = 2,
    ) -> None:
        """
        Initialize order handler.
        
        Args:
            max_retries: Number of retry attempts for failed orders
            retry_delay_seconds: Delay between retry attempts
        """
        self._last_order_id: str | None = None
        self._order_history: list[dict[str, Any]] = []
        self.max_retries = max_retries
        self.retry_delay_seconds = retry_delay_seconds

    def place_order(
        self,
        payload: dict[str, Any],
        mt5_client: Any = None,
    ) -> dict[str, Any]:
        """
        Place an order with idempotency and retry support.
        
        Args:
            payload: dict with keys:
                - client_order_id: str (optional, for idempotency)
                - symbol: str
                - direction: str ("buy" or "sell")
                - lots: float
                - stop_loss: float (optional)
                - take_profit: float (optional)
                - comment: str (optional)
            mt5_client: MT5Client instance (optional)
        
        Returns:
            dict with:
                - status: "accepted", "duplicate", "failed", "error"
                - order_id: str
                - message: str
                - attempts: int
        """
        # 1. Generate or get client_order_id
        client_order_id = payload.get("client_order_id")
        if not client_order_id:
            client_order_id = f"order_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{id(payload)}"
            payload["client_order_id"] = client_order_id

        # 2. Idempotency check (prevent duplicate orders)
        if client_order_id == self._last_order_id:
            logger.warning(f"Duplicate order detected: {client_order_id}")
            return {
                "status": "duplicate",
                "order_id": client_order_id,
                "message": "Order already placed",
                "attempts": 0,
            }

        # 3. Validate payload
        validation_result = self._validate_payload(payload)
        if not validation_result["valid"]:
            logger.error(f"Order validation failed: {validation_result['reason']}")
            return {
                "status": "error",
                "order_id": client_order_id,
                "message": f"Validation failed: {validation_result['reason']}",
                "attempts": 0,
            }

        # 4. Execute with retries
        result = self._execute_with_retries(payload, mt5_client)

        # 5. Log order history
        self._order_history.append({
            "order_id": client_order_id,
            "payload": payload,
            "result": result,
            "timestamp": datetime.now().isoformat(),
        })

        # 6. Update last order id for idempotency
        if result["status"] in ("accepted", "pending"):
            self._last_order_id = client_order_id

        return result

    def _validate_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Validate required fields in order payload."""
        required_fields = ["symbol", "direction", "lots"]
        missing = [f for f in required_fields if not payload.get(f)]

        if missing:
            return {"valid": False, "reason": f"Missing required fields: {missing}"}

        # Validate direction
        direction = payload.get("direction", "").lower()
        if direction not in ("buy", "sell"):
            return {"valid": False, "reason": f"Invalid direction: {direction}"}

        # Validate lots
        lots = payload.get("lots", 0)
        if lots <= 0:
            return {"valid": False, "reason": f"Invalid lot size: {lots}"}

        return {"valid": True, "reason": ""}

    def _execute_with_retries(
        self,
        payload: dict[str, Any],
        mt5_client: Any = None,
    ) -> dict[str, Any]:
        """
        Execute order with retry logic.
        
        Returns:
            dict with status, order_id, message, attempts
        """
        last_error = None

        for attempt in range(1, self.max_retries + 1):
            try:
                # If MT5 client is provided, use it
                if mt5_client and hasattr(mt5_client, "place_order"):
                    # Convert payload to MT5 format
                    order_result = mt5_client.place_order(
                        symbol=payload["symbol"],
                        order_type=payload["direction"],
                        lots=payload["lots"],
                        stop_loss=payload.get("stop_loss"),
                        take_profit=payload.get("take_profit"),
                        comment=payload.get("comment"),
                    )

                    # MT5Client returns a dict with status, ticket, etc.
                    if order_result.get("status") == "accepted":
                        logger.info(f"Order accepted: {payload['client_order_id']}")
                        return {
                            "status": "accepted",
                            "order_id": payload["client_order_id"],
                            "ticket": order_result.get("ticket"),
                            "message": "Order placed successfully",
                            "attempts": attempt,
                        }
                    else:
                        last_error = order_result.get("message", "Unknown error")
                        logger.warning(f"Order attempt {attempt} failed: {last_error}")

                else:
                    # Fallback: mock execution (for testing)
                    logger.warning("No MT5 client provided, using mock execution")
                    return {
                        "status": "accepted",
                        "order_id": payload["client_order_id"],
                        "ticket": 99999,
                        "message": "Mock order accepted",
                        "attempts": attempt,
                    }

            except Exception as e:
                last_error = str(e)
                logger.error(f"Order attempt {attempt} failed: {e}")

            # Wait before retry
            if attempt < self.max_retries:
                import time
                time.sleep(self.retry_delay_seconds)

        # All retries failed
        logger.error(f"Order failed after {self.max_retries} attempts: {last_error}")
        return {
            "status": "failed",
            "order_id": payload.get("client_order_id", "unknown"),
            "message": f"All {self.max_retries} retry attempts failed: {last_error}",
            "attempts": self.max_retries,
        }

    def get_order_history(self) -> list[dict[str, Any]]:
        """Return the order history."""
        return self._order_history

    def get_last_order_id(self) -> str | None:
        """Return the last order ID for idempotency."""
        return self._last_order_id

    def reset(self) -> None:
        """Reset the order handler state."""
        self._last_order_id = None
        self._order_history = []

    def is_duplicate(self, order_id: str) -> bool:
        """Check if an order is a duplicate."""
        return order_id == self._last_order_id