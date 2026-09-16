"""
MCP Hazard Server — 日本物件ハザードリスクMCPプロトタイプ
APIエンドポイント: MLIT不動産情報ライブラリAPI (XKT025-029)
出力スキーマ: {address, lat, lon, flood:0-3, landslide:0-3, tsunami:0-3, liquefaction:0-3, sources:[...]}
"""

import os
import json
import logging
from typing import Optional
from dataclasses import dataclass, asdict
from enum import IntEnum

import httpx

logger = logging.getLogger(__name__)

# ── MLIT不動産情報ライブラリAPI ──
BASE_URL = "https://www.reinfolib.mlit.go.jp/ex-api/external"
API_KEY = os.environ.get("MLIT_API_KEY", "")


class HazardLevel(IntEnum):
    """ハザードレベル 0=未指定 1=低 2=中 3=高"""
    NONE = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3


@dataclass
class HazardResult:
    address: str
    lat: float
    lon: float
    flood: int       # 0-3
    landslide: int   # 0-3
    tsunami: int     # 0-3
    liquefaction: int # 0-3
    sources: list

    def to_dict(self) -> dict:
        return asdict(self)


def _build_headers() -> dict:
    """APIリクエストヘッダー"""
    headers = {"Accept": "application/json"}
    if API_KEY:
        headers["Ocp-Apim-Subscription-Key"] = API_KEY
    return headers


def _get_hazard_layer(
    code: str,
    lat: float,
    lon: float,
    zoom: int = 15,
) -> int:
    """
    MLIT APIから特定ハザード層のレベルを取得 (0-3)
    現在はGeoJSON/PBFタイルからリスクレベルを推定するプロトタイプ実装
    """
    url = f"{BASE_URL}/{code}"
    params = {
        "response_format": "geojson",
        "z": zoom,
        "x": _lon_to_tile(lon, zoom),
        "y": _lat_to_tile(lat, zoom),
    }
    try:
        resp = httpx.get(url, headers=_build_headers(), params=params, timeout=30.0)
        resp.raise_for_status()
        data = resp.json()
        # TODO: GeoJSONからリスクレベルを推定するロジック実装
        return _estimate_level(data)
    except Exception as e:
        logger.warning(f"Hazard layer {code} fetch failed: {e}")
        return 0


def _lon_to_tile(lon: float, zoom: int) -> int:
    """経度からタイルX座標"""
    import math
    return int((lon + 180.0) / 360.0 * (2 ** zoom))


def _lat_to_tile(lat: float, zoom: int) -> int:
    """緯度からタイルY座標"""
    import math
    lat_rad = math.radians(lat)
    return int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * (2 ** zoom))


def _estimate_level(data: dict) -> int:
    """GeoJSONデータからハザードレベルを推定 (プロトタイプ)"""
    # TODO: 実際のリスクレベル推定ロジック実装
    # 現時点ではデータの有無で0/1を返す
    if data and data.get("features"):
        return 1
    return 0


def get_hazard(
    address: str,
    lat: float,
    lon: float,
) -> HazardResult:
    """
    指定座標のハザード情報を取得

    Args:
        address: 住所文字列
        lat: 緯度
        lon: 経度

    Returns:
        HazardResult: flood, landslide, tsunami, liquefaction 各0-3
    """
    flood = _get_hazard_layer("XKT026", lat, lon)       # 洪水
    tsunami = _get_hazard_layer("XKT028", lat, lon)     # 津波
    landslide = _get_hazard_layer("XKT029", lat, lon)   # 土砂
    liquefaction = _get_hazard_layer("XKT025", lat, lon) # 液状化

    return HazardResult(
        address=address,
        lat=lat,
        lon=lon,
        flood=flood,
        landslide=landslide,
        tsunami=tsunami,
        liquefaction=liquefaction,
        sources=["MLIT_XKT025", "MLIT_XKT026", "MLIT_XKT028", "MLIT_XKT029"],
    )