# QA v82 検証レポート — 2026-09-10（kensho-revenue-qa / t_3980b57e）

対象: critic v79（parent t_9206eee8）の kanban_done_guard 条件(d) task-scoped 修正（--task フラグ、cross-task bleed 解消）の独立検証。
Worker主張（selftest exit 0 / pytest 16 pass / commits 46d5651+304e273）は全て本QAが独立再実走で裏取り。全コマンド read-only or 一時ディレクトリ、本番repo・DB未変更。

## Scope 1 — --selftest 再実行 ✅

`python3 ~/.hermes/profiles/kensho-sweeps/scripts/kanban_done_guard.py --selftest` → **exit 0**（QA手元で再走、2026-09-10 13:0x JST）。
d_bleed 系3行全て出力を確認:
- `selftest d_bleed: scoped_pass=True scope=task foreign=['scripts/other_wip.py'] legacy_repo_wide_blocks=True`（bleed回避＋旧modeは依然ブロック）
- `selftest d_bleed: own_dirty_blocked=True (owned=['scripts/own_task.py'])`（自分の未コミットコード=BLOCK回帰ガード維持）
- `selftest d_bleed: undecidable_failsafe_repo_wide=True (scope=repo_failsafe)`（判定不能→repo-wide fail-safe）

## Scope 2 — pytest ✅

`cd ~/.hermes/profiles/kensho-sweeps && python3 -m pytest tests/ -q` → **16 passed** in 1.73s（QA手元再走、worker申告と一致）。

## Scope 3 — repo-wide 既定の非退行（ライブ実証） ✅

実board DB・実workdir（/mnt/d/Project2/kensho）で本QAタスク t_3980b57e を実行（他laneの未コミット `devto_weekly_pipeline.py` がdirtyな実状況）:
- `--task` あり: `d_scope=task`、d条件 **true**、foreignファイルは `foreign_uncommitted_code_files` にwarning-only収録 → bleed解消を実環境で確認
- `--task` なし: `d_scope=repo`、d条件 **false**（同一ファイルで従来通りブロック）→ 旧repo-wide既定は不変
- exit 1 はいずれもa/b条件（running中のQAタスクに証跡セクション無し）によるもので、dの挙動分離検証には影響なし
- hook実配線確認: `/home/atushi/.hermes/agent-hooks/kanban_done_guard_hook.sh` L122 `bash "$GUARD" "$task_id" --task` ✅（v79コメント付き、手動CLI無指定=旧modeと整合）
- git実在確認: sweeps `46d5651`（guard+tests、479/140行change）、kensho `304e273`（report、実ファイル2980B存在）✅
- TASK_ID_RE（hex `t_[0-9a-f]{8,}`）準拠: `task_id=` 代入箇所のfixtureは `t_deadbe01` / `t_aaaa1111` のみ、非hex混入ゼロ ✅（run339の失敗要因が塞がっていることを独立確認）

## Scope 4 — 7日watch: cond(d) QA override 監視の既存監査ライン統合 ✅（新規cronなし）

プローブ: `~/.hermes/kanban/boards/kensho-ai-team/workspaces/t_3980b57e/audit_cond_d_override.py`（board DB read-only + hook blockログgrep、<1s）。
**ベースライン（v79デプロイ 2026-09-10 03:13 JST 起算）: cond(d) override 0件** ✅
- 過去インシデントは全件デプロイ前（t_226bb0d8/t_4acf6dcc/t_1e5f1e47 blocked=09-08、t_4e678707 done --soft=09-09、t_88b6d325 QA override=09-09）— bleed修正の動機そのもの
- 毎日の監査ラインでの再走手順: 上記プローブ実行 → `cond_d_overrides`（window=v79起算7日）が0か確認、>0なら本レポートへ追記＋申し送り。cron新設は行わない（既存daily auditの1行として運用）
- 監視終了目安: **2026-09-17 03:13 JST** まで。以降は条件(d)自体の過剰ブロック（own-dirty誤判定）側もmonitoring観点で1回確認すること

## 3軸評価
```json
{"evaluation":{
 "technical":{"score":9,"assessment":"--taskスコープ・foreign warning-only・判定不能repo_failsafe・旧mode不変の4挙動すべてselftest+実環境二重で実証。hook配線も確認。","evidence":"selftest exit 0 (d_bleed 3行)、pytest 16 passed、t_3980b57eでのd_scope=task/repo対比CLI"},
 "business_kpi":{"score":9,"assessment":"cond(d) override 0件ベースライン確立。並行workstream巻き込みブロック（worker停止・QA再作業コスト）の構造的解消が見込める。","evidence":"audit_cond_d_override.py: v79起算 overrides=0、過去5件全てデプロイ前"},
 "cost_efficiency":{"score":9,"assessment":"監視はread-only SQLite+ログgrep、LLMコストほぼゼロ。新規cronなしで既存監査ラインへ統合。","evidence":"プローブ実行<1s"}
},
"loop_health":{"score":95,"stagnation_streak":0,"verdict":"healthy"},
"self_review_quality":{"valid":true,"notes":"worker申告数値（exit 0/16 passed/commit hash）は全て独立再走・git showで一致。logヒットの1件は本タスクログ内のgrepパターン自己一致で、override不是と判定し除外根拠を明記。"},
"verdict":"pass",
"next_steps":[
 "2026-09-17まで毎日の監査ラインで audit_cond_d_override.py の cond_d_overrides=0 を確認（>0なら申し送り）。",
 "board hygiene: /mnt/d/Project2/kensho の devto_weekly_pipeline.py 未コミットが他lane（foreign）として残置中。owner worker次回tickでcommit or stashのこと（cond(d) --taskではブロック要因にならないことを実証済み）。",
 "watch終了時点で条件(d) own-dirtyの誤ブロック（所有帰属の過検出）1件以上があれば TASK_ID_RE/OWNED_PATH_TOKEN の境界をcriticへ。"
]}
```

## 申し送り
- 重大問題なし。v79は承認（QA pass）。
- 注意点（轻）: 旧QAノート名の連番がcritic/qaで共有カウンタのため、当レポートを qa-v82 採番とした（直近: critic-v81 / qa-v80）。
