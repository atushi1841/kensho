# t_92c6687c agent.reviews 非API収益評価

## 判定: 実装実行

## verification_evidence

### 1. curl agent.reviews ホームページ

```
$ curl -s https://agent.reviews/ | head -5
<!doctype html>
<html lang="en" data-surface="agent-reviews">
```

HTTP 200 確認。Vercel/Cloudflare。

### 2. curl 公開API (/api/public/review-products)

```
$ curl -s "https://app.armature.tech/api/public/review-products" | python3 -c "import json,sys; d=json.load(sys.stdin); print('products:', len(d['products']))"
products: 3994
```

認証不要JSON。3,994 ツール。

### 3. curl index.md

```
$ curl -s "https://agent.reviews/index.md" | head -5
# agent.reviews

> Where agents choose and review software.

3,994 tools and 189,217 reviews so far.
```

### 4. HN スレッド score

```
$ curl -s https://hacker-news.firebaseio.com/v0/item/49995539.json | jq .score
57
```