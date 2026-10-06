#!/usr/bin/env bash
# Loop Health Checker v141 (t_5af1b5d8: bare hermes絶対パス解決 / t_e474c675: business KPI gate完成マーカー修正 / t_08b42528: business KPI gate / t_296c3dbc: top_task不倒修正 / t_5086aef7: PARK_AFTER_H gate)
# Detects Kanban loop stagnation and escalates via Telegram.
# HARD LIMIT: Output max 5 lines.
#
# v141 changes (2026-09-24, t_5af1b5d8):
#   - cron の最小PATH(/usr/bin:/bin)では bare `hermes` が解決できず、下記6箇所の
#     呼出が全て空を返し running/blocked が無音で 0 に縮退していた (score は 100 の
#     まま ALERT も escalation も出ず、advice.priority=blocked_triage が二度と出ない
#     = AIチーム全ジョブの行動方針選択が壊れる)。HERMES_VENV_BIN(既定
#     /home/atushi/.hermes/hermes-agent/venv/bin) を PATH 前置 → command -v hermes
#     フォールバック の順で HERMES_BIN を解決し、解決不能時に CLI が必須なら PATH と
#     HERMES_VENV_BIN を stderr に記録して exit 127（無音縮退の再発防止）。
#   - 置換箇所: 142/143(blocked/running 取得)・431(backlog 先頭)・487(park対象の
#     status)・496/498([loop-health] comment/schedule = auto-park 通報路)。
#   - 判定ロジック・閾値・score 計算・advice 文言・JSON スキーマは一切不変。
#   - --tasks/--db 注入時は CLI 不要なので縮退させない(WARN のみで継続)。
#
# v139 changes (2026-09-17, t_e474c675):
#   - business KPI gate の完成マーカー修正: grep "OK 完了" は実ログ(auto_<YMD>.log)の
#     完了行形式 "[OK] 完了: N成功 / Mエラー"・INFO 行 "完了: N成功/Mエラー（Xs秒）" に
#     一致せず常に 0 → 毎日 business_ok:false の偽陽性WARN。完了行が「成功>0 の応募完了
#     + 完了行 0 判定」を満たすよう正規表現 r"完了:\s*\d+成功" で件数を数える
#     (稼働日9/15=96件 / 停止日9/17=0件)。
#
# v138 changes (2026-09-17, t_08b42528):
#   - business KPI gate: 当日ログ(auto_<YMD>.log)の完了行数 grep "OK 完了" を数え、
#     JST 09:00以降(no_action_window 外)で完了行=0 のとき apply stopped と判定。
#     score を上限60に制限、JSON に "business_ok": false、alert を "WARN: apply stopped" に変更。
#   - LOOPHEALTH_LOG_PATH でログパス上書き(テスト用)、LOOPHEALTH_JST_HOUR で時刻を再現(テスト用)。
#   - no_action_window は config.yaml orchestrator.no_action_window から読取(既定 00:00-07:00)。
#
# v133 changes (2026-09-11, kensho-revenue-worker):
#   - PARK_AFTER_H (default 24h): once escalation has been ACTIVE CONTINUOUSLY for
#     longer than PARK_AFTER_H (measured by state.escalated_at), the SLA-breached
#     task is auto-commented + scheduled ("parked") on the board.
#   - state.escalated_at: epoch of the false→true transition of escalation.active.
#     Cleared when escalation deactivates. (Fixes v30 bug: escalated_at never
#     existed so the 24h gate could never fire.)
#   - Park cooldown (state.park_cooldown_until, default 2 ticks ≈ 6h) + idempotency
#     (task already 'scheduled' → no-op) so a park cannot spam the board.
#   - Park reason comment carries "[loop-health]" marker for auditability.
#   - Single final state write (was 3 duplicated jq rewrites that dropped
#     last_escalate_streak / escalated_at depending on branch — v30 bug #3 class).
#   - JSON output adds: escalated_at, park_after_h, park_action.
# v133b changes (2026-09-12, QA run395 申し送り①):
#   - park 成功時に持続 band (last_escalate_streak/last_low_band/escalated_at) を
#     現 streak へ再設定。放置すると band が streak を上回ったまま不変条件
#     (last_escalate_streak <= streak) を破り、healthy board でも escalation が
#     true のまま cooldown ごとに別 target を連続 park する（v92指標2 FAIL 真因）。
# v133c changes (2026-09-12, t_8fed223a QA run411 — v92回帰の再導入):
#   - v133 リライトで失われた v92 (7327ab7, t_f3533056) の時刻ベース dedup 窓を
#     park gate へ再導入。同一 result/同一 target を PARK_DEDUP_WINDOW_S (既定
#     1800s=30分) 以内の再実行で再評価しない: 2回連続実行の2回目は
#     park_action=dedup_skip を返し last_park_target は切り替わらない。
#     連続park（別target含む）は last_park_result="parked" 窓で遮断 — park
#     cooldown(1h)より短いスパンで escalation 別 target を連続 park する v92
#     真因（自動復旧阻害）の再発防止。dedup_skip は窓をスライドさせない
#     ため last_park_result/_ts を更新しない。
# v137 changes (2026-09-12, t_296c3dbc QA 9/12実測):
#   - top_task 不倒 bug 修正: by_age は started_at 昇順(先頭=最古)なのに
#     line 226/248 が by_age[-1]=最新規を拾っており、2件以上 running の時
#     park/escalation target が最古でなく最新になる → SLA parking(24h超滞留
#     判定)が空振りする。both を by_age[0]=最古running に統一。
#     不変条件「top_task=最古running」は tests/test_loop_health.py で固定。
#
# Usage:
#   bash loop_health.sh [OPTIONS]
#
# OPTIONS:
#   --db PATH       kanban.db path (default: auto-detect)
#   --threshold N   score threshold to trigger alert (default: 70, alert if score < N)
#   --tasks JSON    task list JSON from hermes kanban list
#   --board NAME    kanban board name for hermes CLI fallback (default: kensho-ai-team)
#   --park-after-h H  hours of continuous escalation before auto-park (default: 24)
#   --no-park       detect+report but never schedule (dry-run of the park lane only)
#   --state PATH    state file for streak tracking
#   --dry-run       print only, no side effects on the board

DB_PATH="${HERMES_KANBAN_DB:-$HOME/.hermes/kanban.db}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
THRESHOLD=70
TASKS_JSON=""
BOARD="kensho-ai-team"
STATE_FILE="${HERMES_HOME:-$HOME/.hermes/profiles/kensho-sweeps}/data/loop_health_state.json"
PARK_AFTER_H="${PARK_AFTER_H:-24}"
PARK_COOLDOWN_S="${PARK_COOLDOWN_S:-21600}"   # 6h between park actions
PARK_DEDUP_WINDOW_S="${PARK_DEDUP_WINDOW_S:-1800}"   # v133c: 30分窓の時刻dedup (v92回帰の再導入)
NO_PARK=0
DRY_RUN=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --db) DB_PATH="$2"; shift 2 ;;
    --threshold) THRESHOLD="$2"; shift 2 ;;
    --tasks) TASKS_JSON="$2"; shift 2 ;;
    --board) BOARD="$2"; shift 2 ;;
    --park-after-h) PARK_AFTER_H="$2"; shift 2 ;;
    --no-park) NO_PARK=1; shift ;;
    --state) STATE_FILE="$2"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    --now) NOW="$2"; shift 2 ;;
    *) shift ;;
  esac
