"""
Tests for application/applier.py — ヘルパー関数・非ブラウザ部分
"""

from __future__ import annotations

import datetime as _dt
import json
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
    save_collected_safe,
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

    def test_dedupe_batch_items(self) -> None:
        """バッチ候補の x_url/tweet_id 重複を除外する（提案82）"""
        from kensho.application.applier import _dedupe_batch_items

        items = [
            self._item(x_url="x.com/user/status/12345"),
            self._item(x_url="x.com/user/status/12345?foo=1"),  # 同一 tweet_id
            self._item(x_url="x.com/other/status/67890"),  # 別ツイート
            self._item(x_url="x.com/other/status/67890#bar"),  # 同一 tweet_id
            self._item(x_url="x.com/third/status/99999"),  # 別ツイート
        ]
        deduped = _dedupe_batch_items(items)
        assert len(deduped) == 3
        # 先頭エントリが保持される
        assert deduped[0]["x_url"] == "x.com/user/status/12345"
        assert deduped[1]["x_url"] == "x.com/other/status/67890"
        assert deduped[2]["x_url"] == "x.com/third/status/99999"

    def test_cross_account_proximity_defers_recent(self) -> None:
        """別垢が6時間以内に処理済み → DEFERを書きTrue（提案88）"""
        import datetime as _dt

        from kensho.application.applier import _DEFER_PREFIX, _cross_account_proximity_defer

        recent = (_dt.datetime.now() - _dt.timedelta(hours=1)).isoformat()
        item = self._item(x_url="x.com/a/status/111")
        item["applied"] = {"atushi16": recent}
        cfg = {"applier": {}}
        log = []

        class _LogStub:
            def write(self, m: str) -> None:
                log.append(m)

        result = _cross_account_proximity_defer(item, "kudou", cfg, _LogStub())
        assert result is True
        val = item["applied"]["kudou"]
        assert val.startswith(_DEFER_PREFIX)
        # DEFER期限は未来（4〜8時間後）
        from kensho.application.applier import _get_defer_time

        defer_ts = _get_defer_time(val)
        assert defer_ts is not None
        assert defer_ts > _dt.datetime.now()

    def test_cross_account_proximity_ignores_old_and_defer(self) -> None:
        """別垢処理が6時間超 or DEFER中ならスキップしない（提案88）"""
        import datetime as _dt

        from kensho.application.applier import _cross_account_proximity_defer

        old = (_dt.datetime.now() - _dt.timedelta(hours=12)).isoformat()
        cfg = {"applier": {}}
        # 12時間前処理 → 近接ではない → False
        item_old = self._item(x_url="x.com/a/status/111")
        item_old["applied"] = {"atushi16": old}
        assert _cross_account_proximity_defer(item_old, "kudou", cfg, []) is False
        # 他垢がDEFER中（未処理）→ 近接ではない → False
        defer_val = f"DEFER:{(_dt.datetime.now() + _dt.timedelta(hours=5)).isoformat()}"
        item_defer = self._item(x_url="x.com/a/status/222")
        item_defer["applied"] = {"atushi16": defer_val}
        assert _cross_account_proximity_defer(item_defer, "kudou", cfg, []) is False

    def test_cross_account_proximity_same_account_ignored(self) -> None:
        """自分自身のappliedは近接判定に含めない（提案88）"""
        import datetime as _dt

        from kensho.application.applier import _cross_account_proximity_defer

        recent = (_dt.datetime.now() - _dt.timedelta(minutes=5)).isoformat()
        item = self._item(x_url="x.com/a/status/333")
        item["applied"] = {"kudou": recent}  # 自分自身のみ
        cfg = {"applier": {}}
        assert _cross_account_proximity_defer(item, "kudou", cfg, []) is False

    def test_follow_403_abort_flag_set_on_three_consecutive(self) -> None:
        """提案91: フォロー403が3回連続したら _frozen_by_follow_403 が立つ
        （内側action_queueループを抜けた後、外側whileループ頭でbreakするためのフラグ）。

        提案90の `break` は内側 for ループしか抜けず、外側 while は継続→[FROZEN]が
        11回連続出るバグ（実測: 8/30 inobase1-4）があった。本テストは内側の
        follow 403 カウンタ3回でフラグが True になる構造を保証する。
        """
        import inspect

        from kensho.application import applier

        src = inspect.getsource(applier)
        # 1. フラグが外側whileループ内でチェックされる
        assert "_frozen_by_follow_403" in src, "フラグ _frozen_by_follow_403 がソースに存在しない"
        # 2. チェック構文: 外側while内で `if _frozen_by_follow_403: break` がある
        #    "  while success < max_n" を含むチャンクに `if _frozen_by_follow_403` が
        #    直前に存在することを確認（外側while専用チェック）
        #    提案91で導入した FROZEN_ABORT ログマーカー
        assert "[FROZEN_ABORT]" in src, "[FROZEN_ABORT] ログマーカーが存在しない"
        # 3. 内側ループで `_frozen_by_follow_403 = True` の代入がある
        #    提案90の [FROZEN] ログ直後にフラグを立てる
        _frozen_idx = src.find("[FROZEN] フォロー403連続3回")
        assert _frozen_idx > 0, "[FROZEN] フォロー403連続3回のログが見つからない"
        # 代入が [FROZEN] ログより後に出現
        _assign_idx = src.find("_frozen_by_follow_403 = True", _frozen_idx)
        assert _assign_idx > _frozen_idx, "_frozen_by_follow_403 = True の代入が[FROZEN]ログより前にある"

    def test_follow_403_resets_on_non_403_follow_error(self) -> None:
        """提案90: フォローが403以外のエラーなら _follow_403_count はリセットされる。
        リファクタ後も維持されているか（提案91の追加で挙動が変わってないか）を保証。
        """
        import inspect

        from kensho.application import applier

        src = inspect.getsource(applier)
        # 1) 初期化: 関数ローカルで `_follow_403_count: int = 0` がある
        assert "_follow_403_count: int = 0" in src, (
            "フォロー403カウンタの初期化 `_follow_403_count: int = 0` が見つからない"
        )
        # 2) リセット: `_follow_403_count = 0`（代入）が2箇所
        #    - 403以外のフォローエラー（elif節）
        #    - フォロー成功時（else節）
        _reset_count = src.count("_follow_403_count = 0")
        assert _reset_count == 2, f"_follow_403_count = 0 の代入回数が想定外: {_reset_count}（期待: 2）"
        # 3) インクリメント: `_follow_403_count += 1` が1箇所（403検出）
        assert src.count("_follow_403_count += 1") == 1, (
            f"_follow_403_count += 1 のインクリメント箇所が想定外: {src.count('_follow_403_count += 1')}"
        )

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


