#!/usr/bin/env python3
"""
scripts/wantedly_job_monitor.py

Wantedly 公開求人のキーワード×地域モニタ + Slack/LINE 通知ツール。

Wantedly /projects 公開ページ(robots.txt 許可)を SSR レンダリングして定期クロールし、
監視クエリ(キーワード×地域×雇用形態×並び替え)にマッチする非掲載(できたばかり)の求人を
検出して Slack Incoming Webhook / LINE Notify へ通知する。

設計原則 (task t_4d13bb42 / revenue opportunity 2026-09-05):
  - TOS 遵守: robots.txt が許可する https://www.wantedly.com/projects のみ (Disallow 無し)。
    CAPTCHA 回避・ログイン・非公開データへのアクセスは一切行わない。
    公式ページ上の SSR 埋め込み JSON (__NEXT_DATA__) を解析するだけ。
  - 毎回新規に SSR ページを取得し、job id を SQLite に記録して重複を排除。
    同一 job id を2回通知しない(i = 冪等)。
  - 低レート: ページ間にランダム遅延、1クエリごとに短い待機、再試行付き。
  - 通知は Slack / LINE が設定されている場合のみ。未設定ならログ(toast 相当)に出力。

利用シナリオ (月額980円想定 SaaS のバックエンド):
  求職者/転職エージェントが「Rustエンジニア × 東京 × 中途」「AIエンジニア × 大阪」
  等を設定。更新があると新規掲載として即時通知 = Indeed には無い Wantedly 特化の速報性。

使い方:
  python scripts/wantedly_job_monitor.py --config wantedly_monitor.yaml
  python scripts/wantedly_job_monitor.py --list-filters      # 現在の監視クエリ一覧
  python scripts/wantedly_job_monitor.py --notify-test       # Slack/LINE 疎通テスト
  python scripts/wantedly_job_monitor.py --dry-run --pages 1 # 送信・DB書き込みなしで確認

環境変数(通知が有効になる条件):
  WANTEDLY_SLACK_WEBHOOK_URL   Slack Incoming Webhook URL
  WANTEDLY_LINE_TOKEN          LINE Notify access token
  (どちらも未設定なら通知はログ出力のみ=開発モード)
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

JST = timezone(timedelta(hours=9))
REPO = Path(__file__).resolve().parent.parent
DATA_DIR = REPO / "data" / "wantedly_monitor"
STATE_DB = DATA_DIR / "state.db"
REPORTS_DIR = REPO / "reports" / "revenue-proposals"

USER_AGENT = "kensho-wantedly-job-monitor/1.0 (personal research; respects robots.txt; rate-limited)"
BASE_URL = "https://www.wantedly.com/projects"
PER_PAGE = 10  # Wantedly SSR はページサイズ固定 10
MIN_DELAY = 4.0
MAX_DELAY = 9.0


# ── データモデル ─────────────────────────────────────────────
@dataclass
class Query:
    keywords: list[str] = field(default_factory=list)
    areas: list[str] = field(default_factory=list)
    hiring_types: list[str] = field(default_factory=list)
    order: str = "recent"  # recent | popular | mixed
    pages: int = 2  # SSR は page=N でページング可 (pageSize 固定 10)


@dataclass
class JobPost:
    id: str
    title: str
    company: str
    occupation: str
    hiring_types: list[str]
    published_at: str
    url: str
    description: str = ""


# ── 設定 ─────────────────────────────────────────────────────
DEFAULT_FILTERS: list[dict] = [
    {
        "keywords": ["Rustエンジニア", "Golangエンジニア"],
        "areas": ["tokyo"],
        "hiring_types": ["mid_career"],
        "order": "recent",
        "pages": 2,
    },
    {
        "keywords": ["AIエンジニア"],
        "areas": ["tokyo", "osaka"],
        "hiring_types": ["mid_career", "internship"],
        "order": "recent",
        "pages": 2,
    },
]


def load_config(path: str | None) -> list[Query]:
    """YAML-like な設定を読み込む。config が無ければデフォルト。"""
    if path and Path(path).exists():
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        filters = data.get("filters") or []
    elif path:
        raise FileNotFoundError(f"config not found: {path}")
    else:
        filters = DEFAULT_FILTERS
    queries: list[Query] = []
    for f in filters:
        queries.append(
            Query(
                keywords=list(f.get("keywords") or []),
                areas=list(f.get("areas") or []),
                hiring_types=list(f.get("hiring_types") or []),
                order=f.get("order", "recent"),
                pages=int(f.get("pages") or 2),
            )
        )
    return queries


# ── SSR ページ取得 ───────────────────────────────────────────
def build_url(q: Query, page: int) -> str:
    params: list[tuple[str, str]] = []
    for kw in q.keywords:
        params.append(("keywords", kw))
    for a in q.areas:
        params.append(("areas", a))
    for h in q.hiring_types:
        params.append(("hiringTypes", h))
    params.append(("order", q.order))
    params.append(("page", str(page)))
    return BASE_URL + "?" + urllib.parse.urlencode(params)


def http_get(url: str, timeout: int = 30) -> str | None:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < 2:
                time.sleep(2**attempt * 2)
                continue
            return None
        except (urllib.error.URLError, TimeoutError, OSError):
            return None
    return None


def extract_nested(d: dict, key: str):
    """dict 内を深さ優先で key を探して最初に見つかった値を返す。"""
    if isinstance(d, dict):
        for k, v in d.items():
            if k == key:
                return v
            r = extract_nested(v, key)
            if r is not None:
                return r
    elif isinstance(d, list):
        for item in d:
            r = extract_nested(item, key)
            if r is not None:
                return r
    return None


_REF_RE = re.compile(r'^JobPost:\{"id":"(\d+)"\}$')


def _ref_id(ref) -> str | None:
    """__ref ("JobPost:{"id":"2539170"}") またはそれを包む dict から id を抽出。"""
    if isinstance(ref, dict):
        ref = ref.get("__ref")
    if not isinstance(ref, str):
        return None
    m = _REF_RE.match(ref)
    if m:
        return m.group(1)
    # 'JobPost:{ "id":"..." }' 等の揺れに寛容に
    m2 = re.search(r'"id"\s*:\s*"(\d+)"', ref)
    return m2.group(1) if m2 else None


def parse_ssr(html: str) -> list[JobPost]:
    """__NEXT_DATA__ 埋め込み JSON から JobPost 一覧を抽出。

    - 検索結果の __ref ('JobPost:{"id":"..."}') から id の順序を取得
    - apollo 状態の 'JobPost:{"id":"..."}' キーから詳細オブジェクトを解決
    """
    m = re.search(r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not m:
        return []
    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError:
        return []
    gsi = data.get("props", {}).get("pageProps", {}).get("__apollo", {}).get("graphqlGatewayInitialState", {})

    # 1) 詳細オブジェクトを id → dict で索引付け
    detail: dict[str, dict] = {}
    for k, v in gsi.items():
        mid = _ref_id(k)
        if mid and isinstance(v, dict):
            detail[mid] = v
    # 2) 検索結果の __ref リストから、該当ページの求人 id 順序を収集
    order: list[str] = []
    rq = gsi.get("ROOT_QUERY", {})
    for v in rq.values():
        if not isinstance(v, dict):
            continue
        edge_ref = extract_nested(v, "jobPost")
        rid = _ref_id(edge_ref)
        if rid and rid not in order:
            order.append(rid)
        # jobPosts リスト内の __ref
        for item in extract_all(v, "jobPost"):
            rid2 = _ref_id(item)
            if rid2 and rid2 not in order:
                order.append(rid2)

    jobs: list[JobPost] = []
    for jid in order:
        d = detail.get(jid, {})
        comp = d.get("company") or {}
        htypes = []
        for h in d.get("hiringTypes") or []:
            htypes.append(str(h.get("type") or h.get("label") or ""))
        desc = d.get("detailDescription") or {}
        jobs.append(
            JobPost(
                id=jid,
                title=str(d.get("title") or ""),
                company=str(comp.get("name") or ""),
                occupation=str(d.get("occupationName") or ""),
                hiring_types=htypes,
                published_at=str(d.get("publishedAt") or ""),
                url=f"https://www.wantedly.com/projects/{jid}",
                description=str(desc.get("plainBody") or "")[:400],
            )
        )
    return jobs


def extract_all(d: dict, key: str) -> list:
    """dict 内を深さ優先で key に一致する値をすべて集める。"""
    out: list = []
    if isinstance(d, dict):
        for k, v in d.items():
            if k == key:
                out.append(v)
            out.extend(extract_all(v, key))
    elif isinstance(d, list):
        for item in d:
            out.extend(extract_all(item, key))
    return out


def crawl(queries: list[Query], dry_run: bool = False, page_cap: int | None = None):
    """監視クエリをすべてクロールし、新規求人(未記録)を返す。"""
    conn = get_db()
    all_jobs: list[tuple[Query, JobPost]] = []
    for q in queries:
        pag = min(page_cap, q.pages) if page_cap else q.pages
        for page in range(1, pag + 1):
            url = build_url(q, page)
            html = http_get(url)
            if html is None:
                print(f"  [skip] {url} (取得失敗)")
                break
            jobs = parse_ssr(html)
            for job in jobs:
                all_jobs.append((q, job))
            time.sleep(random.uniform(MIN_DELAY, MAX_DELAY))
    # 新規のみ抽出 (DB に未記録)
    new_jobs: list[tuple[Query, JobPost]] = []
    for q, job in all_jobs:
        if not is_seen(conn, job.id):
            new_jobs.append((q, job))
    if not dry_run:
        # 以降の実行で再通知しないよう記録
        for q, job in all_jobs:
            mark_seen(conn, job.id, job.published_at, job.title)
        conn.commit()
    conn.close()
    return new_jobs


# ── SQLite 状態 ──────────────────────────────────────────────
def get_db() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(STATE_DB)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS seen(
            job_id TEXT PRIMARY KEY,
            published_at TEXT,
            title TEXT,
            first_seen TEXT
        )
    """)
    return conn


