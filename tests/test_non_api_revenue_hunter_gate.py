"""tests/test_non_api_revenue_hunter_gate.py — 収益ハンター品質ゲート (t_2e20f1ef v58) の回帰テスト.

検証対象:
  要件1: score<3 / monetization シグナル無しの案件をスキップ
  要件2: 1実行あたり新規投入を最大3件にキャップ
  要件3: HN item_id 主キー dedup (done/archived 含む全ステータス)
"""

import importlib.util
import sqlite3
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

import kanban_norm  # noqa: E402


def _load_hunter():
    """ハイフン入りファイル名の hunter を importlib でロードする."""
    path = REPO / "kensho-non-api-revenue-hunter.py"
    spec = importlib.util.spec_from_file_location("kensho_non_api_revenue_hunter", path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


hunter = _load_hunter()


def _hi_matches(item):
    """classify_seed 互換の高スコア一致（テスト用）."""
    return [{"category": "アプリ/ツール", "weight": "高", "has_automation_keyword": True}]


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _make_db(tmpdir: str) -> str:
    """kanban tasks テーブルを持つ最小 DB を作る."""
    db = str(Path(tmpdir) / "kanban.db")
    con = sqlite3.connect(db)
    con.execute(
        "CREATE TABLE tasks ("
        " id TEXT PRIMARY KEY, title TEXT, body TEXT, status TEXT,"
        " assignee TEXT, created_by TEXT, created_at INTEGER)"
    )
    return db


def _insert(con, tid, title, body, status):
    con.execute(
        "INSERT INTO tasks (id, title, body, status, assignee, created_by, created_at) VALUES (?,?,?,?,?,?,?)",
        (tid, title, body, status, "kensho-revenue-worker", "kensho-non-api-revenue-hunter", 1),
    )


# ---------------------------------------------------------------------------
# 要件3: HN item_id 抽出と全ステータス dedup (kanban_norm)
# ---------------------------------------------------------------------------


class TestHnItemIdDedup:
    def test_extract_from_hn_url(self):
        assert kanban_norm.extract_hn_item_id("https://news.ycombinator.com/item?id=49601208") == "49601208"

    def test_extract_from_text(self):
        text = "- 元記事HN: https://news.ycombinator.com/item?id=123\n- URL: https://example.com"
        assert kanban_norm.extract_hn_item_id(text) == "123"

    def test_extract_missing(self):
        assert kanban_norm.extract_hn_item_id("https://example.com/nope") == ""
        assert kanban_norm.extract_hn_item_id("") == ""
        assert kanban_norm.extract_hn_item_id(None) == ""

    def test_is_duplicate_hn_id_finds_done_task(self):
        """done/archived 済み案件の hn_id も重複として検出する (v58 要件3)."""
        with tempfile.TemporaryDirectory() as td:
            db = _make_db(td)
            con = sqlite3.connect(db)
            _insert(
                con,
                "t_done0001",
                "[非API自動収益] アプリ/ツール: Show HN: Possess, a TUI",
                "- 元記事HN: https://news.ycombinator.com/item?id=49601208\n",
                "done",
            )
            _insert(
                con,
                "t_arch0002",
                "[非API自動収益] アプリ/ツール: Show HN: Archived thing",
                "- 元記事HN: https://news.ycombinator.com/item?id=999\n",
                "archived",
            )
            con.commit()
            con.close()

            dup, tid = kanban_norm.is_duplicate_hn_id("49601208", db_path=db)
            assert dup is True
            assert tid == "t_done0001"

            dup, tid = kanban_norm.is_duplicate_hn_id("999", db_path=db)
            assert dup is True and tid == "t_arch0002"

            dup, tid = kanban_norm.is_duplicate_hn_id("777", db_path=db)
            assert dup is False and tid == ""

    def test_is_duplicate_hn_id_empty_id(self):
        assert kanban_norm.is_duplicate_hn_id("") == (False, "")

    def test_fetch_existing_hn_ids_missing_db(self):
        assert kanban_norm.fetch_existing_hn_ids(db_path="/nonexistent/kanban.db") == {}


# ---------------------------------------------------------------------------
# 要件1: score / monetization ゲート
# ---------------------------------------------------------------------------


class TestQualityGate:
    def _item(self, score=10, text="a paid SaaS with API and pricing", title="Show HN: Thing"):
        return {"title": title, "text": text, "score": score}

    def test_low_score_skipped(self):
        gate = hunter.quality_gate(self._item(score=2), created_count=0)
        assert gate is not None
        assert gate[0] == "score_low"
        assert "score=2" in gate[1]

    def test_score_boundary_passes(self):
        """score == MIN_HN_SCORE (3) は通過 (要件は score<3 のスキップ)."""
        assert hunter.quality_gate(self._item(score=3), created_count=0) is None

    def test_no_monetization_signal_skipped(self):
        item = self._item(score=50, text="a fun browser game, free and open source, no account needed")
        gate = hunter.quality_gate(item, created_count=0)
        assert gate is not None
        assert gate[0] == "no_monetization"

    def test_monetization_signals_detected(self):
        for text in [
            "now with paid tiers and subscription billing",
            "dataset available for sale, API access included",
            "販売開始、月額サブスクです",
            "monetized via affiliate links",
        ]:
            assert hunter.has_monetization_signal({"title": "", "text": text}), text

    def test_cap_reached(self):
        gate = hunter.quality_gate(self._item(), created_count=hunter.MAX_KANBAN_PER_RUN)
        assert gate is not None
        assert gate[0] == "cap_reached"

    def test_cap_constant_is_3(self):
        assert hunter.MAX_KANBAN_PER_RUN == 3
        assert hunter.MIN_HN_SCORE == 3


# ---------------------------------------------------------------------------
# 要件3 (hunter 側): create_kanban_task の hnid-skip
# ---------------------------------------------------------------------------


class TestCreateKanbanTaskHnidSkip:
    def test_hnid_skip_before_title_dedup(self, monkeypatch):
        calls = {"hn": 0, "title": 0}

        def fake_hn(hn_id, **kw):
            calls["hn"] += 1
            return True, "t_existing"

        def fake_title(title, **kw):
            calls["title"] += 1
            return False, ""

        monkeypatch.setattr(hunter, "_is_duplicate_hn_id", fake_hn)
        monkeypatch.setattr(hunter, "_kanban_is_duplicate", fake_title)
        tid, status = hunter.create_kanban_task(
            "[非API自動収益] アプリ/ツール: Show HN: New thing",
            "body",
            "高",
            url="https://example.com",
            hn_id="49601208",
        )
        assert tid is None
        assert "(hnid-skip)" in status
        assert "t_existing" in status
        assert calls["hn"] == 1
        # hnid-skip で確定したので title dedup には行かない
        assert calls["title"] == 0

    def test_hnid_extracted_from_body_when_not_passed(self, monkeypatch):
        seen = {}

        def fake_hn(hn_id, **kw):
            seen["hn_id"] = hn_id
            return True, "t_from_body"

        monkeypatch.setattr(hunter, "_is_duplicate_hn_id", fake_hn)
        body = "- 元記事HN: https://news.ycombinator.com/item?id=4545\n"
        tid, status = hunter.create_kanban_task("title", body, "高", url="https://example.com")
        assert seen["hn_id"] == "4545"
        assert tid is None and "(hnid-skip)" in status

    def test_hn_dedup_error_falls_through_to_title_dedup(self, monkeypatch):
        def boom(hn_id, **kw):
            raise sqlite3.OperationalError("db locked")

        monkeypatch.setattr(hunter, "_is_duplicate_hn_id", boom)
        monkeypatch.setattr(hunter, "_kanban_is_duplicate", lambda t, **kw: (True, "t_title_dup"))
        tid, status = hunter.create_kanban_task("t", "body", "高", url="https://news.ycombinator.com/item?id=111")
        assert tid is None and "(dedup-skip)" in status

    def test_weight_low_still_skipped_first(self, monkeypatch):
        def never(*a, **k):  # pragma: no cover
            raise AssertionError("must not be called")

        monkeypatch.setattr(hunter, "_is_duplicate_hn_id", never)
        tid, status = hunter.create_kanban_task("t", "b", "低")
        assert tid is None and "見送り" in status


# ---------------------------------------------------------------------------
# メインループ統合: ゲート通過は最大3件、score<3 は0件
# ---------------------------------------------------------------------------


class TestMainLoopIntegration:
    def _seed(self, n_high=10, score=5, monetized=True):
        src = {"name": "HN", "weight": "高", "url": "x", "kind": "hn_ids", "limit": 1, "rationale": ""}
        seeds = []
        for i in range(n_high):
            item = {
                "title": f"Show HN: Product {i}",
                "url": f"https://example.com/{i}",
                "hn_url": f"https://news.ycombinator.com/item?id={1000 + i}",
                "score": score,
                "comments": 0,
                "text": "paid API with pricing tiers" if monetized else "totally free hobby project",
            }
            matches = [{"category": "アプリ/ツール", "weight": "高", "has_automation_keyword": True}]
            seeds.append((src, item, matches))
        return seeds

    def test_cap_three_creates(self, monkeypatch):
        created = []

        monkeypatch.setattr(hunter, "SOURCES", [])
        monkeypatch.setattr(hunter, "classify_seed", _hi_matches)

        # fetch 系を差し替えて1ソースから10件返す
        def fake_fetch_hn_list(url, limit):
            return [dict(s[1]) for s in self._seed(10)]

        monkeypatch.setattr(hunter, "fetch_hn_list", fake_fetch_hn_list)
        monkeypatch.setattr(
            hunter,
            "SOURCES",
            [{"name": "HN", "url": "u", "kind": "hn_ids", "limit": 30, "weight": "高", "rationale": "r"}],
        )
        monkeypatch.setattr(hunter, "_is_duplicate_hn_id", lambda hid, **k: (False, ""))
        monkeypatch.setattr(hunter, "_kanban_is_duplicate", lambda t, **k: (False, ""))

        def fake_run(cmd, **kw):
            class R:
                returncode = 0
                stdout = "created t_new00001"
                stderr = ""

            created.append(cmd)
            return R()

        monkeypatch.setattr(hunter.subprocess, "run", fake_run)
        # OUT_DIR 書き出しを一時ディレクトリへ
        with tempfile.TemporaryDirectory() as td:
            monkeypatch.setattr(hunter, "OUT_DIR", Path(td))
            rc = hunter.main()
        assert rc == 0
        # 新規作成は最大3件
        assert len(created) <= hunter.MAX_KANBAN_PER_RUN

    def test_low_score_never_created(self, monkeypatch):
        created = []
        seeds = self._seed(10, score=2)

        monkeypatch.setattr(
            hunter,
            "SOURCES",
            [{"name": "HN", "url": "u", "kind": "hn_ids", "limit": 30, "weight": "高", "rationale": "r"}],
        )
        monkeypatch.setattr(hunter, "fetch_hn_list", lambda url, limit: [dict(s[1]) for s in seeds])
        monkeypatch.setattr(hunter, "classify_seed", _hi_matches)
        monkeypatch.setattr(hunter, "_is_duplicate_hn_id", lambda hid, **k: (False, ""))
        monkeypatch.setattr(hunter, "_kanban_is_duplicate", lambda t, **k: (False, ""))

        def fake_run(cmd, **kw):
            class R:
                returncode = 0
                stdout = "created t_new00002"
                stderr = ""

            created.append(cmd)
            return R()

        monkeypatch.setattr(hunter.subprocess, "run", fake_run)
        with tempfile.TemporaryDirectory() as td:
            monkeypatch.setattr(hunter, "OUT_DIR", Path(td))
            hunter.main()
        assert created == []

    def test_no_monetization_never_created(self, monkeypatch):
        created = []
        seeds = self._seed(10, score=50, monetized=False)

        monkeypatch.setattr(
            hunter,
            "SOURCES",
            [{"name": "HN", "url": "u", "kind": "hn_ids", "limit": 30, "weight": "高", "rationale": "r"}],
        )
        monkeypatch.setattr(hunter, "fetch_hn_list", lambda url, limit: [dict(s[1]) for s in seeds])
        monkeypatch.setattr(hunter, "classify_seed", _hi_matches)
        monkeypatch.setattr(hunter, "_is_duplicate_hn_id", lambda hid, **k: (False, ""))
        monkeypatch.setattr(hunter, "_kanban_is_duplicate", lambda t, **k: (False, ""))

        def fake_run(cmd, **kw):
            class R:
                returncode = 0
                stdout = "created t_new00003"
                stderr = ""

            created.append(cmd)
            return R()

        monkeypatch.setattr(hunter.subprocess, "run", fake_run)
        with tempfile.TemporaryDirectory() as td:
            monkeypatch.setattr(hunter, "OUT_DIR", Path(td))
            hunter.main()
        assert created == []
