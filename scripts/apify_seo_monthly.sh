#!/usr/bin/env bash
# apify_seo_monthly.sh — Apify SEO 監査→適用→効果測定の月次自動化
# 毎月1回・3:00に実行想定（cron登録: 0 3 1 * * /path/to/apify_seo_monthly.sh）
#
# 使い方:
#   bash scripts/apify_seo_monthly.sh           # 本実行
#   bash scripts/apify_seo_monthly.sh --dry-run # テスト実行（PUT実行せず終了コードのみ）
#   bash scripts/apify_seo_monthly.sh --skip-audit --skip-apply --skip-effect # ステップスキップ
#
# 依存: apify_seo_audit.py / apify_seo_apply.py / apify_seo_effect.py / apify_run_monitor.py
# 環境変数: APIFY_TOKEN（必須、未設定なら exit 2 で通知）

set -euo pipefail

# --- 設定 ---
PROJECT_DIR="/mnt/d/Project2/kensho"
SCRIPT_DIR="${PROJECT_DIR}/scripts"
REPORT_DIR="${PROJECT_DIR}/reports/apify-seo"
LOG_DIR="${PROJECT_DIR}/logs"
VENV_ACTIVATE="/home/atushi/kensho-venv/bin/activate"

# 実行日（JST基準）
RUN_DATE=$(date '+%Y-%m-%d')
RUN_MONTH=$(date '+%Y-%m')
TIMESTAMP=$(date '+%Y%m%d_%H%M%S')

# フラグ
DRY_RUN=false
SKIP_AUDIT=false
SKIP_APPLY=false
SKIP_EFFECT=false
VERBOSE=false

# 引数解析
while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run) DRY_RUN=true ;;
        --skip-audit) SKIP_AUDIT=true ;;
        --skip-apply) SKIP_APPLY=true ;;
        --skip-effect) SKIP_EFFECT=true ;;
        --verbose) VERBOSE=true ;;
        *) echo "Unknown option: $1" >&2; exit 2 ;;
    esac
    shift
done

# --- ログ設定 ---
mkdir -p "${LOG_DIR}" "${REPORT_DIR}"
LOG_FILE="${LOG_DIR}/apify_seo_monthly_${TIMESTAMP}.log"

# ログ関数
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "${LOG_FILE}"; }
log_err() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $*" | tee -a "${LOG_FILE}" >&2; }
log_warn() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] WARN: $*" | tee -a "${LOG_FILE}"; }

# APIFY_TOKEN チェック
if [[ -z "${APIFY_TOKEN:-}" && -z "${APIFY_TOKEN_DEFAULT:-}" ]]; then
    log_err "APIFY_TOKEN 環境変数が未設定"
    # 通知（Telegram等）は cron 側で stdout/stderr を転送する想定
    exit 2
fi

# 仮想環境アクティベート
if [[ -f "${VENV_ACTIVATE}" ]]; then
    source "${VENV_ACTIVATE}"
    export PYTHONPATH="${PROJECT_DIR}"
else
    log_warn "venv not found at ${VENV_ACTIVATE}, using system python"
fi

# DRY_RUN 時の振る舞い制御
PYTHON_DRY_RUN_ARGS=()
if [[ "${DRY_RUN}" == "true" ]]; then
    PYTHON_DRY_RUN_ARGS=(--limit 5)  # 少数のみで動作確認
    log "=== DRY RUN MODE (limit 5 actors) ==="
fi

# --- ステップ 1: 監査 ---
AUDIT_JSON="${REPORT_DIR}/apify-seo-audit-${RUN_DATE}.json"
AUDIT_CSV="${REPORT_DIR}/apify-seo-audit-${RUN_DATE}.csv"

