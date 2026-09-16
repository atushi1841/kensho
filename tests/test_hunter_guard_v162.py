"""tests/test_hunter_guard_v162.py — 発券重複防止ガード (critic v162 / t_37c0fafa) の回帰テスト.

検証対象:
  要件1: 決定的キー hunter-YYYYMMDD-<スラッグハッシュ8桁> の生成 (決定的・JST日付)
  要件2: 起票前 open カード走査 — 日英 cross-lingual 二重登録 (t_c3af4776≡t_06fdd792
         実事例) を検出し、無関係テーマを誤検知しない
  要件3: hit 時は新規作らず既存カードへコメント追記で代替
  統合:  hunter create_kanban_task がキー無し発券をしない・guard-skip で止まる
"""

import importlib.util
import sqlite3
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

import kensho_hunter_guard as guard  # noqa: E402


def _load_hunter():
    path = REPO / "kensho-non-api-revenue-hunter.py"
    spec = importlib.util.spec_from_file_location("kensho_non_api_revenue_hunter_v162", path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


hunter = _load_hunter()

JST = timezone(timedelta(hours=9))

# 実事例 (2026-09-16): 英タイトル先行カードと 和タイトル重複カード
CARD_EN_TITLE = "7th MCP: Japan property hazard risk server (MLIT flood/landslide zones by address)"
CARD_EN_BODY = (
    "Revenue opportunity auto-discovery 2026-09-16. Build an MCP/RapidAPI server: "
    "input = Japanese address or lat/lng, output = structured hazard risk (flood depth "
    "zone, landslide alert zone, earthquake liquefaction, tsunami inundation). "
    "Monetization: freemium on RapidAPI."
)
CARD_JP_TITLE = "日本物件ハザードリスクMCP プロトタイプ作成"
CARD_JP_BODY = (
    "プロトタイプMCPサーバーを作成し、住所から洪水・土砂・津波・液状化リスクを判定する。"
    "技術的可否: GSIジオコーディングAPIと災害マップAPIの存在を確認。"
    "競合: nankai-trough-mcp（地震専門）。次ステップ: ApifyまたはSmitheryで公開。"
)


def _make_db(tmpdir: str) -> str:
    db = str(Path(tmpdir) / "kanban.db")
    con = sqlite3.connect(db)
    con.execute(
        "CREATE TABLE tasks ("
        " id TEXT PRIMARY KEY, title TEXT, body TEXT, status TEXT,"
        " assignee TEXT, created_by TEXT, created_at INTEGER,"
        " idempotency_key TEXT)"
    )
    return db


def _insert(con, tid, title, body, status="ready"):
    con.execute(
        "INSERT INTO tasks (id, title, body, status, assignee, created_by, created_at) VALUES (?,?,?,?,?,?,?)",
        (tid, title, body, status, "kensho-worker", "worker", 1),
    )


# ---------------------------------------------------------------------------
# 要件1: 決定的キー
# ---------------------------------------------------------------------------


class TestHunterIdempotencyKey:
    def test_format(self):
        k = guard.hunter_idempotency_key(CARD_JP_TITLE, when=datetime(2026, 9, 16, 10, 0, tzinfo=JST))
        assert k.startswith("hunter-20260916-")
        assert len(k.rsplit("-", 1)[1]) == 8
        int(k.rsplit("-", 1)[1], 16)  # hex であること

    def test_deterministic_across_notation_noise(self):
        a = guard.hunter_idempotency_key("Hazard Risk  MCP!!")
        b = guard.hunter_idempotency_key("hazard risk mcp")
        assert a == b

    def test_different_themes_different_keys(self):
        a = guard.hunter_idempotency_key("hazard risk mcp")
        b = guard.hunter_idempotency_key("fuel price mcp")
        assert a.rsplit("-", 1)[1] != b.rsplit("-", 1)[1]

    def test_hunter_create_uses_hunter_key(self, monkeypatch):
        """create_kanban_task が hunter-YYYYMMDD-<8hex> キーを付与して発券する。"""
        seen = {}

        def fake_run(cmd, **kw):
            seen["cmd"] = cmd

            class R:
                returncode = 0
                stdout = "created t_newkey01"
                stderr = ""

            return R()

        monkeypatch.setattr(hunter.subprocess, "run", fake_run)
        monkeypatch.setattr(hunter, "_is_duplicate_hn_id", lambda hid, **k: (False, ""))
        monkeypatch.setattr(hunter, "_kanban_is_duplicate", lambda t, **k: (False, ""))
        monkeypatch.setattr(hunter, "_hunter_guard_scan", lambda t, b: [])
        tid, status = hunter.create_kanban_task(
            "[非API自動収益] アプリ/ツール: Show HN: Widget", "body", "高", url="https://example.com/widget"
        )
        assert status == "ok"
        cmd = seen["cmd"]
        key = cmd[cmd.index("--idempotency-key") + 1]
        assert key.startswith(f"hunter-{datetime.now(JST).strftime('%Y%m%d')}-")


# ---------------------------------------------------------------------------
# 要件2: open カード走査
# ---------------------------------------------------------------------------


class TestOpenScan:
    def test_cross_lingual_dup_detected(self):
        """実事例再現: 英語 open カードがある状態で和文起票 → Hit."""
        with tempfile.TemporaryDirectory() as td:
            db = _make_db(td)
            con = sqlite3.connect(db)
            _insert(con, "t_en000001", CARD_EN_TITLE, CARD_EN_BODY, status="running")
            con.commit()
            con.close()
            hits = guard.find_open_duplicates(CARD_JP_TITLE, CARD_JP_BODY, db_path=db)
            assert hits
            assert hits[0][0] == "t_en000001"
            shared = hits[0][1]
            assert any("bridge:" in s for s in shared)

    def test_unrelated_theme_not_flagged(self):
        """語域が違うのみ (mcp 共有) では起票を止めない。"""
        with tempfile.TemporaryDirectory() as td:
            db = _make_db(td)
            con = sqlite3.connect(db)
            _insert(con, "t_en000001", CARD_EN_TITLE, CARD_EN_BODY)
            _insert(
                con,
                "t_boiler1",
                "[非API自動収益] アプリ/ツール: Show HN: Triplox, a distributed Datalog engine",
                "HNボイラープレート本文 自動検出 実装可能",
                status="todo",
            )
            con.commit()
            con.close()
            hits = guard.find_open_duplicates(
                "Fuel price alert bot",
                "Monitor Japanese gasoline prices hourly and alert via LINE webhook.",
                db_path=db,
            )
            assert hits == []

    def test_closed_statuses_ignored(self):
        """done/archived カードは open 走査では無視 (別経路の全ステータス dedup が担う)。"""
        with tempfile.TemporaryDirectory() as td:
            db = _make_db(td)
            con = sqlite3.connect(db)
            _insert(con, "t_done001", CARD_EN_TITLE, CARD_EN_BODY, status="archived")
            _insert(con, "t_done002", CARD_EN_TITLE, CARD_EN_BODY, status="done")
            con.commit()
            con.close()
            assert guard.find_open_duplicates(CARD_JP_TITLE, CARD_JP_BODY, db_path=db) == []

    def test_boilerplate_df_filter(self):
        """open カード過半数が共有するテンプレ語のみの重複はスコアに寄与しない。"""
        with tempfile.TemporaryDirectory() as td:
            db = _make_db(td)
            con = sqlite3.connect(db)
            for i in range(6):
                _insert(
                    con,
                    f"t_tpl{i:06d}",
                    f"Show HN: Template item {i} with widgetry plumbing",
                    "定番テンプレ: apify rapidapi scraper monetization pipeline",
                )
            con.commit()
            con.close()
            hits = guard.find_open_duplicates(
                "Show HN: Another widgetry plumbing entry 99",
                "定番テンプレ: apify rapidapi scraper monetization pipeline",
                db_path=db,
            )
            assert hits == []

    def test_missing_db_returns_empty(self):
        assert guard.find_open_duplicates("anything", "", db_path="/nonexistent/kanban.db") == []


# ---------------------------------------------------------------------------
# 要件3: コメント代替
# ---------------------------------------------------------------------------


class TestCommentAlternative:
    def test_dry_run_makes_no_calls(self, monkeypatch):
        called = []
        monkeypatch.setattr(guard.subprocess, "run", lambda *a, **k: called.append(a))
        assert guard.comment_instead_of_create("t_x0000001", "新テーマ", dry_run=True) is True
        assert called == []

    def test_uses_comment_verb(self, monkeypatch):
        seen = {}

        def fake_run(cmd, **kw):
            seen["cmd"] = cmd

            class R:
                returncode = 0
                stdout = "ok"
                stderr = ""

            return R()

        monkeypatch.setattr(guard.subprocess, "run", fake_run)
        assert guard.comment_instead_of_create("t_x0000002", "新テーマ") is True
        cmd = " ".join(seen["cmd"])
        assert "comment" in cmd and "t_x0000002" in cmd

    def test_failure_is_swallowed(self, monkeypatch):
        def boom(*a, **k):
            raise FileNotFoundError("hermes missing")

        monkeypatch.setattr(guard.subprocess, "run", boom)
        assert guard.comment_instead_of_create("t_x0000003", "テーマ") is False


# ---------------------------------------------------------------------------
# hunter 統合: guard hit → guard-skip (作らない・コメントする)
# ---------------------------------------------------------------------------


class TestHunterGuardIntegration:
    def test_guard_skip_blocks_create(self, monkeypatch):
        calls = {"run": 0, "comment": None}

        def fake_run(cmd, **kw):
            calls["run"] += 1

            class R:
                returncode = 0
                stdout = "created t_bad"
                stderr = ""

            return R()

        monkeypatch.setattr(hunter.subprocess, "run", fake_run)
        monkeypatch.setattr(hunter, "_is_duplicate_hn_id", lambda hid, **k: (False, ""))
        monkeypatch.setattr(hunter, "_kanban_is_duplicate", lambda t, **k: (False, ""))
        monkeypatch.setattr(
            hunter, "_hunter_guard_scan", lambda t, b: [("t_en000001", ["bridge:ハザード", "bridge:リスク"])]
        )
        monkeypatch.setattr(
            hunter, "_hunter_guard_comment", lambda tid, title, shared: calls.__setitem__("comment", tid) or True
        )

        tid, status = hunter.create_kanban_task(CARD_JP_TITLE, CARD_JP_BODY, "高", url="https://example.com/hazard")
        assert tid is None
        assert "(guard-skip)" in status
        assert "t_en000001" in status
        assert calls["run"] == 0  # kanban create は一度も呼ばれない
        assert calls["comment"] == "t_en000001"

    def test_scan_error_does_not_block_create(self, monkeypatch):
        """guard 走査が DB 障害で [] に化けた場合は発券を継続する (fail-open)。"""
        seen = {}

        def fake_run(cmd, **kw):
            seen["cmd"] = cmd

            class R:
                returncode = 0
                stdout = "created t_fallbk01"
                stderr = ""

            return R()

        monkeypatch.setattr(hunter.subprocess, "run", fake_run)
        monkeypatch.setattr(hunter, "_is_duplicate_hn_id", lambda hid, **k: (False, ""))
        monkeypatch.setattr(hunter, "_kanban_is_duplicate", lambda t, **k: (False, ""))
        monkeypatch.setattr(hunter, "_hunter_guard_scan", lambda t, b: [])
        tid, status = hunter.create_kanban_task(
            "Show HN: Safe fallthrough", "body", "高", url="https://example.com/safe"
        )
        assert status == "ok"
        key = seen["cmd"][seen["cmd"].index("--idempotency-key") + 1]
        assert key.startswith("hunter-")

    def test_guard_internal_exception_swallowed(self, monkeypatch):
        """_guard が例外を投げても _hunter_guard_scan は [] を返し発券を止めない。"""

        class BadGuard:
            @staticmethod
            def find_open_duplicates(*a, **k):
                raise RuntimeError("db exploded")

            @staticmethod
            def hunter_idempotency_key(title, extra=""):
                return "hunter-20260916-deadbeef"

        monkeypatch.setattr(hunter, "_guard", BadGuard)
        assert hunter._hunter_guard_scan("t", "b") == []


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


class TestCli:
    def test_check_hit_exit1(self, tmp_path):
        db = _make_db(str(tmp_path))
        con = sqlite3.connect(db)
        _insert(con, "t_en000001", CARD_EN_TITLE, CARD_EN_BODY, status="running")
        con.commit()
        con.close()
        rc = guard.main(["check", "--title", CARD_JP_TITLE, "--body", CARD_JP_BODY, "--db", db])
        assert rc == 1

    def test_check_unique_exit0(self, tmp_path):
        db = _make_db(str(tmp_path))
        con = sqlite3.connect(db)
        _insert(con, "t_en000001", CARD_EN_TITLE, CARD_EN_BODY)
        con.commit()
        con.close()
        rc = guard.main([
            "check",
            "--title",
            "Fuel price alert bot",
            "--body",
            "Monitor gasoline prices and send LINE alerts.",
            "--db",
            db,
        ])
        assert rc == 0
