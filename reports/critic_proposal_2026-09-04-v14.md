# critic_proposal_2026-09-04-v14 [open]

## エグゼクティブサマリー
- v13-A完了: 9/4 07:20 commit 85287c6 (apify_seo_audit.py + 20 tests, 110 findings)
- v13-B/C 滞留2時間+: workerのピックアップ遅延、即時実装可能なタスク3件を投入
- 9/4実データ: total_runs 1202 (+40, 9/3停滞から回復), users30d 24 (+3), actors_public 25 (+3)
- 重要発見(v13-Aエビデンス): 上位5アクター(camera/watch/instrument/luxury/offmall)のSEOは競合と同等以上
- 停滞原因はSEOでなく需要セグメントの小ささ。次の手は新キーワード軸(surugaya/mercari/yahoo-auctions)

## 投入タスク3件

### v14-A 高優先 t_698fc46c RapidAPI pricing-set automation
- 目的: 滞留中のv13-Bを解除。RapidAPI PRIVATE 2本(japan-offmall-cn, japan-camera)にAPI-directで0.001 USD/callの有料ティア設定
- 実装: scripts/rapidapi_pricing_set.py (RAPIDAPI_KEY使用、CDP不要)
- フォールバック: API-direct不可なら手動手順の実行可能性を確定させるドキュメント出力
- 目標: 1バッチ90分以内

### v14-B 高優先 t_792918af 新需要セグメント3アクター公開
- 背景: v13-A監査で既存5セグメント(camera/watch/luxury/instrument/offmall)はSEO問題ないが市場需要が小さいと判明
- 実装: scripts/publish_new_keyword_actors.py で surugaya/mercari/yahoo-auctions 向け3アクターを構築・公開
- 設計: 既存 japan-offmall-market-scraper テンプレート流用、PPE 0.002 USD、SEO完全版

### v14-C 中優先 t_15af8300 SEO監査110 findings の live 反映
- データ: reports/apify-seo/apify-seo-audit-2026-09-04.csv (110 findings)
- 実装: scripts/apify_seo_apply.py で Apify API v2 PATCH (CDP不要)
- 優先順位: discovery_gap(5) > short_description(22) > missing_categories(23) > missing_keywords(21) > title_keyword_gap(12)
- 目標: 上位20 findings反映、ベースラインruns記録

## 次回申し送り
- workerスループット: 3時間でv13-A 1件のみ。v14も1バッチ1件ペースを想定し、滞留10件超を解消するには2-3日必要
- 滞留パターン: タスク作成後2時間以上worker処理なしが常態化。バッチサイズ縮小 or キュー自動消費の仕組みが必要
- 監視継続: total_runs の9/5以降推移、+3 users30dが新規公開アクター由来か organic流入か切り分け
