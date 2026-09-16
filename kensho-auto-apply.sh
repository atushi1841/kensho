#!/usr/bin/env bash
# Kensho 自動応募 — Hermes cron から15分おきに呼ばれる（垢別並列ディスパッチャ）
# 2026-08-23 改修: 全垢を直列で回すと「1垢セッションがロックを握って全tickを足止め→
# 各垢の予定バッチが消化されず応募が極端に少ない」問題を解消。
# → 実行予定の垢ごとに orchestrator を背景起動して並列化（各垢は自分の時間/日次上限を維持）。
# → 並行坙の同一垢の二重実行は 垢別flock + 垢別PIDロック で防止。
# → 同時実行数は config orchestrator.max_concurrent_accounts で制限（Firefoxメモリ対策）。

# ── WSL2 cgroup との衝突（歴史的メモ） ──
# systemd-run --scope を作ると Hermes が SIGKILL される（sibling scope 衝突）。
# → orchestrator は素のnohup/バックグラウンド（scope不使用）で起動する。2026-08-20確実。
# 万一クラッシュ再発時は: /home/atushi/kensho-backups/backup_kensho_scripts.sh restore <tag>

PROJECT_DIR="/mnt/d/Project2/kensho"
LOG_DIR="$PROJECT_DIR/logs"
VENV_PY="/home/atushi/kensho-venv/bin/python"
mkdir -p "$LOG_DIR"

LOG_FILE="/mnt/d/Project2/kensho/logs/auto_$(date +%Y%m%d).log"
# 垢別フロックファイル
LOCK_DIR="/tmp/kensho-locks"
mkdir -p "$LOCK_DIR"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG_FILE"; }

log "=== kensho-auto-apply (並列ディスパッチ) 開始 ==="

cd "$PROJECT_DIR"
export HOME=/home/atushi

# ── config から アカウント一覧・同時実行上限を読取 ──
read_config() {
  "$VENV_PY" - "$PROJECT_DIR/config.yaml" <<'PY'
import sys, yaml
cfg = yaml.safe_load(open(sys.argv[1], encoding='utf-8')) or {}
accounts = cfg.get('accounts', [])
print(' '.join(a['key'] for a in accounts))
print(int(cfg.get('orchestrator', {}).get('max_concurrent_accounts', 3)))
PY
}
CONFIG_OUT=$(read_config)
ACCOUNTS=$(echo "$CONFIG_OUT" | sed -n '1p')
MAX_CONCURRENT=$(echo "$CONFIG_OUT" | sed -n '2p')
MAX_CONCURRENT=${MAX_CONCURRENT:-3}

if [ -z "$ACCOUNTS" ]; then
  log "configからアカウント一覧を読めず → 終了"
  exit 0
fi
log "対象垢: $ACCOUNTS | 同時実行上限: $MAX_CONCURRENT"

# ── 垢順を毎tickローテーション（均等dispatch）──
# 修正: 固定config順だと atushi16→kudou(序1,2) がpermanentに全スロットを独占し、
# 後方垢(TankanNotes/inobase1-4等)が同時3上限で永遠に出発できず応募が極端に枯渇する。
# → 開始インデックスを毎回1ずつずらして全垢に公平な当番を持たせる。
ROTATION=$(( $(cat "$LOCK_DIR/rotate.offset" 2>/dev/null || echo 0) ))
N_ACCT=$(echo "$ACCOUNTS" | wc -w)
ROTATION=$(( ROTATION % N_ACCT ))
# 回転
ACCT_ARR=( $ACCOUNTS )
ROTATED=$( ( printf '%s\n' "${ACCT_ARR[@]:$ROTATION}"; printf '%s\n' "${ACCT_ARR[@]:0:$ROTATION}" ) | paste -sd' ' )
ACCOUNTS="$ROTATED"
# 次tick用にオフセット更新
echo $(( (ROTATION + 1) % N_ACCT )) > "$LOCK_DIR/rotate.offset" 2>/dev/null || true
log "垢順(回転$ROTATION): $ACCOUNTS"

# ── critic v154 follow-up (t_ed8baffa) 案B: 垢別スタガー ──
# 15分グリッド±2分98.8%集中（検出④層=出口IP×時刻の結合分布）対策。
# spawn前に垢別乱数分(0-9分)の就寝を挟むことで、実開始時刻をグリッドから外す。
# ・同時実行キャップ/RAMガードは就寝前に評価済み（スロット予約済み扱い）→ 意味論不変。
# ・二重実行防止pgrepは就寝後の子プロセス内で行う（前tick稼働中は就寝後に見つけてskip）。
# ・seedは秒精度tick刻み → 日次決定論（orchestrator側seed=日付+垢+バッチ）と逆引き面が異なる。
STAGGER_MOD=${KENSO_STAGGER_MOD:-10}   # 0で無効化（ロールバック）

