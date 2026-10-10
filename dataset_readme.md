# Japan Hobby Collectibles Prices (Sample)

日本フィギュア・ホビー・レトロゲームの価格相場サンプルデータセット。
LLM学習・価格分析・EC開発の参考データとして利用可能。

## データ概要
- ソース: MyFigureList 等
- レコード数: 655（sample）
- カラム: figure_id, source, source_url, name, series, character, manufacturer, category, release_date, scale, sculptor, height_cm, jan_code, image_url, offers, msrp_jpy, lowest_price_jpy, highest_price_jpy, in_stock_count, total_offers_count, fetched_at, confidence, sources_merged

## リアルタイム収集（Apify PPE アクター）
このデータセットの収集元は Apify で公開されている PPE (Pay-Per-Event) アクターです。
最新データを取得するには以下のアクターを実行してください:

- [surugaya-japan-hobby-prices](https://www.apify.com/store/actor/surugaya-japan-hobby-prices)
- [mandarake-auction-scraper](https://www.apify.com/store/actor/mandarake-auction-scraper)
- [mercari-japan-scraper](https://www.apify.com/store/actor/mercari-japan-scraper)
- [rakuten-japan-scraper](https://www.apify.com/store/actor/rakuten-japan-scraper)

Apify Store: https://apify.com/atushi1841

## ライセンス
CC-BY-4.0（ソース attribution 必須）
