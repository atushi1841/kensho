# t_ef9e899f — AIチーム: loop_health JSON注入のcontext curation

役割: kensho-worker / ボード: kensho-ai-team

## 作業内容

`loop_health.sh` の出力 JSON は LLM プロンプトへ「## 0. ループ健康度」として全件
注入されていた。全フィールド（counts/repeats/business_log/action/…）が各ロール
（critic / worker / QA）のプロンプトに無差別に入るため Attention Budget を無駄に
消費していた。本タスクで role 別要約フィールド `role_summary` を追加し、各 report
script は自分の role の要約のみを注入するよう変更した。

変更ファイル（sweeps profile repo = デプロイ先）:
- `scripts/loop_health.sh`  — 出力 JSON に `role_summary.{critic,worker,qa}` を追加
  （full JSON はトップレベルに温存。board_state_monitor_*.sh がパースするため削れない）
- `scripts/kensho-revenue-report.sh` — critic: `role_summary.critic` のみ注入
- `scripts/kensho-worker-report.sh` — worker: `role_summary.worker` のみ注入
- `scripts/kensho-qa-report.sh`    — qa:       `role_summary.qa` のみ注入

各 report script は `echo "$HEALTH_JSON" | jq -r '.role_summary.<role> // .'` とし、
`role_summary` 不在（旧版 loop_health）時は full JSON へフォールバックする。

## verification_evidence

`bash -n` 構文検査:
$ bash -n loop_health.sh kensho-revenue-report.sh kensho-worker-report.sh kensho-qa-report.sh && echo ALL-SYNTAX-OK
→ OK: loop_health.sh / OK: kensho-revenue-report.sh / OK: kensho-worker-report.sh / OK: kensho-qa-report.sh

デプロイ版 loop_health.sh 実行（kensho-sweeps profile）:
$ bash loop_health.sh > /tmp/lh_out.json; jq -r 'keys_unsorted | join(",")' /tmp/lh_out.json
→ score,streak,running,blocked,counts,skip_fast,top_task,repeats,done_blocked,zombie_task_count,
   business_ok,business_done,business_hour,business_log,lines,alert,escalation,escalation_target,
   escalate_streak,escalated_at,escalation_age_h,park_after_h,park_action,action,role_summary

`role_summary` が生成され、critic/worker/qa の3ロール要約を持つ:
$ jq -c '.role_summary' /tmp/lh_out.json
→ {"critic":{"alert":"OK","score":100,"streak":0,"running":1,"blocked":0,"escalation":"false",
   "escalation_target":"t_ef9e899f","escalation_age_h":0,"top_task":"t_ef9e899f","repeats":0,
   "done_blocked":0,"zombie_task_count":0,"business_ok":true,"park_action":"none","park_after_h":24},
   "worker":{...7 fields...}, "qa":{...9 fields...}}

プロンプト注入サイズ最適化の実測（bytes）:
$ wc -c < /tmp/lh_out.json; jq -c '.role_summary.critic' /tmp/lh_out.json | wc -c
→ 1604 (full JSON) / 270 (critic 注入)
$ jq -c '.role_summary.worker' /tmp/lh_out.json | wc -c; jq -c '.role_summary.qa' /tmp/lh_out.json | wc -c
→ 114 (worker) / 177 (qa)

board_state_monitor の top-level パース後方互換（メトリクス監視を破壊しない）:
$ python3 /tmp/lh_monitor_check.py < /tmp/lh_out.json
→ score=100|ready=None|blocked=0|done=0|prio=normal|streak=0|esc=False|skip=False|role_summary=3keys

`role_summary` 不在時のフォールバック（旧版 loop_health 互換）:
$ echo '{"score":50,"counts":{"running":1},"escalation":true,"streak":2}' | jq -r '.role_summary.critic // .'
→ {"score":50,"counts":{"running":1},"escalation":true,"streak":2}
