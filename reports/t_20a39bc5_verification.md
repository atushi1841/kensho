# Apify PPE External Traffic引导 – Verification Evidence

Task: t_20a39bc5
Commit: 7819920
Owner: kensho-revenue-worker

## verification_evidence

### 1. コード改修の適用確認
- `git diff --name-only HEAD~1` に以下が含まれること:
  ```
  $ git diff --name-only HEAD~1
  reports/weekly_market_report.py
  scripts/apify_store_promo.py
  ```

### 2. apify_store_promo.py クロスプロモ URL 設定
- `APIFY_ACTOR_URLS` が追加され、PRIORITY_ACTORS の全 20 アクターに対応する URL を保持:
  ```
  $ grep -n "APIFY_ACTOR_URLS = {" scripts/apify_store_promo.py
  51:APIFY_ACTOR_URLS = {
  ```
- X 文字数上限対応の trim 関数が追加 (CJK 換算 280):
  ```
  $ grep -n "def trim_to_x_limit" scripts/apify_store_promo.py
  365:def trim_to_x_limit(text: str, limit: int = X_CHAR_LIMIT) -> str:
  ```
- 投稿文に actor_url が埋め込まれる:
  ```
  $ grep -n "actor_url = APIFY_ACTOR_URLS.get" scripts/apify_store_promo.py
  440:    actor_url = APIFY_ACTOR_URLS.get(actual_name, APIFY_STORE_BASE)
  ```

### 3. weekly_market_report.py クロスプロモ欄追加
- MARKET_TO_ACTOR / APIFY_ACTOR_URLS が追加:
  ```
  $ grep -n "MARKET_TO_ACTOR" reports/weekly_market_report.py
  48:MARKET_TO_ACTOR = {
  ```
- レポート出力に Apify Store 関連データソースセクション生成:
  ```
  $ grep -n "関連データソース (Apify Store)" reports/weekly_market_report.py
  224:        "## 関連データソース (Apify Store)",
  ```

### 4. X 投稿テンプレートの文字数検証
- `pick_text` 経由で生成されたツイートが X_CHAR_LIMIT (CJK換算 280) に収まる:
  ```
  $ python3 /tmp/check_tweet_len.py
  slot=a cjk_len=278 OK
  slot=b cjk_len=276 OK
  ```

### 5. 再現性チェック
- `--dry-run` 実行で actor_url が正しく埋め込まれる:
  ```
  $ python3 scripts/apify_store_promo.py --dry-run --slot a
  [2026-09-29 01:41:50] ツイート内容: 'Apify Storeで Mandarake Auction を公開中...👉 https://apify.com/fruitful_quintessence/mandarake-auction-scraper #まんだらけ ...'
  ```

### 成果物
- `scripts/apify_store_promo.py` — X 投稿に actor 個別 URL、文字数トリム、クロス言及追加
- `reports/weekly_market_report.py` — Gumroad 商品説明更新時に Apify Store クロスリンクを自動追記

外部ユーザートラフィック誘導の基盤実装は完了。`external_users_total ≥1` の実現は今後の投稿効果測定による。
