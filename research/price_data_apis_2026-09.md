# 価格データ関連 API/テンプレストアの最新事例レポート

**調査日**: 2026年9月5日
**調査対象**: Hacker News / Reddit / IndieHackers / Apify Store / Gumroad / Lemonsqueezy (Twitter #buildinpublic は xurl CLI が Windows 専用で本WSL環境から実行不可、ProductHunt は Cloudflare bot ブロックのため除外)
**選定基準**: 個人開発者として興味が持て、かつ「価格データ API/テンプレ」として商品化可能性が高いもの

> 注: 今回の調査で Reddit JSON/RSS および ProductHunt は Cloudflare bot ブロックにより取得不可。Gumroad/Lemonsqueezy は公式検索 API が公開されていないため、Apify Store (公開 API) と HN Algolia API (公開 API) を中核に、その他は個別ページフェッチで補完した。

---

## 1. **Indextkn** — 900+ AIモデル価格の一元API
- **リンク**: https://indextkn.com
- **出典**: Hacker News Show HN (2026-09-01, pts=2)
- **要約**: OpenAI / Anthropic / Google など全主要プロバイダの 900+ AIモデルのリスト価格 (per 1Mトークン) を単一の高速APIで提供。free key 配布で開発者向けに最適化。
- **商品化可能性**: **高**
  - 理由は3点: (1) 需要が既に Apify Store に「AI Model Price Monitor」(runs=53) や「AI Model Prices: Cost, Speed and Uptime」(runs=43) として存在し、商業的需要が証明されている (2) 自前スクレイピング + 正規化のパイプラインは技術的に再現可能 (3) RapidAPI / Stripe で $9〜$49/月 tier がそのまま転用できる。kensho の既存 X セッション/スクレイピング資産 (kensho_collect.py パターン) と類似。

## 2. **Spread** — ニュージーランド supermarkets 価格API/MCP
- **リンク**: https://spread.butterup.app/
- **出典**: Hacker News Show HN (2026-08-16)
- **要約**: 「The grocery market, in one API」— NZ のスーパーマーケット (Pak'nSave, Woolworths NZ, New World 等) の生鮮・日用品価格をリアルタイム取得。MCP対応で AI エージェントから直接呼び出せる。
- **商品化可能性**: **中**
  - ニッチが狭く (NZ限定) 国内市場では転用困難だが、**MCP対応で AI Agent ツールとして $0.001/call** 課金モデルはそのまま日本に持ってこられる。kensho なら「日本のスーパーマーケット特化 (ヨーカドー/イオン/ライフ)」で類似構成が可能。

## 3. **Hackney** — Uber/Lyft/Waymo/Robotaxi ライドシェア価格比較
- **リンク**: https://hackney.app/
- **出典**: Hacker News Show HN (2026-07-13, **pts=60** = 本バッチで最多)
- **要約**: 1つのアプリで Uber・Lyft・Waymo・Robotaxi の見積もりを同時比較。iOS アプリとして一般消費者向け、APIは非公表。
- **商品化可能性**: **中**
  - B2C アプリは開発・運用コストが高いが、**「タクシー料金比較API」 (日本版: GO・Uber・S.RIDE・DiDi)** として B2B 提供すれば需要あり。kensho のスクレイパー基盤 (config.yaml / scraping/) を日本タクシーアプリ向けに再利用しやすい。

## 4. **Apify Store: AI Model Price Monitor** (by genetheaiguy)
- **リンク**: https://apify.com (search "AI Model Price Monitor")
- **出典**: Apify Store API 直接取得 (runs=53, 2026)
- **要約**: GPT/Claude/Gemini/Llama/Mistral など 300+ モデルの per-token API 価格を正規化して $/1M tokens で返す actor。price-change detection 付き。
- **商品化可能性**: **高**
  - Apify 上で既に runs=53 = 実ユーザーが利用中 = **需要の実証データ**。kensho なら同じカテゴリで **「日本版 eコマース価格監視 actor」** (Amazon Japan / 楽天 / Yahoo!ショッピング / メルカリ) を作って Apify+RapidAPI で並売できる。kensho のスクレイピング技術スタックと完全一致。

## 5. **ListofDisks** — HDD価格インデックス (7 retailers)
- **リンク**: https://news.ycombinator.com/item?id=46992426 / https://listofdisks.com
- **出典**: Hacker News Show HN (2026-02-12, pts=4)
- **要約**: HDD/SSD の $/TB トレンドを Amazon 含む 7 retailer から集計して表示。スプレッドシート的にシンプルな構成。
- **商品化可能性**: **中**
  - 個人開発の「お手本」案件として価値あり — **テンプレストア的に「Notion テンプレート / Google スプレッドシート + 自動更新スクリプト」として $19〜$49 で販売** できる構造。kensho の utils/backup.py のように「定期スクレイピング + CSV出力」だけの薄い実装で十分利益化可能。

---

## まとめ・所感

- **最も商品化可能性が高い順**: ① Indextkn 系 (AI モデル価格) ② Apify 既存需要の乗っ取り型 (日本eコマース) ③ Hackney 型 (日本タクシー) ④ Spread 型 (MCP × ニッチ小売) ⑤ ListofDisks 型 (テンプレート販売)
- **kensho プロジェクトとの親和性**: kensho の既存資産 (Xセッション分離スクレイピング、scraping/モジュール、Apify トークン保持) はすべて「価格データAPI/テンプレ」商品にそのまま転用可能。**最短で商品化できるのは「Apify actor を作って $5〜$30/month tier で売る」パターン** — 既に海外先行者が需要を証明しているため。
- **未取得ソースについて**: Reddit/ProductHunt/Twitter が本セッションでは Cloudflare+環境制約で取得できなかったため、次回は (a) Reddit は PRAW + OAuth または Pushshift (b) PH は GraphQL 直叩き (c) Twitter は Windows 側で xurl 実行、で再取得推奨。
