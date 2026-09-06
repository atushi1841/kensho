# [status: open] critic_proposal_2026-09-07-v45: audit script drift cleanup + scorer test positive case

- タスク: t_e5f7ea29 (ready, assignee=kensho-revenue-worker, idempotency-key=critic-20260907-v45-DRF)
- 優先度: 中（衛生・誤ターゲット防止） / リスク: 低

## 根拠（エビデンス）
- `kensho-noagent-job-audit.sh` が3コピー存在:
  - `/home/atushi/.hermes/profiles/kensho-sweeps/scripts/` (309行, 09-07 03:01)
  - `/home/atushi/.hermes/scripts/` (309行, 同一)
  - `/home/atushi/.hermes/profiles/kensho-revenue-worker/scripts/` (169行, 09-06 23:48, diff 162行, v33以来dormant)
- worker notepad 03:1x の [SUBMIT next critic] を昇格。
- 監査ジョブ a85cf2d361cf は `kensho-noagent-job-audit.sh` を参照（06:30初tick）。解決先がdrift版だと誤監査リスク。
- 併せて critic HANDOFF 残件（test_scorer_weights.py の正例テスト欠如）を同タスクに統合。

## 成功指標
- find で audit スクリプトのコピーが同一内容（309行）2つ以下 or 1正本+シンボリック
- `pytest tests/test_scorer_weights.py -q` 全通過・正例ケース1件以上追加

## 検証コマンド
`find /home/atushi/.hermes -name kensho-noagent-job-audit.sh -exec wc -l {} + ; cd /mnt/d/Project2/kensho && python -m pytest tests/test_scorer_weights.py -q`

## 失敗時の代替
シンボリックリンクがcronのscript解決を壊す場合、drift版を309行版にsync-copyで上書き（削除しない）。

## 観測メモ（04:20-04:25実測）
- ce22c907d66d (kanban-ready-deprecate-nightly): 04:00:52 tick **ok**（9/6 failed=Script not found は復旧済み、v42系修正が効いた）→ error残留は解消、監視解除。
- c0e8e4d76933 (kensho-dataset-weekly-update): last run 8/31 error 残留。次回tick 9/7 10:00（本日月曜）。ここで判定。
- a85cf2d361cf 初tick 06:30 = 初の実Telegram配信。QA v45 NEXTと整合、06:30以降に評価。
- ready=0供給不足→本件1件投入（priority=new_proposals 準拠）。
