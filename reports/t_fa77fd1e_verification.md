# t_fa77fd1e 復活完了証明 — Gumroad外部導線（dev.to 同期）

## verification_evidence

- 実測: 下書き同期で 2 ファイル blog dir へ移動
- 実測: 同期後、dev.to パイプラインが「未公開 3 件」を発見（従来は 0 件で EXIT_NO_CANDIDATES 無言死）
- 実測: `DEVTO_API_KEY=***`（3文字プレースホルダ）で API 認証不可 → `EXIT_KEY_INVALID` 正常検出
- 実測: Gumroad API で商品属性取得成功（sales_count=0 / price=3999 USD / short_url 確認）

## 実施内容

`devto_weekly_pipeline.py` に Phase 0（下書き同期）を追加:
- `DEFAULT_DRAFTS_DIR = /mnt/d/Project2/kensho/reports/journalism/drafts`
- `sync_drafts()`: 既公開済み（`.published.json` 記録済み）のみスキップし、未公開 `.md` を blog dir へ `shutil.copy2` 同期
- `import shutil` 追加

## 失敗時の代替案

DEVTO_API_KEY がプレースホルダ（***）のため本番公開は不可 → 【要ユーザー対応】。
代替案: dev.to ダッシュボードで API キーを再発行し `/mnt/d/Project2/kensho/.env` の `DEVTO_API_KEY=` 行を更新。キー長 12 文字以上・英数字のみでない下一世代の mask/is_valid チェックに通過する必要あり。

## 実測証拠

```bash
$ python3 devto_weekly_pipeline.py 2>&1 | tail -12
[SYNC] 同期: devto-2026W39.md → /mnt/d/Project2/apify-sales-funnel/blog
[SYNC] 同期: qiita-2026W39.md → /mnt/d/Project2/apify-sales-funnel/blog
[SYNC] 2 file(s) synced
--- Phase 1: Discovering draft articles ---
[SKIP] already published: devto-mercari-japan-scraper.md (id=4606013)
Found 4 markdown candidate(s) / 未公開 3
[FAIL] DEVTO_API_KEY が未設定またはプレースホルダのため公開を中止（要ユーザー対応）
```

```bash
$ python3 -c "import re; k=open('/mnt/d/Project2/kensho/.env').read(); ..."
DEVTO_API_KEY=*** len=3 charset_ok=False
```

```bash
$ curl -s "https://api.gumroad.com/v2/products/IcBs3CFvhQUBxjsi-igJIw==" -H "Authorization: Bearer $TOKEN" | ...
sales_count=0 sales_usd_cents=0.0 formatted_price=$39.99
```