# ニッチデータセット(日本中古市場価格データ)の買い手セグメント調査

調査日: 2026-09-06 | 商品前提: Gumroad「Japanese Hobby & Collectibles Market Price Dataset」$29.99(売上0)。元データ: メルカリ/駿河屋/ヤフオクの中古ホビー価格、週次更新可。

## セグメント別判定サマリ

| セグメント | 実在性 | 単価 | 当商品への適合 | 優先度 |
|---|---|---|---|---|
| (c) リセラー/アービトラージャー | ★★★ 実証済み | $9-249/月 | ★★★ 最適合 | **最優先** |
| (e) 価格追跡・SaaS開発者 | ★★★ 実証済み | $0.01-0.05/コール、API | ★★★ 高 | 高 |
| (d) 市場調査・アナリスト | △(要再考) | $2,000+レポート | ★ 低(買い物が違う) | 低 |
| (b) アカデミック | △ | ほぼ$0(無料データ使用) | ★ 低 | 低 |
| (a) AI/LLM学習データ | △ | B2B企業案件($KB-万) | ★ 低(個人には向かない) | 低 |

---

## (c) リセラー/アービトラージャー ー 最優先セグメント

**何を買っているか**: メルカリJP→eBay等への越境転売の「商品リサーチ」。出品・落札価格、コンディション、売れ筋、sold comps。生データより「割安アラート」や「落札相場」そのものが欲しい。

**どこで探しているか**: Apify Store(複数Mercari系アクターが明示的にresale research/arbitrage訴求)、Bright Data Dataset、YouTube/TikTokの転売コミュニティ、Reddit r/Flipping、その他転売ブログ。事例出典:
- Apify「Mercari Japan Scraper: Price, Condition & Seller」~$3.99/1,000 listing。明記文言「Cross-border resale research: ...before sourcing items to flip on eBay, Mercari US, or Depop」 — https://apify.com/devanshlive/mercari-japan-scraper (検索スニペットで確認、直接ページは404)
- Apify「Mercari Japan Scraper | Listings Prices Sellers」resale research/price tracking訴求 — https://apify.com/lentic_clockss/mercari-scraper
- Apify「Mercari Japan Scraper – Sold Prices & Listings API」sold prices(comps)明示 — https://apify.com/datalab-jp/mercari-scraper
- ScraperScoop「Japan Mercari Dataset」 — https://www.scraperscoop.com/datasets/japan-mercari-dataset/
- Bright Data「Mercari Dataset」 & Price Tracker — https://brightdata.com/products/insights/price-tracker/mercari 、 https://github.com/danielshashko/mercari-scraper
- 独立記事「Mercari Japan Reselling 2026: Import & Flip for Profit」(プロキシ+転売ガイド) — https://www.underpriced.app/blog/mercari-japan-import-reselling-guide-2026
- オープンソース自作ツール群: https://github.com/egosashimi/japan-arbitrage (Yahoo Auctions→eBay/Grailed)

**いくら払うか**(推測ではなく実在の課金事例):
- StartupHeist記事「Japan's Collectibles Arbitrage Gap ($28K MRR)」: 越境アービトラージスキャナーの収益モデルとして **100人の本気リセラー×約$72/月≈$7.2K MRR、200-300垢で$16-28K MRR**、**4段階価格(free→$249/月ストア)** を提示。実経営者数値を論じる一次分析 — https://www.startupheist.com/japans-collectibles-arbitrage-gap-28k-mrr/
- 同記事が既存カテゴリとして **Tactical Arbitrage / SellerAmp / Keepa**(Amazonセラー向け商品リサーチ)を挙げ、そのサブスク定価$30-100/月相当が相場観の基準。
- 2025-08-29米de minimis関税発令(EO 14324)+2026-02-28のad valorem一本化で、**landed cost計算込みのツール価値が上昇**。Buyee代理手数料も2026-04に¥500/件へ値上げ + DDP関税込み化。→ 割安基軸の需要が「正味利ザヤ計算」軸へ移行中(出典: 同StartupHeist記事内)。

**どう訴求すれば刺さるか**:
- 「eBay/米相場との差分」「sold price / comps」
- 「¥入り価格」+ コンディション + 出品者実績(低取引=真の割安が多い、OtakuAlpha実測)
- 高速性(割安出品は2-6時間で売れるため、週次データはボトルネック→リアルタイムAPI/アラートが本命)
- 出典: AIボット自作記事 OtakuAlpha「I Built an AI Bot to Hunt Underpriced Japanese Collectibles」 — 出品後2-6時間で高値アノマリー購入、低取引出品者ほど割安、1日1回のモニタはほぼ無意味 / 2xマージン以上のみアラート — https://ai-global-insight.beehiiv.com/p/i-built-an-ai-bot-to-hunt-underpriced-japanese-collectibles-here-s-what-i-learned

---

## (e) 価格追跡ツール開発者・SaaS ー 高優先

**何を買っているか**: API/スクレイパー/ダウンロード可能なCSV。収集システムを自作せず、二次利用可能なデータ or 開発者向けエンドポイント。

**どこで探しているか**: Apify Store、RapidAPI、GitHub。

**いくら払うか**(実例):
- PriceCharting(ゲーム/カード価格ガイド)は公式API+CSV販売。Apify上で非公式スクレイパーが複数稼働。公式API docs — https://www.pricecharting.com/api-documentation(Cloudflareで本文取得不可だがAPI存在確認)、RapidAPI版 — https://rapidapi.com/apidock-apidock-default/api/pricecharting-api
- Apify標準日本データ相場 $4/1,000件 (= $0.002/件)。Mercari系アクターも同帯($3.99/1,000)。 — https://apify.com/devanshlive/mercari-japan-scraper
- OKX.AI「Secondhand Market Price Comparisons」エンドポイント **0.05 USDT/コール**(メディアン・パーセンタイル・サンプル出品を返す) — https://www.okx.ai/tasks/410269(本文に+ 自己文書化 https://api.ballpark.to/docs)
- RapidAPI手数料20%が既存相場。

