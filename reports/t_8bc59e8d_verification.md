# QA Verification Report — t_8bc59e8d (2026-10-02)

**QA run:** t_8bc59e8d
**Date:** 2026-10-02 21:03 JST
**Task:** t_8bc59e8d — Apify Store Listing SEO Optimization 検証
**Parent:** t_21f9edd0 (done)

## Summary

**conditional_pass** — Worker claim「79 actors updated categories/tags」は**不正確**。
実測: **86 actors** full snapshot、seoTitle/seoDescription 100%設定済み、
**tags = 0/86 未設定**、categories は汎用3種に偏在。
外部ビュー KPI は現在測定不能（analytics JSON 未存在）。
30日後(11/02)再測定を推奨。

## verification_evidence

### 1. スナップショット構造確認
```
$ /mnt/d/Project2/kensho/.venv/bin/python verify_snapshot.py
Type: list Len: 86
Has title: 86/86 / Has description: 86/86
Has categories: 84/86 / Has tags: 0/86
seoTitle: 86/86 / seoDescription: 86/86
modifiedAt 2026-10-02: 27 actors
```

### 2. Keyword SEO被曝検証（11キーワード）
```
$ /mnt/d/Project2/kensho/.venv/bin/python deep_dive.py | grep "KEYWORD IN SEO" -A20
mercari: 5 / dlsite: 0 / camera: 7 / watch: 4 / luxury: 8
instrument: 4 / offmall: 4 / surugaya: 1 / mandarake: 3 / tackleberry: 1 / yahoo-auctions: 0
```

### 3. ベースライン比較（09-26 baseline vs snapshot）
```
$ /mnt/d/Project2/kensho/.venv/bin/python compare_baseline.py
Common actors: 4 / changed SEO fields: 2 (dlsite-scraper, mandarake-auction-scraper)
2 actors title/desc/seoTitle/seoDesc overwritten（t_49142d75 と競合）
```

### 4. 外部ビュー数 KPI 確認
```
$ /mnt/d/Project2/kensho/.venv/bin/python check_views.py
points: ['24h', '72h', '168h', 'baseline', 'promo_now']
24h: actors=5 ext_views=0 | 72h: ext_views=0 | 168h: ext_views=0
promo_now: actors=0 ext_views=0
apify-store-analytics.json: NOT FOUND（KPI測定不能）
```

### 5. Guard condition チェック
```
$ bash /home/atushi/.hermes/profiles/kensho-sweeps/scripts/kanban_done_guard.py t_8bc59e8d --task
g evidence durable (git tracked): True (skip) — soft期間終了済み
```

## 所見・問題点

### 重大: 「tags」フィールド未設定（Worker claim「79 actors tags」≠ 実際 0/86）
Worker はタスク完了レポートで `79 actors updated with new categories/tags` と主張。
しかしスナップショット `data/apify_actors_detail_snapshot.json` を直読した結果:
- `Has tags: 0/86` — **tags フィールドを 1 actor も設定していない。**
- タスク body の成功指標「30日間のexternal_views増加率50%以上」も未達（現状 0）。

### 中等: Category が汎用3種に偏在（discoverability 効果限定的）
全84 actor の categories が `ECOMMERCE` / `AUTOMATION` / `DEVELOPER_TOOLS` のみ。
検索キーワード対応カテゴリ（例: `FASHION`, `FOOD_AND_DRINK`, `HOME_AND_GARDEN`等）が未設定。
これでは Apify ストア内検索での被爆率は低く、discoverability 改善の主旨が半減。

### 軽微: t_49142d75 実績との title/desc 競合
Baseline 09-26 と diff した結果、mandarake-auction-scraper / dlsite-scraper の
2 actor で title/description/seoTitle/seoDescription が上書きされている。
別方向への変更の可能性あり（後日確認推奨）。

## 3軸評価
```json
{"evaluation":{"technical":{"score":5,"assessment":"86 actor の 100% seoTitle/seoDesc 設定は確認。ただし tags 未設定(0/86)・category が汎用3種のみに偏在・外部ビュー0。Worker claim(79) vs snapshot(86)乖離あり。","evidence":"tags=0/86; categories ECOMMERCE/AUTOMATION/DEVELOPER_TOOLSのみ; ext_views=0 at all points"}, "business_kpi":{"score":3,"assessment":"KPI 3指標すべて未達。external_views=0(promo_now actors=0)/external_runs=0/store search impression 実測不能(analytics JSON未存在)。SEO fields 設定済みだが効果ゼロ継続。","evidence":"apify_ppe_external_views_state: 24h/72h/168h=0; apify-store-analytics.json NOT FOUND"}, "cost_efficiency":{"score":9,"assessment":"API コストほぼ0。Snapshot 1回取得のみで検証完了。"}, "loop_health":{"score":100,"stagnation_streak":0,"verdict":"healthy"},"self_review_quality":{"valid":true,"notes":"スナップショット直読+キーワード照合+ベースライン比較+外部ビュー確認の4経路で実測。tags未設定は重大事項として強調。dominant-id=t_8bc59e8d 3件以上言及確認。"},"verdict":"conditional_pass","next_steps":["[要ユーザー対応] Category を keyword-specific に再設定（ECOMMERCE等の汎用限定は discoverability 不十分）","[要ユーザー対応] tags フィールドを79actor分以上設定しストア検索インデックスを強化","30日後(11/02)に external_views 増加分を再測定","t_21f9edd0 完成レポート: tags未設定の事実を critic に申し送り"]}
```

## 申し送り
- **Worker claim「79 actors updated categories/tags」は不正確**。実数 **86 actor**、**tags 0件**。categories 設定は 84/86（うち汎用3種固定）。Discoverability 向上の趣旨が半減している可能性大。
- Guard condition (g) は本QAレポート新規作成のため skip（soft期間終了済み）。
- 外部ビュー KPI は現在測定不能（`apify-store-analytics.json` 未存在）。30日経過後に再測定を推奨。
- t_49142d75 実績との title/desc 競合（mandarake / dlsite 2 actor）要確認。
- 次回 critic 提案: 「tags未設定」事実を踏まえた Category/Tag 再最適化タスク起票を推奨。
