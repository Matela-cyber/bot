import pandas as pd


def make_candles(values, freq="15min"):
    idx = pd.date_range("2026-01-01", periods=len(values), freq=freq)
    df = pd.DataFrame(values, columns=["open", "high", "low", "close", "volume"], index=idx)
    return df


def test_decision_engine_execute(monkeypatch):
    from strategic.decision_engine import StrategicDecisionEngine

    # Fake frame
    vals = [(1.0, 1.01, 0.99, 1.005, 100) for _ in range(30)]
    frame = make_candles(vals)
    swings = {"highs": [], "lows": []}

    # Monkeypatch detect_patterns to return a high-confidence bull pattern
    import strategic.decision_engine as de_mod

    def fake_detect_patterns(frame_arg, swings_arg):
        return [{
            "pattern_name": "TestPattern",
            "confidence": 0.9,
            "direction": "bull",
            "breakout_level": float(frame_arg["close"].iloc[-1]),
            "stop_loss_zone": float(frame_arg["close"].iloc[-1]) - 0.001,
        }]

    # Patch the detect_patterns used by the decision engine module
    monkeypatch.setattr(de_mod, "detect_patterns", fake_detect_patterns, raising=False)

    # Monkeypatch SmartMoneyConcepts.analyze to return supportive SMC
    import structure.smart_money as smc_mod

    def fake_analyze(self, frame_arg, swings_arg):
        return {
            "bos": {"status": "bull", "strength": 0.5},
            "choch": {"status": "bull"},
            "order_block": {"status": "bull", "zone_high": 1.02, "zone_low": 1.004},
            "fvg": {},
            "liquidity": {},
            "score": 0.8,
        }

    monkeypatch.setattr(smc_mod.SmartMoneyConcepts, "analyze", fake_analyze, raising=True)

    # Simple fake mt5 client for risk approval
    class FakeMT5:
        def get_open_positions(self):
            return []

        def get_equity(self):
            return 1000000.0

    engine = StrategicDecisionEngine()
    decision = engine.think(frame, swings, FakeMT5(), symbol="EURUSD")
    assert decision["action"] == "EXECUTE"
    assert decision["cycles_passed"] == 5
