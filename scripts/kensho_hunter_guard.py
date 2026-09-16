#!/usr/bin/env python3
"""
scripts/kensho_hunter_guard.py — 発券重複防止ガード (critic v162 / t_37c0fafa)

背景 (2026-09-16 実測):
  t_06fdd792「7th MCP: Japan property hazard risk server」(08:09, user発券)
  に対し、t_c3af4776「日本物件ハザードリスクMCP プロトタイプ作成」
  (09:29, created_by=worker, idempotency_key=None) が同一テーマの二重登録と
  なった。HNハンター経路 (kensho-non-api-revenue-hunter.py) は v58/v148 で
  hn-キー+全ステータスdedup済みのだが、LLMワーカーの ad-hoc 発券
  (hermes kanban create / kanban_create native) はキー欠落のままだった。
  9/5教訓「hunter毎晩再作成」のルール化が済んでいて today 再発したため、
  決定的キー強制 + 起票前ボード走査を共通ガードとして実装する。

提供機能:
  1. hunter_idempotency_key(title) -> "hunter-YYYYMMDD-<テーマスラッグハッシュ8桁>"
     (JST日付スコープの決定的キー。同一日同一テーマの再起票は hermes kanban
      create の idempotency 照合で既存カードが返され no-op になる)
  2. find_open_duplicates(title, body) -> [(task_id, [共通トークン...]), ...]
     open状態 (ready/running/todo/scheduled/blocked/triage) のタイトル+本文と
     語彗トークン重複を走査。閾値以上で hit = 起票中止の判定材料。
  3. comment_instead_of_create(task_id, ...) -> 既存カードへコメント追記で代替
     (新規を作らない。要件3)
  4. CLI `check`: 起票前に叩く単一コマンド。
       exit 0 -> 起票可 (stdout に決定的キーを1行出力)
       exit 1 -> 同一テーマの open カードあり (stdout に既存ID+理由、起票中止)
     いずれも stderr にログ1行を残す。

閾値の設計判断:
  日英混在 (hazard vs ハザード) は字面上一致しないため、ラテン語トークン
  (mcp, apify, server 等の技術語) と CJK 文字列トークンの両方を比較する。
  誤検知時の代替アクションは「コメント追記」なので、起票漏れよりは寄る方を
  取る (min_overlap=2 既定)。単一ヒットの "mcp" だけで止める板カード洪水は
  避けたいので既定2以上。
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import subprocess
import sys
from collections.abc import Iterable, Sequence
from datetime import datetime, timedelta, timezone
from pathlib import Path

JST = timezone(timedelta(hours=9))

# ---------------------------------------------------------------------------
# DB / home 解決 (kanban_norm.py / hunter と同一実装)
# ---------------------------------------------------------------------------


def _real_home() -> Path:
    import pwd

    try:
        return Path(pwd.getpwuid(os.getuid()).pw_dir)
    except (KeyError, ImportError):
        return Path(os.environ.get("HOME") or str(Path.home()))


KANBAN_BOARD_SLUG = "kensho-ai-team"

# open状態 = 起票前に照合すべき未完了ステータス (critic v162 要件2)
OPEN_STATUSES = ("ready", "running", "todo", "scheduled", "blocked", "triage")

# 技術用語として重複シグナルになるが単独では弱すぎる通用語トークン。
# (これら「だけ」の重複で止めてと legit 発券を潰さないための閾値設計とセット)
# mcp/api/japan はこのボードでは全件が共有しうる語なので raw 一致から除外し、
# 決定的シグナルは bridge (対訳テーマ語) に委ねる。
GENERIC_TOKENS = {
    "task",
    "tasks",
    "kensho",
    "kanban",
    "hermes",
    "http",
    "https",
    "www",
    "check",
    "verify",
    "test",
    "qa",
    "cron",
    "worker",
    "critic",
    "report",
    "mcp",
    "api",
    "japan",
    "server",
    "コミット",
    "タスク",
    "検証",
    "対応",
    "実施",
    "確認",
}

LATIN_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9\-_\.]{2,}")
CJK_RUN_RE = re.compile(r"[\u3040-\u30ff\u4e00-\u9faf\u3400-\u4dbf]{2,}")

# 日英テーマブリッジ (critic v162 実測事案対策):
#   t_06fdd792「7th MCP: Japan property hazard risk server」(英) と
#   t_c3af4776「日本物件ハザードリスクMCP プロトタイプ作成」(和) のような
#   同一テーマの cross-lingual 二重登録は、素のトークン一致では "mcp" 1語しか
#   共通せず検出できない。テーマ語の対訳表で比較集合を両言語へ展開し、
#   決定的 (LLM不要) なチェックで拾えるようにする。追加は「発券実績が
#   出た対」のみ — 汎用語 (確認/検証 等) は GENERIC_TOKENS 側で除外済み。
THEME_BRIDGE: dict[str, list[str]] = {
    "ハザード": ["hazard"],
    "リスク": ["risk"],
    "物件": ["property", "real estate", "real-estate"],
    "サーバー": ["server"],
    "プロトタイプ": ["prototype"],
    "洪水": ["flood"],
    "土砂": ["landslide"],
    "津波": ["tsunami"],
    "液状化": ["liquefaction"],
    "ジオコーディング": ["geocoding"],
    "災害": ["disaster"],
    "住所": ["address"],
}


# ---------------------------------------------------------------------------
# 1) 決定的 idempotency キー
# ---------------------------------------------------------------------------


def theme_slug_hash(title: str, extra: str = "") -> str:
    """テーマ文字列からスラッグハッシュ8桁を生成する。

    正規化: 小文字化・空白/記号圧縮後、英数字+CJKのみ残した文字列の
    sha1 先頭8桁。同一テーマ表記 (大文字小文字・空白差) は同一ハッシュになる。
    """
    t = (title or "").strip().lower()
    t = re.sub(r"[\s]+", " ", t)
    t = re.sub(r"[^0-9a-z\u3040-\u30ff\u4e00-\u9faf]+", "", t)
    if extra:
        e = re.sub(r"[\s]+", " ", extra.strip().lower())
        e = re.sub(r"[^0-9a-z\u3040-\u30ff\u4e00-\u9faf]+", "", e)
        t = t + "|" + e
    return hashlib.sha1(t.encode("utf-8")).hexdigest()[:8]


def hunter_idempotency_key(title: str, when: datetime | None = None, extra: str = "") -> str:
    """ハンター発券の決定的キー: 'hunter-YYYYMMDD-<テーマスラッグハッシュ8桁>'.

    YYYYMMDD は JST 起算。日跨ぎの再作成防止 (9/5教訓) はタイトル/HN item_id
    全ステータス dedup 側が担い、このキーは同日内の二重登録 (retry・複数 run)
    を最終防衛する (critic v162 要件1 の指定フォーマット)。
    """
    when = when or datetime.now(JST)
    return f"hunter-{when.strftime('%Y%m%d')}-{theme_slug_hash(title, extra)}"


# ---------------------------------------------------------------------------
# 2) open カード走査 (同一テーマキーワード)
# ---------------------------------------------------------------------------


def tokenize(text: str) -> set[str]:
    """ラテン語トークン (3文字以上) + CJK 連なり (2文字以上) を小文字集合で返す。

    ここに素のトークン一致だけでは cross-lingual (和英混在) の同一テーマを
    拾えないため、theme_tokens() でブリッジ語を別途付与する。
    """
    text = (text or "").lower()
    toks: set[str] = set()
    for m in LATIN_TOKEN_RE.findall(text):
        toks.add(m.strip("-_."))
    for m in CJK_RUN_RE.findall(text):
        toks.add(m)
    return {t for t in toks if t and t not in GENERIC_TOKENS and len(t) >= 2}


def theme_tokens(text: str) -> set[str]:
    """THEME_BRIDGE の対訳を部分文字列検出し 'bridge:<key>' 正規トークンを返す。

    CJK 連なりトークンは語境界を跨いで連結される (日本物件ハザードリスク…)
    ため exact-match では機能しない。ブリッジ語はサブストリング検索する。
    英側は token 化後と生 text 両方で確認 (複数語 synonym 対策に小文字 text 検索)。
    """
    t = (text or "").lower()
    out: set[str] = set()
    for key, synonyms in THEME_BRIDGE.items():
        if key in t:
            out.add(f"bridge:{key}")
            continue
        for syn in synonyms:
            if syn in t:
                out.add(f"bridge:{key}")
                break
    return out


def default_db_path() -> Path:
    return _real_home() / ".hermes" / "kanban" / "boards" / KANBAN_BOARD_SLUG / "kanban.db"


def find_open_duplicates(
    title: str,
    body: str = "",
    db_path: Path | str | None = None,
    statuses: Sequence[str] = OPEN_STATUSES,
    min_score: int = 5,
) -> list[tuple[str, list[str]]]:
    """open状態カードのタイトル+本文と、新テーマの重複スコアを照合する。

    スコア = 2 * (対訳ブリッジ語の共通数) + 1 * (通用語を除く raw トークンの共通数)。
    raw トークンは document frequency フィルタを掛ける: open カードの
    max(3, 15%) 以上に出現する語はテンプレ/ボイラープレート (hunter 本文の
    「自動検出」「実装可能」等) とみなし無視する。これにより同一テンプレ由来の
    誤検知で legit 発券が全滅するのを防ぐ。
    既定閾値5 = ブリッジ語2語(+raw1語)以上、またはブリッジ3語で Hit。
    ブリッジ2語のみ (score4) は「別プロダクトだが語域が近い」許容範囲とした。
    戻り値: スコア順 [(task_id, 共通トークン一覧)]。閾値未満は除外。
    DB 不在時は空リスト (ガード不能時 create を止めない呼び出し側の判断に委ねる)。
    """
    import sqlite3
    from math import ceil

    db = Path(db_path) if db_path else default_db_path()
    if not db.exists():
        return []
    new_raw = tokenize(f"{title}\n{body}")
    new_bridge = theme_tokens(f"{title}\n{body}")
    if not new_raw and not new_bridge:
        return []
    statuses = tuple(statuses)
    ph = ",".join("?" * len(statuses))
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        rows = con.execute(
            f"SELECT id, title, body FROM tasks WHERE status IN ({ph})",
            statuses,
        ).fetchall()
    finally:
        con.close()
    if not rows:
        return []

    existing_raw: dict[str, set[str]] = {}
    existing_bridge: dict[str, set[str]] = {}
    doc_freq: dict[str, int] = {}
    for tid, ex_title, ex_body in rows:
        full = f"{ex_title or ''}\n{ex_body or ''}"
        raw = tokenize(full)
        existing_raw[tid] = raw
        existing_bridge[tid] = theme_tokens(full)
        for tok in raw:
            doc_freq[tok] = doc_freq.get(tok, 0) + 1

    generic_cap = max(3, ceil(len(rows) * 0.15))
    hits: list[tuple[int, str, list[str]]] = []
    for tid, _t, _b in rows:
        shared_bridge = sorted(new_bridge & existing_bridge[tid])
        shared_raw = sorted(tok for tok in (new_raw & existing_raw[tid]) if doc_freq[tok] < generic_cap)
        score = 2 * len(shared_bridge) + len(shared_raw)
        if score >= min_score:
            hits.append((score, tid, [f"b:{x}" for x in shared_bridge] + shared_raw))
    hits.sort(key=lambda x: -x[0])
    return [(tid, toks) for _score, tid, toks in hits]


# ---------------------------------------------------------------------------
# 3) 既存カードへのコメント追記で代替
# ---------------------------------------------------------------------------


def comment_instead_of_create(
    task_id: str,
    new_title: str,
    author: str = "kensho-hunter-guard",
    note: str = "",
    dry_run: bool = False,
) -> bool:
    """新規作らず既存カードへ抑止記録コメントを追記する (要件3)。

    失敗しても例外にせず False を返す — 発券中止は既に達成済みで、コメント
    追記はベストエフォート。
    """
    body = f"hunter-guard: 同一テーマの重複起票を抑止しました (差し替え対象: 「{new_title[:80]}」)。"
    if note:
        body += f"\n{note}"
    if dry_run:
        print(f"[DRY-RUN] would comment on {task_id}: {body}")
        return True
    try:
        r = subprocess.run(
            ["hermes", "kanban", "--board", KANBAN_BOARD_SLUG, "comment", task_id, body, "--author", author],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return r.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


# ---------------------------------------------------------------------------
# 4) CLI
# ---------------------------------------------------------------------------


def main(argv: Iterable[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="kanban 発券重複防止ガード (critic v162)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    ck = sub.add_parser("check", help="起票前チェック: exit0=起票可(stdoutにキー), exit1=中止")
    ck.add_argument("--title", required=True)
    ck.add_argument("--body", default="")
    ck.add_argument("--body-file", default="")
    ck.add_argument("--db", default=None)
    ck.add_argument("--min-score", type=int, default=5)
    ck.add_argument("--annotate", action="store_true", help="hit時に既存カードへ抑止コメントを追記する")
    ck.add_argument("--author", default="kensho-hunter-guard")

    key = sub.add_parser("key", help="決定的 idempotency キーを出力するだけ")
    key.add_argument("--title", required=True)

    args = ap.parse_args(list(argv) if argv is not None else None)

    if args.cmd == "key":
        print(hunter_idempotency_key(args.title))
        return 0

    body = args.body
    if args.body_file:
        body = Path(args.body_file).read_text(encoding="utf-8", errors="replace")

    key_out = hunter_idempotency_key(args.title)
    try:
        hits = find_open_duplicates(args.title, body, db_path=args.db, min_score=args.min_score)
    except Exception as e:  # DB障害でガード不能時は発券を止めない (hunter方針と同一)
        sys.stderr.write(f"[hunter-guard] scan error (continue): {e}\n")
        print(key_out)
        return 0

    if hits:
        existing, shared = hits[0]
        sys.stderr.write(
            f"[hunter-guard] BLOCKED dup-theme: '{args.title[:60]}' -> 既存 {existing} "
            f"(共通語 {shared[:6]} 他{len(hits) - 1}件)\n"
        )
        print(f"dup {existing} {' '.join(shared[:8])}")
        if args.annotate:
            comment_instead_of_create(existing, args.title, author=args.author, note=f"共通トークン: {shared[:8]}")
        return 1

    sys.stderr.write(f"[hunter-guard] OK unique: '{args.title[:60]}' key={key_out}\n")
    print(key_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
