# データセット販売 買い手セグメント & 売上ゼロ脱却 販促戦術 調査報告

調査日: 2026-09-06 | 対象: Gumroad「Japanese Hobby & Collectibles Market Price Dataset」$29.99(売上0)
調査手法: DuckDuckGo検索+一次ページ取得(4並列ワーカー)。成果物: 本文件 + `reports/buyer-segments-secondhand-price-data-2026-09.md` + `research_output_free_sample_paid_funnel.json` + `marketplace_research.json`

---

## ① 発見事項(出典付き)

### A. 買い手セグメント(実在性検証済み)

| セグメント | 実在性 | 支払額の実例 | 優先度 |
|---|---|---|---|
| リセラー/アービトラージャー(メルカリJP→eBay越境) | ★★★ 実証済み | $9-249/月(Tactical Arbitrage等$30-100/月が相場観) | **最優先** |
| 価格追跡ツール/SaaS開発者 | ★★★ 実証済み | Apify $4/1,000件、OKX.AI $0.05/コール | 高 |
| 市場調査・アナリスト | △ | $2,000+の完成レポート(生CSVは買わない) | 低 |
| アカデミック | △ | ほぼ$0(Kaggle/HF無料文化) | 低 |
| AI/LLM学習データ | △ | B2B企業契約のみ($29.99圏に買い手なし) | 低 |

**リセラー実在の証拠**:
- ApifyにMercari Japan系スクレイパーが複数出品され「resale research / flip on eBay」訴求で有料販売 — https://apify.com/datalab-jp/mercari-scraper
- Bright Data「Mercari Dataset」— https://brightdata.com/products/insights/price-tracker/mercari
- StartupHeist「Japan's Collectibles Arbitrage Gap」: 100人×$72/月≈$7.2K MRR試算、4段階価格(free→$249/月) — https://www.startupheist.com/japans-collectibles-arbitrage-gap-28k-mrr/
- OtakuAlpha実測: 割安出品は2-6時間で売れ、1日1回の監視はほぼ無意味 — https://ai-global-insight.beehiiv.com/p/i-built-an-ai-bot-to-hunt-underpriced-japanese-collectibles-here-s-what-i-learned
- 2025-08 米de minimis関税発令→landed cost(関税込み利ザヤ)計算の価値上昇(同StartupHeist記事)

### B. 無料サンプル+有料フル版 / Gumroadの実態

- Gumroad実測(146,271商品分析): **44%が売上$0**。$30-49帯は$10未満より28%良く転換。**メールが販売の約42%**(リスト転換率3.2% vs 広告1.9%) — https://insightraider.com/en/answers/what-is-gumroad-discover-and-does-it-cost-extra ほか
- 手数料: 直接10%+決済2.9%+$0.30(実効~13.2%)、**Discover経由は30%**(諸説あり: 20%とする分析も)で全販売の約12% — https://checkoutpage.com/blog/gumroad-fees
- 実在の無料サンプル+有料版モデル: 20データセット/5.3万レコードの各**30行を無料公開**、フル版をGumroadで$24-29・バンドル40-55%off — https://futdevpro.github.io/niche-datasets-free/
- CSVは透かし不可能→差別化は「行サブセット・カラム削減・鮮度(更新は有料限定)」で行う
- **Kaggleは不適**: dataset-metadata.jsonでライセンス(CC0等)必須+無料再配布構造→有料版の排他性が消える。Kaggle→Gumroadファネルの成功事例は複数クエリで確認できず(確証なし) — https://github.com/Kaggle/kaggle-cli/wiki/Dataset-Metadata
- **HF Gated Datasetは適**: ダウンロード条件でユーザー名+メール共有を強制可(auto/manual承認、カスタム項目、API可)→公式のメール獲得装置 — https://huggingface.co/docs/hub/datasets-gated
- 法務: hiQ v. LinkedIn(9th Cir. 2022)で公開データスクレイプはCFAA違反にならない蓋然性高いが、各サイトToS上の契約リスクは残る — https://www.eff.org/deeplinks/2022/04/scraping-public-websites-still-isnt-crime-court-appeals-declares

### C. データマーケットプレイス(個人が出品できるか)

| プラットフォーム | 個人出品 | 手数料 | 判定 |
|---|---|---|---|
| **Apify Store** | 可(誰でも) | 開発者80%−利用コスト(PPE) | **最有力**。同ニッチ(駿河屋/Mandarake価格データ)の有料商品が実在 — https://apify.com/datalab-jp/suruga-ya-scraper, https://apify.com/jpmarketdata/mandarake-market-checker/api/cli |
| **RapidAPI** | 可(セルフサービス) | 20%、PayPalのみ | 第2候補(要ホストAPI) — https://docs.rapidapi.com/v2.0/docs/payouts-and-finance |
| AWS Data Exchange | 登録は個人可だが出品にオンボーディング承認+W-8+SWIFT口座 | 3%+S3等 | 見送り(B2B・成約遅) — https://docs.aws.amazon.com/marketplace/latest/userguide/user-guide-for-sellers.html |
| Datarade | 実質法人前提(年額サブスク+手数料30%、紹介型で取引なし) | 30% | 見送り — https://pipeline.zoominfo.com/sales/datarade-pricing |
| Databricks/Snowflake/data.world | 法人プログラム前提 | — | 見送り |
| Lemon Squeezy / itch.io / Payhip | 可 | 5%+$0.50 / 10% / 5% | 手数料はGumroadより軽いが発見可能性は解決しない — https://www.lemonsqueezy.com/gumroad-alternative |
| BASE/BOOTH | 可 | 6.6%+40円 / 5.5% | 日本語圏向けで英語圏顧客に届かない |

