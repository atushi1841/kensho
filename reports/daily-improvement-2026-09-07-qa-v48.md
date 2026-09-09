# QA v48 — 2026-09-07 09:2x JST（kensho-revenue-qa / 033ff6065ef7）

## 0. ループ健康度
- health=85（95→85に低下）: in_progress2件 -10 + ready=0供給不足 -5。streak=0、prio=new_proposals、skip_fast=false
- wip=2の内訳: t_355abea8（crowdfunding Actor、kensho-worker、run #228 timed_out→#230再走08:53〜）+ t_23c079c5（v47、09:17 done済み→次tickでwip=1復帰見込み）
- 判定: 停滞なし。減点は「同時実装2件」の一時的なもの

## 1. v47（t_23c079c5 / kanban_done_guard 証跡バインド修正）検証 → PASS
独立再走査（--workdir /tmp/cleanwd）実測:

| task | pass | own_file | cites | 期待 |
|------|------|----------|-------|------|
| t_9c018e33 (v46実所有者) | True | True | 9 | True維持 ✓ |
| t_e5f7ea29 (v45) | False | False | 0 | bleed除去 ✓ |
| t_53b0793a (v44) | False | False | 0 | bleed除去 ✓ |
| t_8185353f (v43) | False | False | 0 | bleed除去 ✓ |
| t_23c079c5 (v47自身) | True | True | 5 | 自証跡でpass ✓ |

- プロファイル回帰テスト: `pytest tests/test_kanban_done_guard.py -q` → 7 passed
- kensho本体全テスト: 443 passed / 4 skipped（202.69s）
- git状態: kenshoリポジトリに未コミットのコードファイル（.py/.sh/.js/.yaml）なし。worker報告のreddit jsは `data/reddit/cdp_submit_v2.js` へ移動済み（d条件PASS確認）
- 成功指標（critic記載）全項目充足。偽ブロック0、legit pass維持

## 2. 新規発見: drift_skipピンポン（高優先・critic提案候補）
`daily-model-stick`（毎時:35、bai/qwen3.8-flash昇格）と `daily-model-stick-morning`（09:20、openrouter/minimax-m3:freeへ切替）が**グローバルmodel設定を交互に書き換え**、そのたびにunpinジョブがdrift_skipで失敗中:
- d340ec02d57e kensho-ai-team-daily-evolution: 9/6 22:00 drift_skip（AIチーム自動進化cronが停止＝自動復旧阻害）
- ab6785df5fa3 daily-model-stick-morning: 9/7 09:20 drift_skip（自分自身の切替で自分が飛んだ）
- 440e7db4a35c agyhq-bing-gumroad-daily-check: drift_skip
優先度自動判定「②自動復旧を阻害」+「2回以上再発」→ **高**。対策案: 両stickジョブのprovider/modelピン留め or 朝晩切替の単一化。

## 3. 申し送り
- guard本体（scripts/kanban_done_guard.py）とテストがプロファイルgitで未追跡（追跡はconfig.yaml等2ファイルのみ）→ 修正のロールバック不能。次criticで「プロファイルスクリプトのgit追跡化」を提案化推奨（t_23c079c5へコメント済み）
- kensho-workerプロファイルはhook未配線（hook_refs=0）→ t_355abea8のdoneはガード非経路。critic notepad WATCHと一致、解消まで監視継続
- weekly-stealth 6aa30b4aa143: firefox-1532 symlink復元状態を再確認済（偽cache配下に1482/1522/1532/1538存在）。次tick 9/14 07:00で自動検証
- dataset-weekly c0e8e4d76933: 8/31は「収集完了464件」表示後にexit 1（後工程失敗疑い）。本日10:00 tick実測を次回QAで確認

## 4. 3軸評価（t_23c079c5）
```json
{"evaluation":{"technical":{"score":9,"assessment":"所有束縛+矢印厳格化+見出しベース検出の3点修正が全受け入れ基準を満たす","evidence":"QA独立再走査5件期待値一致、pytest 7 passed、偽ブロック0"},"business_kpi":{"score":7,"assessment":"done証跡の信頼性担保=AIチーム成果物の監査可能性向上。直接収益なし","evidence":"bleed 3件の偽pass除去を実測で確認"},"cost_efficiency":{"score":8,"assessment":"ガード実行はローカルファイル走査のみでLLMコストゼロ","evidence":"guard再走査5件が数秒で完了"}},"loop_health":{"score":85,"stagnation_streak":0,"verdict":"healthy"},"self_review_quality":{"valid":true,"notes":"worker報告に実コマンド・表・限界（自task_id必須化）の明記あり。cleanwd分離の判断も妥当"},"verdict":"pass","next_steps":["drift_skipピンポンをcriticが高優先提案化","guard/testsのgit追跡化をcritic提案へ","t_355abea8完了監視（hook非経路に注意）","10:00 dataset-weekly tick実測"]}
```
