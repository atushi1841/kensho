#!/bin/bash
# kensho-hang-watchdog.sh — orchestratorハング自動kill + 自動再起動（2026-09-07追加, 2026-09-18強化, 2026-09-22自動復旧）
# 発火条件: orchestrator_*.log が30分無音 + 対応orchestratorプロセス生存 → プロセスグループkill
# 根拠: 正常セッションのログ間隔は最大3分（9/6全ログ実測）→ 30分無音はハング確定
# ハングパターン実績: 「[STORE] ✓ 保存済みテキスト利用」直後・ブラウザ0MB・do_epoll_waitでフリーズ
#
# ★ 2026-09-18 (t_c189d8d8 提案2): pkill -P のワンライン親子kill をプロセスグループ殺に昇格。
#   - kensho-auto-apply.sh が setsid で起動するようになり、flock==セッションリーダ
#     (pgid==flock.pid)、配下ツリー全体が同一PGIDを継承する。
#   - orchestrator.py の guard で特定した PGID に kill -TERM -<PGID> → 猶予秒待機 →
#     kill -KILL -<PGID> の TERM→KILL エスカレーション（research/flock_kill_watchdog 検証済み）。
#   - kill(2): pid < -1 はプロセスグループ全体へシグナル（PGID=-pid）。
#   - SIGTERMはPlaywrightのハング時には無視されうる(main threadがC呼び出しで塞がる)ため、
#     TERM grace→KILL を必ず組む。flockを含むpidグループ全部が死ねばロックも自動解放。
#
# ★ 2026-09-22 (自動復旧): kill直後に該当垢の orchestrator を即時再spawnする。
#   従来は次tick(15分後)の kensho-auto-apply.sh が再spawnするまで待っていたが、
#   その間その垢の応募が完全に止まる。→ kill→flock解放を確認後、kensho-auto-apply.sh と
#   同一のガード（二重実行/同時実行上限/RAM）を回して即時復旧。rate-limitで再起動暴走を防止。
#
# 退出コード: 常に 0（処理成功）。内部エラーも 0。

LOG_BASE="/mnt/d/Project2/kensho/logs"
TODAY_DIR="$LOG_BASE/$(date +%Y-%m-%d)"
YEST_DIR="$LOG_BASE/$(date -d yesterday +%Y-%m-%d)"
NOW=$(date +%s)
GRACE="${KENSO_HANG_GRACE_SEC:-8}"   # SIGTERM を受けてから SIGKILL までの猶予
SILENT_MIN="${KENSO_HANG_SILENT_MIN:-30}"
LOCK_DIR="${KENSO_LOCK_DIR:-/tmp/kensho-locks}"

# ── 自動復旧設定 ──
RESTART="${KENSO_HANG_RESTART:-1}"                  # 0=無効（killのみ・次tick待ち）
RESTART_MAX="${KENSO_HANG_RESTART_MAX_PER_HOUR:-3}" # 同一垢の1時間あたり自動再起動回数上限
STATE_DIR="${KENSO_HANG_STATE_DIR:-/home/atushi/.hermes/profiles/kensho-sweeps/scripts/state}"
RESTART_LEDGER="$STATE_DIR/hang_restarts.json"
PROJECT_DIR="/mnt/d/Project2/kensho"
LOG_FILE="/mnt/d/Project2/kensho/logs/auto_$(date +%Y%m%d).log"
VENV_PY="/home/atushi/kensho-venv/bin/python"
MAX_CONCURRENT="${KENSO_MAX_CONCURRENT:-3}"
RAM_GUARD="${KENSOHO_RAM_GUARD:-3}"

# ── 自動復旧関数: kill後に該当垢を即時re-spawn（kensho-auto-apply.sh と同一ガード）──
restart_acct() {
  local acct="$1"
  if [ "$RESTART" != "1" ]; then
    echo "[$(date '+%F %T')] RESTART skip: acct=$acct (KENSO_HANG_RESTART=$RESTART) — 次tickで復旧待ち"
    return 0
  fi
  who_echo() { echo "[$(date '+%F %T')] RESTART: $*"; }

  # rate-limit: 1時間当たり再起動上限チェック&記録
  mkdir -p "$STATE_DIR"
  "$VENV_PY" - "$acct" "$RESTART_MAX" "$RESTART_LEDGER" <<'PY' >>"$LOG_FILE" 2>&1
import json, os, sys, time
acct, max_per_hour, ledger_path = sys.argv[1], int(sys.argv[2]), sys.argv[3]
now = int(time.time()); cutoff = now - 3600
data = {}
try:
    data = json.load(open(ledger_path, encoding="utf-8"))
except Exception:
    data = {}
data[acct] = [t for t in data.get(acct, []) if t >= cutoff]
if len(data[acct]) >= max_per_hour:
    print(f"RESTART limit exceeded: acct={acct} restarts={len(data[acct])} max={max_per_hour}/h → skip")
    sys.exit(1)
data[acct].append(now)
tmp = ledger_path + ".tmp"
with open(tmp, "w", encoding="utf-8") as f:
    json.dump(data, f)
os.replace(tmp, ledger_path)
print(f"RESTART rate-limit ok: acct={acct} restarts={len(data[acct])}/h")
sys.exit(0)
PY
  RC=$?
  if [ "$RC" -ne 0 ]; then
    who_echo "acct=$acct rate-limit超過または破損 → 再spawn中止（次tick或いは手動）"
    return 0
  fi

  # 二重実行・同時上限・RAMガード（kensho-auto-apply.sh と同一）を評価してから setsid flock spawn
  # ★ 2026-09-18 教訓: 実行行に concrete 'kensho/orchestrator.py --account <acct>' を残さず
  #   ORCH_ARG 変数化 + pgrep パターンを [k]ensho で自己マッチ回避（flock argv 誤検知防止）
  ACCT_SAFE="$acct"
  setsid flock -n "$LOCK_DIR/$acct.lock" -c "
    cd '$PROJECT_DIR'
    export HOME=/home/atushi PYTHONPATH='$PROJECT_DIR'
    if pgrep -f '[k]ensho/orchestrator.py --account $ACCT_SAFE' >/dev/null 2>&1; then exit 0; fi
    if [ \$(pgrep -cf '[k]ensho/orchestrator.py --account' 2>/dev/null || echo 0) -ge $MAX_CONCURRENT ]; then exit 0; fi
    if [ \$(free -g | awk '/^Mem:/{print \$7+0}') -lt $RAM_GUARD ]; then exit 0; fi
    ORCH_ARG='kensho/orchestrator.py'
    '$VENV_PY' \$ORCH_ARG --account '$ACCT_SAFE'
  " >>"$LOG_FILE" 2>&1 &
  who_echo "acct=$acct re-spawn発火（setsid flock, pid=$!）"
}

