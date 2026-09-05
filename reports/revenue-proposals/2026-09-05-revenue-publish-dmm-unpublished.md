# revenue-worker: dmm-scraper + 未公開残り publish 実行 (2026-09-05)

## タスク
t_fc326d38 — 9/4 daily limit 解消後、優先順位で (1) dmm-scraper publish、(2) 残り rakuten/未公開 actors を publish。

## 実施前の状態（API実測）
- **dmm-scraper** (nUm22B2guMo8vXom6): 既に public 化されていたが **pricingInfos 空 = 無料公開のまま**（有料設定が漏れていた）。build 0.1.8 SUCCEEDED 確認済み。
- **japan-figure-plamo-resale-price-stats** (WnrudUFF2kZxZcj7Z): 非公開。build 0.1.1 **FAILED**（`.actor/INPUT_SCHEMA.json` がソースに無い）、かつ main.py はスタブ（httpx未import・偽のソース呼び出し）。
- **rakuten-market-scraper** (pZ20lXqRtsJUl9bGk): 非公開。build 0.1.2 SUCCEEDED。

## 実施内容
1. **dmm-scraper**: pricingInfos を PAY_PER_EVENT $0.00005 start + $0.002/件、margin 0.2 で設定 → **有料アクター化**（公開状態は維持）。
2. **rakuten-market-scraper**: 同価格設定 → **公開**（categories=[ECOMMERCE]）。
3. **japan-figure-plamo-resale-price-stats**:
   - ソース修正（build FAILED の原因解消）: `.actor/INPUT_SCHEMA.json` 追加、`README.md` 追加、actor.json outputSchema の文言修正。
   - main.py を公開済み兄弟アクター japan-camera-resale-price-stats の実績コードに基づき修正（Yahoo Auctions + Mandarake を内部APIで呼び、価格統計に集約。httpx import、サブアクター実行・正常系リトライ・部分失敗耐性を実装）。
   - **build 0.1.2 SUCCEEDED** → テストラン実行: **実データ5件取得**（Gundam: ¥2,781〜¥11,000, avg ¥7,256, median ¥6,500）。
   - pricingInfos 設定 + SEO（seoTitle/seoDescription）+ exampleRunInput → **公開**。

## 検証結果（API実測）
| actor | isPublic | model | price/件 | users | u30d | runs |
|-------|----------|-------|---------|------|------|------|
| dmm-scraper | True | PAY_PER_EVENT | 0.002 | 2 | 1 | 8 |
| rakuten-market-scraper | True | PAY_PER_EVENT | 0.002 | 2 | 1 | 3 |
| japan-figure-plamo-resale-price-stats | True | PAY_PER_EVENT | 0.002 | 2 | 1 | 2 |

- ポートフォリオ全体: **public 61 / paid(PPE) 60**（非公開3件は debug/test: mini-actor-test-0903, rakuten-debug-fetch, tabelog-debug-fetch — 意図的に非公開維持）。

## 申し送り（24-48h 後の discovery 効果測定）
タスク本体の「公開後 24-48h で discovery 効果を測定、u ユーザー数変化を revenue-daily.json で確認」は**9/6〜9/7 実施**のこと。
- 基準値（本レポート時点）: dmm(users=2,u30d=1), rakuten-market(users=2,u30d=1), figure-plamo(users=2,u30d=1)。
- 測定: `GET /v2/acts/{id}` の stats.totalUsers / totalUsers30Days を取得し、本基準値から増分を確認。
- 注意: 上記3アクターは revenue-daily.json の tracked 25ポートフォリオに含まれない。測定には個別API参照 or collect のポートフォリオ拡張が必要。
