#!/bin/bash
# ============================================================
# team_memory_compact.sh — チーム長期記憶のcompaction化（Anthropic compaction パターン）
#
# 目的: AIチーム(critic/worker/qa)の短期notepad教訓 + loop_health状態が
#   3 notepadに分散・冗長化し、メモリ上限到達（avoidableな将来リスク）がある。
#   「重要なアーキテクチャ判断・未解決バグ・禁止領域を保持し、冗長な実行ログ・
#   陳腐化運用記録を破棄」を1スクリプトで集約する。
#
# 出自: https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
#
# compactionルール:
#   KEEP  = 未解決バグ / 要ユーザー対応 / アーキテクチャ判断 / 禁止領域 / 監視対象
#           / 方針・恒久ガード / 不変条件 （現行・維持すべき重要な状態）
#   EVICT = 解決済み / 復旧済み / クローズ / 断念 / 見送り / 日次運用記録 / 健康度スナップ
#           （過去3日超 または 解決・運用記録として陳腐化）
#
# 失敗時代替: notepadは強制圧縮せず「アーカイブ退避」のみ。
#   ・全元値はまず reports/backups/ にバックアップ（巻き戻し可能）
#   ・現行状態（未解決/要対応/アーキテクチャ等）は保護
#   --evict 指定・または対象が「解決済み·運用記録」と判定されたエントリのみ退避
#
# 出力:
#   reports/team-compaction-YYYYMMDD.md   — 集約レポート（保持+退避+loop_healthスナップショット）
#   reports/backups/notepad-<job>-<key>-backup-YYYYMMDD.md — 巻き戻し用バックアップ
#
# Usage:
#   bash scripts/team_memory_compact.sh          # 実行（退避対象をnotepadから除去しレポートへ集約）
#   bash scripts/team_memory_compact.sh --dry-run  # 実行せず現行before/after差分のみ表示
#   bash scripts/team_memory_compact.sh --profile kensho-sweeps
# ============================================================
set -uo pipefail

# ─── Config ─────────────────────────────────────────────────────────────────
PROFILE="${PROFILE:-kensho-sweeps}"
HERMES_HOME="${HERMES_HOME:-/home/atushi/.hermes/profiles/$PROFILE}"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPORTS_DIR="$REPO_DIR/reports"
BACKUP_DIR="$REPORTS_DIR/backups"
STATE_FILE="${STATE_FILE:-$HERMES_HOME/data/loop_health_state.json}"
DRY_RUN=0
KEEP_DAYS="${KEEP_DAYS:-3}"     # この日数を超える解決/運用記録を退避対象に

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=1; shift ;;
    --profile) PROFILE="$2"; HERMES_HOME="/home/atushi/.hermes/profiles/$2"; shift 2 ;;
    --keep-days) KEEP_DAYS="$2"; shift 2 ;;
    --state) STATE_FILE="$2"; shift 2 ;;
    *) shift ;;
  esac
done

export HERMES_HOME
TODAY="$(date +%Y%m%d)"
REPORT="$REPORTS_DIR/team-compaction-$TODAY.md"
mkdir -p "$REPORTS_DIR" "$BACKUP_DIR"

# チームnotepad定義: notepad_name|job_id|key
NOTEPADS=(
  "critic|4baf143523e0|lessons"
  "worker|5e8ec4984bba|lessons"
  "worker|5e8ec4984bba|handoff"
  "qa|033ff6065ef7|lessons"
)

NOTEPAD_CLI() { hermes cron notepad "$@"; }
# get value only if the key exists; else empty (missing-key get は空メッセージをstdoutに出すため要ガード)
NOTEPAD_GET() {
  local job="$1" key="$2"
  if NOTEPAD_CLI "$job" list 2>/dev/null | grep -q "^  $key ="; then
    NOTEPAD_CLI "$job" get "$key"
  else
    echo ""
  fi
}