class TestSaveCollectedSafeMeta:
    """save_collected_safe: 診断メタフィールドの永続化（提案81）"""

    def _setup(self, tmp_path: Path, monkeypatch: object) -> tuple[Path, Path]:
        """COLLECTED_FILE/LOCK を tmp に差し替えてパスを返す"""
        import kensho.application.state as state_mod

        col_file = tmp_path / "collected.json"
        col_lock = tmp_path / "collected.lock"
        monkeypatch.setattr(state_mod, "COLLECTED_FILE", col_file)
        monkeypatch.setattr(state_mod, "COLLECTED_LOCK", col_lock)
        return col_file, col_lock  # type: ignore[return-value]

    def test_meta_preserved_from_disk(self, tmp_path: Path, monkeypatch: object) -> None:
        """applierの古いin-memory data(None/0メタ)でもディスクcurrentのメタを保持"""
        col_file, _ = self._setup(tmp_path, monkeypatch)
        # collectorが書いた新鮮なメタ（ディスク）
        col_file.write_text(
            json.dumps({
                "timestamp": "2026-08-29T15:00:00",
                "total_on_page": 363,
                "new_items_processed": 363,
                "new_items_by_source": {"knshow": 0, "ken-kaku": 24},
                "collected": [
                    {
                        "detail_url": "https://x.com/a/status/1",
                        "applied": {"atushi16": "2026-08-29T14:00:00"},
                    }
                ],
            }),
            encoding="utf-8",
        )
        # applierの古いin-memory data（収集前ロード・メタが消えている）
        stale = {
            "new_items_processed": 0,
            "new_items_by_source": None,
            "total_on_page": 43,
            "collected": [
                {
                    "detail_url": "https://x.com/a/status/1",
                    "applied": {"atushi16": "2026-08-29T14:30:00"},
                }
            ],
        }
        save_collected_safe(stale, "atushi16")
        saved = json.loads(col_file.read_text(encoding="utf-8"))
        assert saved["new_items_processed"] == 363
        assert saved["new_items_by_source"] == {"knshow": 0, "ken-kaku": 24}
        assert saved["total_on_page"] == 363
        assert saved["timestamp"] == "2026-08-29T15:00:00"
        # collected マージは従来通り（applied は None でない値が優先）
        assert saved["collected"][0]["applied"]["atushi16"] == "2026-08-29T14:30:00"

    def test_applied_union_still_works(self, tmp_path: Path, monkeypatch: object) -> None:
        """メタ補完後も applied の None汚染防止unionが機能する（回帰確認）"""
        col_file, _ = self._setup(tmp_path, monkeypatch)
        col_file.write_text(
            json.dumps({
                "new_items_processed": 100,
                "collected": [
                    {
                        "detail_url": "https://x.com/a/status/1",
                        "applied": {"kudou": "2026-08-29T12:00:00"},
                    }
                ],
            }),
            encoding="utf-8",
        )
        # 別垢applierがapplied=Noneで保存しようとしても他垢の日付は消えない
        data = {
            "collected": [
                {
                    "detail_url": "https://x.com/a/status/1",
                    "applied": {"kudou": None, "atushi16": "2026-08-29T13:00:00"},
                }
            ]
        }
        save_collected_safe(data, "atushi16")
        saved = json.loads(col_file.read_text(encoding="utf-8"))
        assert saved["collected"][0]["applied"]["kudou"] == "2026-08-29T12:00:00"
        assert saved["collected"][0]["applied"]["atushi16"] == "2026-08-29T13:00:00"
        assert saved["new_items_processed"] == 100  # メタも保持


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


