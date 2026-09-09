"""
Tests for utils/url_guard.py — critic v71 提案② fixupx 失敗ガード
（失敗3回でブロック、成功でリセット、自動解除、fail-open）
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from kensho.utils.url_guard import (
    AUTO_UNBLOCK_DAYS,
    BLOCK_THRESHOLD,
    is_blocked,
    load_guard,
    record_failure,
    record_success,
    tweet_id_of,
)

_URL = "https://x.com/hi_ra_rin_1027/status/2094291340540399946"
_TID = "2094291340540399946"


# ── tweet_id_of ──────────────────────────────────────────────


def test_tweet_id_of_x_com() -> None:
    assert tweet_id_of(_URL) == _TID


def test_tweet_id_of_web_status_variant() -> None:
    assert tweet_id_of("https://x.com/i/web/status/1234567890") == "1234567890"


def test_tweet_id_of_no_status_returns_empty() -> None:
    assert tweet_id_of("https://x.com/some/profile") == ""
    assert tweet_id_of("") == ""


# ── load_guard fail-open ─────────────────────────────────────


def test_load_guard_missing_file(tmp_path: Path) -> None:
    assert load_guard(tmp_path / "nope.json") == {"urls": {}}


def test_load_guard_corrupt_json(tmp_path: Path) -> None:
    p = tmp_path / "guard.json"
    p.write_text("{broken", encoding="utf-8")
    assert load_guard(p) == {"urls": {}}


def test_load_guard_wrong_shape(tmp_path: Path) -> None:
    p = tmp_path / "guard.json"
    p.write_text(json.dumps(["not", "a", "dict"]), encoding="utf-8")
    assert load_guard(p) == {"urls": {}}


# ── 失敗カウント → ブロック ──────────────────────────────────


def test_failure_below_threshold_not_blocked(tmp_path: Path) -> None:
    p = tmp_path / "guard.json"
    guard = load_guard(p)
    for i in range(BLOCK_THRESHOLD - 1):
        assert record_failure(guard, _URL, "HTTP 404", p) == i + 1
    assert not is_blocked(guard, _URL)


def test_third_failure_blocks_persistently(tmp_path: Path) -> None:
    p = tmp_path / "guard.json"
    guard = load_guard(p)
    for _ in range(BLOCK_THRESHOLD):
        record_failure(guard, _URL, "HTTP 404", p)
    assert is_blocked(guard, _URL)
    # 再ロードしてもブロックは永続（＝次回収集でスキップされる）
    reloaded = load_guard(p)
    assert is_blocked(reloaded, _URL)
    saved = json.loads(p.read_text(encoding="utf-8"))
    assert saved["urls"][_TID]["blocked"] is True


def test_blocked_counts_as_skipped_on_fourth_failure(tmp_path: Path) -> None:
    """閾値超過後も is_blocked は True のまま（カウントは増えるが判定は不変）。"""
    p = tmp_path / "guard.json"
    guard = load_guard(p)
    for _ in range(BLOCK_THRESHOLD + 2):
        record_failure(guard, _URL, "exception", p)
    assert is_blocked(guard, _URL)


# ── 成功でリセット ────────────────────────────────────────────


def test_success_resets_failure_count(tmp_path: Path) -> None:
    p = tmp_path / "guard.json"
    guard = load_guard(p)
    record_failure(guard, _URL, "HTTP 404", p)
    record_failure(guard, _URL, "HTTP 404", p)
    record_success(guard, _URL, p)
    assert not is_blocked(guard, _URL)
    # カウントも消えている（1からやり直し）
    assert record_failure(guard, _URL, "HTTP 404", p) == 1


def test_record_success_on_unknown_url_is_noop(tmp_path: Path) -> None:
    p = tmp_path / "guard.json"
    guard = load_guard(p)
    record_success(guard, _URL, p)  # 存在しない → 例外なし・ファイル作らない
    assert not p.exists()


# ── 自動解除（30日） ─────────────────────────────────────────


def test_block_auto_expires_after_window(tmp_path: Path) -> None:
    p = tmp_path / "guard.json"
    guard = load_guard(p)
    for _ in range(BLOCK_THRESHOLD):
        record_failure(guard, _URL, "HTTP 404", p)
    old = (datetime.now() - timedelta(days=AUTO_UNBLOCK_DAYS + 1)).isoformat()
    guard["urls"][_TID]["blocked_at"] = old
    assert not is_blocked(guard, _URL)  # 自動解除 → 再試行許可


def test_block_still_active_within_window(tmp_path: Path) -> None:
    p = tmp_path / "guard.json"
    guard = load_guard(p)
    for _ in range(BLOCK_THRESHOLD):
        record_failure(guard, _URL, "HTTP 404", p)
    recent = (datetime.now() - timedelta(days=AUTO_UNBLOCK_DAYS - 1)).isoformat()
    guard["urls"][_TID]["blocked_at"] = recent
    assert is_blocked(guard, _URL)


# ── URL形態の違う同一ツイートをIDで統一制御 ──────────────────


def test_same_tweet_id_different_host_blocks_once(tmp_path: Path) -> None:
    p = tmp_path / "guard.json"
    guard = load_guard(p)
    variants = [
        "https://x.com/anyone/status/2094291340540399946",
        "https://twitter.com/other/statuses/2094291340540399946",
    ]
    for _ in range(BLOCK_THRESHOLD - 1):
        record_failure(guard, variants[0], "HTTP 404", p)
    record_failure(guard, variants[1], "HTTP 404", p)  # 同一IDの別形態 → 閾値到達
    # 別ユーザー名表記でも同一IDならブロック対象
    assert is_blocked(guard, variants[0])
    assert is_blocked(guard, variants[1])
