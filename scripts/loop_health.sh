#!/usr/bin/env bash
# Loop Health Checker v133 (t_5086aef7: PARK_AFTER_H gate 実装 + 重複状態書き込み解消)
# Detects Kanban loop stagnation and escalates via Telegram.
# HARD LIMIT: Output max 5 lines.
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
    *) shift ;;
  esac
done

# ─── Auto-detect DB if not found ─────────────────────────────────────────────
if [[ ! -f "$DB_PATH" ]]; then
  for board in kensho-ai-team default; do
    cand="$HOME/.hermes/kanban/boards/$board/kanban.db"
    if [[ -f "$cand" ]]; then
      DB_PATH="$cand"
      BOARD="$board"
      break
    fi
  done
fi

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
    _B=$(hermes kanban --board "$BOARD" list --json --status blocked 2>/dev/null)
    _R=$(hermes kanban --board "$BOARD" list --json --status running 2>/dev/null)
    printf '%s' "${_B:-[]}" > "${_TASKS_TMP}.b"
    printf '%s' "${_R:-[]}" > "${_TASKS_TMP}.r"
    jq -s 'add // []' "${_TASKS_TMP}.b" "${_TASKS_TMP}.r" > "$_TASKS_TMP" 2>/dev/null \
      || echo '[]' > "$_TASKS_TMP"
    rm -f "${_TASKS_TMP}.b" "${_TASKS_TMP}.r"
    TASKS_FILE="$_TASKS_TMP"
  fi
fi

if [[ -z "$TASKS_JSON" && -z "$TASKS_FILE" ]]; then
  # DB fallback
  TASKS_JSON=$(sqlite3 -json "$DB_PATH" "SELECT id, status, title, result, started_at FROM tasks WHERE status IN ('running','blocked') ORDER BY started_at ASC LIMIT 100" 2>/dev/null)
fi

if [[ -z "$TASKS_FILE" ]]; then
  [[ -z "$TASKS_JSON" ]] && TASKS_JSON="[]"
  TASKS_FILE=$(mktemp /tmp/loop_health_tasks.XXXXXX.json)
  printf '%s' "$TASKS_JSON" > "$TASKS_FILE"
fi
trap 'rm -f "$TASKS_FILE"' EXIT

NOW=$(date +%s)
export _LH_TASKS_FILE="$TASKS_FILE" _LH_NOW="$NOW" _LH_PREV="$PREV_STREAK"

# ─── Analyze ─────────────────────────────────────────────────────────────────
ANALYSIS=$(python3 - <<'PYEOF'
import json, os, re, time

tasks = json.loads(open(os.environ.get("_LH_TASKS_FILE", "/dev/null")).read() or "[]")
now = int(os.environ.get("_LH_NOW", str(int(time.time()))))
prev_streak = int(os.environ.get("_LH_PREV", "0"))

running = [t for t in tasks if t.get("status") == "running"]
blocked = [t for t in tasks if t.get("status") == "blocked"]

# Sort: longest running first
by_age = sorted(running, key=lambda t: t.get("started_at") or now, reverse=False)

# Detect same-result repeat
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

# ── Score calculation (v22) ──
score = 100

# running >3 = -10
if len(running) > 3:
    score -= 10

# running 5+ = -20 (extra penalty)
if len(running) >= 5:
    score -= 20

# oldest >6h: -10
for t in by_age:
    st = t.get("started_at")
    if st and (now - int(st)) > 6 * 3600:
        score -= 10
        break

# oldest >12h: -15 (extra penalty)
for t in by_age:
    st = t.get("started_at")
    if st and (now - int(st)) > 12 * 3600:
        score -= 15
        break

# same result >=2: -20
if repeats:
    score -= 20

# 3 consecutive low scores (from previous state) → -20
if prev_streak >= 3:
    score -= 20
    streak = prev_streak + 1
elif score < 70:
    streak = prev_streak + 1
else:
    streak = 0

# blocked+done parent: -15
if blocked_with_done_parent:
    score -= 15

score = max(0, min(100, score))

# Build lines output (max 5)
lines = []
lines.append(f"score={score}")
if by_age:
    top = by_age[-1]
    age_h = (now - int(top.get("started_at") or now)) // 3600
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
    "streak": streak,
    "running": len(running),
    "blocked": len(blocked),
    "counts": {"running": len(running), "blocked": len(blocked)},
    "skip_fast": False,
    "top_task": by_age[-1]["id"] if by_age else None,
    "repeats": repeats,
    "done_blocked": blocked_with_done_parent,
    "lines": lines[:5]
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
  _OLDEST_BACKLOG=$(hermes kanban --board "$BOARD" list 2>/dev/null | \
    awk '/running|blocked/{print} ' | \
    head -1 | \
    grep -oE 't_[a-f0-9]{8}')
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
    TARGET_STATUS=$(hermes kanban --board "$BOARD" show "$PARK_TARGET" --json 2>/dev/null | jq -r '.task.status // .status // empty')
    case "$TARGET_STATUS" in
      scheduled)
        PARK_ACTION="already_scheduled"
        LAST_PARK_TS="$NOW"; LAST_PARK_RESULT="$PARK_ACTION"; LAST_PARK_TARGET="$PARK_TARGET"
        ;;
      running|blocked|ready|todo)
        MARKER="[loop-health] SLA ${ESC_AGE_H}h > ${PARK_AFTER_H}h parking gate"
        if [[ "$DRY_RUN" -eq 0 ]]; then
          hermes kanban --board "$BOARD" comment "$PARK_TARGET" \
            "${MARKER}: escalation active ${ESC_AGE_H}h (since epoch ${ESCALATED_AT}), score=${SCORE}, streak=${STREAK_COUNT}. Auto-parking per t_5086aef7; needs human decision — see hermes kanban show ${PARK_TARGET}." >/dev/null 2>&1
          if hermes kanban --board "$BOARD" schedule "$PARK_TARGET" \
             "${MARKER} (auto-scheduled by loop_health v133)" >/dev/null 2>&1; then
          PARK_ACTION="parked"
          # v133b (QA run395①): park成功で持続bandを再設定。bandを旧値(例11)のまま
          # 置くと streak(0) を上回ったまま不変条件を破り、healthy boardでも
          # escalation=trueが持続→cooldownごとに別targetを連続parkする。
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
  ESCALATION_TARGET_JSON=$(echo "$ESCALATION_TARGET" | jq -R .)
fi

echo "$ANALYSIS" | jq \
  --argjson escalation "$ESCALATION_OUTPUT" \
  --argjson target "$ESCALATION_TARGET_JSON" \
  --arg escalate_streak "$LAST_ESCALATE_STREAK" \
  --arg escalated_at "${ESCALATED_AT:-}" \
  --argjson esc_age_h "$ESC_AGE_H" \
  --arg park_after_h "$PARK_AFTER_H" \
  --arg park_action "$PARK_ACTION" \
  '. + {
    alert: (if .score < 70 then "ALERT" else "OK" end),
    escalation: $escalation,
    escalation_target: $target,
    escalate_streak: ($escalate_streak | tonumber),
    escalated_at: (if $escalated_at == "" then null else ($escalated_at | tonumber) end),
    escalation_age_h: $esc_age_h,
    park_after_h: ($park_after_h | tonumber),
    park_action: $park_action,
    action: null
  } | if .alert == "ALERT" then .action = (.repeats | if . != {} then ("Loop detected: " + (to_entries | .[0] | "task(s) " + (.value | join(",")) + " all output same result")) else null end) else . end'
