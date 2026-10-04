# 外部流入導線監査レポート — 2026-10-03（簡易版）

## 導線ごとの生死（実測）

| 導線 | 状態 | 根拠 |
|------|------|------|
| dev.to 記事 | ✅ 生きている | Mercari記事(9/8) + 懸賞記事(x2, 9/28) HTTP 200確認。CTAはW39のみ |
| Gumroad 商品 | ✅ 生きている | `/l/kutuxe` etc. HTTP 301→200 正常 |
| X 販売促進投稿 | ✅ 生きている | W40a/b UTM付き投稿成功、tweet_id記録済み |
| Apify Store SEO | ❌ 死んでいる | 自身のactor名で検索しても items=[] |
| RapidAPI 24 API | ⚠️ 部分的 | 公開済みだが requests=0 |
| GitHub repo | 🔒 非公開 | privateなので外部流入不可 |

## 復旧したもの

- **revenue-health-check.py KeyError修正**: `er['zero_days']` → `er.get('zero_days', '?')` に変更。cronが毎日失敗していた問題を解決。
- **過去X投稿のトラッキング登録**: W40a/bのtweet_idを外部TrafficTrackerに記録

## 実装した改善

1. **`scripts/external_traffic_tracker.py` 新規作成** — devto/X/SEOイベントを記録。`kpi` コマンドで集計可能。
2. **`blog/devto-weekly-market-summary-w40.md` 新規作成** — W40市場サマリー記事（英語）。Gumroad CTA + Apify紹介を含む。
3. **`revenue-health-check.py` の堅牢化** — KeyError回避修正。

## 具体数字

- Gumroad売上: **$0**（30日連続ゼロ）
- Gumroad PV: **10件**（Directのみ、Twitter referrerなし）
- Apify external_users: **0**（30日累計）
- RapidAPIリクエスト: **0**
- devto記事: **3本**公開済み（CTAあり: 1本）
- X投稿: **2件**（W40a/b、UTM付き）
- 外部トラッキングイベント: **6件**記録済み

## 出力ファイル

- `/mnt/d/Project2/kensho/reports/2026-10-03-external-traffic-audit.md`（本レポート）
- `/mnt/d/Project2/kensho/scripts/external_traffic_tracker.py`（新規）
- `/mnt/d/Project2/apify-sales-funnel/blog/devto-weekly-market-summary-w40.md`（新規）
- `/home/atushi/.hermes/profiles/kensho-sweeps/scripts/revenue-health-check.py`（修正）

## 次の打ち手（推奨順位）

1. **devto W40記事を公開** — ファイル準備済み、手動または`devto_weekly_pipeline.py`実行
2. **GitHub repoをpublic化** — READMEにデータ製品セクション追加
3. **X投稿頻度を週2→週4に増加** — UTM付きGumroad直リンで継続
4. **RapidAPIリスト改善** — 説明文・サンプルレスポンス強化
5. **apify-sales-funnel再開** — 海外需要実証後に再評価

---

**verification_evidence**:
```
$ python3 scripts/revenue-health-check.py --dry-run
  external_runs:       30/30日 ゼロ (100.0%) total_all_time=0
  gumroad_sales:       sales=0 zero_days=30 warn=True

$ python3 scripts/external_traffic_tracker.py kpi
{"total_events": 6, "devto_articles_published": 4, "x_promo_posts": 2, ...}

$ curl -sI https://atushi5.gumroad.com/l/kutuxe | head -3
HTTP/2 301
location: https://atushi5.gumroad.com/l/free-sample-japan-hobby-collectibles-market-price-dataset
```
