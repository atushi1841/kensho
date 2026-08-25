"""
Tests for kensho/core/crash_guard.py — 並列実行時の誤検出防止
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from unittest.mock import patch

from kensho.core.crash_guard import check_previous_crash


class TestCheckPreviousCrash:
    """check_previous_crash: 並列実行の進行中 heartbeat を誤検出しない"""

    def _run(self, hb: dict, pid_alive: bool):
        """HEARTBEAT_FILE 読み込み全体をモックして check_previous_crash を実行"""
        from unittest.mock import MagicMock

        with (
            patch("kensho.core.crash_guard.HEARTBEAT_FILE", new="dummy"),
            patch("kensho.core.crash_guard.os.path.exists", return_value=True),
            patch("kensho.core.crash_guard.open", return_value=MagicMock()),
            patch("kensho.core.crash_guard.json.load", return_value=hb),
            patch("kensho.core.crash_guard._pid_is_alive", return_value=pid_alive),
        ):
            return check_previous_crash()

    def test_done_true_returns_none(self) -> None:
        """done=True なら正常終了 → クラッシュ判定なし"""
        assert self._run({"done": True}, False) is None

    def test_pid_alive_ignored_as_pending(self) -> None:
        """done=False でも pid が生存中 = 別垢の進行中 → 誤検出しない"""
        assert self._run({"done": False, "pid": 99999}, True) is None

    def test_pid_dead_returns_crash(self) -> None:
        """done=False かつ pid 死骸 = 真の異常終了 → クラッシュ報告"""
        res = self._run({"done": False, "pid": 99998}, False)
        assert res is not None
        assert res["done"] is False

    def test_no_heartbeat_returns_none(self) -> None:
        """heartbeat ファイルが無ければクラッシュ判定なし"""
        with (
            patch("kensho.core.crash_guard.HEARTBEAT_FILE", new="x"),
            patch("kensho.core.crash_guard.os.path.exists", return_value=False),
        ):
            assert check_previous_crash() is None

    def test_pid_is_alive_real_process(self) -> None:
        """_pid_is_alive: 自プロセス(=生存) → True"""
        from kensho.core.crash_guard import _pid_is_alive

        assert _pid_is_alive(os.getpid()) is True

    def test_pid_is_alive_dead_process(self) -> None:
        """_pid_is_alive: 存在しない pid → False"""
        from kensho.core.crash_guard import _pid_is_alive

        # 確実に存在しない pid を探す
        dead = 2147483647  # PID_MAX 付近の巨大値（通常存在しない）
        assert _pid_is_alive(dead) is False
