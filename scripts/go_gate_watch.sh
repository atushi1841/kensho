#!/usr/bin/env bash
# ============================================================
# go_gate_watch.sh — critic v155 (t_a085ab68)
# 「GO承認ゲート自己通過」実事故検出（read-only + 通知のみ）
#
# 根拠事故: t_ed8baffa (2026-09-16 01:11, run490)
#   本文に「ユーザーGO必須」→ created(blocked) → promoted → claimed が
#   同一run内で10秒。作業者自身がGOゲートを素通りした（task_events 14257-14260）。
#
# 検出シグネチャ（3条件すべてを満たす claimed イベント）:
#   1. tasks.body に「ユーザーGO必須 / GO承認待ち / GO待ち」のいずれかを含む
#   2. 最初の created イベントの payload.status == "blocked"（= GO待ちで起票された）
#   3. その claimed より前に人間側GOイベント（unblocked / promoted_manual）が無い
#   → 過去ボード548件で該当は t_ed8baffa のみ（誤検知0の実測根拠はselftestに固定）
#
# 二重通知防止: state ファイルに検知済み task_id:run_id を保持（同一runは1回だけ）。
# 出力: 1行警告を logs/go_gate_watch.log + stdout（ai-context-monitor.sh 統合用）。
#       検知時は notify.sh 経由でTelegramへ直接通知（--no-notify で抑止可）。
#
# 制約: kanban DB は mode=ro で開く。台帳の強制blocked化・応募ロジック・
#       crontab・config.yaml には一切触れない（判定は人間/QAに委ねる）。
#
# テスト: bash go_gate_watch.sh --selftest  (tmp DB + fixture、実ボード非依存)
# ============================================================
set -uo pipefail

# 注意: workerセッションではHOMEがプロファイル配下へ書き換えられるため ~ に絶対依存しない。
# 既定値は /home/atushi 絶対アンカー（envで上書き可）。
SWEEPS_SCRIPTS="/home/atushi/.hermes/profiles/kensho-sweeps/scripts"
export GO_GATE_DEFAULT_LOG="${GO_GATE_DEFAULT_LOG:-$SWEEPS_SCRIPTS/logs/go_gate_watch.log}"
export GO_GATE_DEFAULT_STATE="${GO_GATE_DEFAULT_STATE:-$SWEEPS_SCRIPTS/state/go_gate_watch_state.json}"
export GO_GATE_NOTIFY_SH="${GO_GATE_NOTIFY_SH:-$SWEEPS_SCRIPTS/notify.sh}"

exec python3 - "$@" <<'PYEOF'
import argparse
import json
import os
import sqlite3
import subprocess
import sys
import time

MARKERS = ("ユーザーGO必須", "GO承認待ち", "GO待ち")
# HOME書き換え対策: 絶対パスを既定とし、無ければ expanduser にフォールバック。
_DB_CANDIDATES = (
    "/home/atushi/.hermes/kanban/boards/kensho-ai-team/kanban.db",
    os.path.expanduser("~/.hermes/kanban/boards/kensho-ai-team/kanban.db"),
)
DEFAULT_DB = next((p for p in _DB_CANDIDATES if os.path.exists(p)), _DB_CANDIDATES[0])
GO_EVENT_KINDS = ("unblocked", "promoted_manual")


def parse_args(argv):
    p = argparse.ArgumentParser(prog="go_gate_watch.sh")
    p.add_argument("--db", default=os.environ.get("GO_GATE_DB", DEFAULT_DB))
    p.add_argument("--state", default=os.environ.get("GO_GATE_STATE", ""))
    p.add_argument("--log", default=os.environ.get("GO_GATE_LOG", ""))
    p.add_argument("--no-notify", action="store_true",
                   help="notify.sh 経由のTelegram送信を抑止（テスト/selftest用）")
    p.add_argument("--selftest", action="store_true",
                   help="tmp DB + fixture で検出ロジックを検証して exit 0/1")
    args, _unknown = p.parse_known_args(argv)
    if not args.state:
        args.state = os.environ["GO_GATE_DEFAULT_STATE"]
    if not args.log:
        args.log = os.environ["GO_GATE_DEFAULT_LOG"]
    return args


def has_marker(body):
    return any(m in body for m in MARKERS)


def which_markers(body):
    return [m for m in MARKERS if m in body]


