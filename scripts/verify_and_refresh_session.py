#!/usr/bin/env python3
"""verify_and_refresh_session.py — Xセッションの検証と自動リフレッシュ

回線（プロキシ）が生きている垢について:
  1) Playwright Firefox(headless) を その垢のプロキシ経由 で起動
  2) x.com/home を開きログイン状態を判定
  3) ログイン済みなら ctx.cookies() を採取してセッションファイルを更新（--write時）
     → X側でローテートされた auth_token/ct0 を実際に取り直す＝本物のリフレッシュ

安全原則（絶対ルール）:
  - プロキシは必ずその垢のものを使う（自宅IPでのアクセスは厳禁）
  - 出口IPが自宅IPなら即中止
  - --write 時は必ずバックアップを取ってから書き込む（chmod 600）

使い方:
  python scripts/verify_and_refresh_session.py kudou            # 検証のみ（dry-run）
  python scripts/verify_and_refresh_session.py kudou --write    # 検証して更新
  python scripts/verify_and_refresh_session.py --all --write    # 全垢
終了コード: 0=ログイン済み / 1=要再ログイン / 2=エラー(回線不通等)
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
MAP = PROJ / "data" / "account_wifi_map.json"
CONFIG = PROJ / "config.yaml"
PROXY_HOST = os.environ.get("KNE_PROXY_HOST", "172.26.80.1")
HOME_IP = "219.104.132.236"

# 垢ごとのセッションファイル（config.yaml の session を優先）
SESSION_FALLBACK = {
    "atushi16": "data/x_session.json",
    "kudou": "data/x_session_kudou.json",
    "zin20120731": "data/x_session_c.json",
    "TankanNotes": "data/x_session_TankanNotes.json",
    "toushiwatch": "data/x_session_toushiwatch.json",
}


def load_map() -> dict:
    return json.loads(MAP.read_text(encoding="utf-8"))


def resolve(key: str) -> tuple[Path, int]:
    """垢の (セッションファイル, プロキシポート) を返す"""
    port = None
    for ent in load_map().get("accounts", []):
        if ent.get("key") == key:
            port = ent.get("port")
            break
    if port is None:
        raise SystemExit(f"[NG] {key} は垢×回線表に見つかりません")

    sess = None
    try:
        import yaml  # type: ignore

        cfg = yaml.safe_load(CONFIG.read_text(encoding="utf-8")) or {}
        for a in cfg.get("accounts", []) or []:
            if a.get("key") == key and a.get("session"):
                sess = a["session"]
                break
    except Exception:
        pass
    path = PROJ / (sess or SESSION_FALLBACK.get(key, f"data/x_session_{key}.json"))
    return path, int(port)


def egress_of(port: int) -> str:
    """プロキシ経由の出口IP（自宅IPガード用）"""
    cmd = ["curl", "-s", "--max-time", "20", "--proxy", f"socks5h://{PROXY_HOST}:{port}", "https://api.ipify.org"]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=30).stdout.strip()
    except Exception:
        out = ""
    return out


def port_alive(port: int) -> bool:
    with socket.socket() as s:
        s.settimeout(3)
        try:
            s.connect((PROXY_HOST, port))
            return True
        except OSError:
            return False


def check_and_refresh(key: str, write: bool = False) -> int:
    path, port = resolve(key)
    print(f"== {key}: session={path.name} proxy=:{port}")
    if not path.exists():
        print("   [NG] セッションファイルがありません")
        return 2
    if not port_alive(port):
        print(f"   [NG] プロキシ {PROXY_HOST}:{port} に接続できません（回線ダウン）→ この垢はスキップ")
        return 2
    eg = egress_of(port)
    print(f"   egress IP: {eg or '取得失敗'}")
    if not eg:
        print("   [NG] プロキシ経由で外部に出られません（回線不安定）")
        return 2
    if eg == HOME_IP:
        print("   [重大NG] 出口IPが自宅IP。絶対ルール違反のため中止")
        return 2

    from playwright.sync_api import sync_playwright  # type: ignore

    state = json.loads(path.read_text(encoding="utf-8"))
    logged_in = False
    cookies: list[dict] = []
    with sync_playwright() as p:
        browser = p.firefox.launch(headless=True)
        ctx = browser.new_context(storage_state=state, proxy={"server": f"socks5://{PROXY_HOST}:{port}"})
        page = ctx.new_page()
        try:
            page.goto("https://x.com/home", timeout=90000, wait_until="commit")
        except Exception as e:
            print(f"   [注意] 遷移エラー: {str(e)[:100]}")
        time.sleep(4)
        url = page.url
        cookies = ctx.cookies()
        names = {c.get("name") for c in cookies}
        logged_in = ("login" not in url.lower()) and {"auth_token", "ct0"} <= names
        print(f"   URL: {url[:60]} / cookies={len(cookies)} / auth_token={'auth_token' in names} ct0={'ct0' in names}")
        browser.close()

    if not logged_in:
        print("   [要再ログイン] セッションが無効です（ブラウザでログインし直す必要があります）")
        return 1

    if write:
        bak = path.with_suffix(path.suffix + f".bak{time.strftime('%Y%m%d-%H%M%S')}")
        shutil.copy2(path, bak)
        os.chmod(bak, 0o600)
        new = {"cookies": cookies, "origins": state.get("origins", [])}
        path.write_text(json.dumps(new, ensure_ascii=False, indent=2), encoding="utf-8")
        os.chmod(path, 0o600)
        print(f"   [OK] セッション更新（{len(cookies)} cookies）バックアップ={bak.name}")
    else:
        print(f"   [OK] ログイン有効（{len(cookies)} cookies）※dry-run: 書き込みなし")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("key", nargs="?", help="垢キー")
    ap.add_argument("--all", action="store_true", help="全垢")
    ap.add_argument("--write", action="store_true", help="セッションを実際に更新する")
    a = ap.parse_args()

    keys = [e["key"] for e in load_map().get("accounts", [])] if a.all else ([a.key] if a.key else [])
    if not keys:
        ap.error("垢キーか --all を指定してください")

    rc = 0
    for k in keys:
        try:
            rc = max(rc, check_and_refresh(k, write=a.write))
        except SystemExit as e:
            print(f"   {e}")
            rc = 2
        print()
    print(f"--- 終了コード {rc} （0=全部有効 / 1=要再ログインあり / 2=回線エラーあり）")
    return rc


if __name__ == "__main__":
    sys.exit(main())