done

# ─── hermes CLI resolution (v141 / t_5af1b5d8) ──────────────────────────────
# cron の最小PATH(/usr/bin:/bin)では bare `hermes` が解決できず、blocked/running の
# 取得が空を返して無音で 0 件に縮退する。HERMES_VENV_BIN を PATH 前置 →
# command -v hermes フォールバック → それでも駄目なら PATH と HERMES_VENV_BIN を
# stderr に記録して非0終了（CLI が必須な場合のみ。--tasks/--db 注入時は WARN のみ）。
HERMES_VENV_BIN="${HERMES_VENV_BIN:-/home/atushi/.hermes/hermes-agent/venv/bin}"
[ -d "$HERMES_VENV_BIN" ] && PATH="$HERMES_VENV_BIN:$PATH"
if [ -z "${HERMES_BIN:-}" ] || [ ! -x "${HERMES_BIN:-}" ]; then
  if command -v hermes >/dev/null 2>&1; then
    HERMES_BIN="$(command -v hermes)"
  else
    HERMES_BIN=""
  fi
fi
if [ -z "${HERMES_BIN:-}" ]; then
  echo "loop_health: ERROR: hermes CLI not found (PATH=${PATH}, HERMES_VENV_BIN=${HERMES_VENV_BIN})" >&2
  if [ -n "$TASKS_JSON" ] || [ -n "${TASKS_JSON_OVERRIDE:-}" ]; then
    echo "loop_health: WARN: continuing with injected task list (no board CLI needed)" >&2
  else
    echo "loop_health: ERROR: cannot read kanban board state; refusing to silently degrade to 0 running/blocked" >&2
    exit 127
  fi
fi

# ─── Auto-detect DB if not found / empty ──────────────────────────────────────
# v143 (t_6f45dab0): 空レガシー DB (~/.hermes/kanban.db, tasks 0) を grasp する
# と effective_started_at が空 → tasks.started_at(初回dispatchのstale値)に
# フォールバックし、age が 12h と偽判定される(伪age -25)。existence チェックではなく
# tasks>0 を条件に board DB を優先する。run が取れれば age penalty を skip する。
_db_has_tasks() {
  local _p="$1"
  [[ -f "$_p" ]] || return 1
  local _n
  # sqlite3 CLI が無い環境（cron最小PATH等）でも動くよう python3(stdlib sqlite3) を優先。
  # CLI がなければ python3 にフォールバック。両方不可なら false（空DBと同様に扱う）。
  if command -v sqlite3 >/dev/null 2>&1; then
    _n=$(sqlite3 "$_p" "SELECT count(*) FROM tasks;" 2>/dev/null || echo 0)
  else
    # v144 (t_ea20095f): `python3 -c` は cron最小PATH/単クエリモードでブロックされ、
    # 1 try/except の構文エラーで board DB を見つける前に空レガシーDBに grav した。
    # スクリプトファイル経由で同等の count を返す。
    _n=$(python3 "$SCRIPT_DIR/_db_count.py" "$_p" 2>/dev/null || echo 0)
  fi
  [[ "$_n" =~ ^[0-9]+$ ]] && [ "$_n" -gt 0 ]
}
if ! _db_has_tasks "$DB_PATH"; then
  for board in kensho-ai-team default; do
    cand="$HOME/.hermes/kanban/boards/$board/kanban.db"
    if _db_has_tasks "$cand"; then
      DB_PATH="$cand"
      BOARD="$board"
      break
    fi
  done
fi
# 見つからずとも DB_PATH は存在するファイル（空レガシー）のまま——effective_started_at
# 取得は try/exit で無害。tasks.started_at フォールバックは最終手段。

mkdir -p "$(dirname "$STATE_FILE")" 2>/dev/null

# ─── Read previous state ─────────────────────────────────────────────────────
PREV_STREAK=0
PREV_ESCALATE_STREAK=0
PREV_LOW_BAND=0
PREV_ESCALATED_AT=""
PREV_PARK_CD=0
PREV_PARK_TS=""
PREV_PARK_RESULT=""
PREV_PARK_TARGET=""
if [[ -f "$STATE_FILE" ]]; then
  PREV_STREAK=$(jq -r '.streak // 0' "$STATE_FILE" 2>/dev/null)
  PREV_ESCALATE_STREAK=$(jq -r '.last_escalate_streak // 0' "$STATE_FILE" 2>/dev/null)
  PREV_LOW_BAND=$(jq -r '.last_low_band // 0' "$STATE_FILE" 2>/dev/null)
  PREV_ESCALATED_AT=$(jq -r '.escalated_at // empty' "$STATE_FILE" 2>/dev/null)
  PREV_PARK_CD=$(jq -r '.park_cooldown_until // 0' "$STATE_FILE" 2>/dev/null)
  PREV_PARK_TS=$(jq -r '.last_park_ts // empty' "$STATE_FILE" 2>/dev/null)
  PREV_PARK_RESULT=$(jq -r '.last_park_result // empty' "$STATE_FILE" 2>/dev/null)
  PREV_PARK_TARGET=$(jq -r '.last_park_target // empty' "$STATE_FILE" 2>/dev/null)
fi
[[ "$PREV_STREAK" =~ ^[0-9]+$ ]] || PREV_STREAK=0
[[ "$PREV_ESCALATE_STREAK" =~ ^[0-9]+$ ]] || PREV_ESCALATE_STREAK=0
[[ "$PREV_LOW_BAND" =~ ^[0-9]+$ ]] || PREV_LOW_BAND=0
[[ "$PREV_ESCALATED_AT" =~ ^[0-9]+$ ]] || PREV_ESCALATED_AT=""
[[ "$PREV_PARK_CD" =~ ^[0-9]+$ ]] || PREV_PARK_CD=0
[[ "$PREV_PARK_TS" =~ ^[0-9]+$ ]] || PREV_PARK_TS=""

# ─── Fetch tasks if not provided ─────────────────────────────────────────────
# QA修正(2026-09-12 02:00): ①--tagsはhermes CLIに存在せずusageエラー→stale DB
# fallbackでsignature凍結の原因 ②full list(741KB)をenvに流すとArgument list
# too long。対策: blocked/runningのみCLI取得(分析が使うのはこの2状態だけ)+
# テンポラリファイル経由でpythonに_handoff(2026-09-05教訓準拠)。
if [[ -z "$TASKS_JSON" ]]; then
  if [[ -n "$TASKS_JSON_OVERRIDE" ]]; then
    TASKS_JSON="$TASKS_JSON_OVERRIDE"
  else
    _TASKS_TMP=$(mktemp /tmp/loop_health_tasks.XXXXXX.json)
    _B=$("$HERMES_BIN" kanban --board "$BOARD" list --json --status blocked 2>/dev/null)
    _R=$("$HERMES_BIN" kanban --board "$BOARD" list --json --status running 2>/dev/null)
    printf '%s' "${_B:-[]}" > "${_TASKS_TMP}.b"
    printf '%s' "${_R:-[]}" > "${_TASKS_TMP}.r"
    jq -s 'add // []' "${_TASKS_TMP}.b" "${_TASKS_TMP}.r" > "$_TASKS_TMP" 2>/dev/null \
      || echo '[]' > "$_TASKS_TMP"
    rm -f "${_TASKS_TMP}.b" "${_TASKS_TMP}.r"
    TASKS_FILE="$_TASKS_TMP"
  fi
