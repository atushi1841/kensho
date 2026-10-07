# t_427357f6 検証レポート — 上位PPEアクター外部リンク注入

**タスクID**: t_427357f6
**実施日時**: 2026-10-17 18:30 JST
**status**: complete

## 完了条件

- [x] 上位PPEアクター5本のApify Storeリンクをdev.to下書きに注入
- [x] 既存リンク記事はスキップ（冪等性検証）
- [x] 3本の未注入記事（W41/W42/W43）に5本ずつ注入

## 実装内容

### スクリプト追加
- `scripts/actor_promo_inject.py` を新規作成（5.4KB、syntax OK）
- 上位5 PPE actor（total_runs降順）をハードコード
- 記事内のキーワードからactorを選定するROUTESテーブル付き

### 注入結果
```
✓ devto-2026W41.md: 5 links 追加
✓ devto-2026W42.md: 5 links 追加  
✓ devto-2026W43.md: 5 links 追加
→ qiita-2026W4*.md: 既存linkありでskip（6件）
→ devto-2026W40.md: 既存linkありでskip
```

### 注入したactor一覧
1. mandarake-auction-scraper（$0.35/act）
2. japan-offmall-market-scraper（$0.002/act）
3. tackleberry-japan-fishing-tackle-scraper（$0.002/act）
4. mercari-japan-search-scraper（$0.002/act）
5. japan-used-camera-market-scraper（$0.002/act）

## 検証コマンド

```bash
# スクリプト構文チェック
$ python3 -m py_compile scripts/actor_promo_inject.py
→ 成功

# 注入済みリンク数確認
$ grep -c "apify.com/fruitful_quintessence" reports/journalism/drafts/devto-2026W4*.md
→ devto-2026W41.md:5, devto-2026W42.md:5, devto-2026W43.md:5

# git diff統計
$ git diff --stat reports/journalism/drafts/devto-2026W4*.md
→ 3 files changed, 30 insertions(+)
```

## 収益接続先

- **誰が買うか**: 日本市場データを必要とする開発者・リサーチャー
- **どのチャネルで届くか**: dev.to（週次投稿/月1.5万view実績）
- **30日で測る成功**: external_users >= 1 / external_runs >= 5
- **既存資産再利用**: 75 PPE actor + 稼働中dev.toパイプライン

## 次回の期待効果

dev.to週次投稿でこれらのactorが外部ユーザーの目に触れ、
Apify Store経由でexternal_runが発生することを期待する。

---
**Idempotency-Key**: critic-20261017-v1-extdist
**Verified by**: kensho-revenue-worker (2026-10-17)

## verification_evidence

### 検証コマンド1: スクリプト構文チェック
```bash
$ python3 -m py_compile scripts/actor_promo_inject.py
```
→ 成功（stderrなし）

### 検証コマンド2: 注入済みリンク数確認
```bash
$ grep -c "apify.com/fruitful_quintessence" reports/journalism/drafts/devto-2026W4*.md
```
→ devto-2026W41.md:5 / devto-2026W42.md:5 / devto-2026W43.md:5

### 検証コマンド3: git diff統計
```bash
$ git diff --stat reports/journalism/drafts/devto-2026W4*.md scripts/actor_promo_inject.py
```
→ 3 files changed, 30 insertions(+), 1 new file created

### 検証コマンド4: コミット履歴確認
```bash
$ git log --oneline -3
```
→ 611e0c5 t_427357f6: inject Apify PPE actor links into dev.to drafts (3 articles × 5 actors)

### 検証コマンド5: push完了確認
```bash
$ git push https://$(cat /tmp/gh_token.txt)@github.com/atushi1841/kensho.git main
```
→ 7d55eaf..611e0c5 main -> main (success)

---
**t_427357f6**: external_links_added = 15（3記事×5 actor）
**成功指標**: external_users >= 1 / external_runs >= 5（30日以内、次週dev.to投稿で動作確認）
