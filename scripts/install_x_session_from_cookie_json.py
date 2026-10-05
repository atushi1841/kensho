#!/usr/bin/env python3
"""install_x_session_from_cookie_json.py — ブラウザ拡張のcookie JSONから X セッションファイルを作る

背景: data/x_session*.json (Playwright storage_state) を失うと、自動リフレッシュ
(verify_and_refresh_session.py) は「セッションファイルがありません」で即NGとなり復旧できない。
Xはパスワード再ログインを自動化できないため、人間がブラウザでログインしてcookieを渡す必要がある。
本スクリプトは、そのcookie（Cookie-Editor / EditThisCookie のJSON配列）を
Playwright storage_state 形式へ変換して所定パスへ設置する。

使い方:
  # 変換だけ確認（書き込まない）
  python scripts/install_x_session_from_cookie_json.py atushi16 cookies.json --dry-run
  # 設置（既存は .bak<timestamp> へ退避 → chmod 600）
  python scripts/install_x_session_from_cookie_json.py atushi16 cookies.json --write
  # stdin から
  cat cookies.json | python scripts/install_x_session_from_cookie_json.py kudou - --write

安全:
  - 値は絶対にログへ出さない（cookie名と件数のみ表示）
  - 対象キーは config.yaml の accounts（無ければ FALLBACK）にあるものだけ。未知キーは拒否
  - --write 時は必ずバックアップを取る
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
CONFIG = PROJ / "config.yaml"

# verify_and_refresh_session.py と同一のフォールバック表（config.yaml の session を優先）
SESSION_FALLBACK = {
    "atushi16": "data/x_session.json",
    "kudou": "data/x_session_kudou.json",
    "zin20120731": "data/x_session_c.json",
    "TankanNotes": "data/x_session_TankanNotes.json",
    "toushiwatch": "data/x_session_toushiwatch.json",
}

SAME_SITE = {
    "no_restriction": "None",
    "unspecified": "Lax",
    "lax": "Lax",
    "strict": "Strict",
    "none": "None",
}


def resolve_path(key: str) -> Path:
    """垢キー -> 設置先パス（config.yaml の session を優先）"""
    sess = None
    try:
        import yaml  # type: ignore

        cfg = yaml.safe_load(CONFIG.read_text(encoding="utf-8")) or {}
        for a in cfg.get("accounts", []) or []:
            if a.get("key") == key:
                sess = a.get("session")
                break
    except Exception:
        pass
    rel = sess or SESSION_FALLBACK.get(key)
    if not rel:
        raise SystemExit(f"[NG] 未知の垢キー: {key}（config.yaml の accounts に無く、フォールバック表にも無い）")
    return PROJ / rel


def to_storage_state(raw) -> dict:
    """Cookie-Editor配列 / {'cookies':[...]} / storage_state のいずれも受ける"""
    if isinstance(raw, dict) and "cookies" in raw:
        cookies_in = raw.get("cookies") or []
        origins = raw.get("origins") or []
    elif isinstance(raw, list):
        cookies_in = raw
        origins = []
    else:
        raise SystemExit("[NG] 入力形式が不正（Cookie配列 か {'cookies': [...]} を渡す）")

    out = []
    for c in cookies_in:
        if not isinstance(c, dict) or "name" not in c or "value" not in c:
            continue
        dom = c.get("domain") or ""
        # Xに必要なドメインだけ通す（他所のcookieを混ぜない）
        if "x.com" not in dom and "twitter.com" not in dom:
            continue
        exp = c.get("expirationDate")
        item = {
            "name": c["name"],
            "value": c["value"],
            "domain": dom,
            "path": c.get("path") or "/",
            "expires": float(exp) if exp else -1,
            "httpOnly": bool(c.get("httpOnly", False)),
            "secure": bool(c.get("secure", True)),
            "sameSite": SAME_SITE.get(str(c.get("sameSite", "")).lower(), "Lax"),
        }
        out.append(item)
    return {"cookies": out, "origins": origins}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("key", help="垢キー（atushi16 / kudou / zin20120731 / TankanNotes）")
    ap.add_argument("cookie_json", help="cookieのJSONファイル（'-' でstdin）")
    ap.add_argument("--write", action="store_true", help="実際に書き込む（既定はdry-run）")
    ap.add_argument("--dry-run", action="store_true", help="書き込まない（既定）")
    ap.add_argument("--out", default=None, help="設置先を明示（テスト用。通常は垢キーから自動解決）")
    args = ap.parse_args()

    dest = Path(args.out) if args.out else resolve_path(args.key)
    if args.cookie_json == "-":
        raw = json.load(sys.stdin)
    else:
        raw = json.loads(Path(args.cookie_json).read_text(encoding="utf-8"))

    state = to_storage_state(raw)
    names = {c["name"] for c in state["cookies"]}
    need = {"auth_token", "ct0"}
    try:
        shown = dest.relative_to(PROJ)
    except ValueError:
        shown = dest
    print(f"[i] 設置先: {shown}  cookies={len(state['cookies'])}件")
    print(f"[i] auth_token={'OK' if 'auth_token' in names else 'なし'} ct0={'OK' if 'ct0' in names else 'なし'}")
    if not need <= names:
        print("[NG] X のログインに必須の auth_token / ct0 が含まれていません（ログイン済みブラウザから取得すること）")
        return 1

    if not args.write:
        print("[dry-run] 書き込みは行っていません。設置するには --write を付ける")
        return 0

    if dest.exists():
        bak = dest.with_name(dest.name + ".bak" + time.strftime("%Y%m%d-%H%M%S"))
        dest.rename(bak)
        print(f"[i] 既存を退避: {bak.name}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    dest.chmod(0o600)
    print("[OK] 設置完了（600）。次に検証: python scripts/verify_and_refresh_session.py", args.key)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
