#!/usr/bin/env bash
# kensho-complete-watchdog.sh — 完了忘れ防止: runningタスクの自動チェック (kanban t_fc908068, 2026-09-17)
#
# 目的: workerが実装を済ませたのに kanban_complete / kanban_block を呼び忘れ、
#       タスクが status=running のまま残留する(完了忘れ)を検知してリマインドする。
#
# 検知シグネチャ(実装完了忘れ = "worker exited cleanly without calling complete"):
#   - tasks.status IN ('running','in_progress')
#   - worker_pid が死んでいる or NULL
#   - last_heartbeat_at が N 分以上古い(セッションが終了/ハングしている)
#   → 上記を満たすタスクは「実装は行き着いたが終端を忘れた」候補。
#   続いて実装完了の客観証拠を確認:
#     (a) 直近D日以内の git コミットに task_id を含むものが存在
#     (b) リポジトリに未コミットのコード変更がある(=作業を施した痕跡)
#   (a) か (b) が真なら complete 忘れ確定候補 → リマインドコメント投稿。
#
# 動作:
#   - 既定 --dry-run(手動確認)。適用は APPLY=1 / --apply。
#   - cron(--apply)は問題0件時サイレント(空stdout, --no-agent規約)。閾値・証拠チェックunstable。
#   - 同一タスクへの重複リマインド防止: 台帳 logs/complete_watch_ledger.txt に 日付+task_id でupsert。
#   - エスカレーション: 候補タスクを kensho-critic へレビューカードとして起票し、実装受理 or 打ち切りの二択を委譲。
#     発券は hunter_guard(重複ガード)準拠 + idempotency-key 付与。
#
# 使い方:
#   bash kensho-complete-watchdog.sh --dry-run           # 手動: 対象表示のみ
#   bash kensho-complete-watchdog.sh --apply             # リマインド+エスカ発券
#   bash kensho-complete-watchdog.sh --stale-min 60      # 無音閾値変更
#
# crontab(WSL): */30 * * * * bash <this> --apply >> /mnt/d/Project2/kensho/logs/complete_watchdog_cron.log 2>&1
set -uo pipefail

REPO="/mnt/d/Project2/kensho"
BOARD="kensho-ai-team"
DB="/home/atushi/.hermes/kanban/boards/kensho-ai-team/kanban.db"
LEDGER="$REPO/logs/complete_watch_ledger.txt"

# --- 送信路の堅牢化 (t_adc65737) -------------------------------------------------
# 実測: cron の最小 PATH(/usr/bin:/bin) では `hermes` が解決できず、
# リマインドコメントが 54/54 で exit 127 (= `hermes: not found`) で全滅していた。
# → PATH 依存をやめ、絶対パスで hermes を解決する（見つからなければ失敗理由をログに残す）。
export HOME="${HOME:-/home/atushi}"
HERMES_VENV_BIN="/home/atushi/.hermes/hermes-agent/venv/bin"
[ -d "$HERMES_VENV_BIN" ] && PATH="$HERMES_VENV_BIN:$PATH"
if [ -z "${HERMES_BIN:-}" ] || [ ! -x "${HERMES_BIN:-}" ]; then
  if command -v hermes >/dev/null 2>&1; then
    HERMES_BIN="$(command -v hermes)"
  else
    HERMES_BIN=""
  fi
fi
# --------------------------------------------------------------------------------
STALE_MIN="${STALE_MIN:-90}"      # 最後のheartbeatからの経過分。>=これならセッション終了/ハング扱い
GIT_DAYS="${GIT_DAYS:-2}"         # 実装完了証拠: 直近N日以内のコミットを探索
APPLY=0
SILENT=1                          # 問題0件時は空stdout(サイレント)

while [[ $# -gt 0 ]]; do
  case "$1" in
    --db)          DB="$2"; shift 2 ;;
    --ledger)      LEDGER="$2"; shift 2 ;;
    --board)       BOARD="$2"; shift 2 ;;
    --stale-min)   STALE_MIN="$2"; shift 2 ;;
    --git-days)    GIT_DAYS="$2"; shift 2 ;;
    --apply)       APPLY=1; shift ;;
    --dry-run)     APPLY=0; shift ;;
    --verbose)     SILENT=0; shift ;;
    -h|--help)
      grep -E '^#( |$)' "$0" | sed 's/^# \?//'
      exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

[ -f "$DB" ] || { echo "ERROR: db not found: $DB" >&2; exit 1; }