def detect(conn, state_alerted):
    """事故パターンに該当する新規 claimed を行dict一覧で返す（読み取りのみ）。"""
    alerts = []
    rows = conn.execute(
        "select id, title, status, body from tasks where body is not null"
    ).fetchall()
    for tid, title, status, body in rows:
        if not has_marker(body):
            continue
        events = conn.execute(
            "select id, kind, run_id, payload, created_at"
            " from task_events where task_id = ? order by id",
            (tid,),
        ).fetchall()
        created_blocked = None
        claim = None
        human_go = None
        for eid, kind, run_id, payload, created_at in events:
            if kind == "created" and created_blocked is None:
                try:
                    pstat = json.loads(payload).get("status") if payload else None
                except (ValueError, AttributeError):
                    pstat = None
                if pstat == "blocked":
                    created_blocked = (eid, created_at)
            elif kind in ("claimed", "spawned") and claim is None:
                # claimed を優先。claimed 欠落時のみ spawned をフォールバックに使う。
                if kind == "claimed":
                    claim = (eid, run_id, created_at)
                elif claim is None:
                    claim = (eid, run_id, created_at)
            elif kind in GO_EVENT_KINDS and human_go is None:
                human_go = (eid, created_at)
        if claim is None or created_blocked is None:
            continue
        # 人間GOが claimed より後（または存在しない）= ゲート素通り
        if human_go is not None and human_go[0] < claim[0]:
            continue
        run = claim[1] if claim[1] is not None else 0
        key = "%s:%s" % (tid, run)
        if key in state_alerted:
            continue
        gap = claim[2] - created_blocked[1]
        alerts.append({
            "key": key,
            "task": tid,
            "run": run,
            "status": status,
            "title": title or "",
            "markers": which_markers(body),
            "claim_event": claim[0],
            "gap_seconds": gap,
            "at": claim[2],
        })
    return alerts


def format_line(a):
    return ("GO-GATE WARNING task=%s run=%s claim_event=%s gap_from_created=%ds "
            "status=%s markers=%s title=\"%s\" — GO未承認で claimed/running"
            "（t_ed8baffa事故パターン: created(blocked)→promoted→claimed）。"
            "判定は人間/QA委譲（本監視は強制block化しない）" % (
                a["task"], a["run"], a["claim_event"], a["gap_seconds"],
                a["status"], "+".join(a["markers"]), a["title"][:60]))


def write_log(log_path, line):
    try:
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write("[%s] %s\n" % (ts, line))
    except OSError:
        pass


def load_state(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        alerted = data.get("alerted")
        return set(alerted) if isinstance(alerted, list) else set()
    except (OSError, ValueError):
        return set()


def save_state(path, alerted):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"alerted": sorted(alerted)}, f, ensure_ascii=False, indent=1)
        os.replace(tmp, path)
    except OSError:
        pass


def open_ro(db_path):
    uri = "file:%s?mode=ro" % db_path
    return sqlite3.connect(uri, uri=True)


def run_watch(args):
    if not os.path.exists(args.db):
        return 0
    state = load_state(args.state)
    try:
        conn = open_ro(args.db)
    except sqlite3.Error:
        return 0
    try:
        alerts = detect(conn, state)
    finally:
        conn.close()
    lines = []
    for a in sorted(alerts, key=lambda x: x["claim_event"]):
        line = format_line(a)
        write_log(args.log, line)
        lines.append(line)
        state.add(a["key"])
    save_state(args.state, state)
    if lines:
        for line in lines:
            print(line)
        if not args.no_notify:
            notify_sh = os.environ.get("GO_GATE_NOTIFY_SH", "")
            if notify_sh and os.path.exists(notify_sh):
                text = "⚠️ [GO-GATE v155] GO承認ゲート自己通過の疑い %d件:\n%s" % (
                    len(lines), "\n".join(lines))
                try:
                    subprocess.run(
                        ["bash", notify_sh, text],
                        timeout=15, check=False,
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                except Exception:
                    pass
    return 0


# ---------------------------------------------------------------- selftest
SCHEMA = """
create table tasks (
    id TEXT PRIMARY KEY, title TEXT NOT NULL DEFAULT '', body TEXT,
    assignee TEXT, status TEXT NOT NULL DEFAULT 'todo'
);
create table task_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL, run_id INTEGER, kind TEXT NOT NULL,
    payload TEXT, created_at INTEGER NOT NULL
);
"""

T0 = 1789488680


def build_fixture_db(path):
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)

    def add_task(tid, body, status="blocked"):
        conn.execute("insert into tasks(id,title,body,status) values(?,?,?,?)",
                     (tid, "fixture " + tid, body, status))

    def ev(tid, kind, at, run_id=None, payload=None):
        conn.execute("insert into task_events(task_id,run_id,kind,payload,created_at)"
                     " values(?,?,?,?,?)", (tid, run_id, kind, payload, T0 + at))

    # 1) 事故そのもの: t_ed8baffa 再現 → 検知 Must
    add_task("t_incident01", "本番投入前にユーザーGO必須。Telegram経由のみ承認。", "blocked")
    ev("t_incident01", "created", 0, payload=json.dumps({"status": "blocked"}))
    ev("t_incident01", "promoted", 10)
    ev("t_incident01", "claimed", 10, run_id=490,
       payload=json.dumps({"lock": "N100:477", "run_id": 490}))
    ev("t_incident01", "spawned", 10, run_id=490)
    # 2) 誤検知確認: 通常カード（GOマーカーなし）の claimed
    add_task("t_clean01", "収集ログの定期ローテート", "done")
    ev("t_clean01", "created", 0, payload=json.dumps({"status": "todo"}))
    ev("t_clean01", "promoted", 5)
    ev("t_clean01", "claimed", 6, run_id=491)
    # 3) 誤検知確認: ready 起票（GOマーカーあり・blocked起票でない）
    #    = t_cafe0cdd/t_b9a55d7a の実データ形状
    add_task("t_ready01", "research提案A・ユーザーGO承認済みで起票", "done")
    ev("t_ready01", "created", 0, payload=json.dumps({"status": "ready"}))
    ev("t_ready01", "claimed", 3, run_id=492)
    # 4) 誤検知確認: 人間GO(unblocked)後の claimed = 正常フロー
    add_task("t_go01", "ユーザーGO必須の適用カード", "running")
    ev("t_go01", "created", 0, payload=json.dumps({"status": "blocked"}))
    ev("t_go01", "unblocked", 3600)
    ev("t_go01", "promoted", 3610)
    ev("t_go01", "claimed", 3620, run_id=493)
    # 5) 誤検知確認: メタ記述カード（監視自身=本カード形状。created=todo）
    add_task("t_meta01", "本文にユーザーGO必須 / GO承認待ち / GO待ち を列挙する監視の説明", "running")
    ev("t_meta01", "created", 0, payload=json.dumps({"status": "todo"}))
    ev("t_meta01", "unlinked", 5)
    ev("t_meta01", "promoted", 6)
    ev("t_meta01", "claimed", 8, run_id=500)
    conn.commit()
    conn.close()