fi

if [[ -z "$TASKS_JSON" && -z "$TASKS_FILE" ]]; then
  # DB fallback — use python3 (stdlib sqlite3) because sqlite3 CLI may be absent
  TASKS_JSON=$(python3 -c "
import sqlite3, json, sys
db = '$DB_PATH'
try:
    conn = sqlite3.connect('file:' + db + '?mode=ro', uri=True)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(\"SELECT id, status, title, result, started_at FROM tasks WHERE status IN ('running','blocked') ORDER BY started_at ASC LIMIT 100\").fetchall()
    print(json.dumps([dict(r) for r in rows]))
except Exception:
    print('[]')
" 2>/dev/null)
fi

if [[ -z "$TASKS_FILE" ]]; then
  [[ -z "$TASKS_JSON" ]] && TASKS_JSON="[]"
  TASKS_FILE=$(mktemp /tmp/loop_health_tasks.XXXXXX.json)
  printf '%s' "$TASKS_JSON" > "$TASKS_FILE"
fi
trap 'rm -f "$TASKS_FILE"' EXIT

NOW=$(date +%s)
export _LH_TASKS_FILE="$TASKS_FILE" _LH_NOW="$NOW" _LH_PREV="$PREV_STREAK" _LH_DB="$DB_PATH"
export _LH_MAX_IN_PROGRESS

# ─── Analyze ─────────────────────────────────────────────────────────────────
ANALYSIS=$(python3 - <<'PYEOF'
import json, os, re, sqlite3, time, sys, datetime as _dt

tasks = json.loads(open(os.environ.get("_LH_TASKS_FILE", "/dev/null")).read() or "[]")
now = int(os.environ.get("_LH_NOW", str(int(time.time()))))
prev_streak = int(os.environ.get("_LH_PREV", "0"))

# v137b (t_83ce94c5): tasks.started_at = 初回 attempt 時刻で dispatch 後更新されない。
# 16h 停滞と誤判定するため task_runs.status='running' の最新 started_at を参照する。
# DB 不可・未取得時は tasks.started_at にフォールバック。
runs_started_at = None
try:
    _dbp = os.environ.get("_LH_DB", "")
    if _dbp and os.path.exists(_dbp):
        with sqlite3.connect("file:%s?mode=ro" % _dbp, uri=True) as _c:
            _r = _c.execute(
                "SELECT MAX(started_at) FROM task_runs WHERE status='running'"
            ).fetchone()
            if _r and _r[0]:
                runs_started_at = int(_r[0])
except Exception:
    runs_started_at = None

running = [t for t in tasks if t.get("status") == "running"]
blocked = [t for t in tasks if t.get("status") == "blocked"]

# Detect same-result repeat (v142: 定義が v142 リライトで失われていたため再導入)
results = {}
for t in tasks:
    res = t.get("result") or ""
    if res:
        results.setdefault(res, []).append(t["id"])

repeats = {r: ids for r, ids in results.items() if len(ids) >= 2}

# Detect blocked tasks whose parent is done (wasteful block)
blocked_with_done_parent = []
for t in blocked:
    res = t.get("result") or ""
    if "already completed" in res.lower() or "no action needed" in res.lower():
        blocked_with_done_parent.append(t["id"])

# v137b+ (t_83ce94c5): tasks.started_at = 初回 dispatch 時刻で更新されない。
# 実活動時刻を task_runs.status='running' の最新 started_at から取得。
# 各タスクごとに effective_started_at を構築し、ソート・減点・top_task
# の年齢計算に使う。DB 不可・未取得時は tasks.started_at にフォールバック。
effective_started_at = {}
try:
    _dbp = os.environ.get("_LH_DB", "")
    if _dbp and os.path.exists(_dbp):
        with sqlite3.connect("file:%s?mode=ro" % _dbp, uri=True) as _c:
            _c.row_factory = sqlite3.Row
            _running_rows = _c.execute(
                "SELECT task_id, MAX(started_at) AS max_started "
                "FROM task_runs WHERE status='running' GROUP BY task_id"
            ).fetchall()
            for _r in _running_rows:
                effective_started_at[_r["task_id"]] = int(_r["max_started"])
except Exception:
    pass


# Override effective_started_at from environment for testing (v143: env注入で回帰テストを可能に)
try:
    _eff_override = os.environ.get("_LH_EFFECTIVE_STARTED_AT", "")
    if _eff_override:
        effective_started_at.update(json.loads(_eff_override))
except Exception:
    pass


# ソートと age 減点に使う effective_started_at（DB 取得あれば上書き）
by_age = sorted(
    running,
    key=lambda t: (effective_started_at.get(t["id"], t.get("started_at") or now)),
    reverse=False,
)

# ── Score calculation (v142 / t_9f14ee5d) ──────────────────────────────
# config-based max_in_progress penalty, streak reset on zero real deductions
score = 100

# ── Deadlock penalty (t_5dd7ba12) ─────────────────────────────────────
# When ready==0 && todo>0 (no runnable tasks but pending work), apply penalty
# so score drops below 80, triggering WARN alert. Runs kanban_dep_deadlock_guard.py.
deadlock_penalty = 0
try:
    import subprocess
    _dbp = os.environ.get("_LH_DB", "")
    _board = "kensho-ai-team"
    if _dbp and os.path.exists(_dbp):
        # Use the DB path to determine board
        _board = os.path.basename(os.path.dirname(_dbp))
    _deadlock_result = subprocess.run(
        [sys.executable, "/mnt/d/Project2/kensho/scripts/kanban_dep_deadlock_guard.py",
         "--board", _board, "--json"],
        capture_output=True, text=True, timeout=10
    )
    if _deadlock_result.returncode == 1:  # deadlock detected
        _deadlock_data = json.loads(_deadlock_result.stdout)
        if _deadlock_data.get("deadlock"):
            # Apply penalty: ensure score < 80 (WARN threshold per t_5dd7ba12)
            # Subtract enough to drop below 80, minimum 21 points
            deadlock_penalty = max(21, 101 - score)
            score -= deadlock_penalty
except Exception:
    # On any failure, don't apply penalty (fail-safe)
    pass

# ── Review skill preflight (t_36410815) ────────────────────────────────
# review_dispatch force-loads sdlc-review; if unresolvable on any board
# profile, every review run dies at startup (month-long score=100 blind
# spot). --fast = filesystem-only, no hermes CLI spawn. -25 → score<80 WARN.
review_skill_ok = True
try:
    _pf = subprocess.run(
        [sys.executable, "/mnt/d/Project2/kensho/scripts/kanban_skill_preflight.py",
         "--fast", "--json"],
        capture_output=True, text=True, timeout=15
    )
    if _pf.returncode != 0:
        review_skill_ok = False
        score -= 25
except Exception:
    pass  # fail-safe: preflight itself broken must not kill loop_health

# ── Orphan run penalty (t_9ea4b148) ───────────────────────────────────────
# When orphan runs exist (card deleted but run persists), apply penalty to drop score < 80.
orphan_penalty = 0
orphan_runs = 0
stale_heartbeat_runs = 0
running_without_pid = 0
try:
    # Use --db flag for consistent DB resolution (matches deadlock guard approach)
    _dbp = os.environ.get("_LH_DB", "")
    _orphan_result = subprocess.run(
        [sys.executable, "/mnt/d/Project2/kensho/scripts/orphan_run_reaper.py",
         "--db", _dbp, "--json"],
        capture_output=True, text=True, timeout=10
    )
    if _orphan_result.returncode == 0:
        _orphan_data = json.loads(_orphan_result.stdout)
        orphan_runs = _orphan_data.get("orphan_runs", 0)
        stale_heartbeat_runs = _orphan_data.get("stale_heartbeat_runs", 0)
        running_without_pid = _orphan_data.get("running_without_pid", 0)
        if orphan_runs > 0:
            # Apply penalty: ensure score < 80 (WARN threshold per t_5dd7ba12)
            # Each orphan run: -20 points minimum
            orphan_penalty = max(20, 20 * orphan_runs, 101 - score)
            score -= orphan_penalty
except Exception:
    # On any failure, don't apply penalty (fail-safe)
    orphan_runs = 0
    stale_heartbeat_runs = 0
    running_without_pid = 0
    pass

# ── Artifact Age monitoring (t_aeba6230 / 2026-10-06) ─────────────────────
# dev.to pattern: 「プロセス生存より最終成果物の鮮度」。running中タスクの
# 最終 comment/checkpoint 時刻を DB から取得し、経過時間を計算する。
#   >= 2h → score -15, >= 4h → -30（streak 加算用）、>= 6h → park 対象。
# LOOPHEALTH_ARTIFACT_AGE_OVERRIDE: テスト用 env (JSON: {"t_xxx": 1.5, ...})。
artifact_age_hours = {}  # task_id -> hours since last comment
_artifact_override = os.environ.get("LOOPHEALTH_ARTIFACT_AGE_OVERRIDE", "")
if _artifact_override:
    try:
        artifact_age_hours.update(json.loads(_artifact_override))
    except Exception:
        artifact_age_hours = {}
else:
    try:
        _dbp = os.environ.get("_LH_DB", "")
        if _dbp and os.path.exists(_dbp):
            with sqlite3.connect("file:%s?mode=ro" % _dbp, uri=True) as _c:
                _c.row_factory = sqlite3.Row
                for _t in running:
                    _tid = _t["id"]
                    _row = _c.execute(
                        "SELECT MAX(created_at) AS last_ts FROM task_comments WHERE task_id = ?",
                        (_tid,)
                    ).fetchone()
                    _last_ts = _row["last_ts"] if _row and _row["last_ts"] else None
                    if _last_ts:
                        artifact_age_hours[_tid] = (now - int(_last_ts)) / 3600.0
                    else:
                        artifact_age_hours[_tid] = float('inf')  # no comments = infinite age
    except Exception:
        artifact_age_hours = {}

# artifact_age based score deductions (t_aeba6230)
artifact_age_penalty = 0
if artifact_age_hours:
    # Use the oldest running task's artifact age (same as top_task)
    _oldest_id = by_age[0]["id"] if by_age else None
    _oldest_artifact_age = artifact_age_hours.get(_oldest_id, 0) if _oldest_id else 0
    # Also check if ANY running task has artifact_age >= thresholds (for broader detection)
    _any_2h = any(v >= 2 for v in artifact_age_hours.values() if v != float('inf')) or \
              any(v == float('inf') for v in artifact_age_hours.values())
    _any_4h = any(v >= 4 for v in artifact_age_hours.values() if v != float('inf')) or \
              any(v == float('inf') for v in artifact_age_hours.values())
    if _any_4h:
        artifact_age_penalty = 30
    elif _any_2h:
        artifact_age_penalty = 15
score -= artifact_age_penalty

# config-based max_in_progress (v143 / t_6f45dab0): dispatcher と同一の解決経路。
# 旧: resolve_max_in_progress(None) → NameError → score=0/alert=ERROR で監視死亡。
# 本実装: profile config の kanban.max_in_progress → 無い場合は derive_default (8)。
# loop_health は dispatcher と同一の cap を参照し、cap 不一致による偽ALERTを排除する。
def get_profile_cap(_cfg_path=None):
    import os as _os
    _p = _os.environ.get("HERMES_PROFILE_CONFIG", "")
    _val = 8
    try:
        import yaml as _y
        _cand = _p if _p and _os.path.exists(_p) else None
        if _cand is None:
            _home = _os.path.expanduser("~")
            for _c in (
                f"{_home}/.hermes/profiles/kensho-sweeps/config.yaml",
                f"{_home}/.hermes/profiles/kensho-worker/config.yaml",
            ):
                if _os.path.exists(_c):
                    _cand = _c
                    break
        if _cand:
            _d = _y.safe_load(open(_cand, encoding="utf-8"))
            _v = (_d.get("kanban") or {}).get("max_in_progress")
            if _v is not None:
                _val = int(_v)
    except Exception:
        pass
    return _val

def get_dispatcher_cap(_cfg_path=None):
    import os as _os
    _val = 8
    try:
        import yaml as _y
        _home = _os.path.expanduser("~")
        _cand = f"{_home}/.hermes/config.yaml"
        if _os.path.exists(_cand):
            _d = _y.safe_load(open(_cand, encoding="utf-8"))
            _v = (_d.get("kanban") or {}).get("max_in_progress")
            if _v is not None:
                _val = int(_v)
    except Exception:
        pass
    return _val

cap_profile = get_profile_cap(None)
cap_dispatcher = get_dispatcher_cap(None)
cap_mismatch = (cap_profile != cap_dispatcher)

# --max-in-progress override
try:
    _max_in_progress_override = os.environ.get("_LH_MAX_IN_PROGRESS", "")
    if _max_in_progress_override.isdigit():
        _max_in_progress = int(_max_in_progress_override)
    else:
        _max_in_progress = cap_dispatcher
except Exception:
    _max_in_progress = cap_dispatcher

# --prev-streak override
try:
    _prev_streak_override = os.environ.get("_LH_PREV", "")
    if _prev_streak_override.isdigit():
        prev_streak = int(_prev_streak_override)
except Exception:
    pass

# running > max_in_progress: -10 per excess
_excess = len(running) - _max_in_progress
if _excess > 0:
    score -= 10 * _excess

# oldest >6h: -10 (use effective_started_at to match streak calculation)
for t in by_age:
    st = effective_started_at.get(t["id"], t.get("started_at"))
    if st and (now - int(st)) > 6 * 3600:
        score -= 10
        break

# oldest >12h: -15 (extra penalty)
for t in by_age:
    st = effective_started_at.get(t["id"], t.get("started_at"))
    if st and (now - int(st)) > 12 * 3600:
        score -= 15
        break

# aux auth errors from last 30m (kanon_decomposer|background_review|triage_specifier) in errors.log
aux_auth_errors = 0
try:
    _aux_log_path = os.environ.get("LOOPHEALTH_AUX_LOG_PATH") or os.path.expanduser("~/.hermes/logs/errors.log")
    with open(_aux_log_path, "r") as logf:
        log_lines = logf.readlines()
        cutoff_time = time.time() - (30 * 60)
        for line in log_lines:
            # Support both formats: YYYY-MM-DD HH:MM:SS and YYYY-MM-DD HH:MM:SS,mmm
            ts_match = re.match(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", line)
            if not ts_match:
                continue
            log_ts_str = ts_match.group(1)
            if re.search(r"Auxiliary (kanban_decomposer|background_review|triage_specifier):", line) and ("401" in line or "auth" in line.lower()):
                try:
                    # Parse with optional milliseconds
                    log_dt = _dt.datetime.strptime(log_ts_str, "%Y-%m-%d %H:%M:%S")
                    log_ts = time.mktime(log_dt.timetuple())
                    if log_ts >= cutoff_time:
                        aux_auth_errors += 1
                except Exception:
                    pass
except Exception:
    aux_auth_errors = 0

if aux_auth_errors:
    score -= 10 * aux_auth_errors
    if score < 55:
        alert = "ALERT"
    elif score < 70:
        alert = "ALERT"
    else:
        alert = "OK"

# same result >=2: -20
if repeats:
    score -= 20

# blocked+done parent: -15
if blocked_with_done_parent:
    score -= 15


# ── Zombie task detection (t_7748d284) ──────────────────────────────────────
# ゾンビタスク = blocked のまま worker が正常終了(rc=0)しても kanban_complete を
# 呼ばず、プロトコル違反で回路遮断された永久滞留タスク。dispatcher は遮断時に
# 必ず last_failure_error へ protocol violation 文言を刻むため、その LIKE 一致を
# 唯一の疎シグナルにする（run metadata fallback は iteration-budget 等の別原因
# 遮断まで誤検知するため使わない）。1件あたり -10。
# LOOPHEALTH_ZOMBIE_COUNT で個数を上書き(テスト用)。DB 不可時は 0 で無害。
zombie_task_count = 0
_zombie_override = os.environ.get("LOOPHEALTH_ZOMBIE_COUNT", "")
if _zombie_override.isdigit():
    zombie_task_count = int(_zombie_override)
else:
    try:
        _dbp = os.environ.get("_LH_DB", "")
        if _dbp and os.path.exists(_dbp):
            with sqlite3.connect("file:%s?mode=ro" % _dbp, uri=True) as _conn:
                _conn.row_factory = sqlite3.Row
                zombie_task_count = _conn.execute(
                    "SELECT count(*) c FROM tasks t WHERE t.status='blocked' "
                    "AND t.last_failure_error IS NOT NULL "
                    "AND t.last_failure_error LIKE '%protocol violation%'"
                ).fetchone()["c"]
    except Exception:
        zombie_task_count = 0
if zombie_task_count:
    score -= 10 * zombie_task_count

score = max(0, min(100, score))

# ── Business KPI gate (t_08b42528: apply stopped detection) ──
# ループ健康(ボード)に加え「成果」(当日応募完了行)を見る。当日ログの完了行=0 かつ
# JST 09:00以降(no_action_window外)のとき apply stopped と判定し score 上限60/WARN。
# LOOPHEALTH_LOG_PATH: テスト用にログパスを上書き(逃げ道)。LOOPHEALTH_JST_HOUR: 時刻再現用。
import os as _os, datetime as _dt, re as _re

_kpi_log = _os.environ.get("LOOPHEALTH_LOG_PATH", "")
if not _kpi_log:
    _kpi_log = ("/mnt/d/Project2/kensho/logs/auto_"
                + _dt.datetime.now(_dt.timezone(_dt.timedelta(hours=9))).strftime("%Y%m%d")
                + ".log")
_done_count = 0
if _os.path.exists(_kpi_log):
    try:
        # v139: 実ログの完了マーカーは "[OK] 完了: N成功 / Mエラー" と INFO
        # ログ "完了: N成功/Mエラー（Xs秒）" の2形。旧 "OK 完了" は両方とも一致せず
        # 常に0 → 稼働日を偽陽性WARN化。完了行/成功数は "完了: <N>成功" で集計。
        # v170 (critic実測RCA): \d+成功 は "完了: 0成功..." にも一致し、停止時の
        # "0成功" 行を完了扱い → done_count=0 にならず停止判定が発動しない。
        # 成功数>=1 の行のみ完了扱いする ([1-9][0-9]* で 0成功 を除外)。
        with open(_kpi_log, encoding="utf-8", errors="ignore") as _f:
            _done_count = sum(1 for _line in _f if _re.search(r"完了:\s*[1-9][0-9]*成功", _line))
    except Exception:
        _done_count = 0

_jst_hour_raw = _os.environ.get("LOOPHEALTH_JST_HOUR", "")
_jst_hour = int(_jst_hour_raw) if _jst_hour_raw.isdigit() else _dt.datetime.now(
    _dt.timezone(_dt.timedelta(hours=9))).hour

# orchestrator.no_action_window を config.yaml から取得(欠落/読取失敗時は既定 00:00-07:00)。
_no_action_hours = set(range(0, 7))
try:
    _cfg_txt = open("/mnt/d/Project2/kensho/config.yaml", encoding="utf-8").read()
    _m_win = _re.search(r"no_action_window:\s*\[\s*\"(\d{2}):\d{2}\"\s*,\s*\"(\d{2}):\d{2}\"\s*\]", _cfg_txt)
    if _m_win:
        _sh, _eh = int(_m_win.group(1)), int(_m_win.group(2))
        if _sh <= _eh:
            _no_action_hours = set(range(_sh, _eh))
        else:
            _no_action_hours = set(h % 24 for h in range(_sh, _eh + 24))
except Exception:
    pass

_business_detect = (_jst_hour >= 9) and (_jst_hour not in _no_action_hours) and (_done_count == 0)
business_ok = (not _business_detect)
if _business_detect:
    # Check if we have gradients for pattern mining\n    if [ -f "/mnt/d/Project2/kensho/data/textual_gradients.json" ]; then\n        gradient_count=$(python3 -c "import json; d=json.load(open(/mnt/d/Project2/kensho/data/textual_gradients.json)); print(len(d.get(gradients, [])))")\n        if [ "$gradient_count" -gt 0 ]; then\n            echo "[$(date)] Found $gradient_count textual gradients for pattern mining" >> "$LOOPHEALTH_LOG_PATH"\n        fi\n    fi
    score = max(0, min(score, 60))

# ── Streak (v143 / t_6f45dab0) ────────────────────────────────────────────────
# v143: age 減点・表示の参照元を effective_started_at に統一。
# 旧: _real_deductions は t.get("started_at")(初回dispatchのstale値)を直参照 →
#     実活動(task_runs)経過と別ソースで streak 判定が分かれ、score は healthy でも
#     streak が increment される不一致。また age 表示は runs_started_at(全runningのMAX)
#     を最古タスクの年齢に使う誤り。
# 対策: _eff(t) = effective_started_at.get(id)。未取得(None)なら age penalty を
#     skip（tasks.started_at のstale値にはフォールバックしない）。
#     DB 解決(v143)により実 running run が取れれば age=0h になる。
def _eff(t):
    return effective_started_at.get(t["id"])

_real_deductions = (
    (len(running) > _max_in_progress) * 10 * max(0, len(running) - _max_in_progress)
    + (any(_eff(t) and (now - int(_eff(t))) > 6 * 3600 for t in by_age)) * 10
    + (any(_eff(t) and (now - int(_eff(t))) > 12 * 3600 for t in by_age)) * 15
    + (len(repeats) > 0) * 20
    + (len(blocked_with_done_parent) > 0) * 15
    + (zombie_task_count > 0) * 10 * zombie_task_count
    + (not business_ok) * 1  # business KPI gate
    + (orphan_runs > 0) * 20  # orphan run penalty (t_9ea4b148)
)

if _real_deductions > 0:
    if score < 70:
        streak = prev_streak + 1
    else:
        streak = 0
else:
    streak = 0

# ── Priority & advice (t_b75f7c57 偽done 解消 / t_7b49e7bf 実装) ──────────────
# critic は role_summary から priority を「推察」して動いていたが、priority/advice
# フィールドが実装されていなかったため判断基準が停止中。全エージェント(critic/worker/
# QA) の action を决定する health JSON の priority / advice を明示する。
#   blocked_triage : blocked > 0
#   backlog_reduction: ready == 0 AND blocked == 0 AND todo > 0（縮小すべきbacklogが実在する）
#   new_proposals  : ready == 0 AND blocked == 0 AND todo == 0（盤面にworkが無い＝供給が必要）
#   normal         : それ以外
# ready/todo 数は DB の status カウントから取得（DB 不可時は None → 利用可能な情報のみで判断）。
_ready_count = None
_todo_count = None
try:
    _dbp = os.environ.get("_LH_DB", "")
    if _dbp and os.path.exists(_dbp):
        with sqlite3.connect("file:%s?mode=ro" % _dbp, uri=True) as _c:
            _row = _c.execute(
                "SELECT "
                "SUM(CASE WHEN status='ready' THEN 1 ELSE 0 END), "
                "SUM(CASE WHEN status='todo' THEN 1 ELSE 0 END), "
                "SUM(CASE WHEN status='done' THEN 1 ELSE 0 END) "
                "FROM tasks"
            ).fetchone()
            if _row:
                _ready_count = int(_row[0] or 0)
                _todo_count = int(_row[1] or 0)
except Exception:
    pass

if blocked:
    priority = "blocked_triage"
elif _ready_count is not None and _ready_count == 0:
    if _todo_count == 0:
        # 2026-10-04 修正(t_): 旧実装は running>0 を理由に backlog_reduction を返していたが、
        # todo もゼロ＝縮小すべきbacklogが存在しない。running は「進行中が1件」を意味するだけで
        # 供給の必要が無いことの根拠にならない。この誤判定により、盤面が空のときに
        # 「新規提案禁止」が無限に続くデッドロックへ入っていた（Critic が14日で2枚しか
        # 起票できていなかった真因）。todo 実在時のみ backlog_reduction とする。
        priority = "new_proposals"
    else:
        priority = "backlog_reduction"
elif _ready_count is None:
    # DB から ready 数が取れない: 利用可能な情報のみで判断。
    # running が居て blocked=0 は board 活動中とみなし normal（backlog_reduction の
    # 偽陽性を防ぐ）。
    if len(running) == 0 and not blocked:
        priority = "new_proposals"
    else:
        priority = "normal"
else:
    priority = "normal"

# role別 action & reason（{role: {action: ..., reason: ...}} 形式）
def _role_advice(role):
    if priority == "blocked_triage":
        action = "triage_blocked"
        reason = "blocked=%d件のブロックタスクを要処理" % len(blocked)
    elif priority == "backlog_reduction":
        action = "reduce_backlog"
        reason = "ready=0（実行可能タスクなし）→ todo backlog の縮小を"
    elif priority == "new_proposals":
        action = "propose_new"
        reason = "ready=0かつtodo=0（盤面にworkが無い）→ 新規提案の起票を"
    else:
        action = "continue"
        reason = "通常運転（優先度判定不要）"
    return {"action": action, "reason": reason}

advice = {r: _role_advice(r) for r in ("critic", "worker", "qa")}

# Build lines output (max 5)
lines = []
lines.append(f"score={score}")
if by_age:
    # v137: by_ageはstarted_at昇順(先頭=最古)。top_task/park targetは最古running
    # でなければならない(QA 9/12実測: [-1]だと最新規を拾いSLA parkingが空振り)。
    top = by_age[0]
    _top_eff = effective_started_at.get(top['id'])
    if _top_eff:
        age_h = (now - int(_top_eff)) // 3600
    else:
        # DB 解決済みで実 run が取れない場合は age penalty を skip（stale tasks.started_at にはフォールバックしない）
        age_h = 0
    lines.append(f"top={top['id']} age={age_h}h")
else:
    lines.append("top=none")
lines.append(f"running={len(running)}")
lines.append(f"blocked={len(blocked)}")
if repeats:
    for r, ids in list(repeats.items())[:1]:
        lines.append(f"repeat={len(ids)}x {r[:40]}")
elif streak >= 3:
    lines.append(f"streak={streak}⚠️")
else:
    lines.append(f"streak={streak}")

print(json.dumps({
    "score": score,
    "review_skill_ok": review_skill_ok,
    "streak": streak,
    "running": len(running),
    "blocked": len(blocked),
    "counts": {"running": len(running), "blocked": len(blocked)},
    "skip_fast": False,
    "top_task": by_age[0]["id"] if by_age else None,
    "repeats": repeats,
    "done_blocked": blocked_with_done_parent,
    "zombie_task_count": zombie_task_count,
    "business_ok": bool(business_ok),
    "business_done": _done_count,
    "business_hour": _jst_hour,
    "business_log": _kpi_log,
    "aux_auth_errors": aux_auth_errors,
    "cap_profile": cap_profile,
    "cap_dispatcher": cap_dispatcher,
    "cap_mismatch": bool(cap_mismatch),
    "orphan_runs": orphan_runs,
    "stale_heartbeat_runs": stale_heartbeat_runs,
    "running_without_pid": running_without_pid,
    "lines": lines[:5],
    "priority": priority,
    "stagnation_streak": streak,
    "advice": advice,
    "artifact_age_hours": artifact_age_hours,
    "artifact_age_penalty": artifact_age_penalty,
}))
PYEOF
)

if [[ -z "$ANALYSIS" ]]; then
  echo "loop_health: analysis failed" >&2
  echo "score=0"
  echo "alert=ERROR"
  exit 0
fi

SCORE=$(echo "$ANALYSIS" | jq -r '.score')
STREAK_COUNT=$(echo "$ANALYSIS" | jq -r '.streak')
TOP_TASK=$(echo "$ANALYSIS" | jq -r '.top_task // empty')
REPEATS=$(echo "$ANALYSIS" | jq -r '.repeats | length')
DONE_BLOCKED=$(echo "$ANALYSIS" | jq -r '.done_blocked | length')
BUSINESS_STOPPED=$(echo "$ANALYSIS" | jq -r 'if .business_ok == false then true else false end')
PRIORITY=$(echo "$ANALYSIS" | jq -r '.priority // "normal"')
ADVICE_CRITIC=$(echo "$ANALYSIS" | jq -r '.advice.critic.action // "continue"')
ADVICE_WORKER=$(echo "$ANALYSIS" | jq -r '.advice.worker.action // "continue"')
ADVICE_QA=$(echo "$ANALYSIS" | jq -r '.advice.qa.action // "continue"')

# ─── Alert decision (v24/v30 band logic preserved) ──────────────────────────
ESCALATE_THRESHOLD=55

if [[ "$SCORE" -lt "$ESCALATE_THRESHOLD" ]]; then
  # critical: <55
  ESCALATION_OUTPUT="true"
  LAST_ESCALATE_STREAK=0
  LAST_LOW_BAND=0
elif [[ "$SCORE" -eq "$ESCALATE_THRESHOLD" ]]; then
  # 55: active (not escalated) band
  # v30: store the band of the threshold instead of the raw streak to avoid
  # oscillation between True/False across ticks.
  STREAK_BAND=$(( (STREAK_COUNT / 10) * 10 ))
  if [[ "$STREAK_BAND" -gt 0 ]]; then
    ESCALATION_OUTPUT="true"
    LAST_ESCALATE_STREAK=$STREAK_BAND
    LAST_LOW_BAND=$STREAK_BAND
  else
    ESCALATION_OUTPUT="false"
    LAST_ESCALATE_STREAK=0
    LAST_LOW_BAND=0
  fi
else
  # high score: escalation off unless a stored active band persists
  # v133b (QA run395①): persist the band only while the invariant holds
  # (last_escalate_streak <= current streak). A band > streak is stale memory
  # (park/healthy board left it behind, e.g. streak=0 & band=11) — letting it
  # persist kept escalation=true on a healthy board and made the park gate
  # spam different targets every cooldown (v92 指標2 FAIL 真因). Drop it here.
  if [[ "$PREV_ESCALATE_STREAK" -gt 0 && "$PREV_ESCALATE_STREAK" -le "$STREAK_COUNT" ]]; then
    ESCALATION_OUTPUT="true"
    LAST_ESCALATE_STREAK=$PREV_ESCALATE_STREAK
  else
    ESCALATION_OUTPUT="false"
    LAST_ESCALATE_STREAK=0
  fi
  LAST_LOW_BAND=0
fi

# ─── escalated_at tracking (v133) ────────────────────────────────────────────
# epoch of the CURRENT continuous escalation-active span; "" when inactive.
if [[ "$ESCALATION_OUTPUT" == "true" ]]; then
  ESCALATED_AT="${PREV_ESCALATED_AT:-$NOW}"
else
  ESCALATED_AT=""
fi
ESC_AGE_S=0
ESC_AGE_H=0
if [[ -n "$ESCALATED_AT" ]]; then
  ESC_AGE_S=$(( NOW - ESCALATED_AT ))
  (( ESC_AGE_S < 0 )) && ESC_AGE_S=0
  ESC_AGE_H=$(( ESC_AGE_S / 3600 ))
fi

# ─── Escalation target (top of backlog) ─────────────────────────────────────
ESCALATION_TARGET=""
if [[ -n "$TOP_TASK" && "$TOP_TASK" != "null" ]]; then
  ESCALATION_TARGET="$TOP_TASK"
else
  _OLDEST_BACKLOG=$("$HERMES_BIN" kanban --board "$BOARD" list 2>/dev/null | \
    awk '/running|blocked/{print} ' | \
    head -1 | \
    grep -oE 't_[a-f0-9]{8}' | head -1)
  if [[ -n "$_OLDEST_BACKLOG" ]]; then
    ESCALATION_TARGET="$_OLDEST_BACKLOG"
  else
    _OLDEST_BACKLOG_DB=$(sqlite3 -json "$DB_PATH" "SELECT id FROM tasks WHERE status='blocked' ORDER BY created_at ASC LIMIT 1" 2>/dev/null | \
      jq -r '.[0].id // empty' 2>/dev/null)
    [[ -n "$_OLDEST_BACKLOG_DB" ]] && ESCALATION_TARGET="$_OLDEST_BACKLOG_DB"
  fi
fi

# ─── PARK_AFTER_H gate (v133 core fix) ──────────────────────────────────────
# When escalation has been active for >= PARK_AFTER_H continuous hours, park the
# SLA-breached target: [loop-health] comment + `hermes kanban schedule`.
PARK_ACTION="none"
PARK_TARGET="$ESCALATION_TARGET"
PARK_AFTER_S=$(( PARK_AFTER_H * 3600 ))
PARK_CD_UNTIL="$PREV_PARK_CD"
# v133c: park試行ウィンドウ（試行があった時だけ進める。dedup/cooldown判定は窓をスライドしない）
LAST_PARK_TS="$PREV_PARK_TS"
LAST_PARK_RESULT="$PREV_PARK_RESULT"
LAST_PARK_TARGET="$PREV_PARK_TARGET"

if [[ "$ESCALATION_OUTPUT" == "true" && -n "$PARK_TARGET" && "$PARK_TARGET" != "null" && -n "$ESCALATED_AT" && "$ESC_AGE_S" -ge "$PARK_AFTER_S" ]]; then
  # v133c: 30分窓の時刻dedup（v92回帰の再導入、v133系では失われていた）。
  # 直近 PARK_DEDUP_WINDOW_S 以内にpark試行（実park/already_scheduled）があれば
  # target切替を問わず再試行しない → cooldown(6h)より短いスパンでescalation別
  # targetを連続parkするv92真因（自動復旧阻害）の再発防止。dry_run/失敗系は
  # 同一target限定で遮断。判定はPREV_*の窓値に対し、窓の前進は試行時のみ
  # （dedup_skipは窓をスライドさせない）。
  DEDUP_OK=1
  if [[ -n "$PREV_PARK_TS" ]] && [[ $(( NOW - PREV_PARK_TS )) -lt PARK_DEDUP_WINDOW_S ]]; then
    case "$PREV_PARK_RESULT" in
      parked|already_scheduled)
        DEDUP_OK=0
        ;;
      dry_run_would_park|schedule_failed|skipped_status_*)
        if [[ "$PREV_PARK_TARGET" == "$PARK_TARGET" ]]; then
          if [[ "$PREV_PARK_RESULT" != "dry_run_would_park" || "$NO_PARK" -eq 1 || "$DRY_RUN" -eq 1 ]]; then
            DEDUP_OK=0
          fi
        fi
        ;;
    esac
  fi
  if [[ "$DEDUP_OK" -eq 0 ]]; then
    PARK_ACTION="dedup_skip"
  elif [[ "$NO_PARK" -eq 1 || "$DRY_RUN" -eq 1 ]]; then
    PARK_ACTION="dry_run_would_park"
    LAST_PARK_TS="$NOW"; LAST_PARK_RESULT="$PARK_ACTION"; LAST_PARK_TARGET="$PARK_TARGET"
  elif [[ "$NOW" -lt "$PREV_PARK_CD" ]]; then
    PARK_ACTION="cooldown"
  else
    # idempotency: never park a task that is not an actionable open state
    TARGET_STATUS=$("$HERMES_BIN" kanban --board "$BOARD" show "$PARK_TARGET" --json 2>/dev/null | jq -r '.task.status // .status // empty')
    case "$TARGET_STATUS" in
      scheduled)
        PARK_ACTION="already_scheduled"
        LAST_PARK_TS="$NOW"; LAST_PARK_RESULT="$PARK_ACTION"; LAST_PARK_TARGET="$PARK_TARGET"
        ;;
      running|blocked|ready|todo)
        MARKER="[loop-health] SLA ${ESC_AGE_H}h > ${PARK_AFTER_H}h parking gate"
        if [[ "$DRY_RUN" -eq 0 ]]; then
          "$HERMES_BIN" kanban --board "$BOARD" comment "$PARK_TARGET" \
            "${MARKER}: escalation active ${ESC_AGE_H}h (since epoch ${ESCALATED_AT}), score=${SCORE}, streak=${STREAK_COUNT}. Auto-parking per t_5086aef7; needs human decision — see hermes kanban show ${PARK_TARGET}." >/dev/null 2>&1
          if [[ -z "$HERMES_SUPERVISED_CHILD" ]]; then
            if "$HERMES_BIN" kanban --board "$BOARD" schedule "$PARK_TARGET" \
               "${MARKER} (auto-scheduled by loop_health v133)" >/dev/null 2>&1; then
              PARK_ACTION="parked"
              if [[ "$STREAK_COUNT" -gt 0 ]]; then
                LAST_ESCALATE_STREAK=$STREAK_COUNT
              else
                LAST_ESCALATE_STREAK=0
              fi
              LAST_LOW_BAND=$LAST_ESCALATE_STREAK
              ESCALATED_AT=""
            else
              PARK_ACTION="schedule_failed"
            fi
          else
            # gateway内だと schedule が gateway restart をトリガーしSIGTERMで
            # 以降の state.json 書き込みが死ぬ。コメントは既に成功済みなので
            # parked 扱いで継続。
            PARK_ACTION="parked"
          fi
          PARK_CD_UNTIL=$(( NOW + PARK_COOLDOWN_S ))
          LAST_PARK_TS="$NOW"; LAST_PARK_RESULT="$PARK_ACTION"; LAST_PARK_TARGET="$PARK_TARGET"
        else
          PARK_ACTION="dry_run_would_park"
          LAST_PARK_TS="$NOW"; LAST_PARK_RESULT="$PARK_ACTION"; LAST_PARK_TARGET="$PARK_TARGET"
        fi
        ;;
      *)
        PARK_ACTION="skipped_status_${TARGET_STATUS:-unknown}"
        LAST_PARK_TS="$NOW"; LAST_PARK_RESULT="$PARK_ACTION"; LAST_PARK_TARGET="$PARK_TARGET"
        ;;
    esac
  fi
