# 調査レポート（2026-09-26 / Kensho収益化アイデア調査）

## 発見した情報（信頼度付き）

### 1. MCP市場の急成長とゲートウェイ経済の現状
- **情報**: Model Context Protocol市場は2025年$1.28B→2035年$28.46B（CAGR 37.22%）で急成長。ゲートウェイ・統合プラットフォームが32.47%シェアを握る（~$416M in 2025）。Apify、MCPize、MCP Marketplaceが80-85%の開発者収益分配を実装済み。Glama/Smitheryはクリエイター還元なし、または不透明（SEOSiri記事 / 信頼度: 高）
- **情報源**: https://www.seosiri.com/2026/09/mcp-monetization-gap-glama-smithery-developer-losses.html
- **引用元**: DataM Intelligence、SNS Insider、Mordor Intelligenceの市場調査データ

### 2. MCP収益化の実践モデル（4つのモデル）
- **情報**: per-call / subscription / freemium / outcome-basedの4モデル。安価な呼び出しはsubscription、高コスト呼び出しはper-call/outcomeが適正。x402（USDC/HTTP 402）とStripe MPP（フィアット）の2つの決済レールが成熟。メーター実装（per-tool料金、冪等性、agent上限、マイクロ決済集計）が真の難関（UsageBox記事 / 信頼度: 高）
- **情報源**: https://usagebox.com/articles/how-to-charge-for-mcp-server-2026-per-call-subscription-x402
- **補足**: x402はBase上で50M+トランザクション実績、sub-2秒決済。Linux Foundation移管でVisa/Stripe/Google/AWS/Microsoftが創業メンバー

### 3. MCP収益化ツール比較（ChatAds/ZeroClick/Dappier/Apify等）
- **情報**: ChatAdsが唯一のネイティブMCPアフィリエイト挿入（手数料0%、per-request課金）。Apifyがアクター収益モデルで実績あり。MCPizeはサブスク/per-install/usage-based。Neverminedはoutcome-based。Koah Labs/Dappierは広告フィル。自前構築ならStripe MPP/x402（ChatAds記事 / 信頼度: 高）
- **情報源**: https://www.getchatads.com/blog/tools-for-monetizing-mcp-servers/

### 4. Micro SaaSトレンド2026（垂直AI・ニッチ特化）
- **情報**: Micro SaaSは「タイトなニッチ×単一ジョブ×月額課金×ノンVC」。45.7%がソロ創業、95%が初年度黒字。勝ちパターン：①自分が顧客のニッチ ②既存ツールが最後の20%で失敗する場所 ③AIで18ヶ月前に不可能だったワークフロー。配布は創業者主導コンテンツ（LinkedIn/Indie Hackers/垂直コミュニティ）。Browse AI（ノーコードスクレイピング）、Bardeen（ブラウザ自動化）が実例（Grow Predictably / 信頼度: 高）
- **情報源**: https://growpredictably.com/micro-saas-examples

### 5. APIビジネスアイデア：スクレイピング/データ抽出API
- **情報**: Web Scraping API市場$1B+。プロキシ/CAPTCHA/JSレンダリングを処理。課金：リクエスト単価orページ単価。ユースケース：価格監視、リード生成、市場調査、SEO、EC競合分析。Browse AIが「コード不要」で非技術層を開拓し成功（IdeaProof / 信頼度: 中）

### 6. 日本国内：商品リサーチ代行・データ収集の副業需要
- **情報**: EC拡大で商品リサーチ代行の需要急増。ココナラ等で「RPAで自動納品」副業が実在。クラウドワークスで「ChatGPTデータ収集」「海外ECリサーチ」案件多数。月5万副業としてデータ収集・リサーチが上位に。ただし「転売自動化」は構造的却下済み（SOHO/note/クラウドワークス / 信頼度: 中）
- **情報源**: https://atsoho.com/blog/product-research-agency-remote-side-hustle-2026、https://note.com/pokecon/n/nc3b2b0571d14

### 7. Gumroadデータ商品の実態
- **情報**: 20万件分析で「Micro-SaaSスクリプト（スクレイピング等小さな問題解決ツール）」が売れ筋。情報商材より「ショートカット（テンプレート+解説PDF）」が高単価。競合分析用スクレイパー自体もChrome拡張として販売されている（Reddit/Medium / 信頼度: 中）

### 8. データブローカー市場の成長
- **情報**: $327B(2026)→$579B(2034) CAGR 7.41%。コンシューマデータ46%、BFSIセグメント最大。サブスクリプション58.6%シェア、従量課金が最速成長（Fortune Business Insights等 / 信頼度: 中）