**どう訴求**: スキーマ/ドキュメント整備、項目網羅性(itemId/JPY/条件/出品者)を明示し「自前スクレイパー不要」と訴求。API or一括CSVの二形態。Mercari系スクレイパーはApifyに複数あるため差別化必要(後述の競合リスク)。

---

## (d) 市場調査・アナリスト ー 低優先(商品化の再考が必要)

**何を買っているか**: 包括的な市場レポート(GMV/市場規模/予測/CAGR)、生のスクレイプデータではない。

**いくら払うか**: ResearchAndMarkets「Japan Recommerce Market Databook」(60+KPIs)クラスは **$2,000+程度の法人向けレポート**(価格は本文に未記載、購入導線あり)。Statista/Yano Researchも法人サブスク。出典: https://www.researchandmarkets.com/reports/6099567/japan-recommerce-market-intelligence-databook 、 https://www.yanoresearch.com/market_reports/C68102300

**適用不可の理由**: 買い手は「既に集計された市場見通し」を払う。生データセットを個人消費者から買うのはこのセグメントではない。→ 集計した「相場指数/トレンドレポート」に成形すれば別商品になり得るが、スコープ/予測が必要で個人向きでない。

---

## (b) アカデミックリサーチャー ー 低優先

**何を買っているか**: ほぼ無料。Kaggle/HuggingFace/Google Dataset Searchで取得。Mercari Price Suggestion Challenge(2018,Kaggle)が学術/ML利用の歴史的一例 — https://www.kaggle.com/c/mercari-price-suggestion-challenge
- 研究者は「骨格データは無料で手に入る」文化。$29.99の販売データを買う研究予算はほぼ無い。(推測: 大規模・研究用ライセンスなら別だが、個人データ販売では成立しない)。

**適用不可の理由**: 支払い意志ほぼ$0。Kaggle/HFで無料公開済みの競合が需要を満たす。

---

## (a) AI/LLM学習データ需要者 ー 低優先

**何を買っているか**: LLM用学習データは「無償大規模Webスクレイプ/C4等」か、契約済み「コンプライアントなWebデータ」をエンタープライズがB2Bで買う。個人の$29.99データセット購入はほぼ無い。出典: https://github.com/mlabonne/llm-datasets 、 Actowizがeコマース商品リストをLLMファインチューニング向けB2B提供 — https://www.actowizsolutions.com/custom-datasets-llm-fine-tuning-structured-web-data.php 、コンプライアンス論 — https://plainenglish.io/web-scraping/the-permission-economy-how-to-get-compliant-web-data-for-llm-training-without-lawsuits

**適用不可の理由**: 売り先は個人大手(Labs/SaaS/研究機関)で契約額も桁違い。$29.99圏の商売ではない。ただし「無料サンプル公開→上位版販売」の集客導線には使える。

---

## 競合・実在性の要約
- **メルカリデータで稼いでいる実在者あり**: Apify系アクター多数(複数の売上/ユーザー有)、Bright Data販売、ScraperScoop、OKX/ballparkエンドポイント($0.05/call)、OtakuAlpha(無料EA)、StartupHeistが$28K MRRツールを論じる。→ 「Japanese secondhand / Mercari price data」への実在需要は**確定**。
- **競合はレッドオーシャン**: 過去調査(feasibility-research)でApifyにMercari系は177ユーザー規模の有力者 + 複数参入済み。→ 単なるMercari全量データでは価格競争に巻き込まれる。

---

## 当プロジェクトへの適用可否と結論
1. **現行Gumroad $29.99静的データセット単体は売れない**。買い手が欲しいのは「sold comps + 差分 + 正味利ザヤ」であって、週次の静的CSVでは週1更新の低速が致命傷(割安アノマリーは2-6hで消える)。
2. **転売セグメントへ訴求し直すのが唯一の現実的経路**: 商品を「日本中古ホビーの相場リスト+差分情報」としてeBay/Grailed/Depop転売者向けに再位置付け。訴求ワードは sold price, comps, ¥→$, landed cost。
3. **配信形態を「静的CSV→API/定期更新」へ**: Apifyアクター or RapidAPI(20%) or waitlist/メルマガでのアラート更新。月額$9-30が転売者相場。週次CSVは「足元の値下がり/Update通知」付きに。
4. **集計型への寄り**: raw data 再販の法的リスク(feasibility-research記録: 大企業+営利禁止TOS、LY系/メルカリ系は再販に慎重)を避けるべく「相場指数・統計」へ加工した派生データに寄せるのが安全域。メルカリはTOSで自動収集・再配布禁止の可能性が高く、個別checkが必要。

## 非推奨(優先度下げるべき)
- アカデミック/AI学習データ/LI出す正式市場レポート向け: 当面見送り。

## 残課題
- Mercari TOSの原文確認(再販可否)― メルカリ利用規約で自動データ収集/二次配布の明記を精読。
- 競合Mercariアクターの実際のユーザー数/u30d再計測(Apify Store API)。
- 転売コミュニティ(Reddit r/Flipping, note転売ガイド)での実声インタビュー。
- Gumroadからの集客はDiscover依りで限定的→Apify/RapidAPI/Bright Data等の需要ある場所に商品を置く。