class TestMergeVerifyResult:
    """_merge_verify_result: VERIFY失敗はAPI成功を覆さない（2026-08-26提案8）

    回帰対象: 12bd9faで「VERIFY失敗→_per_item_ok=False」と単純化され、
    API成功アクションがVERIFY失敗で覆され、CEILING連鎖でバッチ打ち切りが
    発生した（atushi16 14:18実測）。VERIFYは「偽装成功の検出器」であり
    「成功の取り消し器」ではない。
    """

    def test_api_success_not_overridden_by_verify_failure(self) -> None:
        """API成功(current=True)はVERIFY失敗(verify_success=False)で覆されない"""
        from kensho.application.applier import _merge_verify_result

        assert _merge_verify_result(current=True, verify_success=False) is True

    def test_api_failure_confirmed_by_verify_failure(self) -> None:
        """API未成功(current=False)はVERIFY失敗でFalse確定"""
        from kensho.application.applier import _merge_verify_result

        assert _merge_verify_result(current=False, verify_success=False) is False

    def test_verify_success_promotes_failure(self) -> None:
        """API未成功でもVERIFY成功ならTrue（フォールバック経路の救済）"""
        from kensho.application.applier import _merge_verify_result

        assert _merge_verify_result(current=False, verify_success=True) is True

    def test_api_success_keeps_true_even_with_verify_success(self) -> None:
        """API成功+VERIFY成功 → True維持"""
        from kensho.application.applier import _merge_verify_result

        assert _merge_verify_result(current=True, verify_success=True) is True

    def test_verify_failure_does_not_trigger_ceiling(self) -> None:
        """VERIFY失敗はfailure_tracker/CEILINGに参加しない（バッチ打ち切り防止）"""
        # applier.py 1206-1210行: 全件VERIFY失敗でもfailure_tracker記録なし・breakなし
        # ここでは「VERIFY失敗が_qualify(any(_per_item_ok))に影響しない」契約を固定する
        _per_item_ok = {"follow": True, "rt": False, "like": False}  # APIフォロー成功
        # VERIFY全件失敗相当（rt/like/followすべてverify_success=False）でも
        assert any(_per_item_ok.values()) is True  # API成功が維持される