fi

# ─── SINGLE final state write (v133: replaces 3 duplicated rewrites) ────────
if [[ "$SCORE" -lt "$ESCALATE_THRESHOLD" ]]; then
  STATE_SCORE="$SCORE"
elif [[ "$SCORE" -eq "$ESCALATE_THRESHOLD" ]]; then
  STATE_SCORE=55
else
  STATE_SCORE="$SCORE"
fi

STATE_JSON=$(jq -n \
  --argjson score "$STATE_SCORE" \
  --argjson streak "$STREAK_COUNT" \
  --argjson last_escalate_streak "$LAST_ESCALATE_STREAK" \
  --argjson last_low_band "$LAST_LOW_BAND" \
  --argjson business_ok "$BUSINESS_STOPPED" \
  --arg priority "$PRIORITY" \
  --arg advice_critic "$ADVICE_CRITIC" \
  --arg advice_worker "$ADVICE_WORKER" \
  --arg advice_qa "$ADVICE_QA" \
  --arg escalated_at "${ESCALATED_AT:-}" \
  --argjson park_cooldown_until "$PARK_CD_UNTIL" \
  --arg park_after_h "$PARK_AFTER_H" \
  --arg park_action "$PARK_ACTION" \
  --arg last_park_ts "${LAST_PARK_TS:-}" \
  --arg last_park_result "${LAST_PARK_RESULT:-}" \
  --arg last_park_target "${LAST_PARK_TARGET:-}" \
  --arg top_task "$ESCALATION_TARGET" \
  --arg ts "$(date -Iseconds)" \
  '{
    score: $score,
    streak: $streak,
    last_escalate_streak: $last_escalate_streak,
    last_low_band: $last_low_band,
    business_ok: ($business_ok | not),
    priority: $priority,
    advice: {critic: $advice_critic, worker: $advice_worker, qa: $advice_qa},
    escalated_at: $escalated_at,
    park_cooldown_until: $park_cooldown_until,
    park_after_h: $park_after_h,
    last_park_action: $park_action,
    last_park_ts: $last_park_ts,
    last_park_result: $last_park_result,
    last_park_target: $last_park_target,
    last_run_ts: $ts,
    escalation_active: ($score < 55)
  }')

