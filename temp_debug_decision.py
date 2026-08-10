from strategic.decision_engine import StrategicDecisionEngine
import pandas as pd
import structure.patterns as patterns_mod
import structure.smart_money as smc_mod

vals = [(1.0,1.01,0.99,1.005,100) for _ in range(30)]
idx = pd.date_range('2026-01-01', periods=len(vals), freq='15min')
frame = pd.DataFrame(vals, columns=['open','high','low','close','volume'], index=idx)
swings = {'highs': [], 'lows': []}

def fake_detect_patterns(frame_arg, swings_arg):
    return [{
        'pattern_name': 'TestPattern',
        'confidence': 0.9,
        'direction': 'bull',
        'breakout_level': float(frame_arg['close'].iloc[-1]),
        'stop_loss_zone': float(frame_arg['close'].iloc[-1]) - 0.001,
    }]

def fake_analyze(self, frame_arg, swings_arg):
    return {
        'bos': {'status': 'bull'},
        'choch': {'status': 'bull'},
        'order_block': {'status': 'bull', 'zone_high': 1.02, 'zone_low': 1.004},
        'fvg': {},
        'liquidity': {},
        'score': 0.8,
    }

patterns_mod.detect_patterns = fake_detect_patterns
smc_mod.SmartMoneyConcepts.analyze = fake_analyze

class FakeMT5:
    def get_open_positions(self):
        return []
    def get_equity(self):
        return 1000000.0

engine = StrategicDecisionEngine()
decision = engine.think(frame, swings, FakeMT5())
print(decision)