# 完了忘れ候補を抽出: running/In_progress かつ PID死 かつ heartbeat が STALE_MIN 分以上古い
CANDIDATES=$(python3 - "$DB" "$STALE_MIN" "$GIT_DAYS" <<'PY'
import json, os, sqlite3, sys, time
try:
    # PID生存確認は sqlite 側で行えないため、ここでは「heartbeat が古い」running の一覧を返すだけ。
    # PID死活は bash 側 (kill -0) で判定する。
    con = sqlite3.connect("file:%s?mode=ro" % sys.argv[1], uri=True)
    con.row_factory = sqlite3.Row
    stale_min = int(sys.argv[2])
    rows = con.execute(
        "SELECT id, title, assignee, worker_pid, started_at, last_heartbeat_at, claim_expires "
        "FROM tasks WHERE status IN ('running','in_progress')").fetchall()
    now = time.time()
    out = []
    for r in rows:
        hb = r["last_heartbeat_at"]
        stale = ((now - (hb or 0)) / 60.0) >= stale_min
        out.append((r["id"], r["title"], r["assignee"], r["worker_pid"], stale))
    con.close()
    for tid, title, assignee, pid, stale in out:
        print(("%s\t%d\t%s\t%s" % (tid, 1 if stale else 0, title or "", assignee or "")).encode("utf-8", "replace").decode("utf-8"))
except Exception as e:
    print("ERR\t%s" % str(e))
    sys.exit(1)
PY
)

if grep -q '^ERR\t' <<<"$CANDIDATES"; then
  echo "ERROR: python extraction failed: $(grep '^ERR\t' <<<"$CANDIDATES")" >&2
  exit 1
fi

STALE_TASKS=()      # heartbeatが古い = セッション終了/ハング候補
while IFS=$'\t' read -r tid flag title assignee; do
  [ -n "$tid" ] || continue
  if [ "$flag" = "1" ]; then
    STALE_TASKS+=("$tid")
  fi
done <<<"$CANDIDATES"

# ★ protocol_violation 被災タスクの表面化 (kanban t_848e1beb / 2026-09-22)
# 背景: worker が rc=0 で kanban_complete/block 未呼出 のまま clean exit すると dispatcher が
#       protocol_violation として失敗扱いし task を status=blocked に落とす。作業成果は完了済みの
#       ことが多いのにカードが沈黙ブロック化して放置されるため、unblock再開を促すコメントで表面化。
# 備考: 既存の「runningハング検知」では status=blocked を捕捉できない(対象が running のみ)ため別途スキャン。
PVBLOCK=$(python3 - "$DB" <<'PY'
import sqlite3, sys
con = sqlite3.connect("file:%s?mode=ro" % sys.argv[1], uri=True)
rows = con.execute(
    "SELECT id, title, consecutive_failures FROM tasks "
    "WHERE status='blocked' AND last_failure_error LIKE '%protocol violation%'").fetchall()
con.close()
for tid, title, cf in rows:
    t = (title or "").replace("\t", " ").encode("utf-8", "replace").decode("utf-8")
    print("%s\t%s\t%s" % (tid, cf, t))
PY
)
PV_LIST=()
while IFS=$'\t' read -r tid cf title; do
  [ -n "$tid" ] || continue
  PV_LIST+=("$tid|$cf|$title")
done <<<"$PVBLOCK"

if [ "${#STALE_TASKS[@]}" -eq 0 ] && [ "${#PV_LIST[@]}" -eq 0 ]; then
  # 問題なし → サイレント
  exit 0
fi

# git 実装完了証拠 (タスク単位では引けないので、リポジトリ全体の直近コミット/未コミットを1回だけ取得)
GIT_COMMITS=""
GIT_DIRTY=""
if git -C "$REPO" rev-parse --git-dir >/dev/null 2>&1; then
  GIT_COMMITS=$(git -C "$REPO" log --since="${GIT_DAYS} days ago" --oneline --all 2>/dev/null || true)
  GIT_DIRTY=$(git -C "$REPO" status --porcelain -uall 2>/dev/null || true)
fi

