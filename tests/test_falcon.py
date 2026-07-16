import pandas as pd

from falcon.engine import FalconEngine


def test_falcon_engine_generates_questionnaire_scores() -> None:
    frame = pd.DataFrame(
        {
            "open": [1.0, 1.01, 1.02, 1.03, 1.04],
            "high": [1.01, 1.02, 1.03, 1.04, 1.05],
            "low": [0.99, 1.0, 1.01, 1.02, 1.03],
            "close": [1.01, 1.02, 1.03, 1.04, 1.05],
            "volume": [100, 110, 105, 115, 120],
        },
        index=pd.to_datetime([
            "2026-01-01 00:00:00",
            "2026-01-01 00:15:00",
            "2026-01-01 00:30:00",
            "2026-01-01 00:45:00",
            "2026-01-01 01:00:00",
        ]),
    )
    pattern = {
        "pattern_name": "Bull_Flag",
        "direction": "bull",
        "confidence": 0.72,
        "candlestick_strength": 0.8,
        "candlestick_bonus": True,
        "breakout_strength": 0.85,
        "trend_strength": 0.003,
        "range_contraction": 0.12,
        "metadata": {"quality": 0.75},
        "breakout_level": 1.045,
    }

    engine = FalconEngine()
    trade_plan = engine.generate_trade_plan(frame, pattern)

    assert trade_plan["pattern_name"] == "Bull_Flag"
    assert trade_plan["quality"] >= 0.0
    assert trade_plan["quality"] <= 1.0
    assert "falcon_scores" in trade_plan
    assert trade_plan["falcon_scores"]["overall_score"] == trade_plan["quality"]
    assert trade_plan["falcon_scores"]["questionnaire"]["meta"]["pattern_confidence"] == 0.72
