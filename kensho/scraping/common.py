"""Kensho — snowflake 年齢による deadline 空アイテムの期限切れ判定（共有ロジック）

critic v67（collector パージ）+ critic v70（applier 保存層パージ）で共通利用するため
kensho/scraping/collector.py から抽出・独立化した。このモジュールは stdlib のみに
依存する（application/state.py からの軽量 import を維持するため）。

- tweet_id は Twitter snowflake。生成時刻を (id >> 22) + epoch で復元。
- deadline 空 かつ 生成から STALE_TWEET_DAYS 超 → 期限切れ（stale empty）とみなす。
- cp.meikan.org は期限を一覧から抽出できないため deadline が空のまま滞留するのが主因。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

# deadline 空アイテムを snowflake 年齢で除去する閾値（日）。critic v67 で決定。
STALE_TWEET_DAYS: int = 14
_TWITTER_EPOCH_MS: int = 1288834974657


def snowflake_ts_ms(tweet_id: Any) -> int | None:
    """tweet_id（Twitter snowflake）から生成時刻(ms)を復元。非数値・欠落は None。"""
    try:
        return (int(tweet_id) >> 22) + _TWITTER_EPOCH_MS
    except (ValueError, TypeError):
        return None


def is_stale_empty_deadline(item: dict[str, Any], now: datetime) -> bool:
    """deadline 空かつ tweet 生成から STALE_TWEET_DAYS 超なら True（snowflake 年齢パージ）。

    collector.py（critic v67）と state.py save_collected_safe（critic v70）の
    保存層パージで共通利用する。tweet_id 非数値・deadline 有りは False。
    """
    if item.get("deadline"):
        return False
    ts_ms = snowflake_ts_ms(item.get("tweet_id", ""))
    if ts_ms is None:
        return False
    return (now.timestamp() * 1000 - ts_ms) > STALE_TWEET_DAYS * 86400 * 1000
