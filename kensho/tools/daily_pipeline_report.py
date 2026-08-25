#!/usr/bin/env python3
"""Kenshoパイプライン日次実績レポート — AI自己改善ループ（Critic Agent）への入力生成。

audit.jsonl・daily_counts.json・config.yaml を集計し、前日の運用実績を
構造化して stdout に出力する。Hermes cron の script として使い、
この出力を Critic Agent のプロンプトに注入して改善提案を生成させる。

使い方:
    python3 kensho/tools/daily_pipeline_report.py [YYYY-MM-DD]
    date省略時は「昨日」(JST) を集計。

出力: 安定したマークダウン形式（毎日同じ構造 → cron monitorの差分検知にも使える）
"""

from __future__ import annotations

import collections
import datetime
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
AUDIT_PATH = ROOT / "data" / "audit.jsonl"
COUNTS_PATH = ROOT / "data" / "daily_counts.json"
CONFIG_PATH = ROOT / "config.yaml"

ACCOUNTS = ["atushi16", "kudou", "chugakujuken", "zin20120731", "TankanNotes", "inobase1-4"]
DEFAULT_TARGET = {
    "atushi16": 75,
    "kudou": 50,
    "chugakujuken": 50,
    "zin20120731": 50,
    "TankanNotes": 50,
    "inobase1-4": 50,
}

JST = datetime.timezone(datetime.timedelta(hours=9))


def _load_target_date() -> str:
    if len(sys.argv) > 1:
        return sys.argv[1]
    return (datetime.datetime.now(JST) - datetime.timedelta(days=1)).strftime("%Y-%m-%d")


def _load_config() -> dict:
    try:
        import yaml

        return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def _jst_of(ts: str) -> datetime.datetime | None:
    try:
        return datetime.datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(JST)
    except (ValueError, TypeError):
        return None


def main() -> int:
    date_s = _load_target_date()
    cfg = _load_config()

    # 目標値: config 優先、なければデフォルト
    targets: dict[str, int] = {}
    acct_cfg = cfg.get("accounts", [])
    if isinstance(acct_cfg, list):
        for a in acct_cfg:
            if isinstance(a, dict) and a.get("key") in ACCOUNTS:
                targets[a["key"]] = int(a.get("daily_target", DEFAULT_TARGET.get(a["key"], 50)))
    for k, v in DEFAULT_TARGET.items():
        targets.setdefault(k, v)

    # audit.jsonl を日付でフィルタ
    by_acct: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)  # (action,status) -> n
    errs: collections.Counter = collections.Counter()  # error -> n
    acct_errs: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    hourly: collections.Counter = collections.Counter()
    total_actions = 0

    if AUDIT_PATH.exists():
        with open(AUDIT_PATH, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    continue
                ts = r.get("timestamp", "")
                jst = _jst_of(ts)
                if jst is None or jst.strftime("%Y-%m-%d") != date_s:
                    continue
                acct = r.get("account", "?")
                if acct not in ACCOUNTS:
                    continue
                act = r.get("action_type", "?")
                st = r.get("status", "?")
                by_acct[acct][(act, st)] += 1
                total_actions += 1
                if st == "failed":
                    e = r.get("error", "?") or "?"
                    errs[e] += 1
                    acct_errs[acct][e] += 1
                if st == "success":
                    hourly[(acct, jst.strftime("%H"))] += 1

    # ── 出力 ──
    print(f"# Kensho パイプライン日次レポート: {date_s}")
    print(f"(生成: {datetime.datetime.now(JST).strftime('%Y-%m-%d %H:%M')} JST | アクション総数: {total_actions})")
    print()

    # アカウント別サマリ
    print("## アカウント別実績")
    print("| アカウント | 目標 | follow | rt | like | reply | 成功計 | 失敗計 | 達成率 |")
    print("|---|---|---|---|---|---|---|---|---|")
    for acct in ACCOUNTS:
        c = by_acct[acct]
        succ = sum(n for (a, s), n in c.items() if s == "success")
        fail = sum(n for (a, s), n in c.items() if s == "failed")
        tgt = targets.get(acct, 50)
        rate = f"{succ / tgt * 100:.0f}%" if tgt else "-"
        fl = c.get(("follow", "success"), 0)
        rt = c.get(("rt", "success"), 0)
        lk = c.get(("like", "success"), 0)
        rp = c.get(("reply", "success"), 0)
        flag = " ⚠️" if succ < tgt * 0.5 else ""
        print(f"| {acct} | {tgt} | {fl} | {rt} | {lk} | {rp} | {succ} | {fail} | {rate}{flag} |")

    # エラー内訳
    print()
    print("## 失敗エラー内訳（全体）")
    if errs:
        for e, n in errs.most_common(8):
            print(f"- `{e}`: {n}件")
    else:
        print("- なし")

    # アカウント別エラー
    heavy = {a: ec for a, ec in acct_errs.items() if sum(ec.values()) >= 10}
    if heavy:
        print()
        print("## 失敗10件以上のアカウント")
        for acct, ec in sorted(heavy.items()):
            desc = ", ".join(f"{e}={n}" for e, n in ec.most_common(3))
            print(f"- {acct}: {sum(ec.values())}件 ({desc})")

    # BOT安全監査の結果も併記（存在すれば）
    print()
    print("## BOT安全監査")
    try:
        import subprocess

        res = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "audit_bot_safety.py"), date_s],
            capture_output=True,
            text=True,
            timeout=60,
        )
        out = (res.stdout or "").strip()
        print(out if out else f"[audit_bot_safety] {date_s}: 実行結果なし")
    except Exception as e:
        print(f"[audit_bot_safety] 実行失敗: {e}")

    # 時系列の異常（1時間あたり15件超）
    hot = [(a, h, n) for (a, h), n in hourly.items() if n > 15]
    if hot:
        print()
        print("## 時間集中（1時間15件超）")
        for a, h, n in sorted(hot):
            print(f"- {a} {h}時台: {n}件")

    print()
    print("## 前日比（参考）")
    prev = (datetime.date.fromisoformat(date_s) - datetime.timedelta(days=1)).isoformat()
    prev_total = 0
    if AUDIT_PATH.exists():
        with open(AUDIT_PATH, encoding="utf-8") as f:
            for line in f:
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    continue
                jst = _jst_of(r.get("timestamp", ""))
                if jst and jst.strftime("%Y-%m-%d") == prev and r.get("account") in ACCOUNTS:
                    if r.get("status") == "success":
                        prev_total += 1
    if prev_total:
        diff = total_actions - prev_total
        arrow = "↑" if diff > 0 else ("↓" if diff < 0 else "→")
        print(f"- 前日({prev})成功: {prev_total}件 → 本日: {total_actions}件 ({arrow}{abs(diff)})")
    else:
        print(f"- 前日({prev})データなし")

    return 0


if __name__ == "__main__":
    sys.exit(main())