### D. 販促チャネルの費用対効果順(ゼロフォロワー)

1. **Reddit**(最有力・無料): ただし新規垢はスパムサンドボックス(dev.to実録「5投稿全部弾かれた」)— https://dev.to/sessionzero_ai/i-posted-on-reddit-5-times-in-march-not-one-made-it-through-4efc 。2-4週のカルマ/垢齢育成が前提。r/Entrepreneur等は週次プロモスレッドのみ許可 — https://threadcite.live/reddit-communities/entrepreneur
2. **ロングテールSEO**(Gumroadページ+自前ページ): 効果まで1-3ヶ月だが$0で複利
3. **Show HN**: データセット単体告知は1-6点で沈む典型。「ツール+ストーリー」型なら一度試す価値
4. **Build in public(X/Indie Hackers)**: 3-4ヶ月忍耐前提
5. **Gumroad Discover**: 設定のみ・追加手数料30%(20%説あり)・期待値低め
6. **Product Hunt**: ゼロフォロワー実測例「1 upvote、#333位」— https://www.indiehackers.com/post/i-launched-on-product-hunt-with-zero-audience-1-upvote-333-heres-everything-i-learned-as-a-complete-beginner-2a05a30acf → **今は見送り**
7. Hacker Newsletter: 有料広告のみ→予算$0の対象外

---

## ② 当プロジェクトへの適用可否

1. **現商品(週次静的CSV $29.99)のままでは売れない(確度高い)**。買い手の中心は転売者で、欲しいのは「sold comps+eBay差分+landed cost利ザヤ」であり、割安出品は2-6hで消えるため週次更新では需要を満たせない。Gumroadは自前トラフィック前提(44%の商品が$0)で、ページ整備済みでも流入がゼロがボトルネック。
2. **訴求の再定位は有効**: 同じデータを「eBay/Grailed/Depop転売者向け sold comps・相場ツール」として再位置付けする経路だけが実在需要と接続する。$29.99価格は$30-49帯が最も転換するという実測と整合。
3. **無料サンプル(メールゲート)+有料フル版**: 最も再現性のあるGumroad内ファネル(メール=販売の42%)。HF Gated Dataset併用は適合。**Kaggleへのフル版サンプル掲載は不適合**(ライセンス必須で排他性消失)。
4. **Apify Store出品が最適合**: 個人可・80%取り分・同ニッチの有料データ商品が既に売れている・既存Apifyスキル資産あり。RapidAPIは第2候補。Datarade/AWS Data Exchange等B2Bは今回は見送り(法人前提・審査負担・$29.99圏の買い手がいない)。
5. **販促はReddit(カルマ育成)+ロングテールSEO先行**。Product Hunt/派手なローンチは現フォロワー数では期待値ほぼゼロ。

## ③ 具体的な実装ステップ(優先順)

1. **商品の再定位(今週)**: Gumroadページを転売者向け文言に書き直す(sold comps / eBay price gap / landed cost / ¥→$ 計算)。カテゴリ別の週次相場サマリーPDFを商品に付ける。
2. **無料サンプル商品を新規作成($0)**: カテゴリ横断30-100行+1週間分の代表サブセット。出品者ID/URLは削除かハッシュ化、updated_atは過去値固定、「週次更新は有料版のみ」を明記。ダウンロードでメール取得(Gumroad顧客リスト)。
3. **有料版を再構成**: 全件+全カラム+週次更新+更新通知。Gumroadのファイル更新機能で既存購入者へ自動再配信。上位ティア(全カテゴリ+アーカイブ版$49-79)を追加。
4. **HF Gated Datasetでサンプル公開**(auto-approve+利用目的のカスタム項目、license: other+独自規約、カードにGumroadリンク)。Kaggleには置かない(ブランド露出のみに限定)。
5. **Apify Actor化(2-4週)**: 既存データをペイパーイベント型Actor(例$1-3/クエリ or $0.002-0.005/結果)としてStore公開。日本ニッチデータの有料事例が実在する最有力チャネル。RapidAPIを第2候補にAPI横展き。
6. **Redditカルマ育成(2-4週)**: r/AnimeFigures, r/gamecollecting, r/Flipping等で価値提供投稿を積む→育った垢で無料サンプル(広告なしの価値投稿)+プロフィール経由導線。r/DataSetsは規約確認後に再挑戦。
7. **週次ニュースレター開始**: $0ダウンロード層に「今週の高騰アイテム」等の実利用例を送り有料版へ誘導(メール=販売の42%)。
8. **KPI計測(月次)**: $0 DL数、$0→有料転換率、チャネル別売上。1ヶ月でメール30件未満ならサンプル/掲載先をA/B改善。2-3ヶ月でゼロのままならApify中心へ比重移管。
9. **法務維持**: 個人情報・出品者特定情報を含めない集計/匿名化設計を守る。メルカリ等のToS再確認(自動収集・再配布条項の精読)。
10. **見送りリスト**: Product Hunt(数ヶ月後再評価)、Datarade/AWS Data Exchange(Databricks/Snowflake/data.world)(データがB2Bサブスクに育ったら再評価)、有料広告全般。
