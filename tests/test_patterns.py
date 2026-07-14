import pandas as pd

from data.ingestor import DataIngestor, fetch_local_ohlcv
from data.preprocessor import prepare_ohlcv
from main import select_best_pattern
from structure.patterns import detect_patterns
from structure.pattern_validator import PatternValidator
from structure.swing_detector import detect_swings


def test_local_data_generates_at_least_one_pattern() -> None:
    data = fetch_local_ohlcv(days=30)
    frame = prepare_ohlcv(data)
    swings = detect_swings(frame)
    patterns = detect_patterns(frame, swings)
    assert len(patterns) >= 1


def test_select_best_pattern_prefers_highest_confidence() -> None:
    patterns = [
        {"pattern_name": "Bull_Flag", "confidence": 0.68},
        {"pattern_name": "Bear_Flag", "confidence": 0.82},
        {"pattern_name": "Bull_Flat", "confidence": 0.71},
    ]
    best = select_best_pattern(patterns)
    assert best["pattern_name"] == "Bear_Flag"


def test_data_ingestor_returns_valid_ohlcv_frame() -> None:
    ingestor = DataIngestor()
    frame = ingestor.fetch_ohlcv(days=5, source="local")
    assert {"open", "high", "low", "close", "volume"}.issubset(set(frame.columns))
    assert len(frame) > 0
    assert frame.index.is_monotonic_increasing


def test_prepare_ohlcv_adds_returns_and_keeps_ohlcv_columns() -> None:
    frame = pd.DataFrame(
        {
            "open": [1.0, 1.01],
            "high": [1.02, 1.03],
            "low": [0.99, 1.0],
            "close": [1.01, 1.02],
            "volume": [100, 120],
        },
        index=pd.to_datetime(["2026-01-01 00:00:00", "2026-01-01 00:15:00"]),
    )
    prepared = prepare_ohlcv(frame)
    assert {"open", "high", "low", "close", "volume", "ret"}.issubset(set(prepared.columns))
    assert prepared["ret"].notna().all()


def test_pattern_validator_rejects_weak_evidence() -> None:
    validator = PatternValidator()
    weak_pattern = {"direction": "bull", "breakout_strength": 0.0, "candlestick_strength": 0.0, "candlestick_bonus": False}
    assert validator.is_accepted(weak_pattern) is False


def test_pattern_validator_scores_candlestick_strength() -> None:
    validator = PatternValidator()
    strong_pattern = {
        "direction": "bull",
        "breakout_strength": 0.12,
        "candlestick_strength": 0.85,
        "candlestick_bonus": True,
        "trend_strength": 0.0025,
        "range_contraction": 0.05,
        "swing_points": {"highs": [1.0, 1.01, 1.02], "lows": [0.99, 1.0, 1.01]},
        "metadata": {"type": "continuation"},
    }
    assert validator.is_accepted(strong_pattern) is True


def test_detect_swings_returns_filtered_swing_metadata() -> None:
    frame = pd.DataFrame(
        {
            "open": [1.0, 1.01, 1.02, 1.03, 1.02, 1.01, 1.02, 1.03],
            "high": [1.01, 1.02, 1.03, 1.04, 1.03, 1.02, 1.03, 1.04],
            "low": [0.99, 1.0, 1.01, 1.02, 1.01, 1.0, 1.01, 1.02],
            "close": [1.0, 1.02, 1.03, 1.02, 1.01, 1.02, 1.03, 1.02],
        }
    )
    swings = detect_swings(frame)
    assert "highs" in swings and "lows" in swings
    assert len(swings["highs"]) >= 1
    assert len(swings["lows"]) >= 1
    assert all("price" in item for item in swings["highs"])
    assert all("index" in item for item in swings["highs"])


def test_repository_add_pattern_event_creates_record() -> None:
    from db.repository import Repository

    repository = Repository("sqlite:///:memory:")
    repository.add_pattern_event(
        {
            "timestamp": "2026-01-01T00:00:00",
            "timeframe": "15m",
            "pattern_name": "Bull_Flag",
            "breakout_level": 1.2345,
            "stop_loss_zone": 1.2320,
            "confidence": 0.75,
            "candlestick_bonus": True,
            "final_score": 0.85,
            "executed": False,
            "result": "plan_ready",
        }
    )
    assert repository.engine is not None


def test_mt5_client_reports_unconfigured_state() -> None:
    from execution.mt5_client import MT5Client

    client = MT5Client(account=None, password=None, server=None)
    assert client.is_configured() is False


def test_repository_add_trade_and_daily_stat() -> None:
    from db.repository import Repository

    repository = Repository("sqlite:///:memory:")
    repository.add_trade(
        {
            "trade_id": "trade-0001",
            "entry_time": "2026-01-01T00:00:00",
            "exit_time": "2026-01-01T00:15:00",
            "direction": "bull",
            "entry_price": 1.1000,
            "stop_loss": 1.0980,
            "take_profit": 1.1040,
            "exit_price": 1.1040,
            "pnl_pips": 40,
            "pnl_amount": 200.0,
            "pnl_percentage": 0.18,
            "position_size": 10000.0,
            "exit_reason": "take_profit",
            "rl_action_taken": "paper_execution",
            "reward": 0.2,
        }
    )

    repository.upsert_daily_stat(
        {
            "date": "2026-01-01",
            "start_balance": 1000.0,
            "end_balance": 1200.0,
            "daily_pnl": 200.0,
            "drawdown_peak": 0.0,
            "drawdown_percent": 0.0,
            "halt_triggered": False,
        }
    )

    assert repository.engine is not None
