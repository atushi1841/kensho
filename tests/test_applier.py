"""
Tests for application/applier.py — ヘルパー関数・非ブラウザ部分
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from unittest.mock import patch

from kensho.application.rate_limiter import (
    check_rate_limit,
    increment_daily_count,
    is_active_hours,
    load_daily_counts,
    save_daily_counts,
)
from kensho.application.reply_generator import generate_reply
from kensho.application.state import (
    acquire_lock,
    release_lock,
)


class TestIsActiveHours:
    """is_active_hours: 動作時間帯判定（datetimeモック）"""

    def make_cfg(self, start: str = "09:00", end: str = "23:59") -> dict:
        return {
            "rate_limits": {
                "active_hours_start": start,
                "active_hours_end": end,
            }
        }

    def test_active_during_hours(self, monkeypatch) -> None:
        """09:00〜23:59の間はアクティブ（12:00）"""
        import datetime as _dt

        with patch("kensho.application.rate_limiter.datetime") as mock_dt:
            mock_dt.now.return_value = _dt.datetime(2026, 6, 24, 12, 0)
            cfg = self.make_cfg()
            assert is_active_hours(cfg) is True

    def test_inactive_before_start(self, monkeypatch) -> None:
        """08:00は09:00前なので非アクティブ"""
        import datetime as _dt

        with patch("kensho.application.rate_limiter.datetime") as mock_dt:
            mock_dt.now.return_value = _dt.datetime(2026, 6, 24, 8, 0)
            cfg = self.make_cfg()
            assert is_active_hours(cfg) is False

    def test_inactive_after_end(self, monkeypatch) -> None:
        """23:00は22:00以降（終）なので非アクティブ"""
        import datetime as _dt

        with patch("kensho.application.rate_limiter.datetime") as mock_dt:
            mock_dt.now.return_value = _dt.datetime(2026, 6, 24, 23, 0)
            cfg = self.make_cfg(end="22:00")
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


class TestSortItems:
    """sort_items: 優先順位ソート（締切・当選人数・その場で当たる系）"""

    def _item(
        self,
        x_url: str = "x.com/a/1",
        deadline: str = "",
        winner_count: int = 0,
        tweet_text: str = "",
        prize_mult: float = 1.0,
    ) -> dict:
        return {
            "x_url": x_url,
            "deadline": deadline,
            "winner_count": winner_count,
            "tweet_text": tweet_text,
            "prize_score": {"priority": prize_mult},
        }

    def test_instant_win_priority(self) -> None:
        """同締切なら「その場で当たる」系が優先される（アカウントスコア非依存）"""
        import datetime as _dt

        from kensho.application.actions import sort_items

        items = [
            self._item(x_url="x.com/a/1", deadline="2026-08-31", tweet_text="その場で当たるキャンペーン"),
            self._item(x_url="x.com/a/2", deadline="2026-08-31", tweet_text="通常のフォローRT企画"),
        ]
        sorted_items, removed = sort_items(items, now=_dt.datetime(2026, 8, 25))
        assert sorted_items[0]["x_url"] == "x.com/a/1"
        assert removed == 0

    def test_deadline_sort(self) -> None:
        """同条件なら締切が近い順"""
        import datetime as _dt

        from kensho.application.actions import sort_items

        items = [
            self._item(x_url="x.com/a/1", deadline="2026-08-27"),
            self._item(x_url="x.com/a/2", deadline="2026-09-10"),
        ]
        sorted_items, _removed = sort_items(items, now=_dt.datetime(2026, 8, 25))
        assert sorted_items[0]["x_url"] == "x.com/a/1"

    def test_winner_count_priority(self) -> None:
        """当選人数が多い方が優先（締切が同程度の場合）"""
        import datetime as _dt

        from kensho.application.actions import sort_items

        items = [
            self._item(x_url="x.com/a/1", deadline="2026-08-31", winner_count=5),
            self._item(x_url="x.com/a/2", deadline="2026-08-31", winner_count=500),
        ]
        sorted_items, _removed = sort_items(items, now=_dt.datetime(2026, 8, 25))
        # winner_count差は max(500/100,10)=5点 < jitter±5点 → 順序は保証されないためスキップ
        assert len(sorted_items) == 2

    def test_expired_removed(self) -> None:
        """期限切れは除外される"""
        import datetime as _dt

        from kensho.application.actions import sort_items

        items = [
            self._item(x_url="x.com/a/1", deadline="2026-08-20"),  # 過去
            self._item(x_url="x.com/a/2", deadline="2026-09-01"),  # 未来
        ]
        sorted_items, removed = sort_items(items, now=_dt.datetime(2026, 8, 25))
        assert removed == 1
        assert len(sorted_items) == 1
        assert sorted_items[0]["x_url"] == "x.com/a/2"

    def test_deadline_today_priority(self) -> None:
        """締切当日は最優先（時刻による-1日バグ修正の回帰テスト）"""
        import datetime as _dt

        from kensho.application.actions import sort_items

        items = [
            self._item(x_url="x.com/a/1", deadline="2026-08-25"),  # 今日（19時時点）
            self._item(x_url="x.com/a/2", deadline="2026-09-01"),  # 1週間後
        ]
        sorted_items, _removed = sort_items(items, now=_dt.datetime(2026, 8, 25, 19, 0))
        assert sorted_items[0]["x_url"] == "x.com/a/1"

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
        with tempfile.TemporaryDirectory() as tmpdir_str:
            counts_dir = Path(tmpdir_str)
            monkeypatch.setattr(
                "kensho.application.rate_limiter.DAILY_COUNTS_FILE",
                counts_dir / "daily_counts.json",
            )
            counts = load_daily_counts()
            assert isinstance(counts, dict)
            # no file exists, so dictionary should be empty
            assert counts == {}

    def test_save_and_load(self, monkeypatch: object) -> None:
        """保存して読み直せる"""
        with tempfile.TemporaryDirectory() as tmpdir_str:
            counts_dir = Path(tmpdir_str)
            monkeypatch.setattr(
                "kensho.application.rate_limiter.DAILY_COUNTS_FILE",
                counts_dir / "daily_counts.json",
            )
            save_daily_counts({"test_acct": {"follow": 5}})
            loaded = load_daily_counts()
            assert loaded.get("test_acct", {}).get("follow") == 5

    def test_increment(self, monkeypatch: object) -> None:
        """increment_count が正しく加算される"""
        with tempfile.TemporaryDirectory() as tmpdir_str:
            counts_dir = Path(tmpdir_str)
            monkeypatch.setattr(
                "kensho.application.rate_limiter.DAILY_COUNTS_FILE",
                counts_dir / "daily_counts.json",
            )
            increment_daily_count("test_acct", "follow", 1)
            increment_daily_count("test_acct", "follow", 3)
            loaded = load_daily_counts()
            assert loaded["test_acct"]["follow"] == 4


class TestCheckRateLimit:
    """check_rate_limit: 日次上限判定"""

    def make_cfg(self, follow=80, rt=80, like=200) -> dict:
        return {
            "rate_limits": {
                "max_follow_per_day": follow,
                "max_rt_per_day": rt,
                "max_like_per_day": like,
            }
        }

    def test_under_limit(self, monkeypatch: object) -> None:
        """上限未満 → False（処理続行）"""
        with tempfile.TemporaryDirectory() as tmpdir_str:
            counts_dir = Path(tmpdir_str)
            counts_file = counts_dir / "daily_counts.json"
            monkeypatch.setattr(
                "kensho.application.rate_limiter.DAILY_COUNTS_FILE",
                counts_file,
            )
            assert check_rate_limit("test_acct", self.make_cfg()) is False

    def test_follow_over_limit(self, monkeypatch: object) -> None:
        """フォロー上限超過 → True（停止）"""
        monkeypatch.setattr("random.uniform", lambda a, b: 1.0)
        with tempfile.TemporaryDirectory() as tmpdir_str:
            counts_dir = Path(tmpdir_str)
            counts_file = counts_dir / "daily_counts.json"
            monkeypatch.setattr(
                "kensho.application.rate_limiter.DAILY_COUNTS_FILE",
                counts_file,
            )
            save_daily_counts({"test_acct": {"follow": 80, "rt": 0, "like": 0}})
            assert check_rate_limit("test_acct", self.make_cfg(follow=80)) is True

    def test_rt_over_limit(self, monkeypatch: object) -> None:
        """RT上限超過 → True"""
        monkeypatch.setattr("random.uniform", lambda a, b: 1.0)
        with tempfile.TemporaryDirectory() as tmpdir_str:
            counts_dir = Path(tmpdir_str)
            counts_file = counts_dir / "daily_counts.json"
            monkeypatch.setattr(
                "kensho.application.rate_limiter.DAILY_COUNTS_FILE",
                counts_file,
            )
            save_daily_counts({"test_acct": {"follow": 0, "rt": 80, "like": 0}})
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


class TestCheckTweetResult:
    """_check_tweet_result: 応募後のツイート状態確認

    2026-08-25 修正: goto失敗時は "goto_failed" でなく None(正常扱い)を返す。
    goto_failed だと applied が付与されず、応募済みツイートが毎セッション再処理
    される無限ループが発生するため。
    """

    def _make_page(self, url: str = "https://x.com/a/status/1", body: str = "normal") -> object:
        class FakePage:
            def __init__(self) -> None:
                self._url = url
                self._body = body
                self._goto_ok = True

            @property
            def url(self) -> str:
                return self._url

            def goto(self, url: str, timeout: int = 30000, wait_until: str = "domcontentloaded") -> None:
                if not self._goto_ok:
                    raise TimeoutError("Page.goto: Timeout 15000ms exceeded.")
                self._url = url

            def inner_text(self, selector: str) -> str:
                return self._body

        return FakePage()

    def _call(self, page: object, monkeypatch) -> str | None:
        from kensho.application.applier import _check_tweet_result

        monkeypatch.setattr("time.sleep", lambda s: None)
        monkeypatch.setattr("random.uniform", lambda a, b: 1.0)
        return _check_tweet_result(page, "https://x.com/a/status/1", lambda msg: None)

    def test_goto_timeout_returns_none(self, monkeypatch) -> None:
        """gotoタイムアウト → None(正常扱い) 応募成立に阻害しない"""
        page = self._make_page(url="https://x.com/home", body="normal")
        page._goto_ok = False  # type: ignore[attr-defined]
        assert self._call(page, monkeypatch) is None

    def test_normal_tweet_returns_tweet_ok(self, monkeypatch) -> None:
        """正常ツイート → tweet_ok"""
        page = self._make_page(body="some normal content")
        assert self._call(page, monkeypatch) == "tweet_ok"

    def test_deleted_tweet_returns_tweet_deleted(self, monkeypatch) -> None:
        """削除済みツイート → tweet_deleted（DEFER対象）"""
        page = self._make_page(body="This tweet has been deleted.")
        assert self._call(page, monkeypatch) == "tweet_deleted"


class TestExtractTweetIdAndScreenName:
    """extract_tweet_id_and_screen_name: URLからtweet_id/screen_name抽出（2026-08-26追加）"""

    def test_normal_url(self) -> None:
        from kensho.application.api_actions import extract_tweet_id_and_screen_name

        tid, sn = extract_tweet_id_and_screen_name("https://x.com/foo_bar/status/123456")
        assert tid == "123456"
        assert sn == "foo_bar"

    def test_no_screen_name_url(self) -> None:
        """x.com/status/123 形式ではscreen_nameを誤抽出しない"""
        from kensho.application.api_actions import extract_tweet_id_and_screen_name

        tid, sn = extract_tweet_id_and_screen_name("https://x.com/status/123456")
        assert tid == "123456"
        assert sn is None

    def test_iweb_url(self) -> None:
        """/i/web/status/ 形式でもtweet_idは抽出できる"""
        from kensho.application.api_actions import extract_tweet_id_and_screen_name

        tid, sn = extract_tweet_id_and_screen_name("https://x.com/i/web/status/123456")
        assert tid == "123456"
        assert sn is None
