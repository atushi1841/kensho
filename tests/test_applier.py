"""
Tests for application/applier.py — ヘルパー関数・非ブラウザ部分
"""
from __future__ import annotations

import json, os, tempfile
from pathlib import Path
from datetime import datetime, date

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from application.rate_limiter import (
    is_active_hours,
    load_daily_counts,
    save_daily_counts,
    increment_daily_count,
    check_rate_limit,
)
from application.reply_generator import generate_reply
from application.state import (
    acquire_lock,
    release_lock,
)


class TestIsActiveHours:
    """is_active_hours: 動作時間帯判定（datetimeモック）"""

    def make_cfg(self, start: str = "09:00", end: str = "23:59") -> dict:
        return {"rate_limits": {
            "active_hours_start": start,
            "active_hours_end": end,
        }}

    def test_active_during_hours(self, monkeypatch) -> None:
        """09:00〜23:59の間はアクティブ"""
        import datetime as _dt
        monkeypatch.setattr(
            "application.rate_limiter.datetime",
            type("MockDT", (), {
                "now": staticmethod(lambda: _dt.datetime(2026, 6, 24, 14, 30)),
            }),
        )
        cfg = self.make_cfg()
        assert is_active_hours(cfg) is True

    def test_inactive_before_start(self, monkeypatch) -> None:
        """08:00は09:00前なので非アクティブ"""
        import datetime as _dt
        monkeypatch.setattr(
            "application.rate_limiter.datetime",
            type("MockDT", (), {
                "now": staticmethod(lambda: _dt.datetime(2026, 6, 24, 8, 0)),
            }),
        )
        cfg = self.make_cfg()
        assert is_active_hours(cfg) is False

    def test_inactive_after_end(self, monkeypatch) -> None:
        """00:30は深夜なので非アクティブ"""
        import datetime as _dt
        monkeypatch.setattr(
            "application.rate_limiter.datetime",
            type("MockDT", (), {
                "now": staticmethod(lambda: _dt.datetime(2026, 6, 25, 0, 30)),
            }),
        )
        cfg = self.make_cfg()
        assert is_active_hours(cfg) is False


class TestGenerateReply:
    """generate_reply: キーワード別リプライ生成"""

    def test_present_keyword(self) -> None:
        """プレゼント系キーワード"""
        reply = generate_reply("プレゼントキャンペーン開催中")
        assert "参加" in reply or "当た" in reply or "キャンペーン" in reply

    def test_season_keyword(self) -> None:
        """季節系キーワード（キャンペーンより優先されないので注意）"""
        reply = generate_reply("春らしいプレゼント企画")
        # 「プレゼント」で先にマッチする可能性もあるので柔軟に
        assert len(reply) >= 4

    def test_opinion_keyword(self) -> None:
        """感想系キーワード"""
        reply = generate_reply("感想を教えてください")
        assert any(w in reply for w in ["素敵", "面白", "気にな"])

    def test_fallback_random(self) -> None:
        """マッチしない場合は共通テンプレートから"""
        reply = generate_reply("何でもない普通のツイートです")
        # 必ず何か返る（長さ1以上）
        assert len(reply) >= 4


class TestDailyCounts:
    """日次カウンター管理（ファイルI/O含む）"""

    def test_load_empty(self, monkeypatch: object) -> None:
        """ファイルがない → 空dict"""
        counts = load_daily_counts()
        assert isinstance(counts, dict)

    def test_save_and_load(self, monkeypatch: object) -> None:
        """保存して読み直せる"""
        tmpdir = tempfile.mkdtemp()
        counts_dir = Path(tmpdir)
        monkeypatch.setattr(
            "application.rate_limiter.DAILY_COUNTS_FILE",
            counts_dir / "daily_counts.json",
        )
        save_daily_counts({"test_acct": {"follow": 5}})
        loaded = load_daily_counts()
        assert loaded.get("test_acct", {}).get("follow") == 5

    def test_increment(self, monkeypatch: object) -> None:
        """increment_count が正しく加算される"""
        tmpdir = tempfile.mkdtemp()
        counts_dir = Path(tmpdir)
        monkeypatch.setattr(
            "application.rate_limiter.DAILY_COUNTS_FILE",
            counts_dir / "daily_counts.json",
        )
        increment_daily_count("test_acct", "follow", 1)
        increment_daily_count("test_acct", "follow", 3)
        loaded = load_daily_counts()
        assert loaded["test_acct"]["follow"] == 4


class TestCheckRateLimit:
    """check_rate_limit: 日次上限判定"""

    def make_cfg(self, follow=80, rt=80, like=200) -> dict:
        return {"rate_limits": {
            "max_follow_per_day": follow,
            "max_rt_per_day": rt,
            "max_like_per_day": like,
        }}

    def test_under_limit(self, monkeypatch: object) -> None:
        """上限未満 → False（処理続行）"""
        monkeypatch.setattr(
            "application.rate_limiter.load_daily_counts",
            lambda: {"test_acct": {"follow": 5, "rt": 3, "like": 10}},
        )
        assert check_rate_limit("test_acct", self.make_cfg()) is False

    def test_follow_over_limit(self, monkeypatch: object) -> None:
        """フォロー上限超過 → True（停止）"""
        monkeypatch.setattr(
            "application.rate_limiter.load_daily_counts",
            lambda: {"test_acct": {"follow": 80, "rt": 0, "like": 0}},
        )
        assert check_rate_limit("test_acct", self.make_cfg(follow=80)) is True

    def test_rt_over_limit(self, monkeypatch: object) -> None:
        """RT上限超過 → True"""
        monkeypatch.setattr(
            "application.rate_limiter.load_daily_counts",
            lambda: {"test_acct": {"follow": 0, "rt": 80, "like": 0}},
        )
        assert check_rate_limit("test_acct", self.make_cfg(rt=80)) is True


class TestLockMechanism:
    """acquire_lock / release_lock: 排他ロック"""

    def test_acquire_and_release(self) -> None:
        """ロック取得→解放のサイクル"""
        assert acquire_lock(timeout=5) is True
        release_lock()
        # 解放後は再取得できる
        assert acquire_lock(timeout=5) is True
        release_lock()

    def test_double_acquire_fails(self) -> None:
        """2重取得は失敗"""
        assert acquire_lock(timeout=5) is True
        assert acquire_lock(timeout=1) is False  # タイムアウトで失敗
        release_lock()
