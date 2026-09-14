# 調査レポート（2026-09-13 / 収益化アイデア調査：Kensho資産活用・戦略視点）

調査者: kensho-research-agent（cron） / シード: aee13aca

## 調査方法
- DuckDuckGo検索 8クエリ（EN: MCP monetization / Apify revenue / n8n templates / API販売 / JP: 懸賞ツール）
- 記事fetch 4本（godberrystudios MCP収益化プレイブック / mcp-marketplace状態レポート / Apify MCPドキュメント / Apify Store実ページ）
- GitHub trend・Apify Store実地検索（giveaway / japan系actorの競合確認）
- 情報源: Web検索4+fetch4+ストア実地2 = 規定（3情報源・4キーワード）充足

## 発見した情報（信頼度付き）

### 1. Apify経由のMCP公開が「作らずに売れる」最新チャネルになっている（信頼度: 高）
- Apify公式MCPサーバー `mcp.apify.com` に接続すると、**既存ActorがそのままAIエージェント（Claude/Cursor/VS Code）から実行可能なツールになる**。開発者は追加実装ゼロで、エージェント経済の流通に乗れる
- 重要制約2つ（Apify公式ドキュメントで実測確認）:
  - **full-permission ActorはMCP検索・実行から除外**（セキュリティ上LLMに承認を委ねられない）
  - **サブスク課金モデルのActorは除外**（断続的オンデマンド実行と合わない）。残る pay-per-result / pay-per-event 課金のみがMCP経由で売れる
- 決済レールが2系統進化: x402（USDCマイクロ決済、`mcpc connect "mcp.apify.com?payment=x402"`）と Stripe MPP（2026年3月公開、セッション合算請求）。エージェントが自律的に支払い→実行する流れが本稼働
- 収益分配は80%、Store累計$4M+を支払済、トップ開発者は$10k–50k/月（Apify公式help + proxies.sx 2026-02 + use-apify の3ソース一致）
- 出典: https://docs.apify.com/platform/integrations/mcp / https://github.com/mcp/com.apify/apify-mcp-server / https://help.apify.com/en/articles/8684010 / https://apify.com/partners/actor-developers

### 2. MCPサーバー市場は「95%が無料=収益化済みなし」= 早期ポジションが取れる（信頼度: 中〜高）
- MCPサーバーは12,000–12,770本超、SDKダウンロード97M+/月、**収益化できているのは5%未満**（SettleGridデータレポート+itlibra+mcp-marketplaceの3ソース一致）
- 課金モデルは4種に収束: per-call（$0.001–0.10）/ サブスク（$10–50/月）/ freemium（変換率の実証例あり）/ outcome-based（成功時課金。Moesifがネイティブ対応）
- 実例: 21st.dev Magic MCP = freemium（無料100credits→$20/月）で**6週間で$10K MRR**（創業者申告値なので上限気味に解釈）。PulseMCP/Glama/Smithery等のディレクトリSEOが流入源
- 警鐘例: Godberry StudiosのContent-to-Social MCPは $0.07/call で4/12公開→**2週間で支払いユーザーゼロ**。マーケティング停止。著者自身「配管は簡単、売るのが難しい」と結論 — Kenshoの自己診断（ボトルネックは売る側）と一致
- 手数料比較: Apify 20% / MCPize 15% / MCP Marketplace（Stripe Connect+ライセンスキーSDK同梱）/ セルフホスト+ゲートウェイ ~3%
- 出典: https://godberrystudios.com/posts/how-to-monetize-mcp-servers-2026/ / https://mcp-marketplace.io/blog/state-of-mcp-monetization-2026 / https://arte.itlibra.com/en/articles/can-mcp-servers-be-monetized

### 3. 「懸賞/キャンペーン」ドメインはXデータ系の成熟ニッチ、ただし日本データは空白（信頼度: 高）
- Apify Store実地検索で確認できた競合: X Giveaway Winner Picker（apify.com/jan.jiran/twitter-giveaway-picker、抽選側）、twxpicker.com / commentpicker.com / simpliers.com（無料抽選ツール=需要実証）、日本ではcan4u.jp（キャンペーン自動化SaaS=国内需要の実証）
- 日本系スクレイパーは **japan-contact-scraper / rakuma-japan-scraper / mercari-japan-scraper / japan-houjin-bangou-scraper あたりが数本あるのみで、Google Play上位級の本数ではない**。しかし「懸賞・キャンペーン情報まとめサイト」の専用スクレイパーは見つからず（knshow/ken-kaku/kenshou.club系のデータはStoreに不在=競合ゼロの手がかり、信頼度: 中=不在の証明は困難）
- Tweet Scraperの相場は $0.18–0.40/1K tweets、Pay-Per-Result型が主流
- 出典: Apify Store実地（https://apify.com/store?query=giveaway）+ 検索結果（信頼度: 高=一次確認）

### 4. n8nテンプレ販売は「実録$47K/年」の一方、公式無料ライブラリ11,741本で飽和気味（信頼度: 低〜中=宣伝記事バイアス注意）
- Medium記事: 5本のn8nオートメーションで$3,200/月（2026-03）/ 同一3ワークフローで$47K/年（2026-01）— いずれも販売促進色が強く一次検証不可
- 公式n8.io/workflowsは無料テンプレ11,741本（2026-08時点）。無料ライブラリが厚い分、売れるのは「ニッチ×保守込み×日本語」など差別化軸に限る
- Kenshoの応募パイプラインはPlaywright/CDP寄りであり、n8n転用の親和性は中程度（収集→選別→通知のオーケストレーション部分はテンプレ化可能）
- 出典: https://medium.com/write-a-catalyst/... / https://connectsafely.ai/articles/n8n-templates-workflow-automation-examples

