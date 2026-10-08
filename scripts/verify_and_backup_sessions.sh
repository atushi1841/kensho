#!/bin/bash
# verify_and_backup_sessions.sh — 日次セッション検証+リフレッシュ+バックアップ
# Cron: 0 3 * * * → /home/atushi/kensho-secrets/YYYYMMDD/x_session_*.json に保存
# 検出: auth_token/ct0欠落 or セッション14日以上 → --write でリフレッシュ
# 通知: Telegram /logs/session_verify_YYYYMMDD.log に記録

set -euo pipefail

PROJECT_DIR="/mnt/d/Project2/kensho"
SCRIPT="$PROJECT_DIR/scripts/verify_and_refresh_session.py"
BACKUP_ROOT="/home/atushi/kensho-secrets"
DATE=$(date +%Y%m%d)
BACKUP_DIR="$BACKUP_ROOT/$DATE"
LOG_DIR="$PROJECT_DIR/logs"
LOG_FILE="$LOG_DIR/session_verify_${DATE}.log"
NOTIFY="/home/atushi/.hermes/profiles/kensho-sweeps/scripts/notify.sh"
STATE_FILE="$PROJECT_DIR/data/session_verify_state.json"
WARN_DAYS=14

mkdir -p "$BACKUP_DIR" "$LOG_DIR"
touch "$LOG_FILE"

log() { echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG_FILE"; }

# ── 既知の垢キー（config.yaml accountsから抽出）──
read -ra KEYS <<< "$(python3 -c "
import yaml, json
cfg = yaml.safe_load(open('$PROJECT_DIR/config.yaml', encoding='utf-8'))
print(' '.join(a['key'] for a in (cfg.get('accounts') or [])))
" 2>/dev/null || echo 'atushi16 kudou zin20120731 TankanNotes toushiwatch')"

REFRESHED=()
ALERTS=()

# ── ステップ1: 検証実行（dry-run）──
log "=== セッション検証開始 ($DATE) ==="
VERIFY_LOG="$LOG_DIR/session_verify_dry_${DATE}.log"
cd "$PROJECT_DIR"
if .venv/bin/python "$SCRIPT" --all > "$VERIFY_LOG" 2>&1; then
    log "✓ 検証完了（すべてログイン有効）"
else
    VERIFY_RC=$?
    log "⚠ 検証中にエラー/要ログインあり (rc=$VERIFY_RC)"
    # どの垢がNGか解析
    while read -r KEY; do
        if grep -q "\[NG\]\|\[要再ログイン\]" "$VERIFY_LOG" 2>/dev/null && \
           grep -B5 "\[NG\]\|\[要再ログイン\]" "$VERIFY_LOG" 2>/dev/null | grep -q "$KEY"; then
            ALERTS+=("$KEY: 要再ログインまたは回線不通")
        fi
    done <<< "${KEYS[@]}"
fi

# ── ステップ2: 期限切れセッションをリフレッシュ──
log "--- リフレッシュチェック ---"
REFRESHED=()
for KEY in "${KEYS[@]}"; do
    # セッションファイル取得
    SESS=$(python3 -c "
import yaml, sys
cfg = yaml.safe_load(open('$PROJECT_DIR/config.yaml', encoding='utf-8'))
for a in (cfg.get('accounts') or []):
    if a.get('key') == '$KEY' and a.get('session'):
        print(a['session'])
        break
" 2>/dev/null || echo "")
    [ -z "$SESS" ] && SESS="data/x_session_${KEY}.json"
    # toushiwatch は config に未登録なので fallback
    [ "$KEY" = "toushiwatch" ] && [ ! -f "$PROJECT_DIR/$SESS" ] && SESS="data/x_session_toushiwatch.json"
    
    FULL="$PROJECT_DIR/$SESS"
    [ ! -f "$FULL" ] && continue
    
    # 日数計算
    AGE_DAYS=$(python3 -c "
from pathlib import Path
import datetime
p = Path('$FULL')
print((datetime.datetime.now() - datetime.datetime.fromtimestamp(p.stat().st_mtime)).days)
" 2>/dev/null || echo "999")
    
    if [ "$AGE_DAYS" -ge "$WARN_DAYS" ]; then
        log "  $KEY: セッション $AGE_DAYS 日齢 → リフレッシュ実行 (--write)"
        # バックアップ取得（.bak<timestamp>）
        if .venv/bin/python "$SCRIPT" "$KEY" --write >> "$VERIFY_LOG" 2>&1; then
            log "  ✓ $KEY リフレッシュ完了"
            REFRESHED+=("$KEY")
        else
            log "  ✗ $KEY リフレッシュ失敗 → 要手動対応"
            ALERTS+=("$KEY: リフレッシュ失敗")
        fi
    else
        log "  $KEY: セッション $AGE_DAYS 日齢（OK）"
    fi
done

# ── ステップ3: バックアップコピー（git管理外・chmod 600）──
log "--- バックアップ保存 ---"
mkdir -p "$BACKUP_DIR"
for KEY in "${KEYS[@]}"; do
    SESS=$(python3 -c "
import yaml
cfg = yaml.safe_load(open('$PROJECT_DIR/config.yaml', encoding='utf-8'))
for a in (cfg.get('accounts') or []):
    if a.get('key') == '$KEY' and a.get('session'):
        print(a['session'])
        break
" 2>/dev/null || echo "")
    [ -z "$SESS" ] && SESS="data/x_session_${KEY}.json"
    [ "$KEY" = "toushiwatch" ] && [ ! -f "$PROJECT_DIR/$SESS" ] && SESS="data/x_session_toushiwatch.json"
    
    SRC="$PROJECT_DIR/$SESS"
    [ ! -f "$SRC" ] && continue
    
    DST="$BACKUP_DIR/x_session_${KEY}.json"
    cp -f "$SRC" "$DST"
    chmod 600 "$DST"
    log "  ✓ $KEY → $DST"
done

# ── ステップ4: 状態ファイル更新──
REFRESHED_JSON=$(printf '%s\n' "${REFRESHED[@]+"${REFRESHED[@]}"}" | python3 -c "import sys,json; print(json.dumps([l.strip() for l in sys.stdin if l.strip()]))" 2>/dev/null || echo "[]")
ALERTS_JSON=$(printf '%s\n' "${ALERTS[@]+"${ALERTS[@]}"}" | python3 -c "import sys,json; print(json.dumps([l.strip() for l in sys.stdin if l.strip()]))" 2>/dev/null || echo "[]")
python3 -c "
import json, datetime, pathlib
state = {
    'last_run': datetime.datetime.now().isoformat(),
    'date': '$DATE',
    'refreshed': $REFRESHED_JSON,
    'alerts': $ALERTS_JSON,
    'backup_dir': '$BACKUP_DIR',
}
pathlib.Path('$STATE_FILE').write_text(json.dumps(state, ensure_ascii=False, indent=2))
"

# ── ステップ5: Telegram通知（異常時）──
if [ ${#ALERTS[@]} -gt 0 ]; then
    MSG="🚨 [kensho] セッション異常検出 ($DATE)\n"
    for a in "${ALERTS[@]}"; do
        MSG+="  • $a\n"
    done
    if [ -x "$NOTIFY" ]; then
        bash "$NOTIFY" "$MSG"
        log "  📱 Telegram通知送信済み"
    else
        log "  ⚠ notify.sh が見つからないか実行不可"
    fi
elif [ ${#REFRESHED[@]} -gt 0 ]; then
    MSG="✅ [kensho] セッションリフレッシュ完了 ($DATE)\n"
    MSG+="  更新: ${REFRESHED[*]}"
    if [ -x "$NOTIFY" ]; then
        bash "$NOTIFY" "$MSG"
        log "  📱 Telegram通知送信済み"
    fi
else
    log "  ✓ 異常なし（通知不要）"
fi

log "=== セッション検証終了 ($DATE) ==="
exit 0
