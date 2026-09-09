"""
Kensho State Manager — collected.json の排他制御と安全な保存
v3.3: application/applier.py から抽出、公開関数化
"""

from __future__ import annotations

import json
import os
import random
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import psutil

from kensho.scraping.common import is_stale_empty_deadline
from kensho.utils.backup import safe_save_json

DATA_DIR: Path = Path(__file__).parent.parent.parent / "data"
COLLECTED_FILE: Path = DATA_DIR / "collected.json"
COLLECTED_LOCK: Path = DATA_DIR / "collected.lock"


def acquire_lock(timeout: int = 30) -> bool:
    """排他ロックを取得する（最大timeout秒待つ）"""
    deadline: float = time.time() + timeout
    while time.time() < deadline:
        try:
            fd: int = os.open(str(COLLECTED_LOCK), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode())
            os.close(fd)
            return True
        except (FileExistsError, OSError):
            try:
                with open(COLLECTED_LOCK) as f:
                    old_pid: int = int(f.read().strip())
                if not psutil.pid_exists(old_pid):
                    os.remove(str(COLLECTED_LOCK))
                    continue
            except Exception as e:
                print(f"[LOCK] 古いロック読み込み失敗: {e}", flush=True)
            time.sleep(random.uniform(0.5, 1.5))
            continue
    return False


def release_lock() -> None:
    """排他ロックを解放"""
    try:
        if COLLECTED_LOCK.exists():
            COLLECTED_LOCK.unlink()
    except Exception as e:
        print(f"[LOCK] 解放失敗: {e}", flush=True)


def save_collected_safe(data: dict[str, Any], account_key: str, log: Any = None) -> None:
    """
    collected.json を安全に保存（race condition対策）。
    保存直前にディスクから再読み込みし、他プロセスの変更をマージしてから書き込む。
    """

    def out(msg: str) -> None:
        if log:
            log.write(msg)
        else:
            print(msg, flush=True)

    locked: bool = acquire_lock(timeout=30)
    if not locked:
        out("  [LOCK] collected.json ロック取得失敗 → 強制保存")

    try:
        try:
            with open(COLLECTED_FILE, encoding="utf-8") as f:
                current: dict[str, Any] = json.load(f)
            current_items: list[dict[str, Any]] = current.get("collected", [])
            current_map: dict[str, dict[str, Any]] = {item["detail_url"]: item for item in current_items}

            my_items: list[dict[str, Any]] = data.get("collected", [])
            merged_items: list[dict[str, Any]] = list(current_items)
            merged_urls: set[str] = set(current_map.keys())

            for item in my_items:
                detail_url: str = item.get("detail_url", "")
                if detail_url in merged_urls:
                    idx: int = next(i for i, it in enumerate(merged_items) if it.get("detail_url") == detail_url)
                    # ★ 2026-08-23修正: applied は丸ごと上書きせず垢キー単位でunion。
                    #   並列垢プロセスが同じcollected.jsonに保存するため、後から保存する側が
                    #   他垢のappliedスタンプ(日付なし/None化)を消して再処理+二重RTの原因になっていた。
                    # ★ 2026-08-23 追加修正★: 素朴な {**dst, **src} マージは src の None 値が
                    #   dst の「応募済み日付」をキー単位で上書き(=None汚染)するバグがあった。
                    #   collector.py が収集時に全垢キーを None 初期化するため、処理中の垢以外は
                    #   src が None になり、他垢の応募済み日付が次々と消されていた。
                    #   → 「None 以外の値(日付/DEFER)を優先する」unionに変更。
                    _src_applied: dict = item.get("applied") or {}
                    _dst_applied: dict = merged_items[idx].get("applied") or {}
                    _merged_applied: dict[str, Any] = dict(_dst_applied)
                    for _k, _v in _src_applied.items():
                        if _v is None:
                            # srcがNoneでもdstに日付があるなら残す（消さない）
                            _merged_applied.setdefault(_k, None)
                        else:
                            # 日付/DEFERは上書き/追加
                            _merged_applied[_k] = _v
                    merged_items[idx]["applied"] = _merged_applied
                    # ★ 全文取得できた場合、tweet_text を上書き保存（次回のNGフィルター用）
                    _new_text: str = item.get("tweet_text", "") or ""
                    _old_text: str = merged_items[idx].get("tweet_text", "") or ""
                    if _new_text and len(_new_text) > len(_old_text):
                        merged_items[idx]["tweet_text"] = _new_text
                else:
                    merged_items.append(item)

            data["collected"] = merged_items

            # ★ 2026-09-09 critic v70: 保存層パージ（マージ後・書き込み前）。
            #   applier はセッション開始時にロードしたメモリ上の data（collector の v67 パージ
            #   前スナップショット）を保持したまま応募を進めるため、上記の無条件 append が
            #   collector が除去した stale empty（deadline 空かつ tweet 年齢>14d）をディスクに
            #   再追加（復活）させていた。これを防ぐため、collector と同一判定
            #   （kensho/scraping/common.py の is_stale_empty_deadline）をマージ後に適用する。
            #   collector の全件対象パージ（critic v67）と合わせ、毎時 backfill の L1 ゲート
            #   （stale_empty>15d=0）を復活で壊さない。
            merged_items = [item for item in merged_items if not (is_stale_empty_deadline(item, datetime.now()))]
            data["collected"] = merged_items

            # ★ 2026-08-29 提案81: 診断メタフィールドをディスク current から補完。
            #   collector.py が収集時に new_items_processed / new_items_by_source /
            #   total_on_page / timestamp を書く唯一の書き込み元。applier の in-memory
            #   data は収集前にロードした古い値（None/0/空）を持ち、save_collected_safe
            #   の `data` 丸ごと保存でメタを上書き消滅させていた
            #   （QA27実測: new_items_by_source=None / new_items_processed=0）。
            #   → マージ後に current 側の値で補完（current にあれば current 優先、
            #      current になければ data の値を維持）＝収集供給モニタリングの回復。
            _meta_keys: tuple[str, ...] = (
                "new_items_processed",
                "new_items_by_source",
                "total_on_page",
                "timestamp",
            )
            for _k in _meta_keys:
                data[_k] = current.get(_k, data.get(_k))
        except Exception as e:
            print(f"[SAVE] マージ読み込み失敗: {e}", flush=True)

        safe_save_json(COLLECTED_FILE, data, "collected.json")
    finally:
        if locked:
            release_lock()
