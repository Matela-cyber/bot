from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from filter.volatility_detector import VolatilityDetector


class FakeClient:
    def __init__(self, spread: float = 0.0001) -> None:
        self.spread = spread

    def _require_mt5(self) -> Any:
        return SimpleNamespace(
            TIMEFRAME_M1=1,
            TIMEFRAME_M5=5,
            TIMEFRAME_M15=15,
            TIMEFRAME_H1=60,
            symbol_info=self._symbol_info,
            copy_rates_from_pos=self._copy_rates,
        )

    def _symbol_info(self, symbol: str) -> SimpleNamespace:
        return SimpleNamespace(point=0.0001)

    def _copy_rates(self, symbol: str, timeframe: int, start: int, count: int) -> list[dict[str, float]]:
        return [
            {"high": 1.1, "low": 1.099, "close": 1.0995, "tick_volume": 100}
        ] * count

    def resolve_symbol(self, symbol: str) -> str:
        return symbol

    def get_price(self, symbol: str) -> dict[str, float]:
        return {"bid": 1.1000, "ask": 1.1000 + self.spread}

    def get_symbol_spec(self, symbol: str) -> dict[str, float | str]:
        return {"symbol": symbol, "point": 0.0001}


def test_normal_market_is_allowed() -> None:
    detector = VolatilityDetector(FakeClient())
    result = detector.detect_volatility("EURUSD")
    allowed, reason, multiplier = detector.should_trade("EURUSD")

    assert result["level"] == "normal"
    assert allowed is True
    assert reason == "Normal market"
    assert multiplier == 1.0


def test_unavailable_market_data_blocks_trading() -> None:
    class BrokenClient(FakeClient):
        def resolve_symbol(self, symbol: str) -> str:
            raise RuntimeError("terminal disconnected")

    detector = VolatilityDetector(BrokenClient())
    allowed, reason, multiplier = detector.should_trade("EURUSD")

    assert allowed is False
    assert "Unavailable" in reason
    assert multiplier == 0.0
