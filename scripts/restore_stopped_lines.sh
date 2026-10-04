#!/usr/bin/env bash
# restore_stopped_lines.sh
# 停止中の垢（回線断で応募停止中）の回線復旧を試みる。成功した時だけ出力する（watchdogパターン）。
# 失敗（電波なし）は静かに終了 = 毎朝cronで呼んでも通知が飛ばない。
#
# 対象: zin20120731 / toushiwatch（data/account_wifi_map.json で 応募停止中 と記録されている垢）
# 安全: 出口IPが自宅IPと一致したら restore_account_line.sh 側が異常終了する（絶対ルール）
set -uo pipefail
cd /mnt/d/Project2/kensho || exit 2
OK=0
for K in zin20120731 toushiwatch; do
  OUT=$(timeout 180 bash scripts/restore_account_line.sh "$K" 2>&1)
  if echo "$OUT" | grep -q '^   \[OK\]'; then
    OK=$((OK+1))
    echo "[回線復旧] $K"
    echo "$OUT" | grep -E '^==|^   \[OK\]|egress|adapter IPv4'
    echo "  → 次: Xセッションが失効しているため再ログイン後に config.yaml の batches を有効化する"
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
