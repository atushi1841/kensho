#!/usr/bin/env bash
# kensho-timeout-watch.sh — timeout監視定例化 (kanban t_e366401f, 2026-09-15)
#
# 1日1回、前日の収集ログ logs/collect_YYYYMMDD_*.log から
# ソース別(KENKAKU/KCLUB/KEMA/CPMK)Timeout件数を自動集計し、
# logs/timeout_watch.tsv に日次台帳行を追記(upsert)する。
# 閾値(既定20件/day)超が2日連続で成立したら kensho-critic へ
# エスカレーションカードを起票(idempotency-key + 未クローズ重複ガード)。
#
# 読み取り専用。応募ロジック・config・パイプラインには一切触れない。
# v144(t_902d09ac kenkakuリトライ)GO待ちの間もエスカ見逃しを防ぐ定例監視。
#
# 使い方:
#   bash kensho-timeout-watch.sh                     # 通常運用(前日対象)
#   TIMEOUT_WATCH_DATE=YYYY-MM-DD bash ...           # 対象日override(バックフィル/検証)
#   TIMEOUT_WATCH_DRY=1 bash ...                     # 起票条件成立時もカードを作らず表示
#   TIMEOUT_WATCH_STATE=/path bash ...               # 台帳TSV override(検証用)
#
# crontab(WSL): 55 7 * * * bash /home/atushi/.hermes/profiles/kensho-revenue-worker/scripts/kensho-timeout-watch.sh >> /mnt/d/Project2/kensho/logs/timeout_watch_cron.log 2>&1
#
# 変更履歴:
#   t_e366401f (2026-09-15): 新設
#   t_e67d5550 (2026-09-24): 起票路の絶対パス化 — cron最小PATH(/usr/bin:/bin)では
#     bare `hermes` が exit 127 で解決不能。エスカレーション条件成立時にだけ
#     静かに全滅する潜在バグ(親 t_adc65737 と同型)を修正。集計・閾値・判定は不変。
set -uo pipefail

REPO="/mnt/d/Project2/kensho"
BOARD="kensho-ai-team"
DB="/home/atushi/.hermes/kanban/boards/kensho-ai-team/kanban.db"
STATE="${TIMEOUT_WATCH_STATE:-$REPO/logs/timeout_watch.tsv}"
THRESHOLD="${TIMEOUT_WATCH_THRESHOLD:-20}"
DATE="${TIMEOUT_WATCH_DATE:-$(date -d 'yesterday' +%Y-%m-%d)}"
NUM="${DATE//-/}"
PREV_DATE=$(date -d "$DATE -1 day" +%Y-%m-%d)
PREV_NUM="${PREV_DATE//-/}"
SELF="/home/atushi/.hermes/profiles/kensho-revenue-worker/scripts/kensho-timeout-watch.sh"

# --- 起票路の堅牢化 (t_e67d5550) ------------------------------------------------
# 実測: cron の最小 PATH(/usr/bin:/bin) では `hermes` が解決できず、起票行が
# exit 127 (= `hermes: not found`) で必ず失敗する。エスカレーション条件
# (>threshold x2日) が一度も成立していなかったため今日まで顕在化していない
# = 最も必要な瞬間に安全網が機能しない潜在バグ。t_adc65737(complete-watchdog)と
# 同一の真因クラス。PATH 依存をやめ、絶対パスで hermes を解決する。
# 見つからなければ失敗理由(PATH/HERMES_VENV_BIN)を stderr に残して exit 127。
export HOME="${HOME:-/home/atushi}"
HERMES_VENV_BIN="${HERMES_VENV_BIN:-/home/atushi/.hermes/hermes-agent/venv/bin}"
[ -d "$HERMES_VENV_BIN" ] && PATH="$HERMES_VENV_BIN:$PATH"
if [ -z "${HERMES_BIN:-}" ] || [ ! -x "${HERMES_BIN:-}" ]; then
  if command -v hermes >/dev/null 2>&1; then
    HERMES_BIN="$(command -v hermes)"
  else
    HERMES_BIN=""
  fi
fi
# --------------------------------------------------------------------------------

if ! touch "$STATE" 2>/dev/null; then
  echo "[error] cannot write state file: $STATE" >&2
  exit 1
fi

FILES=("$REPO"/logs/collect_"${NUM}"_*.log)
if [ ! -e "${FILES[0]}" ]; then
  echo "[$DATE] no collect logs found (logs/collect_${NUM}_*.log); skip"
  exit 0
fi

# 検証コマンダー.Rule: ソース別Timeout集計 (t_e366401f 受理条件と同一grep)
KENKAKU=$(grep -hoE '\[KENKAKU\].*(Timeout|timeout)' "${FILES[@]}" 2>/dev/null | wc -l)
KCLUB=$(grep -hoE '\[KCLUB\].*(Timeout|timeout)' "${FILES[@]}" 2>/dev/null | wc -l)
KEMA=$(grep -hoE '\[KEMA\].*(Timeout|timeout)' "${FILES[@]}" 2>/dev/null | wc -l)
CPMK=$(grep -hoE '\[CPMK\].*(Timeout|timeout)' "${FILES[@]}" 2>/dev/null | wc -l)
TOTAL=$((KENKAKU + KCLUB + KEMA + CPMK))

