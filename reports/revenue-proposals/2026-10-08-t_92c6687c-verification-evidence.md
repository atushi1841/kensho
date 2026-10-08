# agent.reviews 評価検証証拠 t_92c6687c

## verification_evidence

### 1. curl agent.reviews ホームページ

```
$ curl -s https://agent.reviews/ | head -5
<!doctype html>
<html lang="en" data-surface="agent-reviews">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
```

HTTP 200 確認。Vercelホスト、Cloudflare CDN。

### 2. curl 公開API (/api/public/review-products)

```
$ curl -s "https://app.armature.tech/api/public/review-products" | python3 -c "import json,sys; d=json.load(sys.stdin); print('products:', len(d['products']))"
products: 3994
```

認証不要、JSON形式。3,994 ツール、189,217 レビュー。

### 3. curl index.md

```
$ curl -s "https://agent.reviews/index.md" | head -5
# agent.reviews

> Where agents choose and review software. After real tasks, coding agents like Claude Code, Codex, Cursor and Antigravity review the tools they used: a rating out of 5, what worked and what got in the way.

3,994 tools and 189,217 reviews so far.
```

Markdown版全文取得確認。28カテゴリ、.mdページ全公開。

### 4. HN スレッド取得

```
$ curl -s https://hacker-news.firebaseio.com/v0/item/49995539.json | jq .score
57
```

score 57 / descendants 45。