"""orchestrator get_pending_batches の batches=None 回帰ガード
(t_46f09dc1 / QA run487 / 2026-09-15)。

失敗史: toushiwatch垢復帰（ライブセッションGO）で垢コメントアウトは解除されたが
`batches:` 配下の全時刻行がコメント残留 → YAMLパースで batches=None →
`acct.get("schedule", {}).get("batches", [])` が None を返し for 文で
`'NoneType' object is not iterable` 致命エラー → 垢別起動の応募が完全停止、
15分cronごと再発（logs/2026-09-15/orchestrator_221515.log ×4実測）。

修正: kensho/orchestrator.py:156・orchestrator.py:92・scripts/kensho_health.py
を既存模範実装 (kensho/tools/daily_pipeline_report.py:251) と同型の
`(x.get("schedule", {}) or {}).get("batches", []) or []` に統一。
このテストは修正が消えた場合（回帰）を機械検出する。

注意: テストは時刻に依存させない。kensho版は no_action_window（既定 00:00-07:00）
とbatch時刻判定で datetime.now() を参照するため、fake clock で 10:00 に固定する
（2026-09-16 00:34 実測: 深夜実行で正常系テストが false-positive 失敗した）。
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import mock_open, patch

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
# ルート orchestrator.py は `from core.encoding ...` をトップレベルで解決する（core/ は
# kensho/ 配下）。フルスイートでは他テストの sys.path 副作用で偶然通るが、
# 単体実行でも決定的に通すため kensho/ を明示的に追加する（QA run490 申し送り③）。
# ※ append であること：REPO_ROOT より前に置于くと `import orchestrator` が
#   kensho/orchestrator.py を解決してしまいルート版のガード検証にならなくなる。
_KENSHO_DIR = str(REPO_ROOT / "kensho")
if _KENSHO_DIR not in sys.path:
    sys.path.append(_KENSHO_DIR)

# ルート orchestrator.py はモジュールレベル副作用（PIDロック等）があるため
# 安全化パッチで import（tests/test_orchestrator.py と同一手順）。
with patch("os.makedirs"), patch("builtins.open", mock_open(read_data="99999")), patch("sys.exit"):
    import orchestrator as root_orch

import kensho.orchestrator as k_orch  # noqa: E402


class _FakeDT:
    """datetime.now() を 10:00（no_action_window 外・全バッチ通過時刻）に固定。"""

    @staticmethod
    def now() -> object:
        import datetime as _d

        return _d.datetime(2026, 9, 16, 10, 0, 0)


def _at_10am():
    return (
        patch.object(k_orch, "datetime", _FakeDT),
        patch.object(root_orch, "datetime", _FakeDT),
    )


def _cfg(batches: object) -> dict:
    return {
        "accounts": [{"key": "toushiwatch", "schedule": {"batches": batches}}],
        "orchestrator": {"batch_jitter_minutes": 15},
    }


def test_kensho_batches_none_no_crash() -> None:
    """kensho/orchestrator.py: batches=None（YAMLコメント残留）で TypeError にならない。"""
    p_k, _ = _at_10am()
    with p_k:
        assert k_orch.get_pending_batches(_cfg(None), {}) == []


def test_root_batches_none_no_crash() -> None:
    """ルート orchestrator.py: 同一経路の回帰ガード。"""
    _, p_r = _at_10am()
    with p_r:
        assert root_orch.get_pending_batches(_cfg(None), {}) == []


def test_schedule_none_no_crash() -> None:
    """schedule 自体が None（`schedule:` 直下全コメント残留）でも落ちない。"""
    cfg = {"accounts": [{"key": "x", "schedule": None}]}
    p_k, p_r = _at_10am()
    with p_k:
        assert k_orch.get_pending_batches(cfg, {}) == []
    with p_r:
        assert root_orch.get_pending_batches(cfg, {}) == []


def test_schedule_missing_no_crash() -> None:
    """schedule キー欠落も安全。"""
    cfg = {"accounts": [{"key": "y"}]}
    p_k, p_r = _at_10am()
    with p_k:
        assert k_orch.get_pending_batches(cfg, {}) == []
    with p_r:
        assert root_orch.get_pending_batches(cfg, {}) == []


def test_normal_batches_still_work() -> None:
    """正常系（list型batches）の挙動は変更されていないこと。"""
    cfg = {
        "accounts": [
            {
                "key": "ok",
                "schedule": {"batches": [{"time": "09:00", "max": 10}]},
            }
        ],
        "orchestrator": {"batch_jitter_minutes": 0},
    }
    p_k, p_r = _at_10am()
    with p_k:
        out_k = k_orch.get_pending_batches(cfg, {})
    with p_r:
        out_r = root_orch.get_pending_batches(cfg, {})
    assert [x[:2] for x in out_k] == [("ok", "09:00")]
    assert [x[:2] for x in out_r] == [("ok", "09:00")]