if [[ "${SKIP_AUDIT}" != "true" ]]; then
    log "=== Step 1/3: SEO Audit (全公開アクター約200件) ==="
    cd "${PROJECT_DIR}"

    # --limit 200 で全アクター監査（時間分割のため actor 単位で中間保存される仕様）
    if python3 "${SCRIPT_DIR}/apify_seo_audit.py" \
        --limit 200 \
        --json "${AUDIT_JSON}" \
        --csv "${AUDIT_CSV}" \
        --top 8 \
        "${PYTHON_DRY_RUN_ARGS[@]}" \
        2>&1 | tee -a "${LOG_FILE}"; then
        log "✓ Audit completed: ${AUDIT_JSON}"
    else
        AUDIT_EXIT=$?
        log_err "Audit failed with exit code ${AUDIT_EXIT}"

        # 429/timeout の場合は前月結果を継続、次回に順延
        if grep -qi "429\|timeout\|rate limit\|Too Many Requests" "${LOG_FILE}" 2>/dev/null; then
            log_warn "Rate limit/timeout detected — keeping previous month results, will retry next run"
            # 前月結果があればそれを月次レポートとしてコピー
            PREV_MONTH=$(date -d "${RUN_DATE} -1 month" '+%Y-%m')
            PREV_REPORT="${REPORT_DIR}/monthly-${PREV_MONTH}.json"
            if [[ -f "${PREV_REPORT}" ]]; then
                cp "${PREV_REPORT}" "${REPORT_DIR}/monthly-${RUN_MONTH}.json"
                log "Copied previous month report: ${PREV_REPORT} -> monthly-${RUN_MONTH}.json"
            fi
            # apify_run_monitor.py の retry ロジックを流用するため、monitor を実行
            log "Triggering apify_run_monitor.py for retry queue..."
            python3 "${SCRIPT_DIR}/apify_run_monitor.py" 2>&1 | tee -a "${LOG_FILE}" || true
            exit 0  # 正常終了として扱い（cron 再実行待ち）
        fi

        exit ${AUDIT_EXIT}
    fi
else
    log "=== Step 1/3: SKIPPED (--skip-audit) ==="
    # 既存の最新 audit CSV を使用
    AUDIT_CSV=$(ls -t "${REPORT_DIR}"/apify-seo-audit-*.csv 2>/dev/null | head -1 || true)
    if [[ -z "${AUDIT_CSV}" ]]; then
        log_err "No audit CSV found to use with --skip-audit"
        exit 1
    fi
    log "Using existing audit CSV: ${AUDIT_CSV}"
fi

# --- ステップ 2: 適用 ---
APPLY_JSON="${REPORT_DIR}/apify-seo-apply-${RUN_DATE}.json"
APPLY_CSV="${REPORT_DIR}/apify-seo-apply-${RUN_DATE}.csv"

if [[ "${SKIP_APPLY}" != "true" ]]; then
    log "=== Step 2/3: SEO Apply (bulk mode, 1 actor = 1 PUT) ==="
    cd "${PROJECT_DIR}"

    # --bulk で 1 actor = 1 PUT（impact 順で上位 50 findings）
    if python3 "${SCRIPT_DIR}/apify_seo_apply.py" \
        --csv "${AUDIT_CSV}" \
        --bulk \
        --limit 50 \
        2>&1 | tee -a "${LOG_FILE}"; then
        log "✓ Apply completed: ${APPLY_JSON}"
    else
        APPLY_EXIT=$?
        log_err "Apply failed with exit code ${APPLY_EXIT}"

        # 429/timeout の場合は前月結果を継続、次回に順延
        if grep -qi "429\|timeout\|rate limit\|Too Many Requests" "${LOG_FILE}" 2>/dev/null; then
            log_warn "Rate limit/timeout detected during apply — keeping previous month results, will retry next run"
            PREV_MONTH=$(date -d "${RUN_DATE} -1 month" '+%Y-%m')
            PREV_REPORT="${REPORT_DIR}/monthly-${PREV_MONTH}.json"
            if [[ -f "${PREV_REPORT}" ]]; then
                cp "${PREV_REPORT}" "${REPORT_DIR}/monthly-${RUN_MONTH}.json"
                log "Copied previous month report: ${PREV_REPORT} -> monthly-${RUN_MONTH}.json"
            fi
            log "Triggering apify_run_monitor.py for retry queue..."
            python3 "${SCRIPT_DIR}/apify_run_monitor.py" 2>&1 | tee -a "${LOG_FILE}" || true
            exit 0
        fi

        exit ${APPLY_EXIT}
    fi
else
    log "=== Step 2/3: SKIPPED (--skip-apply) ==="
fi

