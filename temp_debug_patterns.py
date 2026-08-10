from data.ingestor import fetch_local_ohlcv
from data.preprocessor import prepare_ohlcv
from structure.swing_detector import detect_swings
from structure.patterns import detect_patterns

frame = prepare_ohlcv(fetch_local_ohlcv(days=30))
print('frame len', len(frame))
swings = detect_swings(frame)
print('swings highs', len(swings.get('highs', [])), 'lows', len(swings.get('lows', [])))
patterns = detect_patterns(frame, swings)
print('patterns found', len(patterns))
for p in patterns:
    print(p['pattern_name'], p.get('confidence'), p.get('breakout_strength'))
 
# Individual detector debug
from structure.patterns.ascending_channel import AscendingChannelPattern
from structure.patterns.bear_flag import BearFlagPattern
from structure.patterns.bull_flag import BullFlagPattern
from structure.patterns.expanding_triangle import ExpandingTrianglePattern

detectors = [
    AscendingChannelPattern(),
    BearFlagPattern(),
    BullFlagPattern(),
    ExpandingTrianglePattern(),
]
for d in detectors:
    res = d.detect(frame, swings)
    print(d.name, '->', 'FOUND' if res else 'None')
    # Deeper inspect BullFlag
    bf = BullFlagPattern()
    recent_highs = bf._recent_swings(swings.get('highs', []), frame)
    recent_lows = bf._recent_swings(swings.get('lows', []), frame)
    print('bull recent highs', len(recent_highs), 'lows', len(recent_lows))
    atr = bf._atr(frame)
    print('atr', atr)
    impulse = bf._detect_impulse(frame)
    print('impulse', impulse)
    # compute consolidation highs/lows
    consolidation_highs = recent_highs[:-1] if len(recent_highs) >= 4 else recent_highs
    consolidation_lows = recent_lows[-3:] if len(recent_lows) >= 3 else recent_lows
    print('consolidation_highs', len(consolidation_highs), 'consolidation_lows', len(consolidation_lows))
    if consolidation_highs:
        print('breakout_level', max(bf._point_price(h) for h in consolidation_highs))
    high_slope, _ = bf._fit_line(consolidation_highs)
    low_slope, _ = bf._fit_line(consolidation_lows)
    print('high_slope', high_slope, 'low_slope', low_slope)
    flag_width = max(bf._point_price(h) for h in consolidation_highs) - min(bf._point_price(l) for l in consolidation_lows)
    print('flag_width', flag_width, 'adaptive_channel_width', bf._adaptive_channel_width(frame))
    last_close = bf._latest_close(frame)
    breakout_level = max(bf._point_price(h) for h in consolidation_highs)
    breakout_strength = bf._proximity_strength(breakout_level, last_close, atr)
    print('last_close', last_close, 'breakout_strength', breakout_strength, 'adaptive_breakout', bf._adaptive_breakout_threshold(frame))
