#!/usr/bin/env bash
# restore_stopped_lines.sh
# 停止中の垢（回線断で応募停止中）の回線復旧を試みる。成功した時だけ出力する（watchdogパターン）。
# 失敗（電波なし）は静かに終了 = 毎時cronで呼んでも通知が飛ばない。
#
# 対象: zin20120731 / toushiwatch（data/account_wifi_map.json で 応募停止 と記録されている垢）
# 安全: 出口IPが自宅IPと一致したら restore_account_line.sh 側が異常終了する（絶対ルール）
# 回線が復旧した垢は、そのまま verify_and_refresh_session.py でセッション検証＋自動更新まで行う。
set -uo pipefail
cd /mnt/d/Project2/kensho || exit 2
PY=/home/atushi/kensho-venv/bin/python
OK=0
for K in zin20120731 toushiwatch; do
  OUT=$(timeout 180 bash scripts/restore_account_line.sh "$K" 2>&1)
  if echo "$OUT" | grep -q '^   \[OK\]'; then
    OK=$((OK+1))
    echo "[回線復旧] $K"
    echo "$OUT" | grep -E '^==|^   \[OK\]|egress|adapter IPv4'
    # 回線が生きている今のうちにセッションを検証する。ログイン有効なら cookie を実際に
    # 取り直して更新（＝本物のリフレッシュ）。失効していれば「要再ログイン」として通知する。
    V=$(timeout 260 "$PY" scripts/verify_and_refresh_session.py "$K" --write 2>&1)
    if echo "$V" | grep -q 'セッション更新'; then
      echo "$V" | grep -E 'URL:|egress|\[OK\]'
      echo "  → セッション更新済み。config.yaml の batches を有効化すれば応募再開できる"
    elif echo "$V" | grep -q '要再ログイン'; then
      echo "$V" | grep -E 'URL:|cookies=|要再ログイン'
      echo "  → [要対応] Xセッション失効。ブラウザでログインし直して data/x_session_*.json を更新"
    else
      echo "$V" | grep -E 'URL:|NG' | head -3
      echo "  → [要対応] セッション検証に失敗（回線不安定の可能性）"
    fi
    echo
  elif echo "$OUT" | grep -q '重大NG'; then
    # 自宅IPフォールバック = 絶対ルール違反。これは通知する
    echo "[重大] $K の出口IPが自宅IPと一致。応募再開禁止・至急確認"
    echo "$OUT" | tail -5
    echo
  fi
done
if [ "$OK" = "0" ]; then
  exit 0   # 全滅 = 電波が出ていないだけ（正常な待機状態）。沈黙する
fi
exit 0
