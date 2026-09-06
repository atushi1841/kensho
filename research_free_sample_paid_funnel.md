# 調査メモ(親エージェント用・JSON本体は別途)

## 調査対象
1. 無料サンプル+有料フル版の設計ベストプラクティス
2. Kaggle/HF無料掲載→Gumroad有料販売ファネルの実効性

## 主要ソース(全てweb_search CLIで取得・検証済)
- Gumroadトラフィック分析(Similarweb): https://roo.beehiiv.com/p/gumroad-traffic-2026-real-data
- Gumroad手数料: https://checkoutpage.com/blog/gumroad-fees
- InsightRaider Gumroad分析(146k商品): https://insightraider.com/en/answers/how-to-market-your-gumroad-products / .../can-you-set-your-own-prices-on-gumroad
- リードマグネットベンチマーク: https://www.digitalapplied.com/blog/lead-magnet-conversion-benchmarks-2026-b2b-data-reference
- 無料→有料の実践事例: https://solopreneurcode.substack.com/p/how-i-made-2600-with-free-products
- データセット無料サンプル+有料販売の実在例(30レコード/データセット、Gumroad販売): https://futdevpro.github.io/niche-datasets-free/
- Kaggle dataset-metadata.json(ライセンス必須): https://github.com/Kaggle/kaggle-cli/wiki/Dataset-Metadata/...
- Kaggleデータセット文化/ライセンス: https://labelyourdata.com/articles/machine-learning/kaggle-datasets
- HF Gated Dataset: https://huggingface.co/docs/hub/datasets-gated
- HFライセンスメタデータ: https://huggingface.co/docs/hub/repositories-licenses
- hiQ v. LinkedIn(CFAA): https://www.eff.org/deeplinks/2022/04/... / Morgan Lewis
- 同ニッチのApify有料データ商品: https://apify.com/datalab-jp/suruga-ya-scraper / https://apify.com/jpmarketdata/mandarake-market-checker/api/cli

## 核心的結論
- Kaggle→Gumroad直結ファネルの成功事例は公開情報では検証不可(≒機能の確証なし)
- 実用になるのは「無料=サンプルに限定、有料の価値=網羅性+更新」の形。Kaggleに無料フル版を置くと有料版の根拠を消す
- HF Gated Datasetは公式のメール獲得装置として機能する
- データセットの「透かし」はCSVには不適。行サブセット/カラム削除/鮮度の差で差別化
