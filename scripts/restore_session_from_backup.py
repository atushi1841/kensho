#!/usr/bin/env python3
"""restore_session_from_backup.py — kensho-secrets からセッションを復元

使い方:
  python scripts/restore_session_from_backup.py              # 最新日付から全垢復元
  python scripts/restore_session_from_backup.py --date 20261008
  python scripts/restore_session_from_backup.py --key atushi16
  python scripts/restore_session_from_backup.py --list       # 利用可能なバックアップ一覧

注意: セッション値はログ/コミットに絶対に記載しない。
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
BACKUP_ROOT = Path("/home/atushi/kensho-secrets")
LOG_DIR = PROJ / "logs"
LOG_DIR.mkdir(exist_ok=True)


def log(msg: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_DIR / "restore_session.log", "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def list_backups() -> None:
    if not BACKUP_ROOT.exists():
        print("バックアップディレクトリが存在しません:", BACKUP_ROOT)
        sys.exit(1)
    dates = sorted(d.name for d in BACKUP_ROOT.iterdir() if d.is_dir() and d.name.isdigit())
    if not dates:
        print("バックアップが見つかりません")
        sys.exit(0)
    print(f"利用可能なバックアップ ({len(dates)}件):")
    for d in dates:
        files = sorted(BACKUP_ROOT.joinpath(d).glob("x_session_*.json"))
        print(f"  {d}: {[f.name for f in files]}")
    print(f"\n最新: {dates[-1]}")


def find_backup(date: str | None, key: str | None) -> Path | None:
    if not BACKUP_ROOT.exists():
        return None
    if date:
        candidate = BACKUP_ROOT / date / f"x_session_{key}.json" if key else None
        if candidate and candidate.exists():
            return candidate
        # key なしで日付のみ指定 → 最新ファイルを探す
        if not key:
            dirp = BACKUP_ROOT / date
            files = list(dirp.glob("x_session_*.json")) if dirp.exists() else []
            return files[0] if files else None
        return None
    # 最新日付を検索
    dates = sorted(d.name for d in BACKUP_ROOT.iterdir() if d.is_dir() and d.name.isdigit())
    if not dates:
        return None
    latest = BACKUP_ROOT / dates[-1]
    if key:
        return latest / f"x_session_{key}.json" if (latest / f"x_session_{key}.json").exists() else None
    return latest


def resolve_session_path(key: str) -> Path | None:
    """config.yaml からセッションファイルパスを取得"""
    import yaml
    cfg_path = PROJ / "config.yaml"
    if not cfg_path.exists():
        return None
    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    for a in cfg.get("accounts", []) or []:
        if a.get("key") == key and a.get("session"):
            return PROJ / a["session"]
    # fallback
    FALLBACK = {
        "atushi16": "data/x_session.json",
        "kudou": "data/x_session_kudou.json",
        "zin20120731": "data/x_session_c.json",
        "TankanNotes": "data/x_session_TankanNotes.json",
        "toushiwatch": "data/x_session_toushiwatch.json",
    }
    sess = FALLBACK.get(key)
    return PROJ / sess if sess else None


def restore(date: str | None, key: str | None) -> int:
    backup_path = find_backup(date, key)
    if not backup_path or not backup_path.exists():
        print(f"バックアップが見つかりません: {backup_path}")
        return 1

    # key 決定
    if key:
        keys = [key]
    else:
        # ファイル名から key 抽出
        stem = backup_path.stem  # e.g. x_session_atushi16
        key = stem.replace("x_session_", "")
        keys = [key]

    restored = []
    for k in keys:
        dest = resolve_session_path(k)
        if not dest:
            print(f"  ⚠ {k}: セッションファイルパスが不明")
            continue
        if not dest.parent.exists():
            dest.parent.mkdir(parents=True, exist_ok=True)
        # バックアップ取得
        bak = dest.with_suffix(dest.suffix + f".bak-restore-{datetime.now().strftime('%Y%m%d-%H%M%S')}")
        if dest.exists():
            shutil.copy2(dest, bak)
            os.chmod(bak, 0o600)
            log(f"  ✓ {k}: 現在ファイルをバックアップ ({bak.name})")
        shutil.copy2(backup_path, dest)
        os.chmod(dest, 0o600)
        log(f"  ✓ {k}: 復元完了 ({dest}) ← {backup_path.name}")
        restored.append(k)

    if restored:
        print(f"\n復元完了: {', '.join(restored)}")
        print(f"バックアップ元: {backup_path}")
        print(f"\n⚠ 次回以降の応募は、ユーザーがブラウザで再ログインしていることを確認してから実行してください。")
        return 0
    print("復元できる垢がありません")
    return 1


def main() -> int:
    ap = argparse.ArgumentParser(description="kensho Xセッション復元ツール")
    ap.add_argument("--date", help="バックアップ日付 (YYYYMMWD, 省略=最新)")
    ap.add_argument("--key", help="対象垢キー (省略=バックアップ内の全垢)")
    ap.add_argument("--list", action="store_true", help="利用可能なバックアップ一覧を表示")
    args = ap.parse_args()

    if args.list:
        list_backups()
        return 0

    return restore(args.date, args.key)


if __name__ == "__main__":
    sys.exit(main())
