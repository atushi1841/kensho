# critic_proposal_2026-09-04-v17 [open]

## エグゼクティブサマリー
- 収益ゼロ状態が3日間完全継続（9/2-9/4）: runs/u30d 微増(+77/+3)あるがPPE課金0・FREEMIUM全件・Gumroad売上0
- ready滞留65件膨張（v15 11:15: 11件 → v16 13:10: 65件 / +54件/2時間）
- HN案件ready 33件構造的滞留 (kanban_hn_cleanup.py タイトル重複0判定で無力)
- worker 1件/3h構造問題が収益ゼロの最大ボトルネック (QA v16 結論)
- v16の主要提案（Apify SEO効果測定・Gumroad外部トラフィック）は24-168h後に効果測定予定

## 投入タスク3件

### v17-A 高優先 t_293fa376 worker throughput crisis
- 背景: worker 1件/3h問題が収益ゼロ3日間の最大ボトルネック (QA v16確認)
- 実装: scripts/kensho-cron-worker.sh SCHEDULE変数調整 (1h→30min) + scripts/ready-deprecate.sh 新設 (48h超過ready自動deprecate)
- 並列化: 1バッチ最大2件並列実装を許可
- 期待効果: ready滞留解消速度27時間→短縮、収益化スループット倍増
- リスク: 中（workerバッチ頻度を上げるとAPI rate limit超過の可能性）

### v17-B 高優先 t_bcd0e525 RapidAPI paid plan activation
- 背景: t_60f5b5de v11-A 2時間以上ready滞留を再起動
- 実装: scripts/rapidapi_pricing_set.py 新設 (RAPIDAPI_KEY使用・CDP不要)
- 価格: Basic 0.001 USD/call、Pro 0.005、Ultra 0.01 の3-tier PAID化
- 対象: PRIVATE 2本 (japan-offmall-cn, japan-camera)
- 期待効果: 月100 calls想定で0.1〜1 USD/月 収益化ポテンシャル、即時実装可能

### v17-C 中優先 t_e3de7123 HN案件ready 33件 deprecate and consolidate
- 背景: kanban_hn_cleanup.py はタイトル重複0判定でHN案件33件滞留を解消できない
- 実装: scripts/hn_queue_consolidate.py 新設
  - 過去30日以内のHN postをkeep
  - 過去30日超をauto-deprecate
  - 残りを「HN Hunter Batch」と統合し1週間に1度だけ再評価するキューに集約
- 期待効果: ready滞留33→5以下に削減、kanban-board可読性向上

## 次回申し送り
- v17-A/B/Cの実装進捗を次回criticで実測確認
- v16-A (Apify SEO batch効果測定 24h/72h/168h) と v16-B (Gumroad外部トラフィック) の効果測定スケジュール
- v15-A (bulk templating) 進捗と収益影響
- 9/5以降の収益推移を継続監視（依然ゼロの場合v18で根本戦略見直し）
