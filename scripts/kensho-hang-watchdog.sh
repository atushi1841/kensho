#!/bin/bash
# kensho-hang-watchdog.sh — orchestratorハング自動kill（2026-09-07追加, 2026-09-18強化）
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
# 退出コード: 常に 0（処理成功）。内部エラーも 0。

LOG_BASE="/mnt/d/Project2/kensho/logs"
TODAY_DIR="$LOG_BASE/$(date +%Y-%m-%d)"
YEST_DIR="$LOG_BASE/$(date -d yesterday +%Y-%m-%d)"
NOW=$(date +%s)
GRACE="${KENSO_HANG_GRACE_SEC:-8}"   # SIGTERM を受けてから SIGKILL までの猶予
SILENT_MIN="${KENSO_HANG_SILENT_MIN:-30}"
LOCK_DIR="${KENSO_LOCK_DIR:-/tmp/kensho-locks}"

# 生存中のorchestratorプロセス一覧（pid + etime秒 + args）
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
done

exit 0
