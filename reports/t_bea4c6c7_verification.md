# QA Verification Report — t_bea4c6c7
## Apify PPE external_views 検証: 10/9 計測で mandarake-auction-scraper 等 external_views>0 確認

**Task ID:** t_bea4c6c7  
**Date:** 2026-09-29  
**Verifier:** kensho-revenue-qa  
**Parent Task:** t_ee861eb5 (Apify Store promo slot b 投稿完了, tweet_id=2104655287496114428)

---

## verification_evidence

### 1. 検証対象アクター（親タスク t_ee861eb5 で投稿された3件）

```bash
$ cd /mnt/d/Project2/kensho && cat data/apify_store_promo_state.json | python3 -c "
import json,sys
d=json.load(sys.stdin)
b=d['posted_weeks']['2026-W40']['b']
print('slot=b actors:', b['actors'])
print('tweet_id:', b['tweet_id'])
"
```
```
slot=b actors: ['mandarake-auction-scraper', 'dlsite-scraper', 'tackleberry-japan-fishing-tackle-scraper']
tweet_id: 2104655287496114428
```

### 2. 現在の external_views 状況（2026-09-29 実測）

```bash
$ cd /mnt/d/Project2/kensho && python3 scripts/check_promo_actors.py
```
```
owner: VMz6nlpHoGIjTeSXS
mandarake-auction-scraper: external_views=0, total_runs=4
dlsite-scraper: external_views=0, total_runs=4
tackleberry-japan-fishing-tackle-scraper: external_views=0, total_runs=27
```

### 3. 既存 PPE top5 アクターの external_views（参考：baseline 2026-09-04 から 168h 時点）

```bash
$ cd /mnt/d/Project2/kensho && python3 scripts/apify_ppe_external_views.py --point now
```
```
=== Apify PPE external_views 計測 ===
  ポイント: 168h  日付: 2026-09-11  baseline: 2026-09-04
  計測時刻: 2026-09-29T05:06:40
  japan-camera-market       ext_views=  0  runs= 122  u30d=1  bm=0  SEO✓
  japan-watch-market        ext_views=  0  runs= 113  u30d=1  bm=0  SEO✓
  japan-luxury-market       ext_views=  0  runs= 112  u30d=1  bm=0  SEO✓
  japan-instrument-market   ext_views=  0  runs= 113  u30d=1  bm=0  SEO✓
  japan-offmall-market      ext_views=  0  runs= 289  u30d=1  bm=0  SEO✓
  合計 external_views(proxy) = 0
```

### 4. git 状態確認

```bash
$ cd /mnt/d/Project2/kensho && git log --oneline -3
```
```
ac607ac docs(evidence): t_ee861eb5 Apify Store promo slot b real tweet_id 2104655287496114428 + external_views follow-up
c33d900 docs(evidence): t_28467ede Gumroad+Apify cross-promo verification
b10c56c docs(qa): t_4fdb5ae1 verification report — Apify Store promo cron + external_views KPI gate (conditional_pass)
```

---

## 判定: **verification_pending (10/9 待ち)**

### 理由
- 3 件すべてのアクターで **external_views = 0**（2026-09-29 時点）
- 成功指標: **10/9 までに external_views > 0 を確認**
- 今日(9/29)から10/9まで **10日間の猶予あり**
- Apify Store 経由の外部 flow は数日〜1週間で反映される傾向

### 次回検証予定
- **2026-10-09** に再度 `python3 scripts/check_promo_actors.py` を実行
- 3 アクター全件で `external_views > 0` になっていれば **pass**
- いずれかが 0 のままなら **fail** → 代替手順(CDP 投稿失敗時フォールバック: tweet_id 取得ロック強化 → 手動投稿で tweet_id 記録 → 翌週自動再挑戦)適用を検討

---

## 推奨アクション
1. **継続監視**: 既存の revenue-daily.json 収集フローに促進アクター3件の external_views 追跡を追加
2. **10/9 再検証**: 専用タスクまたは cron で自動計測・レポート生成
3. **失敗時**: 同一アクターで別スロット/別文言での再プロモーション検討