echo "[$DATE] timeout by source: KENKAKU=$KENKAKU KCLUB=$KCLUB KEMA=$KEMA CPMK=$CPMK total=$TOTAL (threshold $THRESHOLD/day)"

# 台帳 upsert(同日行は置換・再実行でドリフトした最新値を残す)
ROW="${DATE}	${TOTAL}	${KENKAKU}	${KCLUB}	${KEMA}	${CPMK}"
awk -F'\t' -v d="$DATE" '$1 != d' "$STATE" > "${STATE}.tmp"
printf '%s\n' "$ROW" >> "${STATE}.tmp"
mv "${STATE}.tmp" "$STATE"

# 2日連続判定: 前日(${PREV_DATE})の台帳行が存在し、両日とも閾値超
PREV_TOTAL=$(awk -F'\t' -v d="$PREV_DATE" '$1 == d {print $2; exit}' "$STATE")

if [ "$TOTAL" -le "$THRESHOLD" ] || [ -z "${PREV_TOTAL:-}" ] || [ "$PREV_TOTAL" -le "$THRESHOLD" ]; then
  echo "[$DATE] escalation not triggered (cur=$TOTAL prev=${PREV_TOTAL:-n/a})"
  exit 0
fi

# 重複ガード: 未クローズの timeout-watch-* カードが1枚でもあれば起票しない(毎日スパム防止)
OPEN=$(python3 - "$DB" <<'PY' 2>/dev/null || echo 0
import sqlite3, sys
try:
    con = sqlite3.connect("file:%s?mode=ro" % sys.argv[1], uri=True)
    n = con.execute(
        "select count(*) from tasks where idempotency_key like 'timeout-watch-%' "
        "and status not in ('done','archived','cancelled')").fetchone()[0]
    con.close()
    print(n)
except Exception:
    print("0")
PY
)
if [ "${OPEN:-0}" -gt 0 ]; then
  echo "[$DATE] escalation condition met but an open timeout-watch card exists (open=$OPEN); skip create"
  exit 0
fi

TITLE="timeout-watch: >${THRESHOLD}/day x2 days (${PREV_DATE}=${PREV_TOTAL}, ${DATE}=${TOTAL}) critic escalation"
BODY="ASCII escalation from kensho-timeout-watch.sh (kanban t_e366401f).
Days: ${PREV_DATE} total=${PREV_TOTAL} ; ${DATE} total=${TOTAL} (threshold ${THRESHOLD}/day, both exceeded).
Breakdown ${DATE}: KENKAKU=${KENKAKU} KCLUB=${KCLUB} KEMA=${KEMA} CPMK=${CPMK}.
Ledger: ${STATE}
Script: ${SELF}
Verify cmd: grep -hoE '\\[(KENKAKU|KCLUB|KEMA|CPMK)\\].*(Timeout|timeout)' ${REPO}/logs/collect_${NUM}_*.log | cut -d']' -f1 | sort | uniq -c
Context: v144 kenkaku retry (t_902d09ac) may still be pending GO; spike here is cross-source. Decide if a source-wide mitigation review is needed."

if [ "${TIMEOUT_WATCH_DRY:-0}" = "1" ]; then
  # DRY: 起票はせず「hermes 解決に到達したか」を必ずログに残す(t_e67d5550 受入条件2)
  if [ -n "${HERMES_BIN:-}" ]; then
    echo "[$DATE] hermes resolved: ${HERMES_BIN} (PATH=${PATH})"
  else
    echo "[$DATE] ERROR: hermes CLI not found (PATH=${PATH}, HERMES_VENV_BIN=${HERMES_VENV_BIN}); DRY create skipped" >&2
    exit 127
  fi
  echo "[$DATE] DRY-RUN would create critic card: $TITLE"
  exit 0
fi

if [ -z "${HERMES_BIN:-}" ]; then
  echo "[$DATE] ERROR: hermes CLI not found (PATH=${PATH}, HERMES_VENV_BIN=${HERMES_VENV_BIN}); kanban create skipped" >&2
  exit 127
fi

"$HERMES_BIN" kanban --board "$BOARD" create "$TITLE" \
  --body "$BODY" \
  --assignee kensho-critic \
  --idempotency-key "timeout-watch-${NUM}" \
  --priority 10 2>&1
rc=$?
if [ $rc -eq 0 ]; then
  echo "[$DATE] ESCALATED: critic card created (idempotency-key=timeout-watch-${NUM})"
else
  echo "[$DATE] ERROR: kanban create failed rc=$rc (bin=${HERMES_BIN})" >&2
fi
exit $rc
