"""tests for scripts/gumroad_cookies_guard.py — Gumroad Cookieファイル消失の自動復旧（t_53963f88）

背景（2026-09-25 実測）: gumroad_cookies.json が不在のまま日次収集が走ると、
gumroad_sales_collect.js は Cookie注入 0/N のまま login_ok=false の state を書いて
exit 0 で終わる（= 収益測定が無言で死ぬ）。本ガードは「起動前に一次ファイルを保証する」
ことでその経路を塞ぐ。ここでは復元/無操作/退避/復元不能の4挙動を実測で固定する。
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import gumroad_cookies_guard as gcg


def _write_cookies(path: Path, n: int = 3, secret: str = "SECRET-VALUE-abc") -> str:
    """Cookie風のダミーJSONを書く（値は出力に出てはいけない検証用の目印を含む）。"""
    data = [
        {"name": f"c{i}", "value": f"{secret}-{i}", "domain": ".gumroad.com", "path": "/"}
        for i in range(n)
    ]
    path.write_text(json.dumps(data), encoding="utf-8")
    return secret


class TestEnsureCookies:
    def test_valid_primary_is_noop(self, tmp_path: Path) -> None:
        """一次ファイルが有効なら上書きしない（bytes・mtime 不変）。"""
        primary = tmp_path / "gumroad_cookies.json"
        backup = tmp_path / "gumroad_cookies_backup.json"
        _write_cookies(primary, n=5)
        _write_cookies(backup, n=2)
        before = primary.read_bytes()
        before_mtime = primary.stat().st_mtime_ns

        res = gcg.ensure_cookies(str(primary), str(backup))

        assert res["action"] == "ok"
        assert res["exit_code"] == 0
        assert res["cookies_count"] == 5
        assert primary.read_bytes() == before
        assert primary.stat().st_mtime_ns == before_mtime
        assert res["sha256"] == gcg.file_sha256(str(primary))

    def test_restore_when_primary_missing(self, tmp_path: Path) -> None:
        """一次ファイル不在 → バックアップから復元し、内容が一致する。"""
        primary = tmp_path / "gumroad_cookies.json"
        backup = tmp_path / "gumroad_cookies_backup.json"
        _write_cookies(backup, n=4)
        expected = backup.read_bytes()

        res = gcg.ensure_cookies(str(primary), str(backup))

        assert res["action"] == "restored"
        assert res["exit_code"] == 0
        assert res["cookies_count"] == 4
        assert res["restored_from"] == str(backup)
        assert primary.exists()
        assert primary.read_bytes() == expected

    def test_restore_retires_corrupt_primary(self, tmp_path: Path) -> None:
        """壊れた一次ファイルは .invalid-<ts> へ退避してから復元する（証跡を残す）。"""
        primary = tmp_path / "gumroad_cookies.json"
        backup = tmp_path / "gumroad_cookies_backup.json"
        primary.write_text("{ broken json", encoding="utf-8")
        _write_cookies(backup, n=2)

        res = gcg.ensure_cookies(str(primary), str(backup))

        assert res["action"] == "restored"
        retired = res["retired"]
        assert isinstance(retired, str) and retired
        assert Path(retired).read_text(encoding="utf-8") == "{ broken json"
        assert json.loads(primary.read_text(encoding="utf-8"))  # 復元後は正しいJSON

    def test_missing_when_both_absent(self, tmp_path: Path) -> None:
        """一次もバックアップも無い → 復元不能（exit 3・要ユーザー対応）。"""
        res = gcg.ensure_cookies(str(tmp_path / "none.json"), str(tmp_path / "none_bak.json"))
        assert res["action"] == "missing"
        assert res["exit_code"] == gcg.EXIT_MISSING
        assert "Cookie再エクスポート" in res["detail"]

    def test_empty_list_is_invalid(self, tmp_path: Path) -> None:
        """空リスト（要素0件）は「有効」と見なさない。"""
        primary = tmp_path / "gumroad_cookies.json"
        primary.write_text("[]", encoding="utf-8")
        res = gcg.ensure_cookies(str(primary), str(tmp_path / "none_bak.json"))
        assert res["action"] == "missing"
        assert "要素0件" in res["detail"]

    def test_zero_byte_file_is_invalid(self, tmp_path: Path) -> None:
        primary = tmp_path / "gumroad_cookies.json"
        primary.write_text("", encoding="utf-8")
        res = gcg.ensure_cookies(str(primary), str(tmp_path / "none_bak.json"))
        assert res["action"] == "missing"
        assert "空ファイル" in res["detail"]


class TestCli:
    def test_ok_marker_and_exit_zero(self, tmp_path: Path, capsys: Any) -> None:
        primary = tmp_path / "gumroad_cookies.json"
        _write_cookies(primary, n=3)
        code = gcg.main(["--cookies", str(primary), "--backup", str(tmp_path / "none_bak.json")])
        out = capsys.readouterr().out
        assert code == 0
        assert gcg.MARK_OK in out

    def test_restored_marker(self, tmp_path: Path, capsys: Any) -> None:
        primary = tmp_path / "gumroad_cookies.json"
        backup = tmp_path / "gumroad_cookies_backup.json"
        _write_cookies(backup, n=3)
        code = gcg.main(["--cookies", str(primary), "--backup", str(backup)])
        out = capsys.readouterr().out
        assert code == 0
        assert gcg.MARK_RESTORED in out

    def test_missing_exit_code_and_guidance(self, tmp_path: Path, capsys: Any) -> None:
        code = gcg.main([
            "--cookies", str(tmp_path / "none.json"),
            "--backup", str(tmp_path / "none_bak.json"),
        ])
        out = capsys.readouterr().out
        assert code == gcg.EXIT_MISSING
        assert gcg.MARK_MISSING in out
        assert "再エクスポート" in out

    def test_cookie_values_never_printed(self, tmp_path: Path, capsys: Any) -> None:
        """認証情報の値を出力しない（件数とsha256のみ）。--json でも同様。"""
        primary = tmp_path / "gumroad_cookies.json"
        backup = tmp_path / "gumroad_cookies_backup.json"
        secret = _write_cookies(backup, n=3)
        gcg.main(["--cookies", str(primary), "--backup", str(backup), "--json"])
        out = capsys.readouterr().out
        assert secret not in out
        payload = json.loads(out)
        assert payload["action"] == "restored"
        assert payload["cookies_count"] == 3
        assert set(payload) >= {"action", "exit_code", "detail", "sha256"}

    def test_json_output_is_machine_readable(self, tmp_path: Path, capsys: Any) -> None:
        primary = tmp_path / "gumroad_cookies.json"
        _write_cookies(primary, n=1)
        gcg.main(["--cookies", str(primary), "--backup", str(tmp_path / "none_bak.json"), "--json"])
        payload = json.loads(capsys.readouterr().out)
        assert payload["action"] == "ok"
        assert payload["exit_code"] == 0
        assert os.path.basename(payload["restored_from"] or "") == ""
