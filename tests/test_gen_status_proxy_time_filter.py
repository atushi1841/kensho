"""t_e2b356ce: PROXY-CHECK 行の時系列フィルタ — 生成時刻以降の最新 PROXY-CHECK のみ採用。

旧実装は当日ログの「最後の PROXY-CHECK 行」を採用していた。PROXY-CHECK 行自体に
タイムスタンプがないため、前 tick の spawn 時刻に完了した PROXY-CHECK（死骸）が
生成時刻以降の最新 PROXY-CHECK より後ろに並んでいた場合、その死骸を status に
反映するバグ（1 tick 延命で dead_proxy が書かれた）が起きた。

このテストは gen_status_data.py からフィルタ関数（_filter_proxy_check_rows）だけを
AST で取り出して検証する。`import scripts.gen_status_data` はモジュール本体（＝生成
パイプライン）を実行してしまい、`/tmp/kensho_status_data.json` と `data/status/*.json`
を**テストプロセスが書き換える**（実測 2026-09-25 06:49: pytest 実行で本番パネルの
proxy.ts が空に上書きされた）。よって取り出しは副作用の無い load_filter() を使う。
"""
from __future__ import annotations

import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.verify_status_proxy_same_tick import load_filter  # type: ignore

_filter_proxy_check_rows = load_filter()


def test_adopts_latest_row_after_gen_start() -> None:
    """生成時刻以降に完了した最新 PROXY-CHECK を採用する。"""
    gen = datetime(2026, 9, 25, 4, 30, 0)
    txt = (
        "[2026-09-25 04:30:02] 対象垢: atushi16 kudou zin20120731 TankanNotes\n"
        "[2026-09-25 04:30:03] 今回 spawn: 4 垢（即終了：処理本体は各垢が並列で実行）\n"
        "Proxy atushi16:1081 is LISTENING but has NO egress – forcing WiFi reconnect + restart\n"
        "Proxy zin20120731:1084 is dead\n"
        "WiFi reconnect failed – adapter zin_AW6povo still 'Disconnected'\n"
        "[PROXY-CHECK] alive=[1082, 1085] dead=[1081, 1084] restored=1 (33.9s)\n"
    )
    row_ts, alive, dead, restored, ts = _filter_proxy_check_rows(txt, gen, None)
    assert alive == [1082, 1085]
    assert dead == [1081, 1084]
    assert restored == 1
    assert ts == datetime(2026, 9, 25, 4, 30, 3)
    assert row_ts == datetime(2026, 9, 25, 4, 30, 3)


def test_skips_row_before_gen_start() -> None:
    """生成時刻以前に完了した PROXY-CHECK（前 tick の死骸）はスキップする。"""
    gen = datetime(2026, 9, 25, 4, 30, 0)
    txt = (
        "[2026-09-25 04:15:01] 今回 spawn: 4 垢（即終了：処理本体は各垢が並列で実行）\n"
        "Proxy zin20120731:1084 is dead\n"
        "WiFi reconnect failed – adapter zin_AW6povo still 'Disconnected'\n"
        "[PROXY-CHECK] alive=[1081, 1082, 1085] dead=[1084] restored=0 (16.2s)\n"
    )
    row_ts, alive, dead, restored, ts = _filter_proxy_check_rows(txt, gen, None)
    assert alive == []
    assert dead == []
    assert restored == 0
    assert ts is None
    assert row_ts is None


def test_picks_latest_among_multiple_after_gen_start() -> None:
    """同一 tick 内に複数 PROXY-CHECK 行がある場合、最新の ones を採用する。"""
    gen = datetime(2026, 9, 25, 4, 30, 0)
    txt = (
        "[2026-09-25 04:30:02] 今回 spawn: 4 垢\n"
        "[PROXY-CHECK] alive=[1081, 1082, 1085] dead=[1084] restored=0 (16.2s)\n"
        "[PROXY-CHECK] alive=[1082, 1085] dead=[1081, 1084] restored=1 (33.9s)\n"
    )
    row_ts, alive, dead, restored, ts = _filter_proxy_check_rows(txt, gen, None)
    assert alive == [1082, 1085]
    assert dead == [1081, 1084]
    assert restored == 1
    assert ts == datetime(2026, 9, 25, 4, 30, 2)
    assert row_ts == datetime(2026, 9, 25, 4, 30, 2)


