"""
MCP Hazard Server — 日本物件ハザードリスクMCP
データソース: MLIT 不動産情報ライブラリAPI (XKT025-029)
出力スキーマ: {address, lat, lon, flood:0-3, landslide:0-3, tsunami:0-3, liquefaction:0-3, sources:[...], credit}

リスクレベル定義 (0-3):
  0 = 情報なし / 区域外
  1 = 低 (浸水深 <0.5m)
  2 = 中 (浸水深 0.5〜3m)
  3 = 高 (浸水深 >=3m / 想定最大規模の深部)
"""

import os
import re
import logging
from dataclasses import dataclass, asdict
from enum import IntEnum
from typing import Any, Sequence

import httpx

logger = logging.getLogger(__name__)

# 出典・クレジット文言 (不動産情報ライブラリは CC-BY 4.0 相当)
CREDIT_TEXT = (
    "出典: 国土交通省 不動産情報ライブラリAPI "
    "(国土数値情報, CC-BY 4.0相当) https://www.reinfolib.mlit.go.jp/"
)

# MLIT不動産情報ライブラリAPI
BASE_URL = "https://www.reinfolib.mlit.go.jp/ex-api/external"
API_KEY = os.environ.get("MLIT_API_KEY", "")

# 国土地理院 住所検索API (APIキー不要)
GSI_GEOCODE_URL = "https://msearch.gsi.go.jp/address-search/AddressSearch"

# 国土地理院 住所検索API (キー不要)
GSI_GEOCODE_URL = "https://msearch.gsi.go.jp/address-search/AddressSearch"


class HazardLevel(IntEnum):
    """ハザードレベル 0=情報なし/区域外 1=低 2=中 3=高"""

    NONE = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3


@dataclass
class HazardResult:
    address: str
    lat: float
    lon: float
    flood: int
    landslide: int
    tsunami: int
    liquefaction: int
    sources: list[str]
    credit: str = CREDIT_TEXT

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _build_headers() -> dict[str, str]:
    """APIリクエストヘッダー。APIキー未設定時は空(Ocp-Apim-Subscription-Key)。"""
    return {
        "Accept": "application/json",
        "Ocp-Apim-Subscription-Key": API_KEY,
    }


def _lon_to_tile(lon: float, zoom: int) -> int:
    """経度→タイルX座標 (Web Mercator / EPSG:3857)"""
    return int((lon + 180.0) / 360.0 * (2**zoom))


def _lat_to_tile(lat: float, zoom: int) -> int:
    """緯度→タイルY座標 (Web Mercator / EPSG:3857)"""
    import math

    lat_rad = math.radians(lat)
    return int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * (2**zoom))


# 浸水深ランク(1-9) -> 0-3 に圧縮
_DEPTH_RANK_MAP = {
    1: 1,
    2: 1,
    3: 1,
    4: 2,
    5: 2,
    6: 2,
    7: 3,
    8: 3,
    9: 3,
}


def _normalize_rank(value: object) -> int:
    """浸水深ランク(1-9, 数値/文字列) -> 0-3"""
    try:
        rank = int(str(value))
    except (TypeError, ValueError):
        return 0
    return _DEPTH_RANK_MAP.get(rank, 0)


def _parse_depth_string(value: object) -> int:
    """津波/高潮の浸水深文字列('3m以上〜5m未満') -> 0-3"""
    if not value:
        return 0
    numbers = [float(n) for n in re.findall(r"\d+\.?\d*", str(value))]
    if not numbers:
        low = str(value).lower()
        if any(k in low for k in ("なし", "over 0", "0未満", "no")):
            return 0
        return 1
    min_val = min(numbers)
    if min_val <= 0:
        return 0
    if min_val < 0.5:
        return 1
    if min_val < 3.0:
        return 2
    return 3


