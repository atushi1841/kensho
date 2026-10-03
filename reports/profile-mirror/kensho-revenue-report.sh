#!/bin/bash
# kensho-revenue-report.sh - Critic job for AI team improvement
# This script is the critic role in the self-improving loop.
#
# v145 (critic): プレースホルダ lessons 書き込み構造バグを自己修復。
#   - step4/5 の無条件 `set lessons` を削除（上書きで教訓が毎回消えるのを防ぐ）
#   - step3 観察で前日実測値をログから算出し reports/critic-observe-YYYY-MM-DD.md に保存
#   - lessons は「日付: 前日実測サマリ1行」を追記＋最大5行ローリング運用
#     （既存教訓を生かし、プレースホルダ文言を一切書き込まない）
# v146 (critic): step3観察にConnectTimeout源別内訳（KENKAKU/KCLUB/KEMA/CPMK）を追加。
#   観察レポートへ「[源別ConnectTimeout] KENKAKU=N KCLUB=M KEMA=K CPMK=L」を行として追記。
#   応募ロジック・config・パイプライン・kenkaku.pyには一切触れない（v144のkenkaku単体対策が
#   全4源に波及している事実を毎日落としたくないための可視化）。

set -u
CRON_JOB_ID="4baf143523e0"
KENSHO_REPO="/mnt/d/Project2/kensho"
SELF_DIR="/home/atushi/.hermes/profiles/kensho-sweeps/scripts"
TODAY_STR=$(date '+%Y-%m-%d')
YDAY_STR=$(date -d 'yesterday' '+%Y-%m-%d' 2>/dev/null || date -v-1d '+%Y-%m-%d')
YDAY_NUM=${YDAY_STR//-/}
OBS_FILE="$KENSHO_REPO/reports/critic-observe-${TODAY_STR}.md"

# 0. ループ健康度
HEALTH_JSON=$(bash "$SELF_DIR/loop_health.sh" 2>/dev/null || echo '{}')
echo "## 0. ループ健康度"
# v140 (t_ef9e899f): このcriticロールに必要な要約のみ注入(role_summary.critic)。
# full JSON はトップレベルに温存しているがLLM promptへは入れない。
# 2026-10-04 修正(t_ 未採番): v140 の絞り込みが priority / advice まで捨てており、
#   critic プロンプトの「script出力の advice.critic フィールドが行動方針を決定する」が
#   参照先不在になっていた（= 判断材料ゼロで毎時何も提案しない）。role_summary.critic に
#   priority と advice.critic を併せて注入する（実測: 15キー→priority/advice込み）。
echo "$HEALTH_JSON" | jq -r '. as $t | ($t.role_summary.critic // $t) as $r | {role_summary: $r, priority: $t.priority, advice: $t.advice.critic}' 2>/dev/null || echo "$HEALTH_JSON"
echo ""

# 0.5 直近の収益データ（revenue-daily.json 最終エントリ）
#   commit 45be8f0（2026-09-19 17:58）が本スクリプトを古い控えで上書きし、この節が消失していた
#   （lost update）。critic は Apify/RapidAPI/Gumroad の実数を見られず提案が痩せるため、
#   7fcaf78（2026-09-07）版の内容を現行の並び（0.5）へ復元した（2026-09-25 t_61d0db99）。
#   読み取り専用・既存セクションは変更しない。見出しはヘルパー側が出力する（二重echo防止）。
python3 "$SELF_DIR/revenue_headline.py" 2>&1 || echo "  (読み取りエラー)"
echo ""

# 0.6 監視系cronの連続失敗検知（t_eb3528fb / 2026-09-30）
#   1回fire=1日 の監視ジョブでは failure_streak>=3 が「last_status=error 3日連続」に相当する。
#   notepad の lessons は最大5行ローリング＋同日付は重複削除のため数時間で記録が消え、
#   「3日連続なら検知」を記録だけに頼るのは不可能（2026-09-30実測）。そこで毎回 jobs.json
#   から生データを再計算して critic の文脈へ注入する＝消えない常時検知。読み取り専用。
CRON_JOBS_JSON="/home/atushi/.hermes/profiles/kensho-sweeps/cron/jobs.json"
echo "## 0.6 監視系cron健康度（3日連続error検知 / t_eb3528fb）"
if [ -f "$CRON_JOBS_JSON" ] && command -v jq >/dev/null 2>&1; then
    CRON_ALERT=$(jq -r '.jobs[] | select((.failure_streak // 0) >= 3) | "⚠️ ALERT: \(.name) が3日連続 last_status=error（streak=\(.failure_streak), last_error=\((.last_error // "-") | .[0:60])）→ ①当該ジョブを pause ②収集系revenue cron の結果diff監視へ切替"' "$CRON_JOBS_JSON" 2>/dev/null || true)
    CRON_STREAK=$(jq -r '.jobs[] | select((.failure_streak // 0) >= 1) | "  - \(.name): streak=\(.failure_streak) last_status=\(.last_status // "-") last_run=\((.last_run_at // "-") | .[0:19])"' "$CRON_JOBS_JSON" 2>/dev/null || true)
    if [ -n "${CRON_ALERT:-}" ]; then
        echo "$CRON_ALERT"
    else
        echo "  (3日連続失敗ジョブなし)"
    fi
    if [ -n "${CRON_STREAK:-}" ]; then
        echo "$CRON_STREAK"
    fi
else
    echo "  (jobs.json 未検出のため判定不能)"
fi
echo ""

# 1. 自分のnotepadから教訓を読む
LESSONS=$(hermes cron notepad "$CRON_JOB_ID" get lessons 2>/dev/null || echo "教訓なし")
echo "## 1. 自分のnotepadから教訓を読む"
echo "$LESSONS"
echo ""

# 2. worker/QAのnotepadも確認
echo "## 2. worker/QAのnotepadも確認"
for job in 5e8ec4984bba 033ff6065ef7; do
    echo "--- Job $job ---"
    hermes cron notepad "$job" get lessons 2>/dev/null || echo "教訓なし"
done
echo ""

# 3. 観察（Observe）: 前日の実測値をログから算出して保存
echo "## 3. 観察（Observe）: 前日($YDAY_STR)実測値"
# 前日KENKAKU平均取得件数: 各収集セッションの "計N件" の平均
KENKAKU_AVG_ALL=$(grep -h -oE '\[KENKAKU\] 計[0-9]+件' "$KENSHO_REPO"/logs/collect_${YDAY_NUM}_*.log 2>/dev/null)
KENKAKU_N=$(echo "$KENKAKU_AVG_ALL" | grep -c '[0-9]' || true)
if [ "$KENKAKU_N" -gt 0 ]; then
  KENKAKU_SUM=$(echo "$KENKAKU_AVG_ALL" | grep -oE '[0-9]+' | awk '{s+=$1} END {print s}')
  KENKAKU_AVG=$(awk -v s="$KENKAKU_SUM" -v n="$KENKAKU_N" 'BEGIN {printf "%.1f", s/n}')
else
  KENKAKU_AVG="n/a"; KENKAKU_N="0"
fi
echo "- 前日KENKAKU平均取得: ${KENKAKU_AVG}件（${KENKAKU_N}セッション）"

# 前日ConnectTimeout行数: 収集ログ全体の行数
CT_COUNT=$(grep -h -c "ConnectTimeout" "$KENSHO_REPO"/logs/collect_${YDAY_NUM}_*.log 2>/dev/null | awk -F: '{s+=$NF} END {print s+0}')
echo "- 前日ConnectTimeout: ${CT_COUNT}件/day"

# v146: 前日ConnectTimeout源別内訳（KENKAKU/KCLUB/KEMA/CPMK）
CT_LINES=$(grep -h "ConnectTimeout" "$KENSHO_REPO"/logs/collect_${YDAY_NUM}_*.log 2>/dev/null || true)
CT_KENKAKU=$(printf '%s\n' "$CT_LINES" | grep -c '\[KENKAKU\]' || true)
CT_KCLUB=$(printf '%s\n' "$CT_LINES" | grep -c '\[KCLUB\]' || true)
CT_KEMA=$(printf '%s\n' "$CT_LINES" | grep -c '\[KEMA\]' || true)
CT_CPMK=$(printf '%s\n' "$CT_LINES" | grep -c '\[CPMK\]' || true)
CT_SRC_SUM=$((CT_KENKAKU + CT_KCLUB + CT_KEMA + CT_CPMK))
echo "- 前日ConnectTimeout内訳: [源別ConnectTimeout] KENKAKU=${CT_KENKAKU} KCLUB=${CT_KCLUB} KEMA=${CT_KEMA} CPMK=${CT_CPMK}（計${CT_SRC_SUM}/総${CT_COUNT}件）"

# 前日apply成功率: auto_YYYYMMDD.log の "完了: N成功/Mエラー" を集計
APPLY_SUM=$(grep -h -oE '完了: *[0-9]+成功 */ *[0-9]+エラー' "$KENSHO_REPO"/logs/auto_${YDAY_NUM}.log 2>/dev/null \
  | sed -E 's/完了: *([0-9]+)成功 *\/ *([0-9]+)エラー/\1 \2/' \
  | awk '{s+=$1; e+=$2} END {if ((s+e) > 0) printf "%d %d", s, e; else printf "0 0"}')
APPLY_S=$(echo "$APPLY_SUM" | cut -d' ' -f1)
APPLY_E=$(echo "$APPLY_SUM" | cut -d' ' -f2)
if [ "$((APPLY_S + APPLY_E))" -gt 0 ]; then
  APPLY_RATE=$(awk -v s="$APPLY_S" -v e="$APPLY_E" 'BEGIN {printf "%.1f", 100*s/(s+e)}')
else
  APPLY_RATE="n/a"
fi
echo "- 前日apply成功率: ${APPLY_RATE}%（成功${APPLY_S}/エラー${APPLY_E}）"

# 観察結果をレポートファイルに保存
mkdir -p "$KENSHO_REPO/reports"
{
  echo "# Critic観察レポート $TODAY_STR"
  echo ""
  echo "対象: 前日 ${YDAY_STR}"
  echo "- KENKAKU平均取得: ${KENKAKU_AVG}件（${KENKAKU_N}セッション）"
  echo "- ConnectTimeout: ${CT_COUNT}件/day"
  echo "- [源別ConnectTimeout] KENKAKU=${CT_KENKAKU} KCLUB=${CT_KCLUB} KEMA=${CT_KEMA} CPMK=${CT_CPMK}（計${CT_SRC_SUM}件）"
  echo "  - KENKAKU: ${CT_KENKAKU}件"
  echo "  - KCLUB: ${CT_KCLUB}件"
  echo "  - KEMA: ${CT_KEMA}件"
  echo "  - CPMK: ${CT_CPMK}件"
  echo "- apply成功率: ${APPLY_RATE}%（成功${APPLY_S}/エラー${APPLY_E}）"
} > "$OBS_FILE"
echo "- 観察レポート保存: $OBS_FILE"
echo ""

# 3.5 Gumroad鮮度・失効（t_61d0db99 受入基準3 / 2026-09-25）
#   日次収集は Cookie 失効時でも login_ok=false の state を書いて exit 0 で終わるため、
#   失効が「収集成功」に見えて Telegram に届かなかった。login_ok=false または
#   最終成功24h超を【要対応】として明示する。読み取り専用・秘密値は出力しない。
#   見出しはヘルパー側が出力する（二重echo防止）。
python3 "$SELF_DIR/gumroad_freshness.py" 2>&1 || echo "  (Gumroad鮮度の読み取り失敗)"
echo ""

# 4. 教訓notepadに「前回の提案は効果があったか」を反映（観察値に基づく追加はstep7へ集約）
echo "## 4. 教訓notepadへの記録（観察ベース追記はstep7で実施）"
echo "（上書き禁止: 実測サマリはstep7で追記・最大5行ローリング）"
echo ""

# 5. この分析で見つけた新たな問題点の確認（観察レポートに記録済み）
echo "## 5. 新たな問題点の確認"
echo "（詳細は観察レポート $OBS_FILE を参照）"
echo ""

# 6. 提案はエビデンスベースで行う
echo "## 6. 提案（エビデンスベース）"
echo "（健康度JSONの advice.critic に従い、観察レポートの実測値から提案を生成）"
echo ""

# 7. 終了時: 教訓notepadへ実測サマリを追記（最大5行ローリング、プレースホルダ禁止）
echo "## 7. 最終教訓更新（実測サマリ追記）"
# 新エントリ: 日付 + 前日実測サマリ1行
NEW_LINE="${YDAY_STR}: KENKAKU平均 ${KENKAKU_AVG}件 / ConnectTimeout ${CT_COUNT}件 / apply成功率 ${APPLY_RATE}%"
# 既存lessonsを取得し、notepad出力のfooter(updated:)・エラー文のみ除去
OLD_LESSONS=$(hermes cron notepad "$CRON_JOB_ID" get lessons 2>/dev/null || true)
OLD_CLEAN=$(printf '%s\n' "$OLD_LESSONS" \
  | sed '/^[[:space:]]*updated:/d; /^Set notepad key/d' \
  | grep -v '^No notepad key' \
  | sed '/^$/d' \
  | head -20 || true)
# 新エントリを先頭に、既存教訓を後ろに連結して最大5行にローリング
if [ -n "$OLD_CLEAN" ]; then
  MERGED=$(printf '%s\n%s\n' "$NEW_LINE" "$OLD_CLEAN" | head -5)
else
  MERGED="$NEW_LINE"
fi
# 同一日付の旧エントリがあれば新しい1行だけ残す（重複防止）
MERGED=$(printf '%s\n' "$MERGED" | awk -v d="$YDAY_STR" \
  '$0 ~ ("^" d "[ ：:]") { if(!seen){print; seen=1}; next } {print}')
hermes cron notepad "$CRON_JOB_ID" set lessons "$MERGED"
echo "$MERGED"
echo ""

# 8. 事後効果測定（Outcome Review）: 過去N日 done タスクの実測値再確認 (t_eca89f41)
#    「テスト通過=done」で終わらせず、before/after の実KPIが数値で確認できたかを毎時再確認する。
#    出力は critic プロンプトに注入され、未実測タスクは再提案 or 実測追記の対象になる。
echo "## 8. 事後効果測定（Outcome Review / 過去7日 done）"
python3 "$KENSHO_REPO/scripts/outcome_review_check.py" \
  --days 7 --reports-dir "$KENSHO_REPO/reports" --write-report 2>/dev/null \
  || echo "(outcome_review_check 実行失敗: scripts/outcome_review_check.py を確認)"
echo ""

# 9. Kanban同期（オプション）
echo "## 9. Kanban同期"
bash "$SELF_DIR/kensho-kanban-sync.sh" critic || true