spawned=0
for acct in $ACCOUNTS; do
  # 1) その垢の orchestrator が既に動いている → スキップ（二重実行防止）
  if pgrep -f "kensho/orchestrator.py --account $acct" >/dev/null 2>&1; then
    continue
  fi
  # 2) 同時実行数キャップ
  running=$(pgrep -cf "kensho/orchestrator.py --account" 2>/dev/null || echo 0)
  if [ "$running" -ge "$MAX_CONCURRENT" ]; then
    log "同時実行上限($MAX_CONCURRENT)到達 → 残りは次tickで回す"
    break
  fi
  # 2b) RAM上限ガード（6垢同時のFirefox OOM防止、安全弁）
  #   available <= RAM_SAFETY_THRESHOLD なら新規スポーンしない（稼働垢の進行は優先）
  RAM_SAFETY_THRESHOLD="${KENSOHO_RAM_GUARD:-3.0}"  # 残り3GB未満で抑制
  avail_gb=$(free -g | awk '/^Mem:/{print $7+0}')
  if [ "$avail_gb" -lt "$RAM_SAFETY_THRESHOLD" ]; then
    log "RAM残り${avail_gb}GB<${RAM_SAFETY_THRESHOLD}GB → 新規スポーン抑制（OOM防止）"
    break
  fi
  # 3) 垢別ロックで背景起動（ロック取得失敗=その垢が稼働中 → 即スキップ）
  #    案B: spawn前に垢別乱数分 sleep（子内で実行）。就寝中はpgrepに見えないため、
  #    覚醒後に同時実行数・RAMの再ガードをかける（超過時はexit→次tickが拾う）。
  STAGGER_MIN=$(( RANDOM % (STAGGER_MOD > 0 ? STAGGER_MOD : 1) ))
  # 終了スケジュール(22:47)割らせ防止: 22:30以降のtickはスタガー0（即spawn）
  if [ "$(date +%H%M)" -ge 2230 ] 2>/dev/null && [ "$(date +%H)" = "22" ]; then STAGGER_MIN=0; fi
  STAGGER_SEC=$(( STAGGER_MIN * 60 ))
  if [ "$STAGGER_MOD" -gt 0 ]; then log "stagger $acct +${STAGGER_MIN}分"; fi
  flock -n "$LOCK_DIR/$acct.lock" -c "
    sleep $STAGGER_SEC
    cd '$PROJECT_DIR'
    export HOME=/home/atushi PYTHONPATH='$PROJECT_DIR'
    # 覚醒後ガード: ①二重実行 ②同時実行数 ③RAM（前tick稼働分をカウント）
    if pgrep -f 'kensho/orchestrator.py --account $acct' >/dev/null 2>&1; then exit 0; fi
    if [ \$(pgrep -cf 'kensho/orchestrator.py --account' 2>/dev/null || echo 0) -ge $MAX_CONCURRENT ]; then exit 0; fi
    if [ \$(free -g | awk '/^Mem:/{print \$7+0}') -lt ${KENSOHO_RAM_GUARD:-3.0} ]; then exit 0; fi
    '$VENV_PY' kensho/orchestrator.py --account '$acct'
  " >>"$LOG_FILE" 2>&1 &
  spawned=$((spawned+1))
done

log "今回 spawn: $spawned 垢（即終了：処理本体は各垢が並列で実行）"

# ── プロキシ自動復旧（毎tick1回・バックグラウンド） ──
# 2026-08-25: orchestrator.py の Proxy Watchdog ステップは _ACCOUNT=None(メイン)でのみ
# 実行されるが、本ディスパッチャは垢別ワーカー(--account)のみ起動するため、
# そのステップは一度も実行されず「デッドコード」になっていた。
# → ここで毎tick1回 check_proxy_health を直接呼ぶことで自動復旧を有効化。
#    - flock で並行二重起動を防止（前tickのチェックが残っていれば即スキップ）
#    - バックグラウンド実行（spawn を遅延させない）
#    - BOT安全: プロキシ復旧のみ。応募ロジックには一切触れない
(
  flock -n 9 || exit 0
  "$VENV_PY" - "$PROJECT_DIR/config.yaml" <<'PY' >>"$LOG_FILE" 2>&1
import sys, os, yaml
sys.path.insert(0, os.environ.get("PYTHONPATH", "/mnt/d/Project2/kensho"))
from kensho.utils.proxy_watchdog import check_proxy_health
cfg = yaml.safe_load(open(sys.argv[1], encoding="utf-8"))
import time
t0 = time.time()
r = check_proxy_health(cfg)
print(f"[PROXY-CHECK] alive={r['alive_ports']} dead={r['dead_ports']} restored={r['restored_ports']} ({time.time()-t0:.1f}s)")
PY
) 9>"$LOCK_DIR/proxy-check.lock" &

