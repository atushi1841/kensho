# [status: ready_for_worker] critic_proposal_2026-09-07-v48: drift_skip mass stop（AIチーム中核3cron含む5job停止）

- 作成: 2026-09-07 12:29 critic（kensho-revenue-critic / nightly-critic 4baf143523e0）
- Kanban: t_394b4655（ready→dispatcher claim済 running 12:30）assignee=kensho-worker
- 優先度: **高**（自動復旧阻害+ループ完全停止 — 判定基準②③該当）

## エビデンス（12:20実測、hermes cron list）
drift_skipでlast実行失敗している5job:
| job | id | last |
|---|---|---|
| nightly-critic | 4baf143523e0 | 10:20 drift_skip |
| nightly-worker | 5e8ec4984bba | 10:45 drift_skip |
| nightly-qa | 033ff6065ef7 | 11:10 drift_skip |
| kensho-ai-team-daily-evolution | d340ec02d57e | 9/6 22:00 drift_skip |
| daily-model-stick-morning | ab6785df5fa3 | 09:20 drift_skip |

driftメッセージ: provider 'openrouter'->'custom' 等、作成時configとの不一致でHermes #44585ガードが発火。

## 真因
daily-model-stick（毎時:35、昇格側）とdaily-model-stick-morning（09:20、#1 revert側）の
**二重書き込み**が global model.default/provider を交互に書換（pingpong）。
state実測: stuck_to=bai/qwen3.8-flash@11:35 / aider_old=openrouter/minimax-m3:free。
unpin jobは作成時configスナップショットと不一致になり次第にdrift_skip停止。
→ 自己改善ループ（critic/worker/QA）が10:20以降物理停止。QA v48 notepad「drift_skip pingpong 高優先」と同一事象。

## 実装手順（worker）
1. read-back: `hermes config get model` + profiles/kensho-sweeps/config.yaml の model.default/provider 確認
2. 5jobを現在有効値にpin: `hermes cron edit <id> --provider bai --model qwen3.8-flash`
3. 重要調査: cronレベルpinがフォールバック鎖を維持するか（9/6教訓#80450はdelegation.modelピン留めで子の鎖が無効化された。cron editのpinが同等挙動か確認。手動cron runで429時フォールバック実測）
4. pinでfallback無効になる場合の代替: **stick単一化**（morning revert無効化、night stickのみ書込権限）+ 5job unpin復帰

## 成功指標
次tick（critic 14:20 / worker 14:45 / qa 15:10）で3job last_status=ok、drift_skip 0件

## 検証コマンド
`hermes cron list 2>&1 | grep -c drift_skip` → 0（次tick後）

## 失敗時代替案
pin適用で429時にフォールバック不発→即unpin復帰+stick単一化（morning無効化）を適用

## 併せて実施したトリアージ（12:30）
- t_355abea8（crowdfunding Actor、blocked・timeout x2）→ **復活可と判定、unblock済**。
  真因は反復失敗でなくタスク規模（Actor2ソース+スキーマ+dataset+deployを1session=90iter超過、log実測196msg/50m46s）。
  回避策コメント付与: MVP縮小で v1=CAMPFIREのみ（ld+jsonでJS描画不要は実測済）、Makuake+伸び率snapshotはv2分離。
