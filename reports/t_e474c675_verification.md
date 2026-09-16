# t_e474c675 検証レポート — loop_health business KPI gate 完成マーカー修正 (v139)

対象: `~/.hermes/profiles/kensho-sweeps/scripts/loop_health.sh` (v138 → v139)
日時: 2026-09-17 03:4x JST
責務: ループ監視スクリプトのみ改変。応募パイプライン・応募ロジック一切不変更 → 自動GO対象。

## 背景（検出不能の理屈）
- 本タスク t_e474c675 は v138（前身の v138 提案）の失敗を受けて修正した。前身は当日ログの完了行を `grep "OK 完了"` で計数したが、実ログの
  完成マーカーは `[OK] 完了: N成功 / Mエラー` と INFO 行 `完了: N成功/Mエラー（Xs秒）` の
  2形であり、旧 marker `OK 完了` は両方に一致しない → 稼働日でも常に 0。
- 結果、`_business_detect = (JST>=9 & 完了行0)` が毎日発火し、healthy 日でも score 上限60 /
  `business_ok:false` の偽陽性 WARN を出していた（= 検出不能）。
- v139 は正規表現 `完了:\s*\d+成功` で実完了行を集計し、稼働日(9/15)=96件 / 停止日(9/17)=0件 と分離。

## verification_evidence

検証コマンドはタスク本文の指定どおり（LOOPHEALTH_LOG_PATH で実ログ注入 + LOOPHEALTH_JST_HOUR=14 で
no_action_window 外の時刻を再現、`| jq '.business_done,.business_ok'`）。dry-run/state は既定のまま。

### A) 稼働日 (auto_20260915.log, JST 14時) — 成功指標: business_done>=96 かつ business_ok=true
$ LOOPHEALTH_LOG_PATH=/mnt/d/Project2/kensho/logs/auto_20260915.log LOOPHEALTH_JST_HOUR=14 bash /home/atushi/.hermes/profiles/kensho-sweeps/scripts/loop_health.sh | jq '.business_done,.business_ok'
96
true
稼働日相当で business_done=96 (>=96) かつ business_ok=true。score=100 不変（偽陽性WARN解消）✅

### B) 停止日 (auto_20260917.log, JST 14時) — 成功指標: business_ok=false
$ LOOPHEALTH_LOG_PATH=/mnt/d/Project2/kensho/logs/auto_20260917.log LOOPHEALTH_JST_HOUR=14 bash /home/atushi/.hermes/profiles/kensho-sweeps/scripts/loop_health.sh | jq '.business_done,.business_ok,.score,.alert'
0
false
60
WARN: apply stopped
停止日で business_done=0 / business_ok=false / score 上限60 / alert=WARN: apply stopped ✅

### C) 旧 marker の不完全性 (OK 完了 のみのログ) — 修正前バグを明示
$ LOOPHEALTH_LOG_PATH=/mnt/d/Project2/kensho/logs/tmp_okmarker.log LOOPHEALTH_JST_HOUR=14 bash /home/atushi/.hermes/profiles/kensho-sweeps/scripts/loop_health.sh | jq '.business_done,.business_ok'
0
false
旧 marker 'OK 完了' 文字列のみでは完了行としてカウントされない（集計は `完了:\s*\d+成功` のみ）✅

### D) pytest 回帰 (新規 tests/test_loop_health_business.py)
$ cd /mnt/d/Project2/kensho && python -m pytest tests/test_loop_health_business.py -q
3 passed, 1 warning in 12.86s
v139 完成マーカー集計の回帰テスト3件パス（稼働日/停止日/旧marker非集計）✅

## 判定
- 稼働日(9/15): business_done=96 >= 96 かつ business_ok=true ✅
- 停止日(9/17): business_ok=false ✅
- 偽陽性WARN（healthy日 score 上限60）解消 ✅
- 旧 marker `OK 完了` 非集計（修正前挙動と完全一致）✅
- pytest 回帰パス ✅ / 実行成功自体が bash 構文OK ✅

## 備考
- 本タスクは応募パイプライン改修でない監視系のみの変更のため自動GO対象。
- 適用先は稼働中の kensho-sweeps プロファイル配下スクリプト（業務実体）のみ。
  本リポジトリ `scripts/loop_health.sh` は v137 凍結の別コピー（監視系キャノニカル追従対象外、
  t_e474c675 の修正対象は稼働中 kensho-sweeps プロファイル配下スクリプトのみで、本リポジトリは tests/ と本報告のみ）。
- テストは本リポジトリの tests/ に追加（LOOP_HEALTH_SCRIPT 環境変数で対象スクリプト切替可能）。
