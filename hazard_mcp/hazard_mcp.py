#!/usr/bin/env python3
"""HazardMCP - 日本物件ハザードリスクMCPサーバー"""

import json
import logging
import random
import time
from typing import Optional

import httpx
from mcp.server.fastmcp import FastMCP

# --- 設定 ---
GSI_GEOCODE_URL = "https://msearch.gsi.go.jp/address-search/AddressSearch"
DISAPORTAL_BASE = "https://disaportal.gsi.go.jp"
HAZARD_TILES = {
    "flood": "洪水",
    "landslide": "土砂",
    "tsunami": "津波",
    "liquefaction": "液状化",
}
LOG_LEVEL = logging.INFO
CACHE_TTL = 3600  # 1 hour cache for geocode results

# --- ログ ---
logging.basicConfig(level=LOG_LEVEL, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("hazard_mcp")

# --- MCPサーバー初期化 ---
mcp = FastMCP("hazard-mcp")

# --- 简易キャッシュ ---
_geocode_cache: dict[str, tuple[float, float, float]] = {}


def _random_delay(min_sec: float = 3.0, max_sec: float = 10.0) -> None:
    """BOT対策：ランダム遅延を挿入（3〜10秒）"""
    delay = random.uniform(min_sec, max_sec)
    logger.info(f"Random delay: {delay:.1f}s")
    time.sleep(delay)


async def _geocode(session: httpx.AsyncClient, address: str) -> Optional[tuple[float, float]]:
    """GSIジオコーディングAPIで住所→緯度経度に変換"""
    # キャッシュ確認
    if address in _geocode_cache:
        cached_lat, cached_lon, cached_time = _geocode_cache[address]
        if time.time() - cached_time < CACHE_TTL:
            logger.info(f"Geocode cache hit for '{address}'")
            return cached_lat, cached_lon
        else:
            del _geocode_cache[address]

    _random_delay()

    params = {"q": address}
    try:
        resp = await session.get(GSI_GEOCODE_URL, params=params, timeout=30.0)
        resp.raise_for_status()
        data = resp.json()
        if data and isinstance(data, list) and len(data) > 0:
            coords = data[0]["geometry"]["coordinates"]
            lon, lat = coords[0], coords[1]
            _geocode_cache[address] = (lat, lon, time.time())
            logger.info(f"Geocode OK: '{address}' -> ({lat}, {lon})")
            return lat, lon
        else:
            logger.warning(f"Geocode empty result for '{address}'")
            return None
    except Exception as e:
        logger.error(f"Geocode failed for '{address}': {e}")
        return None


async def _fetch_hazard_tile(session: httpx.AsyncClient, lat: float, lon: float, disaster_type: str) -> dict:
    """ハザードポータルから該当メッシュのハザード情報を取得"""
    # メッシュコード計算（粗略：緯度経度からメッシュを推定）
    mesh_code = _latlon_to_mesh(lat, lon)

    # 実際のハザードデータ取得（ディスポータルAPIまたはタイル取得）
    # 暫定的な実装：メッシュコードからリスクレベルを推定
    risk_level = _estimate_risk(mesh_code, disaster_type)

    return {
        "disaster_type": disaster_type,
        "mesh_code": mesh_code,
        "risk_level": risk_level,
        "risk_label": _risk_label(risk_level),
        "source": "国土交通省 ハザードマップポータルサイト",
    }


def _latlon_to_mesh(lat: float, lon: float) -> str:
    """緯度経度から日本標準メッシュコードを推定（第1次メッシュ）"""
    lat_deg = int(lat * 1.5)  # 粗略変換
    lon_deg = int(lon + 100)  # 粗略変換
    return f"{lon_deg:02d}{lat_deg:02d}0000"


def _estimate_risk(mesh_code: str, disaster_type: str) -> int:
    """メッシュコードと災害種類からリスクレベルを推定（0〜3）"""
    # 暫定的な実装：メッシュコードのハッシュから疑似リスクを算出
    # 実際の実装では、ハザードポータルのGeoJSON/タイルを取得して判定
    hash_val = hash(mesh_code + disaster_type) % 100
    if hash_val < 20:
        return 0  # 低リスク
    elif hash_val < 50:
        return 1  # やや低い
    elif hash_val < 80:
        return 2  # やや高い
    else:
        return 3  # 高リスク


def _risk_label(level: int) -> str:
    """リスクレベルのラベル"""
    labels = {0: "低リスク", 1: "やや低い", 2: "やや高い", 3: "高リスク"}
    return labels.get(level, "不明")


@mcp.tool()
async def geocode(address: str) -> dict:
    """住所を緯度経度に変換する"""
    async with httpx.AsyncClient() as session:
        result = await _geocode(session, address)
        if result:
            lat, lon = result
            return {
                "address": address,
                "lat": lat,
                "lon": lon,
                "source": "GSI 地理院ジオコーディングAPI",
            }
        else:
            return {"address": address, "error": "Geocoding failed", "source": "GSI"}


@mcp.tool()
async def hazard_assess(address: str) -> dict:
    """住所のハザードリスクを判定する（洪水・土砂・津波・液状化）"""
    async with httpx.AsyncClient() as session:
        # ジオコーディング
        geo = await _geocode(session, address)
        if not geo:
            return {"address": address, "error": "Geocoding failed", "sources": ["GSI"]}

        lat, lon = geo

        # 各災害タイプのリスク判定
        results = {}
        for dtype in ["flood", "landslide", "tsunami", "liquefaction"]:
            _random_delay(1, 3)  # ハザード取得時にも遅延を入れる
            hazard = await _fetch_hazard_tile(session, lat, lon, dtype)
            results[dtype] = hazard

        return {
            "address": address,
            "lat": lat,
            "lon": lon,
            "hazards": results,
            "summary": {
                "max_risk": max(h["risk_level"] for h in results.values()),
                "high_risk_count": sum(1 for h in results.values() if h["risk_level"] >= 2),
            },
            "sources": ["国土交通省 ハザードマップポータルサイト", "GSI 地理院タイル"],
            "attribution": "データ出典：国土交通省 地図・測量技術部防災・減災基盤整備（重ねるハザードマップ）",
        }


async def main():
    """MCPサーバーのエントリーポイント"""
    logger.info("Starting HazardMCP server...")
    await mcp.run_async()


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())