# --- ステップ 3: 効果測定 ---
EFFECT_JSON="${REPORT_DIR}/apify-seo-effect-${RUN_DATE}.json"
MONTHLY_REPORT="${REPORT_DIR}/monthly-${RUN_MONTH}.json"

if [[ "${SKIP_EFFECT}" != "true" ]]; then
    log "=== Step 3/3: Effect Measurement (baseline=2026-09-04 → today) ==="
    cd "${PROJECT_DIR}"

    if python3 "${SCRIPT_DIR}/apify_seo_effect.py" \
        --date "${RUN_DATE}" \
        2>&1 | tee -a "${LOG_FILE}"; then
        log "✓ Effect measurement completed"

        # 最新 effect ポイント詳細を月次レポートとして保存
        # apify-seo-effect.json は累積だが、月次レポートとして単体ファイルも作る
        ACCUM_FILE="${REPORT_DIR}/apify-seo-effect.json"
        if [[ -f "${ACCUM_FILE}" ]]; then
            # 累積JSONから最新 measurement を抽出して月次レポートにマージ
            python3 -c "
import json, sys, os
from datetime import datetime

accum_path = '${ACCUM_FILE}'
monthly_path = '${MONTHLY_REPORT}'
run_date = '${RUN_DATE}'

with open(accum_path, 'r', encoding='utf-8') as f:
    accum = json.load(f)

measurements = accum.get('measurements', {})
# baseline=2026-09-04 から最新ポイントまでの measurement を抽出
relevant = {k: v for k, v in measurements.items() if k.startswith('2026-09-04->')}

monthly_report = {
    'month': '${RUN_MONTH}',
    'generated_at': datetime.now().isoformat(timespec='seconds'),
    'baseline_date': '2026-09-04',
    'measurement_date': run_date,
    'measurements': relevant,
    'kpi_summary': {}
}

# KPI サマリ計算（最新ポイント）
if relevant:
    latest_key = sorted(relevant.keys())[-1]
    latest = relevant[latest_key]
    actors = latest.get('actors', {})
    total_actors = len(actors)
    improving = sum(1 for m in actors.values() if isinstance(m, dict) and m.get('improving'))
    u30d_grew = sum(1 for m in actors.values() if isinstance(m, dict) and m.get('u30d_grew'))
    u30d_ge2 = sum(1 for m in actors.values() if isinstance(m, dict) and m.get('point_u30d', 0) >= 2)
    monthly_report['kpi_summary'] = {
        'total_actors': total_actors,
        'runs_improving': improving,
        'u30d_grew': u30d_grew,
        'u30d_ge2': u30d_ge2,
        'improving_ratio': round(improving / total_actors * 100, 1) if total_actors > 0 else 0,
    }

with open(monthly_path, 'w', encoding='utf-8') as f:
    json.dump(monthly_report, f, ensure_ascii=False, indent=1)

print(f'Monthly report saved: {monthly_path}')
print(f'KPI: {monthly_report[\"kpi_summary\"]}')
" 2>&1 | tee -a "${LOG_FILE}"

        log "✓ Monthly report generated: ${MONTHLY_REPORT}"
    fi
    else
        EFFECT_EXIT=$?
        log_err "Effect measurement failed with exit code ${EFFECT_EXIT}"

        # エラーでも前月結果があればコピーして継続
        PREV_MONTH=$(date -d "${RUN_DATE} -1 month" '+%Y-%m')
        PREV_REPORT="${REPORT_DIR}/monthly-${PREV_MONTH}.json"
        if [[ -f "${PREV_REPORT}" ]]; then
            cp "${PREV_REPORT}" "${MONTHLY_REPORT}"
            log "Copied previous month report as fallback: ${PREV_REPORT} -> ${MONTHLY_REPORT}"
        fi
        exit ${EFFECT_EXIT}
    fi
else
    log "=== Step 3/3: SKIPPED (--skip-effect) ==="
fi

# --- 完了 ---
log "=== Monthly SEO automation completed successfully ==="
log "Monthly report: ${MONTHLY_REPORT}"
log "Log file: ${LOG_FILE}"

# 結果サマリ出力（cron から Telegram 等へ転送用）
if [[ -f "${MONTHLY_REPORT}" ]]; then
    cat "${MONTHLY_REPORT}" | head -30
fi

exit 0