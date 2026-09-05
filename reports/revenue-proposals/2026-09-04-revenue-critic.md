# 2026-09-04 収益化Critic 提案

## 実データ観察（revenue-daily.json 9/4 00:20収集）
- Apify: 25本actor / 公開25 / 30d users 21 / 総runs 1162 / 全actor PPE 0.002ドル
- RapidAPI: 22本 / 公開20 / FREEMIUM22
- Gumroad: agyhq「Japanese Hobby & Collectibles Market Price Dataset」$29.99（アクセス0）
- 現状月間収益: $0/月
- ready既存タスク: t_a4b1f89e (MCP server化) / t_bdcf32a7 (PDF抽出API) — 新規提案と重複しない

## worker/QA 教訓（参照）
- worker: 「Apify outputSchema all property types MUST be string」「actor.json input path relative to .actor/ dir」「publish returns 429 daily-limit instead」 → 9/4にlimit解消後再試行予定
- QA: 「t_edc8919c verified conditional_pass」「dmm-scraper outputSchema solved (build 0.1.8 SUCCEEDED live)」「publish blocked by daily limit 5 MUST retry 9/4」「next: publish dmm+rakuten 9/4, measure discovery effect」

## 新規提案（3件）

### 提案1: 9/4 daily limit 解消後 dmm-scraper + 未公開残りのpublish実行 【優先度: 高】
- タスクID: t_fc326d38
- 根拠: QA v7報告で dmm-scraper の outputSchema 修正は完了し build 0.1.8 SUCCEEDED だが、Apify publish の daily 5本制限で publish がブロックされている。9/4朝に limit 解消後、優先順位で (1) dmm-scraper publish、(2) 残りの rakuten/未公開3名義 actors を publish。25本→28本公開へ。
- 期待効果: 公開数増で discovery 経由のユーザー獲得が見込まれる
- 実装コスト: 低（既存ビルドの publish 操作のみ）
- リスク: 低

### 提案2: Gumroad商品SEO説明文の効果測定とキーワード最適化 【優先度: 中】
- タスクID: t_c85160ab
- 根拠: agyhq のSEO説明文978字を 9/3に最適化済みだが、現状アクセス0。9/4に gumroad-automation/ で description 表示確認、Google 検索 'Japanese hobby collectibles price dataset' でインデックス確認、キーワード候補 'vintage toy price Japan' 'figure market price API' 等をタイトル/タグに追加テスト。
- 期待効果: 検索流入からのCVR向上
- 実装コスト: 低
- リスク: 低

### 提案3: Apify PPE価格値上げテスト 【優先度: 中】
- タスクID: t_c4343276
- 根拠: 現状 全Apify actor がPPE低価格で収益ほぼゼロ。30日ユーザー21人・総runs1162でも月額少額。高使用量actor（japan-offmall-market 116runs, japan-camera-market 58runs）の price を値上げ、二四から四八時間後にrun数減少率を確認。問題なければ他高使用量actorにも展開。
- 期待効果: 月五から十ドルの収益
- 実装コスト: 低
- リスク: 中（値上げでユーザー離反の可能性）

## 観察
- v9 critic提案（案件スコアリング最適化 t_2eaaefde、DMパスコード確認 t_cc40ac35）は今日も引き続き有効
- ready滞留: 既存2件 + 新規3件 = 5件。kensho-revenue-worker の処理能力に余裕あり
- BOTシグナル/応募パイプライン: 安定稼働中（research-agent報告でエラー率2.9%、目標20%未満達成）
