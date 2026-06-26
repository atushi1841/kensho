"""
Kensho State Manager — collected.json の排他制御と安全な保存
v3.3: application/applier.py から抽出、公開関数化
"""
from __future__ import annotations

import json
import os
import time
import random
import psutil
from pathlib import Path
from typing import Any

from utils.backup import safe_save_json

DATA_DIR: Path = Path(__file__).parent.parent / 'data'
COLLECTED_FILE: Path = DATA_DIR / 'collected.json'
COLLECTED_LOCK: Path = DATA_DIR / 'collected.lock'


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
            with open(COLLECTED_FILE, 'r', encoding='utf-8') as f:
                current: dict[str, Any] = json.load(f)
            current_items: list[dict[str, Any]] = current.get('collected', [])
            current_map: dict[str, dict[str, Any]] = {item['detail_url']: item for item in current_items}

            my_items: list[dict[str, Any]] = data.get('collected', [])
            merged_items: list[dict[str, Any]] = list(current_items)
            merged_urls: set[str] = set(current_map.keys())

            for item in my_items:
                detail_url: str = item.get('detail_url', '')
                if detail_url in merged_urls:
                    idx: int = next(i for i, it in enumerate(merged_items) if it.get('detail_url') == detail_url)
                    merged_items[idx]['applied'] = item.get('applied', merged_items[idx].get('applied', {}))
                else:
                    merged_items.append(item)

            data['collected'] = merged_items
        except Exception as e:
            print(f"[SAVE] マージ読み込み失敗: {e}", flush=True)

        safe_save_json(COLLECTED_FILE, data, 'collected.json')
    finally:
        if locked:
            release_lock()