if [[ -n "$STATE_JSON" ]]; then
  echo "$STATE_JSON" > "$STATE_FILE"
fi

# ─── Output (max 5 lines) ───────────────────────────────────────────────────
ESCALATION_TARGET_JSON="null"
if [[ -n "$ESCALATION_TARGET" ]]; then
  # -Rs (raw slurp) emits ONE JSON string even if the id is multiline;
  # -R would emit multiple strings and break --argjson below.
  # Use printf '%s' (NOT echo): echo injects a trailing \n that -Rs would fold
  # into the JSON value, corrupting the single-id guarantee (FINDING2 regression
  # test asserts no newline in escalation_target).
  ESCALATION_TARGET_JSON=$(printf '%s' "$ESCALATION_TARGET" | jq -Rs .)
fi

echo "$ANALYSIS" | jq \
  --argjson escalation "$ESCALATION_OUTPUT" \
  --argjson business_stopped "$BUSINESS_STOPPED" \
  --argjson target "$ESCALATION_TARGET_JSON" \
  --arg escalate_streak "$LAST_ESCALATE_STREAK" \
  --arg escalated_at "${ESCALATED_AT:-}" \
  --argjson esc_age_h "$ESC_AGE_H" \
  --arg park_after_h "$PARK_AFTER_H" \
  --arg park_action "$PARK_ACTION" \
  '. + {
    alert: (if $business_stopped then "WARN: apply stopped" else (if .aux_auth_errors >= 10 then "ALERT" else (if .score < 80 then "WARN" else (if .score < 70 then "ALERT" else "OK" end) end) end) end),
    escalation: $escalation,
    escalation_target: $target,
    escalate_streak: ($escalate_streak | tonumber),
    escalated_at: (if $escalated_at == "" then null else ($escalated_at | tonumber) end),
    escalation_age_h: $esc_age_h,
    park_after_h: ($park_after_h | tonumber),
    park_action: $park_action,
    orphan_runs: .orphan_runs,
    stale_heartbeat_runs: .stale_heartbeat_runs,
    running_without_pid: .running_without_pid,
    action: null
  }
  # v140 (t_ef9e899f): role別 curated injection。full JSON をトップレベルに温存したまま
  # (board_state_monitor_*.sh が score/counts/escalation等をパースするため削れない)、
  # LLMプロンプト注入用に role_summary.<role> を追加。各report scriptは自分のroleだけを
  # 注入し、Attention Budgetを最適化する(不要フィールドをpromptに入れない)。
  | . + {
    role_summary: {
      critic: {
        alert: .alert, score: .score, streak: .streak,
        running: .running, blocked: .blocked,
        escalation: (.escalation | tostring), escalation_target: .escalation_target,
        escalation_age_h: .escalation_age_h, top_task: .top_task,
        repeats: (.repeats | length), done_blocked: (.done_blocked | length),
        zombie_task_count: .zombie_task_count, business_ok: .business_ok,
        park_action: .park_action, park_after_h: .park_after_h
      },
      worker: {
        alert: .alert, score: .score, streak: .streak,
        running: .running, escalation: (.escalation | tostring),
        top_task: .top_task, business_ok: .business_ok
      },
      qa: {
        alert: .alert, score: .score, streak: .streak,
        running: .running, blocked: .blocked,
        escalation: (.escalation | tostring), top_task: .top_task,
        done_blocked: (.done_blocked | length), repeats: (.repeats | length),
        zombie_task_count: .zombie_task_count, business_ok: .business_ok
      }
    }
  }
  | if .alert == "ALERT" then .action = (.repeats | if . != {} then ("Loop detected: " + (to_entries | .[0] | "task(s) " + (.value | join(",")) + " all output same result")) else null end) else . end'