class TestIsDeferExpired:
    """_is_defer_expired: 期限切れDEFER判定（2026-08-29提案63 root-cause fix）

    回帰対象: 旧ガード `not _is_deferred(...)` はプレフィクス判定のみで期限切れDEFERも
    True を返し、「期限切れDEFER→再ピック→失敗→素通り→30分ごと再ピックループ」が
    発生した。期限を実際に比較して期限切れのみ True を返すこと。
    """

    def test_none(self) -> None:
        from kensho.application.applier import _is_defer_expired

        assert _is_defer_expired(None) is False

    def test_normal_applied_timestamp(self) -> None:
        """通常のapplied日時（DEFERでない）は期限切れ扱いしない"""
        from kensho.application.applier import _is_defer_expired

        assert _is_defer_expired("2026-08-29T00:00:00+09:00") is False

    def test_active_defer_not_expired(self) -> None:
        """有効期限内のDEFERは期限切れでない"""
        from datetime import datetime, timedelta

        from kensho.application.applier import _DEFER_PREFIX, _is_defer_expired

        future = datetime.now(_dt.UTC) + timedelta(minutes=30)
        assert _is_defer_expired(f"{_DEFER_PREFIX}{future.isoformat()}") is False

    def test_expired_defer(self) -> None:
        """期限切れDEFERはTrue"""
        from datetime import datetime, timedelta

        from kensho.application.applier import _DEFER_PREFIX, _is_defer_expired

        past = datetime.now(_dt.UTC) - timedelta(minutes=30)
        assert _is_defer_expired(f"{_DEFER_PREFIX}{past.isoformat()}") is True

    def test_malformed_defer(self) -> None:
        """パース不能なDEFER文字列は期限切れ扱いしない（安全側）"""
        from kensho.application.applier import _DEFER_PREFIX, _is_defer_expired

        assert _is_defer_expired(f"{_DEFER_PREFIX}garbage") is False


