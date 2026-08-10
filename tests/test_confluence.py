import pytest

from structure.confluence import ConfluenceEngine


def test_confluence_full_alignment():
    engine = ConfluenceEngine()
    pattern = {"confidence": 0.9, "direction": "bull"}
    smc = {
        "bos": {"status": "bull"},
        "choch": {"status": "bull"},
        "order_block": {"status": "bull"},
        "fvg": {"status": "bull"},
        "liquidity": {"nearest_high": None, "nearest_low": None},
    }
    res = engine.calculate_confluence(pattern, smc)
    assert isinstance(res, dict)
    assert res["falcon_score"] == pytest.approx(0.9)
    # bos + choch + ob + fvg = 0.25+0.25+0.20+0.15 = 0.85 -> clipped to 0.85
    assert res["smc_score"] == pytest.approx(0.85)
    # weighted average
    exp = (0.9 * 0.5) + (0.85 * 0.5)
    assert res["score"] == pytest.approx(exp)


def test_confluence_no_smc():
    engine = ConfluenceEngine()
    pattern = {"confidence": 0.6, "direction": "bear"}
    smc = {}
    res = engine.calculate_confluence(pattern, smc)
    assert res["smc_score"] == 0.0
    assert res["score"] == pytest.approx((0.6 * 0.5) + (0.0 * 0.5))
