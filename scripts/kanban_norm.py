#!/usr/bin/env python3
"""
scripts/kanban_norm.py

kensho-ai-team kanban の Show HN 案件タイトル重複判定で共通利用する
正規化キーを提供する。既存 scripts/kanban_hn_cleanup.py と
kensho-non-api-revenue-hunter.py の両方から import される前提。

背景:
  kensho-non-api-revenue-hunter.py は HN showstories を cron 毎に
  kanban に投入するが、同一 Show HN 記事が複数 Run に跨って重複作成される。
  重複判定は Run内 URL dedup だけでなく、Run横断の正規化タイトルで照合する
  必要がある。本モジュールは kanban_hn_cleanup.py と同一ルールで
  normalize することで、両者の判定を一致させる。
"""

from __future__ import annotations

import os
import re
import sqlite3
from collections.abc import Iterable
from pathlib import Path

# 既定のボード DB: kensho-ai-team
KANBAN_BOARD_SLUG = "kensho-ai-team"


def _real_home() -> Path:
    """WSL や hermes profile 配下で HOME が書き換わっているケースを救済。
    /etc/passwd の実 home を優先し、無ければ環境変数 HOME、最後に Path.home() に
    フォールバックする。kensho-non-api-revenue-hunter.py と同一実装。
    """
    import pwd

    try:
        return Path(pwd.getpwuid(os.getuid()).pw_dir)
    except (KeyError, ImportError):
        return Path(os.environ.get("HOME") or str(Path.home()))


def default_db_path() -> Path:
    """kensho-ai-team kanban DB の既定パスを返す。
    DB 未作成時は呼び出し側で存在チェックすること。
    """
    return _real_home() / ".hermes" / "kanban" / "boards" / KANBAN_BOARD_SLUG / "kanban.db"


def norm_title(title: str) -> str:
    """Show HN タイトルを重複判定用キーへ正規化。
    ルール:
      - 先頭の [...] プレフィクスを除去 (例: "[非API自動収益]")
      - 先頭の "Show HN:" を除去 (大文字小文字無視)
      - 先頭の "<何か>:" 形式のカテゴリ/ラベルを除去
      - 連続空白を単一空白に
      - 末尾の "…" / " ..." で切り詰められた部分を除去
      - 末尾の短い単語(<=3文字)を切り落とし(=60字制限由来の語断片対策)
    """
    t = (title or "").strip()
    t = re.sub(r"^\[[^\]]*\]\s*", "", t)  # [非API自動収益]
    t = re.sub(r"^Show HN:\s*", "", t, flags=re.I)  # Show HN:
    t = re.sub(r"^[^:]*:\s*", "", t)  # カテゴリ: (アプリ/ツール:)
    t = re.sub(r"\s+", " ", t).strip().lower()
    for mark in ("…", " ..."):
        if mark in t:
            t = t.split(mark)[0]
    words = t.split(" ")
    while len(words) > 1 and len(words[-1]) < 4:
        words = words[:-1]
    return " ".join(words).strip()


# アクティブ状態 = 未完了
ACTIVE_STATUSES = ("ready", "todo", "running", "blocked", "triage")


def fetch_existing_normalized_titles(
    db_path: Path | str | None = None,
    statuses: Iterable[str] = ACTIVE_STATUSES,
    title_like: str = "%show hn%",
) -> dict[str, list[str]]:
    """指定 kanban DB から、アクティブ状態かつ title_like に該当する全 task の
    正規化タイトルを {key: [task_id, ...]} で返す。
    DB が存在しなければ空 dict。
    """
    db = Path(db_path) if db_path else default_db_path()
    if not db.exists():
        return {}
    statuses = tuple(statuses)
    if not statuses:
        return {}
    ph = ",".join("?" * len(statuses))
    con = sqlite3.connect(str(db))
    try:
        if title_like is None:
            rows = con.execute(
                f"SELECT id, title FROM tasks WHERE status IN ({ph})",
                statuses,
            ).fetchall()
        else:
            rows = con.execute(
                f"SELECT id, title FROM tasks WHERE lower(title) LIKE ? AND status IN ({ph})",
                (title_like.lower(), *statuses),
            ).fetchall()
    finally:
        con.close()
    out: dict[str, list[str]] = {}
    for tid, title in rows:
        key = norm_title(title)
        if key:
            out.setdefault(key, []).append(tid)
    return out


def is_duplicate(
    title: str,
    db_path: Path | str | None = None,
    statuses: Iterable[str] = ACTIVE_STATUSES,
    title_like: str = "%show hn%",
) -> tuple[bool, str]:
    """title を正規化し、kanban DB に同キー(同一記事)が既にあれば (True, task_id) を返す。
    無ければ (False, "")。DB 未作成なら (False, "")。
    """
    key = norm_title(title)
    if not key:
        return False, ""
    mapping = fetch_existing_normalized_titles(db_path=db_path, statuses=statuses, title_like=title_like)
    ids = mapping.get(key, [])
    if ids:
        return True, ids[0]
    return False, ""


if __name__ == "__main__":
    # 簡易 self-check
    samples = [
        "[非API自動収益] アプリ/ツール: Show HN: Triplox, a distributed Datalog engine",
        "  Show HN: Yan – In-browser glitch art...",
        "アプリ/ツール: Show HN: I built an app that makes your goals inevitable",
        "Show HN: WiringPi 3.20 – Updated GPIO Library for Raspberry",
    ]
    for s in samples:
        print(f"{s!r}\n  -> {norm_title(s)!r}")
