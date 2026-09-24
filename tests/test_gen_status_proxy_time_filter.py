"""t_e2b356ce: PROXY-CHECK 行の時系列フィルタ — 生成時刻以降の最新 PROXY-CHECK のみ採用。

旧実装は当日ログの「最後の PROXY-CHECK 行」を採用していた。PROXY-CHECK 行自体に
タイムスタンプがないため、前 tick の spawn 時刻に完了した PROXY-CHECK（死骸）が
生成時刻以降の最新 PROXY-CHECK より後ろに並んでいた場合、その死骸を status に
反映するバグ（1 tick 延命で dead_proxy が書かれた）が起きた。

このテストは gen_status_data.py の抽出ロジックを直接 import して検証する。
フィルタ関数はモジュール内に _filter_proxy_check_rows として実装する。
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.gen_status_data import _filter_proxy_check_rows  # type: ignore


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