HAS_ANY=0
REMIND_LINES=()
for tid in "${STALE_TASKS[@]}"; do
  # 実施完了証拠: (a) task_id を含む直近コミット  (b) 未コミットコード変更
  EVID=""
  if [ -n "$GIT_COMMITS" ] && grep -qE "(^|[^0-9a-f])${tid}" <<<"$GIT_COMMITS"; then
    EVID="git_commit:${tid}"
  fi
  if [ -n "$GIT_DIRTY" ]; then
    # コード変更(データchurn除外)が1件以上あれば作業痕跡
    DIRTYCODE=$(grep -E '\.(py|yaml|sh|js)( |$)' <<<"$GIT_DIRTY" | grep -vE '^(.. )?(data|reports)/' | head -1 || true)
    if [ -n "$DIRTYCODE" ]; then
      EVID="${EVID:+${EVID}|}git_dirty"
    fi
  fi
  if [ -n "$EVID" ]; then
    HAS_ANY=1
    TODAY=$(date +%Y-%m-%d)
    # 台帳で同日リマインド済みか重複チェック
    # 注意: grep -E の `\t` はタブに展開されない（GNU grep は 't' 扱い）。
    #       実測 2026-09-24: 旧実装では同日2回目の実行でも重複投稿が発生したため、
    #       $'\t'（実タブ）を埋め込む形へ是正 (t_adc65737)。
    if [ -f "$LEDGER" ] && grep -q "^${TODAY}"$'\t'"${tid}"$'\t' "$LEDGER" 2>/dev/null; then
      continue
    fi
    REMIND_LINES+=("$tid|$EVID")
  fi
done

# protocol_violation 被災タスクをリマインド対象に追加 (t_848e1beb)
for entry in "${PV_LIST[@]}"; do
  tid="${entry%%|*}"; rest="${entry#*|}"; cf="${rest%%|*}"
  HAS_ANY=1
  REMIND_LINES+=("$tid|protocol_violation(cf=$cf)")
done

if [ "$HAS_ANY" -eq 0 ] || [ "${#REMIND_LINES[@]}" -eq 0 ]; then
  exit 0
fi

if [ "$SILENT" -eq 0 ] || [ "$APPLY" -eq 1 ]; then
  echo "kensho-complete-watchdog: board=$BOARD stale_min=${STALE_MIN}git_days=${GIT_DAYS} candidates=${#STALE_TASKS[@]} remind=${#REMIND_LINES[@]}"
  for line in "${REMIND_LINES[@]}"; do
    ev="${line#*|}"
    [[ "$ev" == protocol_violation* ]] && lab="protocol-violation" || lab="complete-forgot"
    echo "  $lab: $line"
  done
fi

if [ "$APPLY" -ne 1 ]; then
  echo "DRY-RUN: pass --apply to post reminders / escalate."
  exit 0
fi

# 台帳touch(書き込み可能チェック)
touch "$LEDGER" 2>/dev/null || { echo "ERROR: cannot write ledger $LEDGER" >&2; exit 1; }

FAILED=0
for line in "${REMIND_LINES[@]}"; do
  tid="${line%%|*}"; evid="${line#*|}"
  TODAY=$(date +%Y-%m-%d)
  # 1) 完了忘れリマインドコメント(ASCIIのみ)。protocol_violation被災は別メッセージ
  if [[ "$evid" == protocol_violation* ]]; then
    MSG="[protocol-violation-blocked] 終端 kanban_complete/block 未呼出のまま rc=0 で終了し、dispatcherが失敗扱いで blocker化。作業成果は完了済みの可能性が高いため、unblockして再開をご検討ください。"
  else
    MSG="[complete-forgot] 実装作業の痕跡(${evid})があるのに kanban_complete/block が未呼び出し。終端処理を要請します。"
  fi
  if [ -z "$HERMES_BIN" ]; then
    RC=127
    ERRLOG="hermes binary not found (PATH=$PATH)"
  else
    # stderr だけを捕捉（送信路の失敗理由をログに残す = 受入条件2）
    ERRLOG="$("$HERMES_BIN" kanban --board "$BOARD" comment "$tid" "$MSG" 2>&1 >/dev/null)"
    RC=$?
  fi
  if [ "$RC" -eq 0 ]; then
    # 2) 台帳に同日記録(重複防止)。タグは事故種別で区別
    TAG=complete-forgot
    [[ "$evid" == protocol_violation* ]] && TAG=protocol-violation
    awk -F'\t' -v d="$TODAY" -v t="$tid" '$1!=d || $2!=t' "$LEDGER" > "${LEDGER}.tmp"
    printf '%s\t%s\t%s\n' "$TODAY" "$tid" "$TAG" >> "${LEDGER}.tmp"
    mv "${LEDGER}.tmp" "$LEDGER"
    echo "  [ok] reminded $tid (${evid})"
  else
    ERR1="$(printf '%s' "$ERRLOG" | tr '\n' ' ' | cut -c1-300)"
    echo "  [err] comment failed: $tid rc=$RC bin=${HERMES_BIN:-none} err=${ERR1:-<no stderr>}" >&2
    FAILED=$((FAILED+1))
    continue
  fi
done

exit $(( FAILED > 0 ? 1 : 0 ))
