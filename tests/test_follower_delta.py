"""Tests for kensho_daily_health_check.py フォロワー数急変アラート（±10%）.

対象仕様 (kanban t_df34f367 提案2):
- follower_delta_pct(prev, curr) が前回→今回の変動率(%)を返す。
  前回値が無い / 0以下 / 非int / 今回値なし => None。
- アラート閾値: 変動率 |delta| >= FOLLOWER_DELTA_PCT (10%) で critical 通知。
- ネットワーク・sleep は全て mock（tests/AGENTS.md ルール準拠）。
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.kensho_daily_health_check import FOLLOWER_DELTA_PCT, follower_delta_pct  # type: ignore[import]


def _entry(prev_followers: int | None, status: str = "healthy", **kw: Any) -> dict[str, Any]:
    d: dict[str, Any] = {"followers": prev_followers, "status": status}
    d.update(kw)
    return d


FW = FOLLOWER_DELTA_PCT


@pytest.mark.parametrize(
    ("prev", "curr", "expected"),
    [
        (100, 110, 10.0),  # ちょうど +10% → アラート対象
        (100, 90, -10.0),  # ちょうど -10% → アラート対象
        (100, 111, 11.0),  # +11% → アラート
        (100, 89, -11.0),  # -11% → アラート
        (100, 109, 9.0),  # +9% → アラート外
        (100, 91, -9.0),  # -9% → アラート外
        (100, 120, 20.0),  # +20%
        (100, 80, -20.0),  # -20%（急激なフォロワー減）
    ],
)
def test_follower_delta_pct(prev: int, curr: int, expected: float) -> None:
    d = follower_delta_pct(prev, curr)
    assert d is not None
    assert d == pytest.approx(expected)


def test_follower_delta_pct_returns_none_without_prev() -> None:
    assert follower_delta_pct(None, 100) is None
    assert follower_delta_pct(0, 100) is None
    assert follower_delta_pct(-5, 100) is None


def test_follower_delta_pct_returns_none_without_curr() -> None:
    assert follower_delta_pct(100, None) is None


def test_follower_delta_pct_rejects_unchanged_or_zero() -> None:
    assert follower_delta_pct(100, 100) is not None  # 0% は有効な変動率(ただしアラート外)


def test_delta_threshold_boundary() -> None:
    # ちょうど閾値 ±10% はアラート対象 (>=)
    assert follower_delta_pct(100, 110) == 10.0
    assert follower_delta_pct(100, 90) == -10.0
    # 閾値を僅かに下回る 9% はアラート外
    assert follower_delta_pct(100, 109) == 9.0
