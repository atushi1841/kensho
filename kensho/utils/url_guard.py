"""Kensho URL Guard — fixupx 永続404 URLの失敗カウント・ブラックリスト（critic v71 提案②）

背景:
  fixupx フォールバックで dead URL（例 x.com/hi_ra_rin_1027/status/2094291340540399946）が
  毎収集で再試行され HTTP 404 を返し続けていた（9/9 だけで 14+ 回連続）。ブラックリスト化
  されず無駄ループになっていたため、data 側キーで失敗カウントを保持し、
  同一ツイートIDの失敗が BLOCK_THRESHOLD 回に達したら以後の fixupx 試行をスキップする。

ルール:
  - キーはツイートID（snowflake）— /i/web/status/ 表記やユーザー名揺れを吸収するため
    URL 全体ではなく ID で判定制御する。
  - 失敗3回（HTTP 非200 / 例外）でブロック入り。
  - 成功（og:description 取得）でカウントはリセット。
  - ブロック入りから AUTO_UNBLOCK_DAYS 経ったら自動解除（再確認の機会を残す）。
  - JSON 破損時は空状態として fail-open（収集・応募を止めない）。
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

# 失敗この回数でブロック（critic v71 提案②「失敗3回でブラックリスト」）
BLOCK_THRESHOLD: int = 3
# ブロック自動解除までの日数（恒久ブラックリスト化による誤ブロックを避ける安全弁）
AUTO_UNBLOCK_DAYS: int = 30

GUARD_FILENAME: str = "fixupx_guard.json"


def tweet_id_of(url: str) -> str:
    """x_url / fixupx URL からツイートID（snowflake）を抽出。失敗時は空文字。"""
    m = re.search(r"/status(?:es)?/(\d+)", url or "")
    return m.group(1) if m else ""


def load_guard(path: Path) -> dict[str, Any]:
    """ガードJSONを読込。破損・不在は空状態（fail-open）。"""
    try:
        if path.exists():
            data: Any = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("urls"), dict):
                return data
    except Exception:  # noqa: BLE001 — fail-open: 破損時はまっさら扱い
        pass
    return {"urls": {}}


def save_guard(path: Path, guard: dict[str, Any]) -> None:
    """ガードJSON保存。失敗しても本処理を止めない（fail-open）。"""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(guard, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)
    except Exception:  # noqa: BLE001
        pass


def is_blocked(guard: dict[str, Any], url: str, now: datetime | None = None) -> bool:
    """このURL（ツイートID）が fixupx ブリスト対象なら True。期限切れは自動解除扱い。"""
    tid = tweet_id_of(url)
    if not tid:
        return False
    entry = guard.get("urls", {}).get(tid)
    if not isinstance(entry, dict) or not entry.get("blocked"):
        return False
    blocked_at = str(entry.get("blocked_at", ""))
    if blocked_at:
        try:
            age = (now or datetime.now()) - datetime.fromisoformat(blocked_at)
            if age > timedelta(days=AUTO_UNBLOCK_DAYS):
                return False  # 自動解除ウィンドウ超過 → 再試行許可
        except ValueError:
            pass
    return True


def record_failure(guard: dict[str, Any], url: str, status: str, path: Path) -> int:
    """fixupx 失敗（HTTP 非200 / 例外）を記録。閾値到達で blocked にする。

    戻り値: 累計失敗回数。ブロック移行した瞬間は 閾値 と同じ値を返す
    （呼び出し側で `count == BLOCK_THRESHOLD` でログを出すと1回だけ報告できる）。
    """
    tid = tweet_id_of(url)
    if not tid:
        return 0
    urls: dict[str, Any] = guard.setdefault("urls", {})
    entry = urls.get(tid)
    if not isinstance(entry, dict):
        entry = {"fails": 0, "blocked": False, "blocked_at": "", "last_error": ""}
        urls[tid] = entry
    entry["fails"] = int(entry.get("fails", 0)) + 1
    entry["last_error"] = str(status)[:120]
    if entry["fails"] >= BLOCK_THRESHOLD and not entry.get("blocked"):
        entry["blocked"] = True
        entry["blocked_at"] = datetime.now().isoformat()
        entry["note"] = f"fixupx 失敗{entry['fails']}回 → ブラックリスト（{AUTO_UNBLOCK_DAYS}日後自動解除）"
    save_guard(path, guard)
    return int(entry["fails"])


def record_success(guard: dict[str, Any], url: str, path: Path) -> None:
    """fixupx 成功で失敗カウントをリセット（存在時のみ消去、通常は何もしない）。"""
    tid = tweet_id_of(url)
    if tid and tid in guard.get("urls", {}):
        guard["urls"].pop(tid, None)
        save_guard(path, guard)