# ── 生存中のorchestratorプロセス一覧（pid + etime秒 + args）
PROC_LIST=$(ps -eo pid,etimes,args | grep 'orchestrator.py --account' | grep -v grep)

[ -z "$PROC_LIST" ] && exit 0

echo "$PROC_LIST" | while read -r pid etime_s args; do
  # このプロセスより新しいログで、プロセス起動後に更新されたorchestrator_*.logを探す
  started_at=$(( NOW - etime_s ))
  # アカウント名を抽出
  acct=$(echo "$args" | grep -oE '\-\-account [A-Za-z0-9_]+' | awk '{print $2}')
  acct=${acct:-unknown}

  silent_min=0
  culprit=""
  for d in "$TODAY_DIR" "$YEST_DIR"; do
    [ -d "$d" ] || continue
    # 垢別ログまたは共通ログの両方を対象（orchestrator_* で網羅）
    for logf in "$d"/orchestrator_*.log; do
      [ -f "$logf" ] || continue
      m=$(stat -c %Y "$logf")
      # プロセス起動以降に更新されたログのみ対象
      [ "$m" -lt "$started_at" ] && continue
      age=$(( (NOW - m) / 60 ))
      if [ "$age" -gt "$silent_min" ]; then silent_min=$age; culprit=$logf; fi
    done
  done

  # プロセス起動後に更新されたログが無い = 起動直後でまだ書いてない → スキップ
  [ -z "$culprit" ] && continue
  # 30分未満の無音は正常（閾値）
  [ "$silent_min" -lt "$SILENT_MIN" ] && continue

  # ── PGID 特定: setsid 起動なら orchestrator.py の PGID == flock.pid == セッションリーダ ──
  PG=$(ps -o pgid= -p "$pid" | tr -d ' ')
  [ -z "$PG" ] && PG=$pid
  # 防御: PGID が自分自身(このwatchdogプロセス)や PID 1 でないこと
  if [ "$PG" -le 1 ] || [ "$PG" = "$$" ] 2>/dev/null; then
    echo "[$(date '+%F %T')] HANG 異常PGID($PG) acct=$acct pid=$pid → TERMのみ(グループ殺スキップ)"
    kill -TERM "$pid" 2>/dev/null
    continue
  fi

  echo "[$(date '+%F %T')] HANG検知: acct=$acct ${silent_min}分無音 $culprit (pid=$pid pgid=$PG) → TERM"
  kill -TERM -- "-$PG" 2>/dev/null               # グループ全員にSIGTERM（flock含む）

  # TERM grace: グループ死亡を確認、残存していれば KILL へ昇格
  waited=0
  while [ "$waited" -lt "$GRACE" ]; do
    kill -0 -- "-$PG" 2>/dev/null || break
    sleep 1
    waited=$((waited+1))
  done
  if kill -0 -- "-$PG" 2>/dev/null; then
    echo "[$(date '+%F %T')] TERM後も生存 pgid=$PG (${waited}s) → SIGKILL"
    kill -KILL -- "-$PG" 2>/dev/null
    sleep 1
  fi

  # ロック解放確認: flock が死んでいれば auto 解放済み。異常時は原因を残す。
  LOCK="$LOCK_DIR/$acct.lock"
  if [ -f "$LOCK" ]; then
    if flock -n "$LOCK" -c true 2>/dev/null; then
      echo "[$(date '+%F %T')] ロック解放済み: $acct ($LOCK)"
    else
      echo "[$(date '+%F %T')] WARN: ロック未解放: $acct ($LOCK) — fuser -v $LOCK で確認"
    fi
  fi
  echo "[$(date '+%F %T')] killed: $acct (pid=$pid pgid=$PG)"

  # ── 自動復旧: 該当垢を即時再spawn ──
  restart_acct "$acct"
done

exit 0
