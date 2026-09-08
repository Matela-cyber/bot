import pandas as pd
from pathlib import Path
from data.trade_analysis import _session_for_timestamp

trades = pd.read_json('data/backtest_results_12m_m5/trades.json')
shock = pd.read_csv('data/shock_analysis_12m/trades_with_shock_flags.csv')
for frame in (trades, shock):
    frame['entry_time'] = pd.to_datetime(frame['entry_time'], utc=True, errors='coerce')
trades['session'] = trades['entry_time'].map(_session_for_timestamp)
shock = shock[['symbol','strategy','direction','entry_time','shock_blocked']]
merged = trades.merge(shock, on=['symbol','strategy','direction','entry_time'], how='left')
merged['shock_blocked'] = merged['shock_blocked'].fillna(False).astype(bool)
smc = merged[(merged['strategy'] == 'smc_breakout') & ~merged['shock_blocked']].copy()

def report(frame, keys):
    result = frame.groupby(keys).agg(
        trades=('profit','size'), wins=('profit', lambda s: (s > 0).sum()),
        net=('profit','sum'), avg=('profit','mean'),
        pf=('profit', lambda s: s[s > 0].sum() / abs(s[s < 0].sum()) if (s < 0).any() else float('inf')),
        win_rate=('profit', lambda s: (s > 0).mean() * 100),
    ).reset_index()
    return result.sort_values(['net','trades'], ascending=[False,False])

print('SMC shock-excluded by DST-aware session')
print(report(smc, ['session']).round(3).to_string(index=False))
print('\nSMC shock-excluded by session and pair, min 5 trades')
print(report(smc, ['session','symbol']).query('trades >= 5').round(3).to_string(index=False))
print('\nSMC shock-excluded by DST-aware entry hour, min 10 trades')
smc['entry_hour'] = smc['entry_time'].dt.hour
print(report(smc, ['entry_hour']).query('trades >= 10').round(3).to_string(index=False))
print('\nCandidate combined filters: session net positive and pair/session net positive, min 10 trades')
print(report(smc, ['session','symbol']).query('trades >= 10 and net > 0').round(3).to_string(index=False))
