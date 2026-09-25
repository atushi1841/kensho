#!/usr/bin/env python3
"""gumroad_cookies_guard — Gumroad Cookieファイル消失時の「起動前」自動復旧ガード。

背景（2026-09-25 実測 / t_ee5ca962 の続報・t_53963f88）:
  `D:\\Project2\\gumroad-automation\\gumroad_cookies.json` が不在のまま日次収集が走ると、
  gumroad_sales_collect.js は Cookie注入 0/N のまま dashboard へ進み、
  `login_ok: false` の state を書いて exit 0 で終わる（= 成功に見える）。
  結果、売上測定は無言で死に、翌月まで「売上ゼロ」と区別できない
  （9/25 07:07 実測: state_exists=true / login_ok=false / collected_at=2026-09-25T07:07:35）。
  実害: 一次ファイル `gumroad_cookies.json` が消えても、同世代の
  `gumroad_cookies_backup.json` (9/22) が残っていたのに復元されなかった。

対策（本ガード）:
  日次収集の直前に呼び、一次ファイルが「無い / 空 / JSON壊れ」の場合のみ
  バックアップから復元する。
    - 一次ファイルが有効なら**何もしない**（上書き禁止＝新しい方が正）
    - 壊れた一次ファイルは `.invalid-<timestamp>` へ退避してから復元する（監査可能）
    - 認証情報の**値は一切出力しない**（件数と sha256 のみ）
    - 復元できなければ exit 3（要ユーザー対応: Cookie再エクスポート）

出力の目印（grep用・no_agent cron向け）:
  cookies-mark OK         … 一次ファイル有効（復元不要）
  cookies-mark RESTORED   … バックアップから復元した
  cookies-mark MISSING    … 復元不可（Cookie再エクスポートが必要）

CLI:
  python3 scripts/gumroad_cookies_guard.py [--cookies PATH] [--backup PATH] [--json] [--quiet]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import time
from typing import Any

# 既定パス（本番）。テストは引数で隔離ディレクトリを渡す。
DEFAULT_COOKIES = "/mnt/d/Project2/gumroad-automation/gumroad_cookies.json"
DEFAULT_BACKUP = "/mnt/d/Project2/gumroad-automation/gumroad_cookies_backup.json"

# 目印タグ（他スクリプト・監視が grep する文字列）
MARK_OK = "cookies-mark OK"
MARK_RESTORED = "cookies-mark RESTORED"
MARK_MISSING = "cookies-mark MISSING"

EXIT_OK = 0
EXIT_MISSING = 3


def file_sha256(path: str) -> str:
    """ファイルの sha256 を返す（読めない場合は空文字）。値そのものは出力しない用途に使う。"""
    try:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return ""


def inspect_cookies(path: str) -> tuple[bool, str, int]:
    """Cookieファイルの妥当性を判定する。

    返り値: (有効か, 理由/件数, 件数)
      - 有効 = 実在し、空でなく、JSONとして読めて、空でないリスト
    値は一切返さない（件数のみ）。
    """
    if not os.path.exists(path):
        return False, "ファイルなし", 0
    try:
        if os.path.getsize(path) == 0:
            return False, "空ファイル", 0
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as e:
        return False, f"JSON不正 ({type(e).__name__})", 0
    if not isinstance(data, list):
        return False, "リスト形式でない", 0
    if not data:
        return False, "要素0件", 0
    return True, f"{len(data)}件", len(data)


def _retire_invalid(primary: str, *, now: float | None = None) -> str:
    """壊れた一次ファイルを .invalid-<ts> へ退避する（監査用・失敗しても例外にしない）。"""
    stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime(now if now is not None else time.time()))
    dest = f"{primary}.invalid-{stamp}"
    try:
        shutil.move(primary, dest)
        return dest
    except OSError:
        return ""


def ensure_cookies(
    cookies: str = DEFAULT_COOKIES,
    backup: str = DEFAULT_BACKUP,
    *,
    now: float | None = None,
) -> dict[str, Any]:
    """一次Cookieファイルを保証する（有効なら無操作、壊れていればバックアップから復元）。

    返り値の dict:
      action / exit_code / detail / cookies_count / sha256 / restored_from / retired
    """
    result: dict[str, Any] = {
        "action": "missing",
        "exit_code": EXIT_MISSING,
        "detail": "",
        "cookies_count": 0,
        "sha256": "",
        "restored_from": None,
        "retired": None,
    }

    ok, detail, count = inspect_cookies(cookies)
    if ok:
        result.update({
            "action": "ok",
            "exit_code": EXIT_OK,
            "detail": f"一次ファイル有効（{detail}）",
            "cookies_count": count,
            "sha256": file_sha256(cookies),
        })
        return result

    primary_reason = detail
    bak_ok, bak_detail, bak_count = inspect_cookies(backup)
    if not bak_ok:
        result["detail"] = (
            f"一次={primary_reason} / バックアップ={bak_detail} → Cookie再エクスポートが必要"
        )
        return result

    # 壊れた一次ファイルは退避（値の混在を避ける）。存在しない場合は何もしない。
    if os.path.exists(cookies):
        result["retired"] = _retire_invalid(cookies, now=now)

    try:
        os.makedirs(os.path.dirname(cookies) or ".", exist_ok=True)
        shutil.copy2(backup, cookies)
    except OSError as e:
        result["detail"] = f"復元コピーに失敗: {type(e).__name__} → Cookie再エクスポートが必要"
        return result

    ok2, detail2, count2 = inspect_cookies(cookies)
    if not ok2:
        result["detail"] = f"復元後も不正（{detail2}）→ Cookie再エクスポートが必要"
        return result

    result.update({
        "action": "restored",
        "exit_code": EXIT_OK,
        "detail": f"バックアップから復元（{detail2} / 元の状態: {primary_reason}）",
        "cookies_count": count2,
        "sha256": file_sha256(cookies),
        "restored_from": backup,
    })
    assert bak_count >= 0  # バックアップ件数も判定済み（値は出力しない）
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Gumroad Cookieファイルの消失/破損を検出しバックアップから復元する")
    parser.add_argument("--cookies", default=DEFAULT_COOKIES, help="一次Cookieファイルのパス")
    parser.add_argument("--backup", default=DEFAULT_BACKUP, help="バックアップCookieファイルのパス")
    parser.add_argument("--json", action="store_true", help="結果をJSONで出力（機械可読）")
    parser.add_argument("--quiet", action="store_true", help="目印1行のみ出力")
    args = parser.parse_args(argv)

    res = ensure_cookies(args.cookies, args.backup)
    mark = {
        "ok": MARK_OK,
        "restored": MARK_RESTORED,
        "missing": MARK_MISSING,
    }[res["action"]]

    if args.json:
        print(json.dumps(res, ensure_ascii=False))
    else:
        print(f"{mark}: {res['detail']}")
        if not args.quiet and res.get("sha256"):
            print(f"  sha256={res['sha256'][:16]}… count={res['cookies_count']}")
        if res["action"] == "missing":
            print("  → 対処: Gumroadへログインし Cookie を再エクスポートして "
                  f"{args.cookies} を更新してください（要ユーザー対応）")

    return int(res["exit_code"])


if __name__ == "__main__":
    sys.exit(main())