# ─── Collect current state ──────────────────────────────────────
declare -A BEFORE_BYTES AFTER_BYTES KEPT_EVICTED
declare -a KEPT_BLOCKS EVICT_BLOCKS
declare -a REPORT_NAMES

for entry in "${NOTEPADS[@]}"; do
  name="${entry%%|*}"; rest="${entry#*|}"; job="${rest%%|*}"; key="${rest##*|}"
  val="$(NOTEPAD_GET "$job" "$key")"
  if [[ -z "$val" ]] && ! NOTEPAD_CLI "$job" list 2>/dev/null | grep -q "^  $key ="; then
    continue
  fi
  bytes=$(printf '%s' "$val" | wc -c | tr -d ' ')
  BEFORE_BYTES["$name|$key"]=$bytes
  REPORT_NAMES+=("$name|$key")
done

# ─── Process each notepad ──────────────────────────────────────
REPORT_BODY=""
for entry in "${NOTEPADS[@]}"; do
  name="${entry%%|*}"; rest="${entry#*|}"; job="${rest%%|*}"; key="${rest##*|}"
  val="$(NOTEPAD_GET "$job" "$key")"
  if [[ -z "$val" ]] && ! NOTEPAD_CLI "$job" list 2>/dev/null | grep -q "^  $key ="; then
    continue
  fi
  before=${BEFORE_BYTES["$name|$key"]:-0}
  if [[ -z "$val" ]]; then
    AFTER_BYTES["$name|$key"]=0; KEPT_EVICTED["$name|$key"]=""
    continue
  fi

  # 分類（保持/退避をpythonワンショットで分離）
  cls_out=$(VAL="$val" python3 - <<PYEOF
import json, re, sys, os
from datetime import date
KEEP_MARKERS = ["要ユーザー対応","未解決","protocol_violation","疑い","アーキテクチャ","禁止","絶対ルール","監視","再発なら","推奨","方針","恒久ガード","不変条件","申し送り","鶏卵","要対応","継続監視"]
EVICT_MARKERS = ["解消","復旧","クローズ","断念","見送り","healthy","健全","実装なし","最優","回帰","配線","成功","PASS","green","unblocked"]
DATE_RE = re.compile(r"(\\d{4}-\\d\\d-\\d\\d)")
KEEP_DAYS=int("$KEEP_DAYS")
val = os.environ.get("VAL","")
def cls(l):
    if any(m in l for m in KEEP_MARKERS): return "keep"
    old=False
    m=DATE_RE.search(l)
    if m:
        try:
            y,mo,d=map(int,m.group(1).split("-")); old=(date.today()-date(y,mo,d)).days>KEEP_DAYS
        except Exception: old=False
    return "evict" if (old or any(m in l for m in EVICT_MARKERS)) else "keep"
k=[l for l in val.split("\n") if cls(l)=="keep"]
e=[l for l in val.split("\n") if cls(l)=="evict"]
print("\n".join(k))
print("=====EVICT=====")
print("\n".join(e))
PYEOF
)
  sep=$(printf '%s' "$cls_out" | grep -n '^=====EVICT=====$' | cut -d: -f1)
  if [[ -n "$sep" ]]; then
    kept_block="$(printf '%s' "$cls_out" | sed -n "1,$((sep-1))p")"
    evict_block="$(printf '%s' "$cls_out" | sed -n "$((sep+1)),\$p")"
  else
    kept_block="$(printf '%s' "$cls_out")"; evict_block=""
  fi

  after=$(printf '%s' "$kept_block" | wc -c | tr -d ' ')
  AFTER_BYTES["$name|$key"]=$after
  KEPT_EVICTED["$name|$key"]="${#kept_block}:${#evict_block}"

  REPORT_BODY+=$'\n## '"$name / $key  (job $job)"
  REPORT_BODY+=$'\n- before: '${before}'B → after: '${after}'B'
  if [[ -n "$kept_block" ]]; then
    REPORT_BODY+=$'\n### 保持（KEEP — 現行重要状態）\n```\n'"$kept_block"$'\n```'
  else
    REPORT_BODY+=$'\n- 保持エントリなし'
  fi
  if [[ -n "$evict_block" ]]; then
    REPORT_BODY+=$'\n### 退避（EVICT — 解決/運用記録）\n```\n'"$evict_block"$'\n```'
  else
    REPORT_BODY+=$'\n- 退避対象なし'
  fi

  # バックアップ保存（常に、dry-run除く）
  if [[ "$DRY_RUN" -eq 0 ]]; then
    backup="$BACKUP_DIR/notepad-$name-$key-backup-$TODAY.md"
    printf '%s\n' "$val" > "$backup"
    # 退避し、保持行をnotepadに再set（カラでなければ）
    if [[ -n "$kept_block" && "$evict_block" != "$val" ]]; then
      NOTEPAD_CLI "$job" set "$key" "$kept_block" >/dev/null 2>&1
    elif [[ -z "$kept_block" ]]; then
      NOTEPAD_CLI "$job" delete "$key" >/dev/null 2>&1
    fi
  fi
