#!/usr/bin/env python3
"""当選率源別自動分析（critic v164 / t_8bf52d53）.

data/dm_wins.json（X DM当選通知）と data/collected.json 系（応募記録 applied）
を突合し、収集源別・カテゴリ別・応募時刻帯別の当選率を Markdown で出力する。
読み取り専用分析のみ — 応募ロジックは一切変更しない。

突合キー（失敗時代替案のフォールバック順）:
1. DM本文/x.com展開URL中の tweet_id 完全一致
2. (sender handle, account_key) 一致
どちらでもない場合は unmatched として明記する。

使い方:
    python3 scripts/kensho_winrate_analysis.py --week 2026W38
    → reports/winrate-2026W38.md
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any

JST = timezone(timedelta(hours=9))
PROJECT_DIR = os.environ.get("PROJECT_DIR", "/mnt/d/Project2/kensho")

# Twitter snowflake epoch (ms)
_TW_EPOCH_MS = 1288834974657

_X_URL_RE = re.compile(r"https?://(?:x|twitter)\.com/([^/?#]+)/status/(\d{5,25})", re.IGNORECASE)
_ANY_STATUS_RE = re.compile(r"/status(?:es)?/(\d{5,25})", re.IGNORECASE)


def tweet_id_to_time_ms(tweet_id: str) -> int | None:
    """snowflake ID → 作成ミリ秒（UTC epoch）。不正IDは None。"""
    try:
        n = int(tweet_id)
    except ValueError:
        return None
    if n <= 0:
        return None
    return (n >> 22) + _TW_EPOCH_MS


def parse_dt(s: str) -> datetime | None:
    """ISO/`YYYY-MM-DD HH:MM` など混在タイムスタンプを JST aware datetime化。

    タイムゾーン指定なしは JST 扱い（dm_wins の message_time 実測に基づく）。
    """
    if not s:
        return None
    txt = s.strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(txt)
    except ValueError:
        try:
            dt = datetime.strptime(txt, "%Y-%m-%d %H:%M")
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=JST)
    return dt.astimezone(JST)


def normalize_handle(sender: str) -> str:
    return (sender or "").lstrip("@").strip().lower()


def load_campaigns(paths: list[str]) -> dict[str, dict[str, Any]]:
    """collected.json系ファイル群から案件インデックスを作る（tweet_id優先キー）。

    重複案件は applied タイムスタンプの最大値で統合（後勝ち）。
    """
    campaigns: dict[str, dict[str, Any]] = {}
    for path in paths:
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        items = data.get("collected") if isinstance(data, dict) else data
        if not isinstance(items, list):
            continue
        for it in items:
            if not isinstance(it, dict):
                continue
            x_url = it.get("x_url") or ""
            m = _X_URL_RE.search(x_url)
            tweet_id = m.group(2) if m else ""
            handle = m.group(1).lower() if m else ""
            detail = it.get("detail_url") or ""
            key = tweet_id or detail
            if not key:
                continue
            applied = {acct: ts for acct, ts in (it.get("applied") or {}).items() if isinstance(ts, str) and ts}
            source = it.get("source") or _derive_source(detail)
            prev = campaigns.get(key)
            if prev is None:
                campaigns[key] = {
                    "tweet_id": tweet_id,
                    "handle": handle,
                    "source": source,
                    "detail_url": detail,
                    "applied": dict(applied),
                    "prize_rank": it.get("prize_rank"),
                    "prize_items": (it.get("prize_score") or {}).get("items") or [],
                }
            else:
                for acct, ts in applied.items():
                    old = prev["applied"].get(acct)
                    if old is None or ts > old:
                        prev["applied"][acct] = ts
    return campaigns


def _derive_source(detail_url: str) -> str:
    """source欠損時のフォールバック（detail_url前置き→収集源名）。"""
    prefixes = [
        ("/kenshouclub", "kenshouclub"),
        ("/twscrape", "twscrape"),
        ("/cpmeikan", "cpmeikan"),
        ("/present", "chancecom"),
        ("/kema", "kema"),
        ("/kensho-everyday", "kensho-everyday"),
        ("/kenkaku", "ken-kaku"),
        ("/detail", "knshow"),
    ]
    for pre, name in prefixes:
        if (detail_url or "").startswith(pre):
            return name
    return "unknown"


def load_wins(path: str) -> list[dict[str, Any]]:
    """dm_wins.json（{account_key: [win,...]}）をフラット化。"""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return []
    wins: list[dict[str, Any]] = []
    if isinstance(data, dict):
        for acct, rows in data.items():
            if not isinstance(rows, list):
                continue
            for w in rows:
                if isinstance(w, dict):
                    row = dict(w)
                    row.setdefault("account_key", acct)
                    wins.append(row)
    return wins


def extract_tweet_ids(text: str) -> set[str]:
    """DM本文から引用符付きx.comステータスリンクを抽出（t.co展開込みの実測経路）。"""
    ids: set[str] = set()
    for m in _ANY_STATUS_RE.finditer(text or ""):
        ids.add(m.group(1))
    return ids


def match_wins(
    wins: list[dict[str, Any]], campaigns: dict[str, dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """当選DM→案件突合。[match,...] と unmatched win一覧のタプルを返す。

    match要素: {win, campaign, key} key ∈ {'tweet_id','handle'}。
    同一winに複数案件が当たった場合は applied に当該垢を持つもの優先。
    """
    by_tweet = {c["tweet_id"]: c for c in campaigns.values() if c["tweet_id"]}
    by_handle: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for c in campaigns.values():
        if c["handle"]:
            by_handle[(c["handle"], "__any__")].append(c)

    matched: list[dict[str, Any]] = []
    unmatched: list[dict[str, Any]] = []
    for win in wins:
        acct = win.get("account_key") or ""
        text = win.get("message_text") or ""
        camp: dict[str, Any] | None = None
        key = ""
        # キー1: tweet_id完全一致（本文内の任意 x.com/status<id>）
        for tid in extract_tweet_ids(text):
            cand = by_tweet.get(tid)
            if cand and acct in cand["applied"]:
                camp, key = cand, "tweet_id"
                break
            if cand and camp is None:
                camp, key = cand, "tweet_id"
        # キー2: handle + account（appliedに当該垢ありを優先、無ければhandle一致のみ）
        if camp is None:
            handle = normalize_handle(win.get("sender") or "")
            cands = by_handle.get((handle, "__any__"), [])
            with_applied = [c for c in cands if acct in c["applied"]]
            pool = with_applied or cands
            if pool:
                # 複数該当時は直近応募（最新タイムスタンプ）の案件を採用
                camp = max(
                    pool,
                    key=lambda c: max(c["applied"].values(), default=""),
                )
                key = "handle"
        if camp is None:
            unmatched.append(win)
        else:
            matched.append({"win": win, "campaign": camp, "key": key})
    return matched, unmatched


def apply_lag_bucket(win: dict[str, Any], camp: dict[str, Any]) -> str:
    """ツイート投稿→応募完了までの遅延帯（instant win検証用、JST）。"""
    acct = win.get("account_key") or ""
    applied = camp["applied"].get(acct)
    a_dt = parse_dt(applied or "")
    t_ms = tweet_id_to_time_ms(camp.get("tweet_id") or "")
    if a_dt is None or t_ms is None:
        return "不明"
    lag_h = (a_dt.timestamp() * 1000 - t_ms) / 3600000.0
    if lag_h < 0:
        return "負値(要調査)"
    if lag_h < 1:
        return "<1h"
    if lag_h < 24:
        return "<24h"
    if lag_h < 168:
        return "<7d"
    return ">=7d"


def hour_band(win: dict[str, Any]) -> str:
    """応募開始時刻帯ではなく『当選通知時刻』のJST 6時間帯。"""
    dt = parse_dt(win.get("message_time") or win.get("detected_at") or "")
    if dt is None:
        return "不明"
    return f"{(dt.hour // 6) * 6:02d}-{(dt.hour // 6) * 6 + 5:02d}時"


def prize_category(camp: dict[str, Any]) -> str:
    items = " ".join(str(x) for x in camp.get("prize_items") or [])
    low = items.lower()
    if "amazon" in low or "アマゾン" in items:
        return "Amazon系"
    if any(k in low for k in ("pay", "ポイント", "quicpay")):
        return "決済・ポイント系"
    if "ギフト" in items or "gift" in low:
        return "ギフト券・コード系"
    if not items:
        return "その他(情報欠損)"
    return "物販・現物系"


def aggregate(
    campaigns: dict[str, dict[str, Any]],
    matched: list[dict[str, Any]],
    unmatched: list[dict[str, Any]],
) -> dict[str, Any]:
    """源別/カテゴリ別/遅延帯別の集計を返す（apply_logs不在→collected applied使用）。"""
    applies_by_source: dict[str, int] = defaultdict(int)
    for c in campaigns.values():
        applies_by_source[c["source"]] += len(c["applied"])
    wins_by_source: dict[str, int] = defaultdict(int)
    wins_by_cat: dict[str, int] = defaultdict(int)
    wins_by_lag: dict[str, int] = defaultdict(int)
    wins_by_hour: dict[str, int] = defaultdict(int)
    for m in matched:
        c = m["campaign"]
        wins_by_source[c["source"]] += 1
        wins_by_cat[prize_category(c)] += 1
        wins_by_lag[apply_lag_bucket(m["win"], c)] += 1
        wins_by_hour[hour_band(m["win"])] += 1
    total_wins = len(matched) + len(unmatched)
    return {
        "applies_by_source": dict(applies_by_source),
        "wins_by_source": dict(wins_by_source),
        "wins_by_cat": dict(wins_by_cat),
        "wins_by_lag": dict(wins_by_lag),
        "wins_by_hour": dict(wins_by_hour),
        "matched": len(matched),
        "unmatched": len(unmatched),
        "total_wins": total_wins,
        "key_breakdown": {k: sum(1 for m in matched if m["key"] == k) for k in ("tweet_id", "handle")},
    }


def render(
    week_label: str,
    stats: dict[str, Any],
    matched: list[dict[str, Any]],
    unmatched: list[dict[str, Any]],
    data_files: list[str],
    week_new: int,
) -> str:
    lines: list[str] = []
    now = datetime.now(JST).strftime("%Y-%m-%d %H:%M JST")
    total_applies = sum(stats["applies_by_source"].values())
    um_rate = stats["unmatched"] / stats["total_wins"] * 100 if stats["total_wins"] else 0.0
    lines.append(f"# 当選率源別レポート {week_label}")
    lines.append("")
    lines.append(f"- 生成時刻: {now}")
    lines.append(f"- 対象データ: {', '.join(os.path.basename(p) for p in data_files)}")
    lines.append(
        f"- 応募記録合計 {total_applies}件 / 当選通知 {stats['total_wins']}件 "
        f"（突合成功 {stats['matched']} / unmatched {stats['unmatched']} = {um_rate:.1f}%）"
    )
    lines.append(
        f"- 突合キー内訳: tweet_id一致 {stats['key_breakdown']['tweet_id']} / "
        f"handle+垢一致 {stats['key_breakdown']['handle']}"
    )
    lines.append(f"- 当週(W{week_label[-2:]})新規当選通知: {week_new}件")
    lines.append("")
    lines.append("## 源別当選率")
    lines.append("")
    lines.append("| 収集源 | 応募数 | 当選 | 当選率 |")
    lines.append("|---|---:|---:|---:|")
    for src in sorted(
        stats["applies_by_source"],
        key=lambda s: -stats["applies_by_source"][s],
    ):
        a = stats["applies_by_source"][src]
        w = stats["wins_by_source"].get(src, 0)
        rate = f"{w / a * 100:.2f}%" if a else "-"
        lines.append(f"| {src} | {a} | {w} | {rate} |")
    lines.append("")
    lines.append("## カテゴリ別当選（景品種別）")
    lines.append("")
    lines.append("| カテゴリ | 当選 |")
    lines.append("|---|---:|")
    for cat, w in sorted(stats["wins_by_cat"].items(), key=lambda kv: -kv[1]):
        lines.append(f"| {cat} | {w} |")
    if not stats["wins_by_cat"]:
        lines.append("| （該当なし） | 0 |")
    lines.append("")
    lines.append("## 応募遅延帯別当選（tweet投稿→応募完了）")
    lines.append("")
    lines.append("| 遅延帯 | 当選 |")
    lines.append("|---|---:|")
    order = ["<1h", "<24h", "<7d", ">=7d", "負値(要調査)", "不明"]
    for b in order:
        if b in stats["wins_by_lag"]:
            lines.append(f"| {b} | {stats['wins_by_lag'][b]} |")
    lines.append("")
    lines.append("※ 「<1h」比率は提案B『新しい順』キューの根拠データ（instant win検証）。")
    lines.append("")
    lines.append("## 当選通知時刻帯（JST 6時間帯）")
    lines.append("")
    lines.append("| 時刻帯 | 当選 |")
    lines.append("|---|---:|")
    for b in sorted(stats["wins_by_hour"]):
        lines.append(f"| {b} | {stats['wins_by_hour'][b]} |")
    lines.append("")
    if unmatched:
        lines.append("## 未突合の当選一覧（収集履歴外）")
        lines.append("")
        for w in unmatched:
            lines.append(f"- {w.get('account_key', '?')} ← {w.get('sender', '?')} @ {w.get('message_time', '?')}")
        lines.append("")
        lines.append(
            "※ 未突合は収集快照前の案件または非X自動化経由の当選。突合キー再設計が必要なら critic へ申し送り。"
        )
    return "\n".join(lines) + "\n"


def iso_week_bounds(week_label: str) -> tuple[datetime, datetime] | None:
    """'2026W38' → (月0時JST, 翌週月0時JST)。不正形式は None。"""
    m = re.fullmatch(r"(\d{4})W(\d{2})", week_label)
    if not m:
        return None
    year, week = int(m.group(1)), int(m.group(2))
    try:
        start = date.fromisocalendar(year, week, 1)
    except ValueError:
        return None
    s = datetime(start.year, start.month, start.day, tzinfo=JST)
    return s, s + timedelta(days=7)


def default_week(today: date | None = None) -> str:
    d = today or datetime.now(JST).date()
    iso = d.isocalendar()
    return f"{iso[0]}W{iso[1]:02d}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--week", default=None, help="ISO週ラベル 例 2026W38（既定=今週）")
    parser.add_argument("--project-dir", default=PROJECT_DIR)
    parser.add_argument(
        "--collected",
        nargs="*",
        default=None,
        help="collected.json系の明示指定（既定=data/collected.json + data/collected.json.bak*）",
    )
    parser.add_argument("--wins", default=None, help="dm_wins.jsonパス（既定=data/dm_wins.json）")
    parser.add_argument("--out", default=None, help="出力mdパス（既定=reports/winrate-<week>.md）")
    args = parser.parse_args(argv)

    pdir = args.project_dir
    week = args.week or default_week()
    bounds = iso_week_bounds(week)
    if bounds is None:
        print(f"ERROR: --week 形式不正: {week}", file=sys.stderr)
        return 2

    collected_paths = args.collected or sorted(
        glob.glob(os.path.join(pdir, "data/collected.json.bak*")) + [os.path.join(pdir, "data/collected.json")]
    )
    wins_path = args.wins or os.path.join(pdir, "data/dm_wins.json")

    campaigns = load_campaigns(collected_paths)
    wins = load_wins(wins_path)
    matched, unmatched = match_wins(wins, campaigns)
    stats = aggregate(campaigns, matched, unmatched)

    start, end = bounds
    week_new = sum(1 for w in wins if (dt := parse_dt(w.get("message_time") or "")) is not None and start <= dt < end)
    md = render(week, stats, matched, unmatched, collected_paths, week_new)

    out = args.out or os.path.join(pdir, "reports", f"winrate-{week}.md")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(md)

    print(
        f"winrate {week}: wins={stats['total_wins']} matched={stats['matched']} "
        f"unmatched_rate={(stats['unmatched'] / stats['total_wins'] * 100 if stats['total_wins'] else 0):.1f}% "
        f"sources={len(stats['applies_by_source'])} → {out}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
