#!/usr/bin/env python3
"""data/collected_today.json に easy_win_score を付与し、非X導線レポートを再生成する（t_c1889d30）。

collector.collect_report() は毎正時の収集時に easy_win_score を付与するが、本タスク導入前の
スナップショット（data/collected_today.json）にはキーが無い。本スクリプトで同一ロジック
（kensho.scraping.scorer.compute_easy_win_score）を当て直し、あわせて
reports/non_x_manual_<date>.md を当選易度 TOP50 付きで再生成する。

仕様（Task body 計画準拠）:
  - easy_win_score = winner_count 正規化(log1p/上限1000) と prize_score.priority 正規化
    (1.0=通常→0.0 / 3.0=満点→1.0) の等重合成 ×100（0-100、float）
  - winner_count 欠落・0・不正 = 計算不能 → score=0.0 を付与し、レポート TOP50 からは分離
  - 応募バッチ配分・応募ロジックには一切触れない（表示・可視化のみ）
  - collected.json / applier / daily_counts / applied_data には無関係（collected_today.json のみ）

使い方:
    .venv/bin/python scripts/backfill_easy_win_score.py            # 付与 + レポート再生成
    .venv/bin/python scripts/backfill_easy_win_score.py --dry-run  # 検算のみ（書き込みなし）
    .venv/bin/python scripts/backfill_easy_win_score.py --date 20260930

保存は kensho.utils.backup.safe_save_json（アトミック保存 + data/backups 自動退避）を使う。
exit 0 = 成功 / exit 1 = 入力不備・書き込み失敗。
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

_PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(_PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(_PROJECT_DIR))

from kensho.scraping.pathway_classifier import (  # noqa: E402
    PATHWAY_KEY,
    build_non_x_report_md,
    easy_win_ranking,
)
from kensho.scraping.scorer import EASY_WIN_SCORE_KEY, attach_easy_win_scores  # noqa: E402
from kensho.utils.backup import safe_save_json  # noqa: E402

DATA_PATH: Path = _PROJECT_DIR / "data" / "collected_today.json"
REPORT_DIR: Path = _PROJECT_DIR / "reports"


def load_items(path: Path) -> list[dict[str, Any]]:
    """collected_today.json を読み込む（list のみ受付）。"""
    if not path.exists():
        raise FileNotFoundError(f"collected_today.json が見つからない: {path}")
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list) or not data:
        raise ValueError(f"collected_today.json が空/想定外形式（{type(data).__name__}）")
    return data


def write_report(items: list[dict[str, Any]], today: str, dry_run: bool) -> Path:
    """当選易度 TOP50 付きの非X導線レポートを再生成する。"""
    label_counts: dict[str, int] = {str(k): v for k, v in Counter(it.get(PATHWAY_KEY) for it in items).items()}
    md = build_non_x_report_md(items, label_counts, today)
    out = REPORT_DIR / f"non_x_manual_{today}.md"
    if dry_run:
        print(f"[DRY-RUN] レポート書き込みスキップ: {out} ({len(md)} chars)")
        return out
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    out.write_text(md, encoding="utf-8")
    print(f"[REPORT] ✅ {out} ({len(md)} chars)")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="collected_today.json へ easy_win_score を付与（t_c1889d30）")
    ap.add_argument("--date", default=datetime.now().strftime("%Y%m%d"), help="レポート日付 YYYYMMDD")
    ap.add_argument("--dry-run", action="store_true", help="書き込みせず検算のみ")
    args = ap.parse_args()

    try:
        items = load_items(DATA_PATH)
    except (OSError, ValueError, json.JSONDecodeError) as e:
        print(f"[BACKFILL] ❌ 読み込み失敗: {e}")
        return 1

    computable, uncomputable = attach_easy_win_scores(items)
    print(f"[BACKFILL] 対象 {len(items)}件 / 計算可能 {computable}件 / 計算不能 {uncomputable}件")

    if not args.dry_run:
        try:
            safe_save_json(DATA_PATH, items, label="collected_today.json")
        except OSError as e:
            print(f"[BACKFILL] ❌ 保存失敗: {e}")
            return 1

    try:
        write_report(items, args.date, args.dry_run)
    except OSError as e:
        print(f"[BACKFILL] ❌ レポート書込失敗: {e}")
        return 1

    top, _ = easy_win_ranking(items, 5)
    print("[BACKFILL] TOP5:")
    for i, it in enumerate(top, start=1):
        url = str(it.get("x_url") or it.get("url"))[:70]
        print(f"  {i}. {float(it[EASY_WIN_SCORE_KEY]):5.1f}  wc={it.get('winner_count')}  {url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