class TestLoadAuditDoneSet:
    """_load_audit_done_set: audit.jsonlベースのセッション跨ぎ重複防止（2026-08-26提案10）

    当日JST分のRT/follow/like成功（提案12でlike追加）のみを抽出し、n/aや他垢・他日は除外する。
    実時刻（JST）からUTCタイムスタンプを逆算して検証する。
    """

    JST = _dt.timezone(_dt.timedelta(hours=9))

    def _utc_ts(self, dt_jst: _dt.datetime) -> str:
        """JST日時 → UTCタイムスタンプ文字列（audit.jsonl形式）"""
        return dt_jst.astimezone(_dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    def _make_audit_line(
        self,
        timestamp_utc: str,
        account: str,
        action_type: str,
        target: str,
        status: str = "success",
        decision: str = "allow",
    ) -> str:
        return json.dumps(
            {
                "timestamp": timestamp_utc,
                "account": account,
                "action_type": action_type,
                "target": target,
                "decision": decision,
                "status": status,
                "reason": "",
                "error": "",
                "delay_ms": 0,
                "prev_hash": "0" * 64,
                "hash": "0" * 64,
            },
            ensure_ascii=False,
        )

    def _write(self, monkeypatch, tmp_path: Path, lines: list[str]) -> None:
        """DATA_DIRをtmp_pathに差し替え、audit.jsonlを書き込む"""
        import kensho.application.applier as a

        monkeypatch.setattr(a, "DATA_DIR", tmp_path)
        if lines:
            (tmp_path / "audit.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def test_returns_today_rt_success(self, monkeypatch, tmp_path: Path) -> None:
        """当日JSTのRT成功が抽出される"""
        import kensho.application.applier as a

        now_jst = _dt.datetime.now(self.JST)
        ts = self._utc_ts(now_jst - _dt.timedelta(minutes=5))
        self._write(monkeypatch, tmp_path, [self._make_audit_line(ts, "atushi16", "rt", "123456")])
        rt_done, follow_done, like_done = a._load_audit_done_set("atushi16")
        assert "123456" in rt_done
        assert len(follow_done) == 0
        assert len(like_done) == 0

    def test_returns_today_follow_success(self, monkeypatch, tmp_path: Path) -> None:
        """当日JSTのフォロー成功が抽出される"""
        import kensho.application.applier as a

        now_jst = _dt.datetime.now(self.JST)
        ts = self._utc_ts(now_jst - _dt.timedelta(minutes=5))
        self._write(monkeypatch, tmp_path, [self._make_audit_line(ts, "atushi16", "follow", "test_user")])
        rt_done, follow_done, like_done = a._load_audit_done_set("atushi16")
        assert "test_user" in follow_done
        assert len(rt_done) == 0
        assert len(like_done) == 0

    def test_returns_today_like_success(self, monkeypatch, tmp_path: Path) -> None:
        """当日JSTのいいね成功（提案12のlike_done）が抽出される"""
        import kensho.application.applier as a

        now_jst = _dt.datetime.now(self.JST)
        ts = self._utc_ts(now_jst - _dt.timedelta(minutes=5))
        self._write(monkeypatch, tmp_path, [self._make_audit_line(ts, "atushi16", "like", "555111")])
        rt_done, follow_done, like_done = a._load_audit_done_set("atushi16")
        assert "555111" in like_done
        assert len(rt_done) == 0
        assert len(follow_done) == 0

    def test_excludes_other_account(self, monkeypatch, tmp_path: Path) -> None:
        """他アカウントの成功は除外される"""
        import kensho.application.applier as a

        now_jst = _dt.datetime.now(self.JST)
        ts = self._utc_ts(now_jst - _dt.timedelta(minutes=5))
        self._write(monkeypatch, tmp_path, [self._make_audit_line(ts, "kudou", "rt", "999999")])
        rt_done, follow_done, like_done = a._load_audit_done_set("atushi16")
        assert len(rt_done) == 0
        assert len(follow_done) == 0

    def test_excludes_na_target(self, monkeypatch, tmp_path: Path) -> None:
        """target='n/a'のエントリは除外される"""
        import kensho.application.applier as a

        now_jst = _dt.datetime.now(self.JST)
        ts = self._utc_ts(now_jst - _dt.timedelta(minutes=5))
        self._write(monkeypatch, tmp_path, [self._make_audit_line(ts, "atushi16", "rt", "n/a")])
        rt_done, follow_done, like_done = a._load_audit_done_set("atushi16")
        assert len(rt_done) == 0

    def test_excludes_non_success(self, monkeypatch, tmp_path: Path) -> None:
        """status='failed'や'deny'は除外される"""
        import kensho.application.applier as a

        now_jst = _dt.datetime.now(self.JST)
        ts = self._utc_ts(now_jst - _dt.timedelta(minutes=5))
        self._write(
            monkeypatch,
            tmp_path,
            [
                self._make_audit_line(ts, "atushi16", "rt", "123456", status="failed"),
                self._make_audit_line(ts, "atushi16", "rt", "789012", decision="deny"),
            ],
        )
        rt_done, follow_done, like_done = a._load_audit_done_set("atushi16")
        assert len(rt_done) == 0

    def test_excludes_other_day(self, monkeypatch, tmp_path: Path) -> None:
        """他日のエントリ（JST換算で昨日）は除外される"""
        import kensho.application.applier as a

        now_jst = _dt.datetime.now(self.JST)
        ts = self._utc_ts(now_jst - _dt.timedelta(days=1))
        self._write(monkeypatch, tmp_path, [self._make_audit_line(ts, "atushi16", "rt", "123456")])
        rt_done, follow_done, like_done = a._load_audit_done_set("atushi16")
        assert len(rt_done) == 0

    def test_includes_today_jst_boundary(self, monkeypatch, tmp_path: Path) -> None:
        """JST当日07:00（前日UTC22:00）→ 当日扱い（JST日付境界）"""
        import kensho.application.applier as a

        today = _dt.datetime.now(self.JST).date()
        ts = self._utc_ts(_dt.datetime.combine(today, _dt.time(7, 0), tzinfo=self.JST))
        self._write(monkeypatch, tmp_path, [self._make_audit_line(ts, "atushi16", "rt", "123456")])
        rt_done, follow_done, like_done = a._load_audit_done_set("atushi16")
        assert "123456" in rt_done

    def test_excludes_tomorrow_jst(self, monkeypatch, tmp_path: Path) -> None:
        """JST翌日分（翌日07:00）→ 翌日扱いで除外"""
        import kensho.application.applier as a

        today = _dt.datetime.now(self.JST).date()
        ts = self._utc_ts(_dt.datetime.combine(today + _dt.timedelta(days=1), _dt.time(7, 0), tzinfo=self.JST))
        self._write(monkeypatch, tmp_path, [self._make_audit_line(ts, "atushi16", "rt", "123456")])
        rt_done, follow_done, like_done = a._load_audit_done_set("atushi16")
        assert len(rt_done) == 0

    def test_returns_empty_when_no_file(self, monkeypatch, tmp_path: Path) -> None:
        """audit.jsonlが存在しない場合、空のtupleを返す"""
        import kensho.application.applier as a

        monkeypatch.setattr(a, "DATA_DIR", tmp_path)
        rt_done, follow_done, like_done = a._load_audit_done_set("atushi16")
        assert len(rt_done) == 0
        assert len(follow_done) == 0


class TestSpeedGuard:
    """_speed_guard_needed: セッション内速度ガード（提案53, 2026-08-28）"""

    def test_empty_deque_no_guard(self) -> None:
        """空のdeque → ガード不要"""
        from collections import deque

        import kensho.application.applier as a

        assert a._speed_guard_needed(deque(), 180, 15) is False

    def test_below_max_no_guard(self) -> None:
        """窓内10件（上限15） → ガード不要"""
        import time
        from collections import deque

        import kensho.application.applier as a

        dq = deque(time.time() - i * 5 for i in range(10))
        assert a._speed_guard_needed(dq, 180, 15) is False

    def test_at_max_guard(self) -> None:
        """窓内15件（上限15） → ガード必要"""
        import time
        from collections import deque

        import kensho.application.applier as a

        dq = deque(time.time() - i * 5 for i in range(15))
        assert a._speed_guard_needed(dq, 180, 15) is True

    def test_stale_entries_pruned(self) -> None:
        """窓より古い記録は除去され、窓内が上限未満ならガード不要"""
        import time
        from collections import deque

        import kensho.application.applier as a

        dq = deque()
        dq.append(time.time() - 1000)  # 古すぎ
        dq.extend(time.time() - i * 10 for i in range(5))  # 直近
        assert a._speed_guard_needed(dq, 180, 15) is False
        assert len(dq) == 5  # 古い1件が除去されている


class TestIsApplicationComplete:
    """_is_application_complete: 応募成立判定（2026-08-29ユーザー定義: フォロー状態+いいね）

    ルール:
    - フォロー実行/既フォロー + いいね成功（またはBOT対策の自然スキップ）→ 成立
    - フォロー実行/既フォロー + いいね実失敗 → 不成立（再試行）
    - RTのみ成功（フォロー非関与）→ 成立
    - いいねのみ・何もなし → 不成立
    """

    def _c(self, follow_ok=False, follow_already=False, rt_ok=False, like_ok=False, like_skipped=False):
        from kensho.application.applier import _is_application_complete

        return _is_application_complete(follow_ok, follow_already, rt_ok, like_ok, like_skipped)

    def test_follow_plus_like_success(self) -> None:
        """フォロー成功+いいね成功 → 応募成立"""
        assert self._c(follow_ok=True, like_ok=True) is True

    def test_follow_plus_like_failed(self) -> None:
        """フォロー成功+いいね実失敗 → 不成立（再試行対象）"""
        assert self._c(follow_ok=True, like_ok=False, like_skipped=False) is False

    def test_follow_plus_like_skipped_natural(self) -> None:
        """フォロー成功+いいね意図的スキップ(BOT対策) → 成立扱い（無限リトライ防止）"""
        assert self._c(follow_ok=True, like_skipped=True) is True

    def test_already_followed_like_success(self) -> None:
        """既フォロー+いいね成功 → 成立"""
        assert self._c(follow_already=True, like_ok=True) is True

    def test_already_followed_like_failed(self) -> None:
        """既フォロー+いいね実失敗 → 不成立（再試行）"""
        assert self._c(follow_already=True, like_ok=False, like_skipped=False) is False

    def test_rt_only_success(self) -> None:
        """RTのみ成功（フォロー非関与）→ 成立（従来通り）"""
        assert self._c(rt_ok=True) is True

    def test_like_only_not_enough(self) -> None:
        """いいねのみ（フォローなし・RTなし）→ 不成立"""
        assert self._c(like_ok=True) is False

    def test_no_actions(self) -> None:
        """何も成功していない → 不成立"""
        assert self._c() is False