def test_no_timestamp_before_proxy_check_is_skipped() -> None:
    """PROXY-CHECK 行の直前に spawn 行がない場合は時刻不明 → スキップ（安全側）。"""
    gen = datetime(2026, 9, 25, 4, 30, 0)
    txt = "[PROXY-CHECK] alive=[1081] dead=[1084] restored=0 (10.0s)\n"
    row_ts, alive, dead, restored, ts = _filter_proxy_check_rows(txt, gen, None)
    assert alive == []
    assert dead == []
    assert restored == 0
    assert ts is None
    assert row_ts is None


def test_wait_timeout_covers_measured_max_proxy_check_duration() -> None:
    """generate-status.sh の WAIT_TIMEOUT が実測最大の PROXY-CHECK 所要を上回っていること。

    実測（2026-09-20〜09-25 の6日分）: 最大 69.5s（9/24）、9/25 は 57.2s。
    ポーリング間隔は5sなので 69.5+5=74.5s 未満の値に戻すと完走行を取り逃す（=無音凍結の再発）。
    """
    src = (Path(__file__).parent.parent / "scripts" / "generate-status.sh").read_text(encoding="utf-8")
    m = re.search(r"^WAIT_TIMEOUT=(\d+)", src, re.M)
    assert m is not None, "generate-status.sh に WAIT_TIMEOUT の定義が無い"
    timeout = int(m.group(1))
    assert timeout >= 90, f"WAIT_TIMEOUT={timeout}s は実測最大69.5s+ポーリング5sに対し余裕不足"


def test_simulate_gen_waits_for_completion_and_caps_at_timeout() -> None:
    """待ちループ模擬: 完走が timeout 内なら完走+5s、超えるなら timeout で打ち切る。"""
    from scripts.verify_status_proxy_same_tick import simulate_gen  # type: ignore

    tick = datetime(2026, 9, 25, 4, 30, 0)
    assert simulate_gen(tick, 17.2, 120) == tick + timedelta(seconds=22.2)  # 完走17.2s + ポーリング5s
    assert simulate_gen(tick, 69.5, 120) == tick + timedelta(seconds=74.5)
    assert simulate_gen(tick, 200.0, 120) == tick + timedelta(seconds=120)  # 打ち切り


def test_replay_freezes_instead_of_adopting_stale_row_when_tick_exceeds_timeout() -> None:
    """timeout 超過 tick では前 tick の死骸も採用しない（＝status は前回値保持）。"""
    from scripts.verify_status_proxy_same_tick import parse_log, simulate_gen, text_at  # type: ignore

    full = (
        "[2026-09-25 04:00:01] 今回 spawn: 4 垢\n"
        "[PROXY-CHECK] alive=[1081, 1082, 1085] dead=[1084] restored=0 (16.0s)\n"
        "[2026-09-25 04:15:01] 今回 spawn: 4 垢\n"
        "[PROXY-CHECK] alive=[1082, 1085] dead=[1081, 1084] restored=1 (200.0s)\n"
    )
    rows = parse_log(full)
    assert [r[3] for r in rows] == [16.0, 200.0]
    ts, _alive, _dead, dur = rows[-1]
    gen = simulate_gen(ts, dur, 120)
    assert gen == ts + timedelta(seconds=120)
    row_ts, got_alive, got_dead, _restored, _best = _filter_proxy_check_rows(
        text_at(full, gen), gen - timedelta(minutes=2), None
    )
    assert row_ts is None, "前 tick の死骸を採用してはならない"
    assert got_alive == []
    assert got_dead == []