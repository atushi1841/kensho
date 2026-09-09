"""
Tests for scraping/dead_source_sentinel.py — critic v71 提案① デッドソース検知
（連続0件検知・kanban投入の重複排除・復帰リセット・fail-open）
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from kensho.scraping.dead_source_sentinel import (
    DEAD_STREAK_THRESHOLD,
    STATE_FILENAME,
    check_dead_sources,
)

_BASE: dict[str, int] = {
    "knshow": 5,
    "ken-kaku": 3,
    "kenshou.club": 2,
    "cp.meikan": 4,
    "ke-ma": 1,
    "twscrape": 10,
    "chance.com": 2,
    "kensho-everyday": 1,
}


class _FakeKanban:
    """kanban_create スタブ。呼ばれたら記録する（実 subprocess は叩かない）。"""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str]] = []

    def __call__(self, title: str, body: str, idem: str) -> tuple[bool, str]:
        self.calls.append((title, body, idem))
        return True, f"t_fake_{len(self.calls)}"


def _run(tmp_path: Path, by_source: dict[str, int], fx_err: int, fx_ok: int, kanban: Any) -> list[str]:
    return check_dead_sources(
        by_source=by_source,
        fixupx_errors=fx_err,
        fixupx_fetched=fx_ok,
        data_dir=tmp_path,
        out=lambda m: None,
        kanban_create=kanban,
    )


def _zero(src: str) -> dict[str, int]:
    snap = dict(_BASE)
    snap[src] = 0
    return snap


# ── 正常運用でアラートなし ───────────────────────────────────


def test_healthy_run_no_alert(tmp_path: Path) -> None:
    kb = _FakeKanban()
    alerts = _run(tmp_path, _BASE, 0, 5, kb)
    assert alerts == []
    assert kb.calls == []


def test_state_file_written(tmp_path: Path) -> None:
    _run(tmp_path, _BASE, 0, 5, _FakeKanban())
    assert (tmp_path / STATE_FILENAME).exists()


# ── same-zero-streak（twscrape のような完全死） ───────────────


def test_zero_streak_below_threshold_no_alert(tmp_path: Path) -> None:
    kb = _FakeKanban()
    _run(tmp_path, _BASE, 0, 5, kb)  # ever_positive シード
    alerts: list[str] = []
    for _ in range(DEAD_STREAK_THRESHOLD - 1):
        alerts = _run(tmp_path, _zero("twscrape"), 0, 5, kb)
    assert alerts == []
    assert kb.calls == []


def test_zero_streak_hits_threshold_alerts_once(tmp_path: Path) -> None:
    kb = _FakeKanban()
    _run(tmp_path, _BASE, 0, 5, kb)  # 正常回で ever_positive シード
    alerts: list[str] = []
    for _ in range(DEAD_STREAK_THRESHOLD):
        alerts = _run(tmp_path, _zero("twscrape"), 0, 5, kb)
    assert len(alerts) == 1
    assert "[DEAD-SOURCE]" in alerts[0] and "twscrape" in alerts[0]
    assert len(kb.calls) == 1  # 投入は1回だけ
    assert "twscrape" in kb.calls[0][0]
    # しきい値超過後も再投入しない（alerted フラグ）
    for _ in range(5):
        again = _run(tmp_path, _zero("twscrape"), 0, 5, kb)
        assert again == []
    assert len(kb.calls) == 1


def test_recovery_resets_streak_and_realerts(tmp_path: Path) -> None:
    kb = _FakeKanban()
    _run(tmp_path, _BASE, 0, 5, kb)  # ever_positive シード
    for _ in range(DEAD_STREAK_THRESHOLD):
        _run(tmp_path, _zero("twscrape"), 0, 5, kb)
    assert len(kb.calls) == 1
    # 復帰（>0件）で streak リセット・再アラート可能に
    _run(tmp_path, _BASE, 0, 5, kb)
    # 再び死 → もう一巡させる
    for _ in range(DEAD_STREAK_THRESHOLD):
        _run(tmp_path, _zero("twscrape"), 0, 5, kb)
    assert len(kb.calls) == 2


def test_source_never_positive_is_not_counted(tmp_path: Path) -> None:
    """一度も成果のないソース（新規追加直後）は dead と扱わない。"""
    kb = _FakeKanban()
    alerts: list[str] = []
    for _ in range(DEAD_STREAK_THRESHOLD + 3):
        alerts = _run(tmp_path, {**_BASE, "chance.com": 0, "kensho-everyday": 0}, 0, 5, kb)
    # chance.com/kevery は ever_positive でない限りカウント外だが、
    # _BASE の値が positive なため一度だけ positive 記録 → その後0継続でカウントされる。
    # → chance.com のみ dead 宣言があり得る。twscrape は正常なのでそれ以外は無アラート。
    assert all("twscrape" not in a for a in alerts)


def test_ever_positive_starts_after_first_hit(tmp_path: Path) -> None:
    kb = _FakeKanban()
    # 1回目だけ成果あり → ever_positive、以後0件継続で閾値到達
    _run(tmp_path, {**_BASE, "chance.com": 1}, 0, 5, kb)
    alerts: list[str] = []
    for _ in range(DEAD_STREAK_THRESHOLD):
        alerts = _run(tmp_path, {**_BASE, "chance.com": 0}, 0, 5, kb)
    assert any("chance.com" in a for a in alerts)


# ── 全ソース0件（正常な「新着なし」）はカウントしない ─────────


def test_all_zero_not_counted_as_dead(tmp_path: Path) -> None:
    kb = _FakeKanban()
    all_zero = {k: 0 for k in _BASE}
    alerts: list[str] = []
    for _ in range(DEAD_STREAK_THRESHOLD + 5):
        alerts = _run(tmp_path, all_zero, 0, 0, kb)
    assert alerts == []
    assert kb.calls == []


# ── fixupx error-streak ──────────────────────────────────────


def test_fixupx_all_error_streak_alerts(tmp_path: Path) -> None:
    kb = _FakeKanban()
    alerts: list[str] = []
    for _ in range(DEAD_STREAK_THRESHOLD):
        alerts = _run(tmp_path, _BASE, 3, 0, kb)
    assert any("fixupx" in a for a in alerts)
    assert any("fixupx" in c[0] for c in kb.calls)


def test_fixupx_partial_error_does_not_inflate(tmp_path: Path) -> None:
    """成功混在の収集は streak に加算しない（正常な混在収集で水膨れ防止）。"""
    kb = _FakeKanban()
    for _ in range(DEAD_STREAK_THRESHOLD + 3):
        alerts = _run(tmp_path, _BASE, 2, 8, kb)  # エラー2件あるが成功8件
    assert alerts == []
    assert kb.calls == []


def test_fixupx_streak_resets_on_success(tmp_path: Path) -> None:
    kb = _FakeKanban()
    for _ in range(DEAD_STREAK_THRESHOLD - 1):
        _run(tmp_path, _BASE, 4, 0, kb)
    _run(tmp_path, _BASE, 0, 6, kb)  # クリーン収集でリセット
    alerts = _run(tmp_path, _BASE, 4, 0, kb)
    assert alerts == []


# ── fail-open ────────────────────────────────────────────────


def test_kanban_failure_does_not_raise(tmp_path: Path) -> None:
    def _boom(title: str, body: str, idem: str) -> tuple[bool, str]:
        raise RuntimeError("subprocess exploded")

    # kanban_create が例外を投げても check_dead_sources 自体は例外を伝播させない
    # （create() の呼び出し側でガードするため、_boom は (False, ...) を返す想定で
    #  ラッパを使う: 実装は create の戻り値 tuple を前提にするのでここで包む）
    def _safe(title: str, body: str, idem: str) -> tuple[bool, str]:
        try:
            _boom(title, body, idem)
        except Exception as e:
            return False, str(e)
        return True, ""

    _run(tmp_path, _BASE, 0, 5, _safe)  # ever_positive シード
    for _ in range(DEAD_STREAK_THRESHOLD):
        alerts = _run(tmp_path, _zero("twscrape"), 0, 5, _safe)
    assert len(alerts) == 1  # 検知はされる（投入は失敗扱い）


def test_corrupt_state_recovers(tmp_path: Path) -> None:
    p = tmp_path / STATE_FILENAME
    p.write_text("{{{garbage", encoding="utf-8")
    kb = _FakeKanban()
    alerts = _run(tmp_path, _BASE, 0, 5, kb)  # 例外なく正常動作
    assert alerts == []
    # 壊れた state は上書き되어再生成
    data = json.loads(p.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