### 5. RapidAPI（現Rapid / Nokia傘下）は先行き不透明、MCP対応が始動（信頼度: 中）
- 2024年11月Nokiaが技術・R&Dチームを買収、マーケットプレイスは "Rapid API Hub" として継続運営、2026年にMCPサポート追加（geekflare+zuploの2ソース一致）。Zuploは「Nokia買収以降将来が不確実」と明記
- 現行20本のRapidAPI公開APIは維持しつつ、**新規の集約はApify+MCP側に寄せるのが合理的**

## Kensho資産との相性評価

| 提案 | 既存資産との相性 | 実装コスト | 売る労力 | リスク |
|---|---|---|---|---|
| A. 現行ApifyアクターのMCP経由最適化 | ◎（61本そのまま） | 低（課金方式・スキーマ監査のみ） | 低（自動発見） | 低 |
| B. 日本懸賞・キャンペーン情報スクリャーパー（新規アクター） | ◎（収集パイプライン4ソース流用） | 中（アクター化1〜2日） | 中（Store+ディレクトリ登録） | 中（ソースサイトのTOS/スクレイピング etiquette） |
| C. Xキャンペーン抽選・スパム除去API（日本語対応） | ○（bot検出の逆引き知見、DMスキャン） | 高（公平性・ルールエンジン） | 中（can4u/twxpickerが需要実証済み） | 中（「bot検出屋」=自らの検出手法公開と読まれ得る） |
| D. n8nテンプレ販売（収集→通知系） | △（パイプラインがPython/CDP寄り） | 中 | 高（飽和市場・自社導線必要） | 低 |

### 提案A（優先度: 高・コストほぼゼロ・即実施可）— 「エージェント流通」への乗せ換え
- 内容: 既存Apifyアクターのうち **full-permission型とサブスク型を監査し、pay-per-result/pay-per-eventへ寄せる**。input/outputスキーマを構造化（hosted MCPはoutput schema inferenceで型を自動露出するため、スキーマ品質がMCP検索ランキングに直結）
- 期待効果: 9/11時点で収益$0の61本が、マーケティング一切なしで Claude/Cursor エージェントのツール検索に現れる。21st.dev型freemium（無料回→課金）を上位2〜3本に試験導入
- リスク: ほぼなし。注意点は課金イベント定義の絞りすぎ（Godberryの教訓: 公開2週間でゼロユーザーが普通、と前提を持つ）

### 提案B（優先度: 高・1〜2日）— 日本キャンペーン情報の空白ニッチ
- 内容: `Japanese Campaign & Giveaway Scraper` として knshow/ken-kaku/kenshou.club/cp.meikan の収集ロジックをアクター化。**X懸賞応募者・マーケター・データ購入者**の3購買層を主張できるが、実証済み層は抽選側ツール購入者（情報源3の実証）とマーケの競合キャンペーン監視（Brand Mention Monitor系の既存需要）
- 差別化: 日本語・日本専用に特化（海外勢が追えない領域）、Storeに同種不在
- 実装コスト: 収集モジュールは既にあるため、input schema + README + 課金イベント設定が中心
- リスク: ソースまとめサイト側の負担をかけないようレート制限・公開データのみ・出典明記。当選確率を上げる「応募bot」機能は一切含めない（X検出リスクの転嫁になるため）

### 提案C（優先度: 中・要検証）— 抽選スプームフィルタAPI
- 内容: 主催者向けに「応募リスト→bot/スパムスコア→公正抽選→当選DM文生成」。twxpicker/can4u/jan.jiran pickerが需要実証。Apify版は1本のみ=競合薄い
- リスクの本質: Kensho自身の検回避ノウハウを逆転させる構造。公開実装は「スパム応募の一次特徴（連投・新規垢・テンプレ文言）」に限定し、検出ロジックの核心は出さない設計が必要。実装前にTOS・倫理レビュー推奨

### 提案D（優先度: 低）— n8nテンプレは現状非推奨
- 無料ライブラリ11,741本の飽和市場+宣传記事頼りの収益実績。Kensho資産との相性も低い。方針転換トリガーは「A/Bが30日で$0だった場合」に限定

## 次のアクション提案（優先順）
1. **今日できること（提案A）**: Apifyのダッシュボードで61本の課金方式・パーミッション種別・スキーマ品質を棚卸し（スクリプト化可: apify APIで(actor list)→full-permission/サブスクの数を数える）
2. **今週（提案B）**: 日本キャンペーンスクレイパーを1本公開 → PulseMCP/Glama/Smithery/MCP Marketplace に無料枠でクロスリスト（MCP Market Place記事: クロスマーケは無料・数分・非独占）
3. **公開2週間はGodberry教訓に従い売上を期待せず**、MCP経由run数が付くかだけ監視 → 付けば上位スキーマを拡充、付かなければ導線（X日本語アカウントでの公開・てくなブログ等）を追加検討
4. 検証用メモリ: Apify可視性ウォッチスクリプトに「MCP経由run数」の項目を追加（既存count読み取りに統合）

## 次のテーマへの申し送り
- mcp.apify.com の検索ランキングロジック（quality score互換パラメータと明記）の具体要因 → 次回: 上位アクターのREADME/schema差分分析
- 日本発MCPサーバー・日本語データツールの競合（Smithery/Glamaでjapan検索して実数確認）→ 次回
- 提案Bの実需検証: 「懸賞 データ セット 販売」の国内検索ボリュームとcan4uの料金ページ詳細
