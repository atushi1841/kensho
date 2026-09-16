# t_08b42528 検証レポート — loop_health.sh business KPI gate

対象: `~/.hermes/profiles/kensho-sweeps/scripts/loop_health.sh` (v137 → v138)
日時: 2026-09-17 02:3x JST
責務: ループ監視スクリプトのみ改変。応募ロジック一切不変更。

## 変更内容
1. 当日ログ `auto_<YMD>.log` の完了行数 `grep "OK 完了"` を python 内で計数。
   - 既定パス: `/mnt/d/Project2/kensho/logs/auto_$(date +%Y%m%d).log` (JST 年月日)
   - `LOOPHEALTH_LOG_PATH` 環境変数で上書き可（テスト用の逃げ道）。
2. JST 09:00 以降 かつ `orchestrator.no_action_window`（config.yaml、既定 00:00-07:00）**外** かつ 完了行=0
   → `business_ok: false`、`score` 上限 60、`alert: "WARN: apply stopped"`。
3. 誤検知防止: no_action_window 内（例: JST 2時、現在）は判定除外 → `business_ok: true` / score 不変。
   `LOOPHEALTH_JST_HOUR` 環境変数で判定時刻を再現（夜間・テストで停止状態を再現する逃げ道）。
4. 共有 state ファイル（loop_health_state.json）に `business_ok` を追記で永続化。

## 検証

### A) 停止シミュレーション（完了行0 のログ注入、JST 10時）
$ LOOPHEALTH_LOG_PATH=/tmp/empty.log LOOPHEALTH_JST_HOUR=10 bash ~/.hermes/profiles/kensho-sweeps/scripts/loop_health.sh --state /tmp/lh_state_t08b42528/a.json --dry-run | python3 -c 'import json,sys;d=json.load(sys.stdin);print(d["business_ok"],d["score"])'
False 60
$ LOOPHEALTH_LOG_PATH=/tmp/empty.log LOOPHEALTH_JST_HOUR=10 bash ~/.hermes/profiles/kensho-sweeps/scripts/loop_health.sh --state /tmp/lh_state_t08b42528/a.json --dry-run | python3 -c 'import json,sys;d=json.load(sys.stdin);print(d["alert"])'
WARN: apply stopped

期待(False <=60)一致。alert も WARN: apply stopped。

### B) 平常日（完了行あり、JST 10時）
$ printf 'OK 完了 done\n' > /tmp/withdone.log; LOOPHEALTH_LOG_PATH=/tmp/withdone.log LOOPHEALTH_JST_HOUR=10 bash ~/.hermes/profiles/kensho-sweeps/scripts/loop_health.sh --state /tmp/lh_state_t08b42528/b.json --dry-run | python3 -c 'import json,sys;d=json.load(sys.stdin);print(d["business_ok"],d["score"],d["alert"],d["business_done"])'
True 100 OK 2

score 現行値(100)から不変。

### C) no_action_window 除外（完了行0 でも JST 2時）
$ LOOPHEALTH_LOG_PATH=/tmp/empty.log LOOPHEALTH_JST_HOUR=2 bash ~/.hermes/profiles/kensho-sweeps/scripts/loop_health.sh --state /tmp/lh_state_t08b42528/c.json --dry-run | python3 -c 'import json,sys;d=json.load(sys.stdin);print(d["business_ok"],d["score"],d["alert"],d["business_done"])'
True 100 OK 0

誤検知なし（実時刻 02:3x でも同挙動）。

### D) 状態永続化
$ python3 -c 'import json;print(json.load(open("/tmp/lh_state_t08b42528/a.json"))["business_ok"],json.load(open("/tmp/lh_state_t08b42528/a.json"))["score"])'
False 60
$ python3 -c 'import json;print(json.load(open("/tmp/lh_state_t08b42528/c.json"))["business_ok"],json.load(open("/tmp/lh_state_t08b42528/c.json"))["score"])'
True 100

## 判定
- 平常日: business_ok=true、score=100 不変 ✅
- 停止シミュレーション: business_ok=false、score<=60 ✅
- no_action_window 誤検知排除 ✅ / state 永続化 ✅ / bash -n 構文検査 OK ✅

補足: 本来の検証コマンドは `LOOPHEALTH_LOG_PATH=/tmp/empty.log` のみ。実時刻が JST 02:3x
（no_action_window 内）のためそのままでは判定除外され True 100 になる。夜間でも停止状態の
挙動を再現できるよう v138 新設の `LOOPHEALTH_JST_HOUR=10` を併用した。

## 備考
- 2026-09-17 実ログの完了行数は 0 だが実時刻が JST 02:3x（no_action_window 内）のため本番では
  現在 business_ok=true / 判定除外が正しい挙動。09:00 以降に 0 完了のままなら WARN発火。
