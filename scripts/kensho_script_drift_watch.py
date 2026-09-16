#!/usr/bin/env python3
"""kensho_script_drift_watch.py — cron配置driftの5分監視+Telegram通知（t_20c9c446 / QA run508）

背景: 既存 kensho_script_drift_check.py（no_agent cron 8c1271fd2158・毎朝08:50）は
  drift検出できるが粒度が1日1回。事故実例 5f32176（apify_run_monitor.py: repo修正済・
  cron配置が旧版のまま数時間稼働）では、検出まで最大丸1日の盲点があった。
  → ai-context-monitor.sh（crontab 5分毎）から本ラッパを呼び、DRIFT/MISSING 発生時に
  state dedupで1回だけ notify.sh 経由でTelegram通知する（go_gate_watch.sh v155と同形式）。

契約:
  - stdout = 現在のFAIL行を毎回出力（monitorログにDRIFTが1行出現 / cp同期後は無出力）。
    crontab側でstdoutは破棄されるため、通知は本スクリプトが直接 notify.sh 経由で行う。
  - 通知dedup: stateファイルに script名→初検知ts を保持。同一scriptの再通知はしない。
    解消（DRIFT→一致）されたらstateから除去し、次回再漂移時のみ再通知。
  - 検出失敗時のみexit 0維持（呼び出し側monitorを止めない）。監査基盤異常はstderr+exit 1。
  - ドライラン: --no-notify（通知抑止・ログ/stdoutは通常）。--state/--log でパス上書き可。

使い方:
  python3 kensho_script_drift_watch.py [--no-notify]
  環境変数: DRIFT_CHECK_PY / KENSHO_DRIFT_STATE / KENSHO_DRIFT_LOG / KENSHO_DRIFT_NOTIFY_SH
            / DRIFT_JOBS / KENSHO_ROOT（DRIFT_JOBS・KENSHO_ROOTはcheck側へそのまま継承）
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

SWEEPS_SCRIPTS = "/home/atushi/.hermes/profiles/kensho-sweeps/scripts"
DEFAULT_CHECK = Path(
    os.environ.get("DRIFT_CHECK_PY") or Path(__file__).resolve().parent / "kensho_script_drift_check.py"
)
DEFAULT_STATE = os.environ.get("KENSHO_DRIFT_STATE", f"{SWEEPS_SCRIPTS}/state/script_drift_watch_state.json")
DEFAULT_LOG = os.environ.get("KENSHO_DRIFT_LOG", f"{SWEEPS_SCRIPTS}/logs/script_drift_watch.log")
DEFAULT_NOTIFY = os.environ.get("KENSHO_DRIFT_NOTIFY_SH", f"{SWEEPS_SCRIPTS}/notify.sh")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(prog="kensho_script_drift_watch.py")
    ap.add_argument("--check", default=str(DEFAULT_CHECK))
    ap.add_argument("--state", default=os.environ.get("KENSHO_DRIFT_STATE", DEFAULT_STATE))
    ap.add_argument("--log", default=os.environ.get("KENSHO_DRIFT_LOG", DEFAULT_LOG))
    ap.add_argument("--notify-sh", default=os.environ.get("KENSHO_DRIFT_NOTIFY_SH", DEFAULT_NOTIFY))
    ap.add_argument("--no-notify", action="store_true", help="Telegram送信を抑止（テスト用）")
    return ap.parse_args(argv)


def load_state(path: str) -> dict:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return {}


def run_check(check_py: str) -> dict:
    proc = subprocess.run(
        [sys.executable, check_py, "--json"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"drift check failed rc={proc.returncode}: {proc.stderr[:200]}")
    line = proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else "{}"
    return json.loads(line)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        data = run_check(args.check)
    except Exception as e:  # 監視基盤の失敗は呼び出し側を止めない
        print(f"script-drift-watch: ERROR {e}", file=sys.stderr)
        return 0

    fails = data.get("fails") or []
    names = [f"{r['status']}:{r['script']}" for r in fails]
    now = int(time.time())

    state_path = Path(args.state)
    state = load_state(args.state)
    notified: dict = dict(state.get("notified") or {})

    # 解消されたエントリを除去（再漂移時のみ再通知）
    for key in list(notified.keys()):
        if key not in names:
            del notified[key]

    fresh = [n for n in names if n not in notified]
    for n in fresh:
        notified[n] = now

    for r in fails:
        # monitor出力契約: DRIFT/MISSING 行を毎回表示（cp同期後は無出力）
        print(f"DRIFT-WATCH [{r['status']}] {r['script']} job={r.get('job')} ({r.get('profile')}/{r.get('job_id')})")

    if fresh and not args.no_notify:
        msg = (
            f"⚠️ cronスクリプト漂移 {len(fresh)}件（5分監視）: "
            + ", ".join(fresh)
            + " — 対策: cp <repo版> <profile scripts dir>（md5一致確認→次回cronで反映）"
        )
        try:
            subprocess.run(["bash", args.notify_sh, msg], capture_output=True, text=True, timeout=15)
        except Exception as e:
            print(f"script-drift-watch: notify failed {e}", file=sys.stderr)

    if fails or state.get("notified"):
        try:
            state_path.parent.mkdir(parents=True, exist_ok=True)
            state_path.write_text(
                json.dumps({"notified": notified, "updated_at": now}, ensure_ascii=False),
                encoding="utf-8",
            )
            log_path = Path(args.log)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            ts = time.strftime("%Y-%m-%d %H:%M:%S")
            if fresh:
                with log_path.open("a", encoding="utf-8") as fh:
                    for n in fresh:
                        fh.write(f"{ts} WARN {n}\n")
            elif not fails:
                with log_path.open("a", encoding="utf-8") as fh:
                    fh.write(f"{ts} RESOLVED (all synced)\n")
        except OSError as e:
            print(f"script-drift-watch: state write failed {e}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
