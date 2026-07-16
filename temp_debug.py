from data.ingestor import fetch_local_ohlcv
from data.preprocessor import prepare_ohlcv
from structure.swing_detector import detect_swings
from structure.patterns.bull_flag import BullFlagPattern
from structure.patterns.bear_flag import BearFlagPattern
from structure.patterns.bull_flat import BullFlatPattern
from structure.patterns.bear_flat import BearFlatPattern
from structure.patterns.bull_triangle import BullTrianglePattern
from structure.patterns.bear_triangle import BearTrianglePattern
from structure.patterns.expanding_triangle import ExpandingTrianglePattern
from structure.patterns.rising_wedge import RisingWedgePattern
from structure.patterns.falling_wedge import FallingWedgePattern
from structure.patterns.ascending_channel import AscendingChannelPattern
from structure.patterns.descending_channel import DescendingChannelPattern
from structure.patterns.head_and_shoulders import HeadAndShouldersPattern
from structure.patterns.inverse_head_and_shoulders import InverseHeadAndShouldersPattern
from structure.patterns.double_top import DoubleTopPattern
from structure.patterns.double_bottom import DoubleBottomPattern
from structure.candlestick_validator import analyze_candlestick_confirmation
from structure.pattern_validator import PatternValidator
from config import settings
from structure.xgboost_validator import XGBoostValidator

frame = prepare_ohlcv(fetch_local_ohlcv(days=30))
print('frame len', len(frame))
print(frame['close'].tail(15).to_list())
swings = detect_swings(frame)
print('highs', len(swings['highs']))
print('lows', len(swings['lows']))
print('high prices', [h['price'] for h in swings['highs'][-10:]])
print('low prices', [l['price'] for l in swings['lows'][-10:]])
print('candlestick', analyze_candlestick_confirmation(frame))
validator = PatternValidator()
xgb_validator = XGBoostValidator(model_path=settings.xgboost_model_path)
for cls in [BullFlagPattern, BearFlagPattern, BullFlatPattern, BearFlatPattern, BullTrianglePattern, BearTrianglePattern, ExpandingTrianglePattern, RisingWedgePattern, FallingWedgePattern, AscendingChannelPattern, DescendingChannelPattern, HeadAndShouldersPattern, InverseHeadAndShouldersPattern, DoubleTopPattern, DoubleBottomPattern]:
    det = cls()
    result = det.detect(frame, swings)
    print('detector', det.name, 'result', result is not None)
    if result is not None:
        conf = analyze_candlestick_confirmation(frame)
        result['candlestick_strength'] = conf.strength
        result['candlestick_bonus'] = conf.confirmed
        result['candlestick_priority'] = conf.priority_level
        result['candlestick_priority_bonus'] = conf.priority_bonus
        result['trend_strength'] = float(frame['close'].iloc[-1] - frame['close'].iloc[-15]) if len(frame) >= 15 else 0.0
        result['range_contraction'] = (float((frame['high'] - frame['low']).iloc[-10:].mean()) - float((frame['high'] - frame['low']).iloc[-20:-10].mean())) / float((frame['high'] - frame['low']).iloc[-20:-10].mean()) if len(frame) >= 20 else 0.0
        result['ml_score'] = xgb_validator.score({'direction': 1.0 if result.get('direction') == 'bull' else -1.0 if result.get('direction') == 'bear' else 0.0, 'breakout_strength': result.get('breakout_strength'), 'candlestick_strength': conf.strength, 'candlestick_priority_bonus': result['candlestick_priority_bonus'], 'trend_strength': result['trend_strength'], 'range_contraction': result['range_contraction']})
        print(' score', validator.score(result), 'accepted', validator.is_accepted(result), 'ml', result['ml_score'], 'quality', result.get('metadata', {}).get('quality'))
