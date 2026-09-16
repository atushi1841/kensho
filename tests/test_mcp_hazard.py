"""MCP Hazard Server tests"""

import pytest
from mcp_hazard.hazard import HazardResult, get_hazard


def test_hazard_result_to_dict():
    result = HazardResult(
        address="東京都千代田区丸の内1-1",
        lat=35.6812,
        lon=139.7671,
        flood=2,
        landslide=1,
        tsunami=0,
        liquefaction=1,
        sources=["MLIT_XKT025", "MLIT_XKT026", "MLIT_XKT028", "MLIT_XKT029"],
    )
    d = result.to_dict()
    assert d["address"] == "東京都千代田区丸の内1-1"
    assert d["flood"] == 2
    assert d["landslide"] == 1
    assert d["tsunami"] == 0
    assert d["liquefaction"] == 1
    assert len(d["sources"]) == 4


def test_hazard_result_fields():
    """全フィールドが存在し正しい型かつ範囲内"""
    result = HazardResult(
        address="test",
        lat=0.0,
        lon=0.0,
        flood=0,
        landslide=0,
        tsunami=0,
        liquefaction=0,
        sources=[],
    )
    assert 0 <= result.flood <= 3
    assert 0 <= result.landslide <= 3
    assert 0 <= result.tsunami <= 3
    assert 0 <= result.liquefaction <= 3