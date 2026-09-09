"""v71 実測シナリオ回帰: 導入時シーディング済みstateで複数ソース同時検知・dupes=0。

2026-09-09 16:00収集で実測した状況（knshow=17, twscrape=247, chance.com=19 の
連続0件）を再現し、
  - 3ソースが同時に [DEAD-SOURCE] 検知されること（ever_positive問わず）
  - kanban投入はソース別1回ずつ（同一エピソード2回目収集で追加投入0）
  - 投入失敗（rc=126系）時は alerted=False のまま次回収集で再試行すること
を検証する（critic v71 task t_51542f18）。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from kensho.scraping.dead_source_sentinel import STATE_FILENAME, check_dead_sources


def _seeded_state(tmp_path: Path) -> Path:
    p = tmp_path / STATE_FILENAME
    p.write_text(
        json.dumps({
            "sources": {
                "knshow": {"zero_streak": 17, "ever_positive": True, "alerted": False},
                "ken-kaku": {"zero_streak": 0, "ever_positive": True, "alerted": False},
                "kenshou.club": {"zero_streak": 0, "ever_positive": True, "alerted": False},
                "cp.meikan": {"zero_streak": 0, "ever_positive": True, "alerted": False},
                "ke-ma": {"zero_streak": 0, "ever_positive": True, "alerted": False},
                "twscrape": {"zero_streak": 247, "ever_positive": False, "alerted": False},
                "chance.com": {"zero_streak": 19, "ever_positive": True, "alerted": False},
                "kensho-everyday": {"zero_streak": 0, "ever_positive": True, "alerted": False},
            },
            "fixupx_streak": 0,
            "fixupx_alerted": False,
            "created_tasks": {},
            "last_run": "",
        }),
        encoding="utf-8",
    )
    return p


_BY_SRC: dict[str, int] = {
    "knshow": 0,
    "ken-kaku": 5,
    "kenshou.club": 30,
    "cp.meikan": 10,
    "ke-ma": 3,
    "twscrape": 0,
    "chance.com": 0,
    "kensho-everyday": 2,
}


class _Recorder:
    def __init__(self, ok: bool = True) -> None:
        self.ok = ok
        self.calls: list[tuple[str, str]] = []

    def __call__(self, title: str, body: str, idem: str) -> tuple[bool, str]:
        self.calls.append((title, idem))
        return self.ok, "t_fake" if self.ok else "rc=126 bad interpreter"


def _run(tmp_path: Path, rec: Any) -> list[str]:
    return check_dead_sources(
        by_source=dict(_BY_SRC),
        fixupx_errors=0,
        fixupx_fetched=8,
        data_dir=tmp_path,
        out=lambda m: None,
        kanban_create=rec,
    )


def test_three_dead_sources_alert_once_each(tmp_path: Path) -> None:
    _seeded_state(tmp_path)
    rec = _Recorder()
    alerts = _run(tmp_path, rec)
    dead = [a for a in alerts if "[DEAD-SOURCE]" in a]
    assert len(dead) == 3
    joined = "\n".join(dead)
    assert "knshow" in joined and "twscrape" in joined and "chance.com" in joined
    # twscrapeは導入以来0件 → 特別文言
    tw = next(a for a in dead if "twscrape" in a)
    assert "導入以来一度も成果なし" in tw
    assert len(rec.calls) == 3
    assert sorted(idem for _, idem in rec.calls) == [
        "dead-src-chance.com",
        "dead-src-knshow",
        "dead-src-twscrape",
    ]


def test_same_episode_second_run_no_dupes(tmp_path: Path) -> None:
    _seeded_state(tmp_path)
    rec = _Recorder()
    _run(tmp_path, rec)
    rec.calls.clear()
    alerts2 = _run(tmp_path, rec)
    assert alerts2 == []  # alerted=True で同一エピソード内は再通知なし
    assert rec.calls == []


def test_kanban_failure_retries_next_collect(tmp_path: Path) -> None:
    _seeded_state(tmp_path)
    rec_fail = _Recorder(ok=False)
    alerts1 = _run(tmp_path, rec_fail)
    assert len([a for a in alerts1 if "[DEAD-SOURCE]" in a and "kanban投入" not in a]) == 3
    # 投入失敗 → alerted=False のまま（state確認）
    state = json.loads((tmp_path / STATE_FILENAME).read_text(encoding="utf-8"))
    assert state["sources"]["knshow"]["alerted"] is False
    assert state["sources"]["twscrape"]["alerted"] is False
    # 次回収集で再試行され、成功以後は抑止される
    rec_ok = _Recorder(ok=True)
    _run(tmp_path, rec_ok)
    assert len(rec_ok.calls) == 3
    rec_third = _Recorder(ok=True)
    _run(tmp_path, rec_third)
    assert rec_third.calls == []