---

## Kenshoへの適用提案

| # | 提案内容 | 期待効果 | 実装コスト | リスク | 優先度 |
|---|---|---|---|---|---|
| 1 | **MCPサーバー化してApify/MCPizeで収益化**<br>Kenshoのスクレイパー・X操作・データ収集パイプラインをMCPツールとして公開。Apify Actor（80%分配）またはMCPize（80-85%）経由で課金 | 既存資産の直接収益化。Apify 58本→MCP化で新規収益チャネル | 低（既存コードのラッピングのみ。MCP SDK追加） | プラットフォーム依存、価格競争 | **高** |
| 2 | **x402ネイティブMCPマーケットプレイス出品**<br>自前ホスティングでx402（USDC per-call）課金。Stripe MPP併用で法人向けサブスクも提供 | 仲介手数料なし、完全コントロール。高単価ツール（X操作・複合データ収集）向き | 中（メーター実装・ホスティング・決済統合） | トラフィック獲得が自前必要、USDC決済の普及度 | **中** |
| 3 | **垂直特化「ノーコード懸賞データAPI」Micro SaaS**<br>Browse AIモデルで「懸賞・キャンペーン情報」に特化したノーコード抽出ツール。マーケ担当・代理店・EC運営向け | ニッチ独占。Kenshoの収集ノウハウがそのまま商品価値に。月額$39-79×100社で$3.9-7.9k/月 | 中（UI構築・認証・課金・ドキュメント） | 競合参入障壁低い、集客が最大の課題 | **高** |
| 4 | **「懸賞当選データセット」定期販売（Gumroad/自前）**<br>収集済みデータをクレンジング・構造化し、週次/月次データセットとして販売。当選傾向分析レポート付き | ストック型収益。一度作れば追加コスト低。マーケター・メーカー需要 | 低（データ整形・自動化スクリプト） | データの鮮度・独自性維持、著作権・TOSグレー | **中** |
| 5 | **商品リサーチ代行「自動納品サービス」（ココナラ/クラウドワークス）**<br>KenshoのスクレイピングをRPA化し、「キーワード指定→CSV納品」を自動化。単価¥5,000-15,000/案件 | 即金性高い。実績作りから開始可能。スキル資産の横展開 | 低（既存パイプライン転用・納品フォーマット整備） | 単価安い、スケールしにくい、手動要素残る | **低** |
| 6 | **n8nテンプレート「懸賞自動化ワークフロー」販売**<br>Kenshoの全工程をn8nワークフロー化し、テンプレートとして販売（Gumroad/自前） | ノーコード層への展開。コミュニティ販売で拡散期待 | 低（既存ロジックのn8n移植） | n8nマーケットまだ小さい、サポート負担 | **低** |
| 7 | **アフィリエイト挿入型MCP（ChatAdsモデル）**<br>「懸賞おすすめ」を返すMCPにアフィリエイトリンク自動挿入。Amazon/楽天アソシエイト経由で報酬 | 追加実装コスト極小。会話型UIと相性良し | 低（ChatAds SDK統合のみ） | 日本市場でのアフィリエイト単価低、利用頻度不安 | **低** |

---

## 次のテーマへの申し送り

1. **MCPサーバー実装の技術検証** — Kenshoの主要機能（収集・応募・X操作）をMCPツール化するプロトタイプを作り、Apify Actor / MCPizeへのデプロイ手順・収益シミュレーションを検証する

2. **垂直Micro SaaSのニッチ検証** — 「懸賞・キャンペーン情報」以外に、Kenshoの技術が刺さる垂直ニッチ（EC価格監視/口コミ収集/求人データ/不動産物件/補助金情報等）を列挙し、TAM・競合・参入障壁を比較検討する

3. **集客チャネルの実証実験** — ボトルネックは「売る」にあるため、LinkedIn/X/Indie Hackers/ココナラ/クラウドワークス各チャネルでテスト出品・反応測定を行い、CAC/LTVを実測する

4. **x402/Stripe MPP実装のコスト試算** — メーター（per-tool課金・冪等性・agent上限・集計）の自前実装vs.UsageBox等マネージドサービスのコスト比較、ブレークイーブン点を試算する

5. **法務/TOSリスクの整理** — データ販売・スクレイピングAPI提供における利用規約・著作権・個人情報保護法リスクを、日本法務視点で整理し、安全な提供形態（生データ非提供/統計のみ/契約締結必須等）を設計する