def _get_hazard_layer(code: str, lat: float, lon: float, kind: str = "rank", zoom: int = 15) -> int:
    """
    MLIT APIから特定ハザード層のレベルを取得 (0-3)

    kind:
      "rank"  -> 浸水深ランク(1-9)ベース (洪水 XKT026)
      "depth" -> 浸水深文字列ベース (津波 XKT028 / 高潮 XKT027)
      "area"  -> 区域区分あり/なし (土砂 XKT029 / 液状化 XKT025)
    """
    url = f"{BASE_URL}/{code}"
    params = {
        "z": zoom,
        "x": _lon_to_tile(lon, zoom),
        "y": _lat_to_tile(lat, zoom),
    }
    try:
        resp = httpx.get(url, headers=_build_headers(), params=params, timeout=30.0)
        # 204 = タイル内にデータなし(区域外), 404 = 区域外
        if resp.status_code in (204, 404):
            logger.info("Hazard layer %s: no data in tile (status %s)", code, resp.status_code)
            return 0
        resp.raise_for_status()
        data = resp.json()
        features = data.get("features", []) if isinstance(data, dict) else []
        if not features:
            return 0
        return _aggregate_level(features, kind)
    except Exception as e:  # noqa: BLE001
        logger.warning("Hazard layer %s fetch failed: %s", code, e)
        return 0


def _aggregate_level(features: Sequence[dict[str, Any]], kind: str) -> int:
    """複数ポリゴンが重なる場合は最大ランクを採用。"""
    max_level = 0
    for feature in features:
        props = feature.get("properties", {}) if isinstance(feature, dict) else {}
        level = _props_to_level(props, kind)
        if level > max_level:
            max_level = level
    return max_level


def _props_to_level(props: dict[str, Any], kind: str) -> int:
    """propertiesを種類に応じてレベル化。"""
    if kind == "area":
        # 土砂/液状化: 区域区分の有無で判定
        for key in ("area_type", "danger_type", "category", "type", "liquefaction_type"):
            v = props.get(key)
            if v is not None and str(v) not in ("", "0", "なし", "区域外"):
                return 3
        return 0
    if kind == "depth":
        # 津波/高潮: 文字列浸水深
        for key in ("tsunami_depth", "inundation_depth", "depth", "max_depth", "rank"):
            v = props.get(key)
            if v is not None and str(v) not in ("", "なし", "区域外"):
                return _parse_depth_string(v)
        return 0
    # rank (洪水 XKT026): 数値ランク
    for key in ("rank", "flood_rank", "inundation_rank", "depth"):
        v = props.get(key)
        if v is not None and str(v) not in ("", "なし", "区域外"):
            val = _normalize_rank(v)
            if val:
                return val
    return _parse_depth_string(
        next((props.get(k) for k in ("inundation_rank", "max_depth", "depth")), None)
    )


def geocode_address(address: str) -> tuple[float, float, str]:
    """
    住所文字列を国土地理院住所検索API(キー不要)で緯度経度に変換する。

    Args:
        address: 住所文字列 (例: "東京都千代田区丸の内1-1")

    Returns:
        (lat, lon, matched_title)

    Raises:
        ValueError: 住所が特定できなかった場合
    """
    resp = httpx.get(
        GSI_GEOCODE_URL,
        params={"q": address},
        headers={"Accept": "application/json"},
        timeout=20.0,
    )
    resp.raise_for_status()
    data = resp.json()
    if not data:
        raise ValueError(f"住所を特定できませんでした: {address}")
    top = data[0]
    lon, lat = top["geometry"]["coordinates"]
    title = top.get("properties", {}).get("title", address)
    return float(lat), float(lon), title


def get_hazard(
    address: str, lat: float | None = None, lon: float | None = None, api_key: str = ""
) -> HazardResult:
    """
    指定座標のハザード情報を取得

    Args:
        address: 住所文字列
        lat: 緯度 (省略時は住所からジオコーディング)
        lon: 経度 (省略時は住所からジオコーディング)
        api_key: MLIT不動産情報ライブラリAPIキー (未指定時は環境変数MLIT_API_KEY)
    """
    global API_KEY
    if api_key:
        API_KEY = api_key

    if (lat is None or lon is None) and address:
        lat, lon, _ = geocode_address(address)
    lat = float(lat) if lat is not None else 0.0
    lon = float(lon) if lon is not None else 0.0

    flood = _get_hazard_layer("XKT026", lat, lon, kind="rank")
    tsunami = _get_hazard_layer("XKT028", lat, lon, kind="depth")
    landslide = _get_hazard_layer("XKT029", lat, lon, kind="area")
    liquefaction = _get_hazard_layer("XKT025", lat, lon, kind="area")

    return HazardResult(
        address=address,
        lat=lat,
        lon=lon,
        flood=flood,
        landslide=landslide,
        tsunami=tsunami,
        liquefaction=liquefaction,
        sources=["MLIT_XKT025", "MLIT_XKT026", "MLIT_XKT027", "MLIT_XKT028", "MLIT_XKT029"],
        credit=CREDIT_TEXT,
    )
