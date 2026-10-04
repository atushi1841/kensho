#!/usr/bin/env python3
"""apify_console_check — Apify Console の画面を CDP 経由で読み取る。

背景（2026-10-03 実測）:
  Apify Store の匿名検索で、自社アクターは一部しか items に現れない。
  `/v2/store?username=<自分>` も `?search=<アクター名>` も「count は返るが items=[]」
  という署名で、API からは掲載状態を確認できない。
  → Console の publishing 画面を人が見るしかない、という結論になっていた。
  本スクリプトはその「人が見る」部分を自動化する（CDP でブラウザを操作して画面を読む）。

仕組み:
  WSL からは Windows の 127.0.0.1:9222 へ直接到達できないため、
  Chrome の起動と node ドライバの実行は powershell.exe 経由で行う。
  永続プロファイル（C:\\temp\\kensho-apify-cdp）を使うので、
  **初回だけ手動で Apify にログイン**すれば以降は無人で読める。

使い方:
  python3 scripts/apify_console_check.py --actor DKzufUSvmuXNKHeYx
  python3 scripts/apify_console_check.py --url https://console.apify.com/actors/DKzufUSvmuXNKHeYx
  python3 scripts/apify_console_check.py --actor DKzufUSvmuXNKHeYx --screenshot

終了コード: 0=取得成功（ログイン済み） / 3=要ログイン / 1=失敗
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
DRIVER_SRC = REPO / "scripts" / "apify_console_driver.js"
WIN_TEMP = Path("/mnt/c/temp")
DRIVER_DST = WIN_TEMP / "kensho_apify_console.js"
OUT_JSON = WIN_TEMP / "apify_console_out.json"
SHOT_PNG = WIN_TEMP / "apify_console.png"
PROFILE_DIR = r"C:\temp\kensho-apify-cdp"
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
PORT = 9222


def ps(cmd: str, timeout: int = 60) -> tuple[int, str]:
    """powershell.exe 経由で Windows コマンドを実行する。"""
    try:
        r = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", cmd],
            capture_output=True, text=True, timeout=timeout,
        )
        return r.returncode, (r.stdout or "").strip().replace("\r", "")
    except subprocess.TimeoutExpired:
        return 124, "timeout"
    except FileNotFoundError:
        return 127, "powershell.exe not found"


def cdp_alive() -> bool:
    _, out = ps(f"curl.exe -s -o NUL -w '%{{http_code}}' http://127.0.0.1:{PORT}/json/version", timeout=20)
    return out.strip().endswith("200")


def launch_chrome() -> bool:
    cmd = (
        f"Start-Process '{CHROME}' -ArgumentList "
        f"'--remote-debugging-port={PORT}','--user-data-dir={PROFILE_DIR}',"
        f"'--no-first-run','--no-default-browser-check','--window-size=1400,1000','about:blank'"
    )
    ps(cmd, timeout=40)
    for _ in range(12):
        time.sleep(2)
        if cdp_alive():
            return True
    return False


def ensure_chrome(verbose: bool = True) -> str:
    """CDP を確保する。戻り値: 'attached' か 'launched'。"""
    if cdp_alive():
        if verbose:
            print(f"[i] 既存の CDP エンドポイント :{PORT} に接続します")
        return "attached"
    if verbose:
        print(f"[i] Chrome を起動します（profile={PROFILE_DIR}）")
    if not launch_chrome():
        raise SystemExit("[x] Chrome の CDP を起動できませんでした（powershell/Chrome を確認）")
    return "launched"


def run_driver(url: str, screenshot: bool) -> dict[str, Any]:
    shutil.copyfile(DRIVER_SRC, DRIVER_DST)
    win_out = r"C:\temp\apify_console_out.json"
    args = f'"{url}" "{win_out}"'
    if screenshot:
        args += r' --screenshot "C:\temp\apify_console.png"'
    rc, out = ps(f'cd C:\\temp; node kensho_apify_console.js {args}', timeout=180)
    if not OUT_JSON.exists():
        raise SystemExit(f"[x] ドライバが出力を書きませんでした rc={rc} out={out[:400]}")
    parsed: dict[str, Any] = json.loads(OUT_JSON.read_text(encoding="utf-8"))
    return parsed


LOGIN_HINTS = ("log in", "login", "log-in", "sign in", "sign-in", "sign up", "sign-up", "auth.apify")


def main() -> int:
    ap = argparse.ArgumentParser(description="Apify Console の画面を CDP で読む")
    ap.add_argument("--actor", help="アクターID または アクター名")
    ap.add_argument("--url", help="直接URLを指定（--actor より優先）")
    ap.add_argument("--screenshot", action="store_true", help="PNGを取得する")
    ap.add_argument("--dump", action="store_true", help="本文全体を出力する")
    args = ap.parse_args()

    if not args.url and not args.actor:
        ap.error("--actor か --url のどちらかが必要です")

    url = args.url or f"https://console.apify.com/actors/{args.actor}"
    ensure_chrome()
    info = run_driver(url, args.screenshot)

    final_url = str(info.get("final_url") or "")
    title = str(info.get("title") or "")
    body = str(info.get("body_text") or "")
    logged_in = bool(info.get("logged_in")) and not any(h in final_url.lower() for h in LOGIN_HINTS)

    print(f"[i] final_url : {final_url}")
    print(f"[i] title     : {title}")
    print(f"[i] 本文長    : {len(body)} 文字")

    if not logged_in or len(body.strip()) < 60:
        print()
        print("[!] Apify Console にログインしていません（初回のみ手動が必要）")
        print(f"    1. 開いている Chrome ウィンドウ（profile={PROFILE_DIR}）を前面に出す")
        print("    2. https://console.apify.com にサインインする")
        print("    3. このコマンドをもう一度実行する（以降は無人で読めます）")
        return 3

    # 掲載状態に関わりそうな行だけ抜き出す
    keys = ("publish", "public", "store", "listed", "visibility", "review",
            "monetiz", "payout", "kyc", "verif", "掲載", "公開")
    hits = [ln.strip() for ln in body.splitlines() if ln.strip() and any(k in ln.lower() for k in keys)]
    print()
    print("=== 掲載/公開に関わる行 ===")
    for ln in hits[:40]:
        print("  " + ln[:160])
    if not hits:
        print("  （該当行なし。--dump で全体を見てください）")

    if args.dump:
        print()
        print("=== 本文全体 ===")
        print(body)

    if args.screenshot and info.get("screenshot"):
        dst = REPO / "reports" / "apify_console_latest.png"
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(SHOT_PNG, dst)
        print(f"\n[i] スクリーンショット: {dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
