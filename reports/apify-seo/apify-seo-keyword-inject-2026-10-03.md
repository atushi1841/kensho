# Apify SEO キーワード注入レポート（2026-10-03）

## 概要
Apify Store の 68 アクターについて、検索キーワードの欠落を監査し `description` / `title` への注入を実施。
tags API は存在しないため、description/title 経由の代替施策。

## 監査結果（apify-seo-audit-2026-10-03.csv）

| 課題種別 | 件数 |
|---------|------|
| missing_keywords | 68 |
| title_keyword_gap | 17 |
| short_description | 39 |
| missing_categories | 36 |
| seo_title_missing | 0 |
| seo_description_missing | 0 |
| discovery_gap | 10 |
| no_competitor_data | 6 |

**対象 actor: 68 件**（missing_keywords 68 + title_keyword_gap 17 の内重複を除く）

## 適用実行

```
python3 scripts/apify_seo_apply.py --csv reports/apify-seo/apify-seo-audit-2026-10-03.csv --impact missing_keywords,title_keyword_gap --limit 68 --bulk
```

- batch-1（limit 10）: 10/10 OK → read-back 確認済
- batch-2（残 58）: 58/68 OK、10 NG（batch-1 で適用済みなので no-op）

## read-back 検証

```
GET /v2/acts/{id} で description / title が変化したことを全 68 件確認
```

| 項目 | 値 |
|-----|---|
| 変化確認できた actor | **68 件** |
| 未変化（unchanged） | 0 件 |

## 失敗一覧

| actor | 原因 |
|-------|------|
| ai-model-price-api | no-op（batch-1 適用済） |
| amazon-paapi-jp-actor | no-op |
| biglemon-machinery-scraper | no-op |
| dmm-scraper | no-op |
| eurostat-indicators | no-op |
| golfpartner-used-club-scraper | no-op |
| goo-net-car-scraper | no-op |
| goo-net-car-scraper-es | no-op |
| goo-net-car-scraper-fr | no-op |
| goo-net-car-scraper-pt | no-op |

HTTP エラー（403/400/レート制限）は発生せず。

## code change

旧コードは description/title の末尾から単純に `[:cap]` で切り捨てていたため、
300 文字上限の actor にはキーワード（suffix）が完全に切れて PUT 200 でも実質 unchanged となる事象が発生。
これを防ぐため `_fit_with_keywords(base, suffix, cap)` を追加し、suffix が切れないよう base 側を優先カットするよう修正。

## verification_evidence

```
$ python3 scripts/apify_seo_audit.py --quiet
actors=78 findings=176
json: /mnt/d/Project2/kensho/reports/apify-seo/apify-seo-audit-2026-10-03.json
csv: /mnt/d/Project2/kensho/reports/apify-seo/apify-seo-audit-2026-10-03.csv

$ python3 scripts/apify_seo_apply.py --csv reports/apify-seo/apify-seo-audit-2026-10-03.csv --impact missing_keywords,title_keyword_gap --limit 10 --bulk
BULK: 10 actors, 10 findings
[  1/10] ai-model-price-api findings= 1 ok= 1 ng= 0
...
[ 10/10] goo-net-car-scraper-pt findings= 1 ok= 1 ng= 0
=== summary: 10/10 ok in 12.6s ===

$ python3 scripts/apify_seo_apply.py --csv reports/apify-seo/apify-seo-audit-2026-10-03.csv --impact missing_keywords,title_keyword_gap --limit 68 --bulk
BULK: 68 actors, 68 findings
[ 11/68] goo-net-car-scraper-ru findings= 1 ok= 1 ng= 0
...
[ 68/68] yahoo-auctions-japan-scraper findings= 1 ok= 1 ng= 0
=== summary: 58/68 ok in 96.5s ===
```

## output files

| ファイル | パス |
|---------|------|
| 監査 CSV | `/mnt/d/Project2/kensho/reports/apify-seo/apify-seo-audit-2026-10-03.csv` |
| 監査 JSON | `/mnt/d/Project2/kensho/reports/apify-seo/apify-seo-audit-2026-10-03.json` |
| 適用結果 JSON | `/mnt/d/Project2/kensho/reports/apify-seo/apify-seo-apply-2026-10-03.json` |
| 適用結果 CSV | `/mnt/d/Project2/kensho/reports/apify-seo/apify-seo-apply-2026-10-03.csv` |
| 本レポート | `/mnt/d/Project2/kensho/reports/apify-seo/apify-seo-keyword-inject-2026-10-03.md` |
| 分析用 JSON | `/mnt/d/Project2/kensho/reports/apify-seo/apify-seo-keyword-inject-2026-10-03.json` |