def run_selftest():
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        db = os.path.join(td, "board.db")
        state = os.path.join(td, "state.json")
        log = os.path.join(td, "logs", "go_gate_watch.log")
        build_fixture_db(db)
        conn = open_ro(db)
        alerts = detect(conn, set())
        conn.close()
        got = sorted(a["task"] for a in alerts)
        if got != ["t_incident01"]:
            print("SELFTEST FAIL: 検知一覧が不正 %r（期待 ['t_incident01'] / 誤検知0）" % got)
            return 1
        # 二重通知防止: 同一 task:run は state 投入後に出ない
        conn = open_ro(db)
        alerted = {a["key"] for a in alerts}
        second = detect(conn, alerted)
        conn.close()
        if second:
            print("SELFTEST FAIL: dedup 失敗 %r" % [a["key"] for a in second])
            return 1
        # 本番経路（watch/log/state）が end-to-end で動作
        args = argparse.Namespace(db=db, state=state, log=log, no_notify=True)
        rc = run_watch(args)
        if rc != 0 or not os.path.exists(log):
            print("SELFTEST FAIL: watch/log 経路 rc=%s log=%s" % (rc, os.path.exists(log)))
            return 1
        with open(log, encoding="utf-8") as f:
            log_lines = [l for l in f.read().splitlines() if l.strip()]
        if len(log_lines) != 1 or "t_incident01" not in log_lines[0]:
            print("SELFTEST FAIL: ログ内容不正 %r" % log_lines)
            return 1
        # 2周目: state 済みなので無出力（誤検知0・再通知0）
        args2 = argparse.Namespace(db=db, state=state, log=log, no_notify=True)
        rc2 = run_watch(args2)
        if rc2 != 0:
            print("SELFTEST FAIL: 2周目 rc=%s" % rc2)
            return 1
        with open(log, encoding="utf-8") as f:
            if len([l for l in f.read().splitlines() if l.strip()]) != 1:
                print("SELFTEST FAIL: 2周目で再通知が発生")
                return 1
        # 実ボード読み取り権限（存在時のみ。壊れても自己終了しない）
        if os.path.exists(DEFAULT_DB):
            conn = open_ro(DEFAULT_DB)
            real = detect(conn, {"t_incident01:490"})
            conn.close()
            print("SELFTEST INFO: 実ボード検知可能件数=%d（state dedup後、本番次回tick分）"
                  % len(real))
        print("SELFTEST OK: 検出1件/誤検知0件/dedup/再通知0/exit0")
        return 0


def main():
    args = parse_args(sys.argv[1:])
    if args.selftest:
        return run_selftest()
    return run_watch(args)


sys.exit(main())
PYEOF