done

# ─── loop_health snapshots ────────────────────────────────────
LH_SNAPSHOT=""
if [[ -f "$STATE_FILE" ]]; then
  LH_SNAPSHOT="$(cat "$STATE_FILE")"
fi

# ─── Sum BEFORE/AFTER ──────────────────────────────────────────
TOTAL_BEFORE=0; TOTAL_AFTER=0
for k in "${!BEFORE_BYTES[@]}"; do
  TOTAL_BEFORE=$(( TOTAL_BEFORE + BEFORE_BYTES[$k] ))
  TOTAL_AFTER=$(( TOTAL_AFTER + ${AFTER_BYTES[$k]:-0} ))
done

# ─── Write report ──────────────────────────────────────────────
{
  echo "# チーム長期記憶 compaction レポート ($TODAY)"
  echo ""
  echo "出自: Anthropic effective-context-engineering (compactionパターン)"
  echo "適用: 重要(未解決/アーキテクチャ/禁止領域)を保持、解決済み/運用記録を破棄"
  echo ""
  echo "## 集約結果"
  echo "- 対象: critic/worker/qa 3 notepad lessons(+worker handoff) + loop_health"
  echo "- notepad合計メモリ使用量: ${TOTAL_BEFORE}B → ${TOTAL_AFTER}B"
  if [[ "$TOTAL_BEFORE" -gt 0 ]]; then
    PCT=$(( (TOTAL_BEFORE - TOTAL_AFTER) * 100 / TOTAL_BEFORE ))
    echo "- 削減率: ${PCT}%"
  else
    echo "- 削減率: n/a"
  fi
  echo ""
  echo "## エントリ別 before→after"
  for entry in "${NOTEPADS[@]}"; do
    name="${entry%%|*}"; rest="${entry#*|}"; job="${rest%%|*}"; key="${rest##*|}"
    if [[ -n "${BEFORE_BYTES["$name|$key"]:-}" ]]; then
      echo "- $name/$key: ${BEFORE_BYTES["$name|$key"]}B → ${AFTER_BYTES["$name|$key"]:-0}B"
    fi
  done
  echo ""
  echo "$REPORT_BODY"
  echo ""
  echo "## loop_health 状態スナップショット"
  printf '%s\n' "$LH_SNAPSHOT"
  echo ""
  echo "戻し: バックアップ reports/backups/notepad-*-backup-$TODAY.md を"
  echo "  'hermes cron notepad <job> set <key> \"\$(cat <file>)\"' で復元（HERMES_HOME=$HERMES_HOME）"
} > "$REPORT"

# ─── Output ────────────────────────────────────────────────────
echo "team_memory_compact: ${TOTAL_BEFORE}B → ${TOTAL_AFTER}B (notepad合計)"
echo "report: $REPORT"
if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "(dry-run: notepad/state は未変更)"
else
  echo "notepad 更新・退避済み (バックアップあり)"
fi
exit 0
