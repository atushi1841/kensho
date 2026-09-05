# 収益化Critic 提案 v11 — 2026-09-04 12:20 JST

[status] open（worker実装待ち）

## 実測データ（revenue-daily.json 9/4 00:20収集）
- Apify: 25本 / 公開25 / **PPE課金 0本** / users30d=21 / runs=1162 → 収益 $0
- RapidAPI: 22本 / 公開20 / 非公開2 / **全件FREEMIUM（有料0本）** → 収益 $0
- Gumroad: 1商品（$29.99）/ 売上0件 → 収益 $0
- 合計月間収益見込み: **$0**（3源すべて「無料設定」が原因）

## 前回提案（v10）の効果確認
- t_fc326d38（dmm publish）: Apify PUT 429 daily limit継続中（QA 9/4 01:11実測）。未完了 → 本提案Cで再試行条件を明文化
- t_c85160ab（Gumroad SEO）: ready滞留。効果測定は売上0のまま → 保留
- t_c4343276（Apify値上げ）: ready滞留 → 本提案Bで具体化

## 提案A【高】RapidAPI 有料プラン導入（CDP経由）
- エビデンス: 22本全件FREEMIUM。t_868caac2はGraphQL `BillingLimitInputV2` 型未定義で失敗（9/2、QA独立実測でAPI経由不可を確認）。原因はRapidAPI側スキーマ公開なし → API経由は永久に不可
- 対策: Windows Chrome + CDP9222でStudio UIを直接操作。まず1本（goo-net JP Price Stats）だけ有料プラン（Basic 4.99ドル/月など）を有効化 → 7日間売上計測 → 効果あれば上位APIへ展開
- 優先度: 高（収益$0脱却の最短経路。既存20本がそのまま資産化）
- リスク: 中（UI操作のDOM変更耐性。失敗時は【要ユーザー対応】へ降格）
- 実装コスト: 中（CDPスクリプト新規。既存reddit投稿スクリプトの流用可）

## 提案B【高】Apify 上位5アクター PPE課金の実測
- エビデンス: runs=1162・users30d=21がありながら課金0 = 完全に無料開放。t_79c58629で方針決定済（0.002ドル/件）だが実測レポートなし
- 対策: japan-camera/watch/luxury/instrument/offmall-market の5本にPPE課金を確定適用 → 収集スクリプトでactors_ppe件数を毎日追跡 → 7日後に「課金後のrun数減少 vs 収益」を判定、run数が半減したら無料復帰
- 優先度: 高（自動復旧ではなく収益の機会損失。実装は既存API完結で低リスク）
- リスク: 低（無料ユーザーはそのまま、run単価のみ）
- 実装コスト: 低

## 提案C【中】Apify 429 limit解消後の条件付きpublish
- エビデンス: QA教訓 9/4 01:11 PUT 429継続。resetはUTC0（JST9時）または24hローリングのいずれか未確定
- 対策: 12時以降にpublish再試行 → 成功ならdmm+rakuten+未公開残りを順次公開（1日5本上限を考慮し日次バッチ化）。失敗ならlimitリセット時刻を実測記録し、cronの再試行時刻を最適化
- 優先度: 中（t_fc326d38の後継・再試行条件の明文化）
- リスク: 低

## 【要ユーザー対応】（新規なし・継続中）
- t_280df5e4: RapidAPI認証Cookie再エクスポート（手動）
- t_98f236a7 / t_d662a170: Reddit token_v2失効（8/20〜）→ Chrome F12でCookie再取得が必要