def is_seen(conn: sqlite3.Connection, job_id: str) -> bool:
    row = conn.execute("SELECT 1 FROM seen WHERE job_id=?", (job_id,)).fetchone()
    return row is not None


def mark_seen(conn: sqlite3.Connection, job_id: str, published_at: str, title: str) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO seen(job_id, published_at, title, first_seen) VALUES(?,?,?,?)",
        (job_id, published_at, title or job_id, datetime.now(JST).isoformat(timespec="seconds")),
    )


# ── 通知 ─────────────────────────────────────────────────────
def _slack_notify(webhook: str, text: str) -> bool:
    payload = json.dumps({"text": text}).encode("utf-8")
    req = urllib.request.Request(
        webhook, data=payload, headers={"User-Agent": USER_AGENT, "Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status in (200, 201, 204)
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def _line_notify(token: str, text: str) -> bool:
    data = urllib.parse.urlencode({"message": text}).encode("utf-8")
    req = urllib.request.Request(
        "https://notify-api.line.me/api/notify",
        data=data,
        headers={
            "User-Agent": USER_AGENT,
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status in (200, 201, 204)
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def fmt_notify(q: Query, job: JobPost) -> str:
    hires = ",".join(job.hiring_types) if job.hiring_types else "-"
    kw = " / ".join(q.keywords) if q.keywords else "全キーワード"
    lines = [
        f"🎯 新着 Wantedly 求人 ({kw})",
        f"・{job.title}",
        f"・会社: {job.company}",
        f"・職種: {job.occupation} / 雇用: {hires}",
        f"・掲載: {job.published_at[:10]}",
        f"🔗 {job.url}",
    ]
    return "\n".join(lines)


def notify(new_jobs: list[tuple[Query, JobPost]]) -> tuple[int, int]:
    """Slack/LINE が設定済みなら通知。返り値 (通知した件数, 配信成功チャネル数)。"""
    slack = os.environ.get("WANTEDLY_SLACK_WEBHOOK_URL", "").strip()
    line = os.environ.get("WANTEDLY_LINE_TOKEN", "").strip()
    delivered = 0
    for q, job in new_jobs:
        text = fmt_notify(q, job)
        if not slack and not line:
            print(f"[notify][log-only] {text}")
            continue
        ok = 0
        if slack and _slack_notify(slack, text):
            ok += 1
        if line and _line_notify(line, text):
            ok += 1
        if ok:
            delivered += 1
        time.sleep(2)  # チャネルをまたいだレート緩和
    return delivered, len(new_jobs)


# ── CLI ──────────────────────────────────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser(description="Wantedly 求人キーワード監視 + Slack/LINE 通知")
    ap.add_argument("--config", default="", help="監視設定 JSON(なければデフォルト)")
    ap.add_argument("--dry-run", action="store_true", help="DB書き込み・通知なしで確認")
    ap.add_argument("--pages", type=int, default=None, help="ページ数キャップ(検証用)")
    ap.add_argument("--list-filters", action="store_true", help="設定済み監視クエリ一覧")
    ap.add_argument("--notify-test", action="store_true", help="Slack/LINE 疎通テスト送信")
    args = ap.parse_args()

    if args.list_filters:
        for i, q in enumerate(load_config(args.config if args.config else None), 1):
            print(f"{i}. keywords={q.keywords} areas={q.areas} hiring={q.hiring_types} order={q.order} pages={q.pages}")
        return 0

    if args.notify_test:
        ok = 0
        slack = os.environ.get("WANTEDLY_SLACK_WEBHOOK_URL", "").strip()
        line = os.environ.get("WANTEDLY_LINE_TOKEN", "").strip()
        if slack and _slack_notify(slack, "✅ Wantedly job monitor: connect test"):
            ok += 1
        if line and _line_notify(line, "Wantedly job monitor: connect test"):
            ok += 1
        if not slack and not line:
            print("[notify-test] 通知先未設定 (WANTEDLY_SLACK_WEBHOOK_URL / WANTEDLY_LINE_TOKEN を設定)")
            return 0
        print(f"[notify-test] delivered={ok} チャネル")
        return 0

    cfg_path = args.config if args.config else "wantedly_monitor.json"
    try:
        queries = load_config(cfg_path if Path(cfg_path).exists() else None)
    except FileNotFoundError:
        print(f"config not found: {cfg_path}; デフォルト監視クエリで実行", file=sys.stderr)
        queries = load_config(None)

    ts = datetime.now(JST)
    print("=" * 72)
    print(f"Wantedly 求人監視 {ts.isoformat()} | queries={len(queries)}")
    print("=" * 72)

    for q in queries:
        print(
            f"  ▶ {q.keywords} × {q.areas or '全国'} (hiring={q.hiring_types or '-'} order={q.order} pages={q.pages})"
        )

    new_jobs = crawl(queries, dry_run=args.dry_run, page_cap=args.pages)
    print(f"\n新規マッチ: {len(new_jobs)} 件")

    for q, job in new_jobs:
        print(f"  ● {job.url}  {job.title} ({job.company})")

    if args.dry_run:
        print("\n[dry-run] DB書き込み・通知はスキップしました")
        return 0

    delivered, total = notify(new_jobs)
    print(f"\n通知: {delivered}/{total} 件配信")

    # レポート
    report_path = REPORTS_DIR / "2026-09-05-wantedly-monitor.md"
    buf = []
    buf.append(f"# Wantedly 求人監視 実行ログ ({ts.date()})")
    buf.append("")
    buf.append(f"- 実行: {ts.isoformat()} / 監視クエリ: {len(queries)} / 新規マッチ: {len(new_jobs)}")
    buf.append(f"- 状態DB: {STATE_DB}")
    buf.append("")
    for q, job in new_jobs:
        buf.append(f"### {job.title}")
        buf.append(f"- company: {job.company} / occupation: {job.occupation}")
        buf.append(f"- 掲載: {job.published_at} / hiring: {job.hiring_types}")
        buf.append(f"- {job.url}")
        if job.description:
            buf.append(f"- 概要: {job.description[:150]}")
        buf.append("")
    if not new_jobs:
        buf.append("(新規マッチなし)")
    buf.append("")
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(buf), encoding="utf-8")
    print(f"レポート: {report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
