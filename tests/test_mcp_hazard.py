"""MCP Hazard Server tests

ネットワーク依存はすべて monkeypatch でモックする (tests/AGENTS.md 準拠)。
"""

import httpx
import pytest

from mcp_hazard import hazard as H
from mcp_hazard.hazard import (
    HazardResult,
    _lat_to_tile,
    _lon_to_tile,
    _normalize_rank,
    _parse_depth_string,
    geocode_address,
    get_hazard,
)


# ── 基本データクラス ──
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
    assert "credit" in d and "不動産情報ライブラリ" in d["credit"]


def test_hazard_result_fields():
    result = HazardResult(address="test", lat=0.0, lon=0.0, flood=0, landslide=0, tsunami=0, liquefaction=0, sources=[])
    for v in (result.flood, result.landslide, result.tsunami, result.liquefaction):
        assert 0 <= v <= 3


# ── リスク正規化 ──
@pytest.mark.parametrize(
    "rank,expected",
    [
        (0, 0),
        (1, 1),
        (3, 1),
        (4, 2),
        (6, 2),
        (7, 3),
        (9, 3),
        (99, 0),
        ("5", 2),
        ("abc", 0),
        (None, 0),
    ],
)
def test_normalize_rank(rank, expected):
    assert _normalize_rank(rank) == expected


@pytest.mark.parametrize(
    "value,expected",
    [
        ("3m以上〜5m未満", 3),
        ("1m以上〜3m未満", 2),
        ("0.5m未満", 2),
        ("0.3m未満", 1),
        ("浸水なし", 0),
        ("", 0),
        (None, 0),
    ],
)
def test_parse_depth_string(value, expected):
    assert _parse_depth_string(value) == expected


# ── タイル座標 (Web Mercator) ──
def test_tile_coordinates_tokyo():
    z = 15
    assert _lon_to_tile(139.7671, z) == 29105
    y = _lat_to_tile(35.6812, z)
    assert 12900 <= y <= 12930


# ── モック用ヘルパー ──
class FakeResp:
    def __init__(self, status_code=200, json_data=None):
        self.status_code = status_code
        self._json = json_data if json_data is not None else {}

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("err", request=None, response=None)


def _layer_feature(rank=None, area_type=None, depth=None):
    props = {}
    if rank is not None:
        props["rank"] = rank
    if area_type is not None:
        props["area_type"] = area_type
    if depth is not None:
        props["tsunami_depth"] = depth
    return {"type": "Feature", "properties": props, "geometry": None}


# ── geocode_address ──
def test_geocode_address(monkeypatch):
    def fake_get(url, params=None, headers=None, timeout=None):
        assert "AddressSearch" in url
        return FakeResp(
            200,
            [
                {
                    "geometry": {"coordinates": [139.767197, 35.681561], "type": "Point"},
                    "properties": {"title": "東京都千代田区丸の内"},
                }
            ],
        )

    monkeypatch.setattr(H.httpx, "get", fake_get)
    lat, lon, title = geocode_address("東京都千代田区丸の内")
    assert abs(lat - 35.681561) < 1e-6
    assert abs(lon - 139.767197) < 1e-6
    assert title == "東京都千代田区丸の内"


def test_geocode_address_not_found(monkeypatch):
    monkeypatch.setattr(H.httpx, "get", lambda *a, **k: FakeResp(200, []))
    with pytest.raises(ValueError):
        geocode_address("存在しない住所XYZ")


# ── get_hazard: 住所のみ (geocode + MLIT mock) ──
def test_get_hazard_address_only(monkeypatch):
    def fake_get(url, params=None, headers=None, timeout=None):
        if "AddressSearch" in url:
            return FakeResp(
                200,
                [
                    {
                        "geometry": {"coordinates": [139.7671, 35.6812], "type": "Point"},
                        "properties": {"title": "東京都千代田区丸の内"},
                    }
                ],
            )
        # MLIT: 1フィーチャ返す
        return FakeResp(200, {"features": [_layer_feature(rank=5, area_type="警戒区域", depth="3m以上〜5m未満")]})

    monkeypatch.setattr(H.httpx, "get", fake_get)

    result = get_hazard(address="東京都千代田区丸の内")
    d = result.to_dict()
    assert d["flood"] == 2  # rank5 -> 2
    assert d["landslide"] == 3  # 区域あり -> 3
    assert d["tsunami"] == 3  # 3m以上 -> 3
    assert d["liquefaction"] == 3  # 区域あり -> 3
    assert "不動産情報ライブラリ" in d["credit"]


# ── get_hazard: 区域外 (204) は全0 ──
def test_get_hazard_no_data(monkeypatch):
    monkeypatch.setattr(H.httpx, "get", lambda *a, **k: FakeResp(204, {}))
    result = get_hazard(address="x", lat=35.0, lon=139.0)
    assert result.flood == 0
    assert result.tsunami == 0
    assert result.landslide == 0
    assert result.liquefaction == 0


# ── get_hazard: MLIT障害時も落ちず0を返す ──
def test_get_hazard_api_error(monkeypatch):
    def boom(*a, **k):
        raise httpx.ConnectError("down")

    monkeypatch.setattr(H.httpx, "get", boom)
    result = get_hazard(address="x", lat=35.0, lon=139.0)
    assert result.flood == 0
