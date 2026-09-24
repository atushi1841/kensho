#!/usr/bin/env bash
# t_37e25225 実測スキャナ（軽量・grep一括）
#   垢単位サーキットブレーカ / 圏外垢スキップの before/after を実ログから数値化する。
#   出力: reports/t_37e25225_scan_output.txt
#   実行: bash reports/t_37e25225_scan.sh
cd /mnt/d/Project2/kensho || exit 1
OUT=reports/t_37e25225_scan_output.txt
: > "$OUT"
DAYS="2026-09-18 2026-09-19 2026-09-20 2026-09-21 2026-09-22 2026-09-23 2026-09-24 2026-09-25"

echo "### 1. [CEILING] このサイクルの連続失敗: N回 の値分布（= 垢単位の連続リトライ回数）" >> "$OUT"
for d in $DAYS; do
  echo "--- $d (orchestrator $(ls logs/$d/orchestrator_*.log 2>/dev/null | wc -l) files) ---" >> "$OUT"
  grep -ho 'このサイクルの連続失敗: [0-9]*回' logs/$d/orchestrator_*.log 2>/dev/null \
    | sort | uniq -c | sed 's/^/   /' >> "$OUT"
done

echo "### 2. attempts=3（self_heal が最大3回まで再実行した最終失敗）ライン数" >> "$OUT"
for d in $DAYS; do
  n=$(grep -rho 'attempts=[0-9]*' logs/$d/orchestrator_*.log 2>/dev/null | grep -c 'attempts=3')
  echo "   $d attempts=3 lines: $n" >> "$OUT"
done
echo "   --- 代表行 (2026-09-23) ---" >> "$OUT"
grep -rh 'attempts=3' logs/2026-09-23/orchestrator_*.log 2>/dev/null | sort -u | head -3 | sed 's/^/     /' >> "$OUT"

echo "### 3. 圏外垢スキップ（条件2）の実発動ログ" >> "$OUT"
for pat in 'ネットワーク圏外/電源OFF/バックOFF' 'プロキシ死骸（'; do
  echo -n "   '$pat' 件数 (logs/2026-09-24,2026-09-25, auto_20260924/0925.log): " >> "$OUT"
  grep -rho "$pat" logs/2026-09-24/ logs/2026-09-25/ logs/auto_20260924.log logs/auto_20260925.log 2>/dev/null | wc -l >> "$OUT"
done

echo "### 4. 圏外垢 zin20120731 の応募経路（orchestrator のバッチ判定）" >> "$OUT"
echo -n "   auto_20260925.log の '垢別起動: zin20120731' 回数: " >> "$OUT"
grep -c '垢別起動: zin20120731' logs/auto_20260925.log 2>/dev/null >> "$OUT"
echo "   --- 垢別起動直後の行（先頭1件・最大8行） ---" >> "$OUT"
L=$(grep -n '垢別起動: zin20120731' logs/auto_20260925.log 2>/dev/null | head -1 | cut -d: -f1)
if [ -n "$L" ]; then sed -n "${L},$((L+7))p" logs/auto_20260925.log | cut -c1-150 | sed 's/^/     /' >> "$OUT"; fi

echo "### 5. 条件2 実装の到達可能性（同一入力の先行 return に遮蔽されていないか）" >> "$OUT"
echo "   applier.py:59  : $(sed -n '59p' kensho/application/applier.py)" >> "$OUT"
echo "   applier.py:860 : $(sed -n '860p' kensho/application/applier.py)" >> "$OUT"
echo "   applier.py:861 : $(sed -n '861p' kensho/application/applier.py)" >> "$OUT"
echo "   applier.py:892 : $(sed -n '892p' kensho/application/applier.py)" >> "$OUT"
echo "   applier.py:893 : $(sed -n '893p' kensho/application/applier.py)" >> "$OUT"
echo "   --- wifi_watchdog の判定入力が applier から参照されているか ---" >> "$OUT"
echo -n "     kensho/ 配下で account_wifi_map を参照するファイル数: " >> "$OUT"
grep -rl 'account_wifi_map' --include='*.py' kensho/ 2>/dev/null | wc -l >> "$OUT"

echo "### 6. BOT制約（rate_limits / max_attempts）が緩められていないか" >> "$OUT"
grep -n -E '^  (max_actions_per_hour|min_delay_between_actions|max_delay_between_actions|max_total_actions_per_day|active_hours_start|active_hours_end):' config.yaml | sed 's/^/   /' >> "$OUT"
grep -n -E '^  max_attempts:' config.yaml | sed 's/^/   /' >> "$OUT"

echo "DONE" >> "$OUT"
