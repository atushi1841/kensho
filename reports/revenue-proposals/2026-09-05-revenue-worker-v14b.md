# revenue-worker v14-B: New demand-side actors publish pipeline (t_792918af)

## タスク
- Kanban: `t_792918af` v14-B: New demand-side actors (surugaya/mercari/yahoo-auctions) publish pipeline
- 目的: v13-A SEO監査の結論（top5アクターはSEO競合水準だが停滞原因は既存キーワードセグメントの需要の小ささ）を受け、
  高需要の JP オークション/マーケットプレイスセグメント（駿河屋・メルカリ・ヤフオク）向けアクターを公開運用する。
- 要求: 各アクター PPE 0.002 USD / フルSEO（categories + seoTitle + seoDescription + 300字description）/ Store公開 / スクリーンショット証跡

## 実態確認（重要）: 3アクターは既に公開済み
調査の結果、3セグメントのアクターは既に Apify アカウント上に存在し Store 公開済み（いずれも実データを出す実績あり）であることを確認。
| セグメント | Actor ID | アクター名 | isPublic | 単価(実効) | Store URL |
|---|---|---|---|---|---|
| mercari JP転売 | whSePszWpMtfeLYBp | mercari-japan-search-scraper | ✅ | **$0.002** | https://apify.com/fruitful_quintessence/mercari-japan-search-scraper |
| yahoo-auctions JP | 8WBam4CPB72q9Rvsd | yahoo-auctions-japan-scraper | ✅ | **$0.002** | https://apify.com/fruitful_quintessence/yahoo-auctions-japan-scraper |
| surugaya 中古品 | F8Hl0a8Cx9bpJBrxR | surugaya-japan-hobby-prices | ✅ | **FREE**（要対応） | https://apify.com/fruitful_quintessence/surugaya-japan-hobby-prices |

## 実施内容
1. `scripts/publish_new_keyword_actors.py` を新規実装（v14-B の要求どおりの公開パイプライン）。
   - 3アクターの SEO（categories/seoTitle/seoDescription/description/title）・価格（$0.002/件）・公開（isPublic）を API で一元管理
   - デフォルト dry-run、`--apply` で本実行、`--actor` で単発対象
   - 冪等（現状が目標値と一致なら no-op）
   - 文字数ガード: title≤80 / seoTitle≤60 / seoDescription≤160 / description≤300 / categories≤3（Apify実測の制限値）
2. `tests/test_publish_new_keyword_actors.py` を新規作成（17 tests、全パス）
3. ライブ検証: mercari / yahoo は実効単価 $0.002＋フルSEO＋公開済みを確認。`--apply` が冪等に安全動作することを確認
4. Store ページのスクリーンショット3枚（mercari / yahoo / surugaya）を取得（evidence/）+ SSR でタイトル実在確認（HTTP 200）

## 検証エビデンス
- `python -m pytest tests/test_publish_new_keyword_actors.py -q` → 17 passed
- `ruff check tests/...` → All checks passed
- ライブ: `publish_new_keyword_actors.py --apply --actor mercari` / `--actor yahoo` → `public=True ppe=0.002 price_matches=True`（冪等）
- Store SSR: 3ページとも HTTP 200・タイトルマーカー実在（html_len ~425-450KB）
- mercari 実測テストラン（2026-09-05）: useApifyProxy:false 構成で SUCCEEDED・リアルデータ（Nikon F3, ￥34,800等）取得。yahoo も直近 runs が HAS_DATA で SUCCEEDED。

## 判断: surugaya 価格は $0.002 に設定せず（安全ガード）
- surugaya は **Japan-IP 限定 + Cloudflare** のサイトで、無料プランの Apify 環境では**データ 0 件**（実測・複数回確認）。
  実行は SUCCEEDED するがデータセット空。有料プランの JP 国指定プロキシ前提（apify-actor-deployment スキルに詳細記録済み）。
- 0件アクターを有料 $0.002 で公開する =「壊れた有料アクター」を売ることになり、Store の評価（無料ユーザーの悪いレビュー）を損ねるため、**デフォルトで価格設定をスキップ**する安全ガードを導入。
- surugaya は公開（無料）のまま Store 上に「live」。機能が回復したら `--force-price-surugaya` で $0.002 適用。

## 残課題 / 申し送り
- **surugaya $0.002 化は保留（要ユーザー判断）**: 有料Apifyプラン（JPプロキシ）を契約しデータが取れるようになったら
  `python3 scripts/publish_new_keyword_actors.py --apply --force-price-surugaya` で適用。
- mercari の直近 FAILED（country-JP プロキシ起因・有料プラン必須）は外部ランチャー由来。INPUT_SCHEMA prefill は `useApifyProxy:false` のため Store/QA 実行はDC直IPで正常。
- **git push 認証切れ**（既知問題）: ローカルコミット予定。pushはユーザー対応が必要。

## 出力ファイル
- `scripts/publish_new_keyword_actors.py`（本体）
- `tests/test_publish_new_keyword_actors.py`（17 tests）
- `reports/apify-new-keyword-actors/publish_new_keyword_actors-result-2026-09-05.json`（ライブ実行スナップショット）
- 本報告: `reports/revenue-proposals/2026-09-05-revenue-worker-v14b.md`
- スクリーンショット（Kanban evidence 添付）: store-mercari.png / store-yahoo.png / store-surugaya.png
