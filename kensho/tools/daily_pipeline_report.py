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

ACCOUNTS = ["atushi16", "kudou", "chugakujuken", "zin20120731", "TankanNotes", "inobase1-4", "toushiwatch"]
DEFAULT_TARGET = {
    "atushi16": 75,
    "kudou": 50,
    "chugakujuken": 50,
    "zin20120731": 50,
    "TankanNotes": 50,
    "inobase1-4": 50,
    "toushiwatch": 50,
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
    real_success: dict[str, collections.Counter] = collections.defaultdict(
        collections.Counter
    )  # acct -> action -> n（already_*除外）
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
                    reason = r.get("reason", "") or ""
                    if reason.startswith("already_"):
                        # already_liked/already_retweeted は新規アクションを伴わないため
                        # 成功・時間帯集計から除外（prop101, 2026-09-01）
                        continue
                    hourly[(acct, jst.strftime("%H"))] += 1
                    real_success[acct][act] += 1

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
        rs = real_success[acct]
        succ = sum(rs.values())
        fail = sum(n for (a, s), n in c.items() if s == "failed")
        tgt = targets.get(acct, 50)
        rate = f"{succ / tgt * 100:.0f}%" if tgt else "-"
        fl = rs.get("follow", 0)
        rt = rs.get("rt", 0)
        lk = rs.get("like", 0)
        rp = rs.get("reply", 0)
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

    # ── セッション健全性 ──
    print()
    print("## セッション健全性（x_session_*.json 最終更新）")
    now = datetime.datetime.now(JST)
    sess_dir = ROOT / "data"
    for f in sorted(sess_dir.glob("x_session_*.json")):
        mtime = datetime.datetime.fromtimestamp(f.stat().st_mtime, JST)
        age_h = (now - mtime).total_seconds() / 3600
        flag = " ⚠️ 更新停滞（24h超）" if age_h > 24 else ""
        print(f"- {f.name}: 更新 {mtime.strftime('%m/%d %H:%M')}（{age_h:.0f}時間前）{flag}")

    # ── 時間帯分散（BOTリスク監視） ──
    print()
    print("## 応募時間帯分散（BOTリスク監視）")
    acct_hours: dict[str, set[str]] = collections.defaultdict(set)
    for (a, h), n in hourly.items():
        if n > 0:
            acct_hours[a].add(h)
    for acct in ACCOUNTS:
        hours = sorted(acct_hours.get(acct, []))
        if not hours:
            print(f"- {acct}: 成功アクションなし")
            continue
        spread = len(hours)
        flag = " ⚠️ 1-2時間帯に集中" if spread <= 2 else ""
        print(f"- {acct}: {spread}時間帯に分散 {hours}{flag}")

    # ── バッチ計画 vs 実績 ──
    # 計画数は config の daily_target（未設定ならデフォルト）を使用。
    # 従来は sum(batches[].max)（1バッチ上限の合計）だったが、実目標と乖離し
    # 「消化率50%未満」の誤警告を生んでいた（提案28, 2026-08-27）。
    print()
    print("## バッチ計画 vs 実績")
    for acct in ACCOUNTS:
        batches: list = []
        if isinstance(acct_cfg, list):
            for a in acct_cfg:
                if isinstance(a, dict) and a.get("key") == acct:
                    batches = (a.get("schedule", {}) or {}).get("batches", []) or []
        n_batches = len(batches)
        succ = sum(real_success[acct].values())
        planned = targets.get(acct, 50)  # 日次目標（daily_target or デフォルト）
        if planned:
            rate = f"{succ / planned * 100:.0f}%"
            flag = " ⚠️ 消化率50%未満" if succ < planned * 0.5 else ""
            print(f"- {acct}: 目標{planned}件/{n_batches}バッチ → 実績{succ}件（{rate}）{flag}")
        else:
            print(f"- {acct}: 目標情報なし → 実績{succ}件")

    # ── 収集→応募の変換率 ──
    print()
    print("## 収集→応募の変換率")
    try:
        col_path = ROOT / "data" / "collected.json"
        if col_path.exists():
            col = json.loads(col_path.read_text(encoding="utf-8"))
            items = col.get("collected", []) if isinstance(col, dict) else []
            n_new = col.get("new_items_processed", 0) if isinstance(col, dict) else 0
            succ_all = sum(sum(rs.values()) for a, rs in real_success.items() if a in ACCOUNTS)
            if items:
                print(f"- 収集ツイート数: {len(items)}件（新規処理: {n_new}件）")
                print(f"- 全垢応募成功合計: {succ_all}件 → 変換率: {succ_all / len(items) * 100:.1f}%")
            else:
                print("- 収集データなし（collected.json空）")
        else:
            print("- collected.json なし")
    except Exception as e:
        print(f"- 変換率計算失敗: {e}")

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
