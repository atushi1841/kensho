#!/usr/bin/env python3
"""kensho apply成功率 集計 — auto_*.log の完了行から算出（計測源の一本化, t_9f37e5e3）.

背景: data/actions.db は 0バイト幽霊DB（生成コード 0 / 読み取りコード 0）。ここから
「成功0/エラー0 = n/a」を出すのは欠陥計測。apply成功率の正しい集計源は自動apply
サブプロセスの標準出力ログ logs/auto_YYYYMMDD.log に書かれる完了行である:

    [OK] 完了: N成功 / Mエラー

本スクリプトは gen_status_data.py の recent_runs（同完了行の採用）と同じ情報を、
指定日の完了行を1日分合算して単一コマンドで報告する。観察者（critic / research /
revenue）は actions.db ではなくこちらを集計源に使うこと。

使用例:
    python3 scripts/apply_success_rate.py            # 当日
    python3 scripts/apply_success_rate.py 20260916   # 指定日
"""

from __future__ import annotations

import argparse
import os
import re
from datetime import date

_COMPLETE_RE = re.compile(r"\[OK\] 完了:\s*(\d+)成功\s*/\s*(\d+)エラー")

PROJECT_DIR = os.environ.get("PROJECT_DIR", "/mnt/d/Project2/kensho")
LOG_DIR = os.environ.get("KENSHO_LOG_DIR", os.path.join(PROJECT_DIR, "logs"))


def summarize_log(log_path: str) -> tuple[int, int, int]:
    """1つの auto_*.log 内の [OK] 完了行を合算して (成功, エラー, 完了行数) を返す."""
    with open(log_path, encoding="utf-8") as fh:
        text = fh.read()
    ok = err = 0
    rows = list(_COMPLETE_RE.finditer(text))
    for m in rows:
        ok += int(m.group(1))
        err += int(m.group(2))
    return ok, err, len(rows)


def summarize_date(ymd: str, log_dir: str | None = None) -> tuple[int, int, int]:
    """'YYYYMMDD' 形式の日次ログ auto_<ymd>.log を集計（'-'/'_' 許容・自動正規化）."""
    compact = re.sub(r"[_-]", "", ymd)
    path = os.path.join(log_dir or LOG_DIR, f"auto_{compact}.log")
    return summarize_log(path)


def format_rate(ok: int, err: int) -> str:
    total = ok + err
    rate = (100.0 * ok / total) if total else 0.0
    return f"成功 {ok} 件 / エラー {err} 件 / 成功率 {rate:.1f}%"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="kensho apply成功率（auto log 完了行）の集計（actions.db は使わない）")
    ap.add_argument(
        "date",
        nargs="?",
        default="",
        help="YYYYMMDD（省略時は当日）",
    )
    args = ap.parse_args(argv)
    ymd = args.date or date.today().strftime("%Y%m%d")
    ok, err, lines = summarize_date(ymd)
    print(f"auto_{ymd}.log  完了行 {lines} 件 — {format_rate(ok, err)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
