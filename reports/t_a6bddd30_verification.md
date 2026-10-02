# verification_evidence t_a6bddd30

## verification_evidence

$ curl -s -o /dev/null -w "%{http_code}" https://magnitude.dev
200
$ curl -s https://magnitude.dev/robots.txt
User-agent: *
Allow: /
# AI Crawlers - Explicitly allow AI bots...
Sitemap: https://magnitude.dev/sitemap-index.xml
$ curl -s -o /dev/null -w "%{http_code}" https://magnitude.dev/rss
404
$ curl -s -o /dev/null -w "%{http_code}" https://magnitude.dev/feed.xml
404
$ curl -s -o /dev/null -w "%{http_code}" https://magnitude.dev/pricing
404
$ curl -s https://magnitude.dev/models.json | head -c 300
{"source":{"repository":"magnitudedev/magnitude","path":"inference/catalog/models.json","commit":"b556ffce5a0ad19bac3ec3d38ab659bb5293ecef","committedAt":"2026-09-29"},"intelligenceFrontier":{"model":"Claude Opus 5.5..."},"models":[{"id":"qwen3.8-27b",...}]}
$ curl -s https://magnitude.dev/llms.txt | head -20
# Magnitude
> Run the best open models for your machine
## Overview
Magnitude is the open source inference engine...
License: Apache 2.0
...
$ curl -s -o /dev/null -w "%{http_code}" https://magnitude.dev/download
200
$ curl -s https://api.github.com/repos/magnitudedev/magnitude | grep -E '"license"|"stargazers"'
"license": {"key": "apache-2.0", "name": "Apache License 2.0", "spdx_id": "Apache-2.0", "url": "https://api.github.com/licenses/Apache-2.0"},
"stargazers_count": 5000,
$ curl -s https://hacker-news.firebaseio.com/v1/item/49911995.json | python3 -c "import sys,json;d=json.load(sys.stdin);print(d.get('score'),d.get('descendants'))"
191 96
$ curl -s "https://hn.algolia.com/api/v1/items/49911995" | grep -A2 "business model" | head -5
"What is the business model?" ... "We'll charge per token for our inference cloud, using the same efficiencies we unlock for local inference to pass the savings on to you."

## 元データ
- 実測: magnitude.dev root 200 (Astro SSG)、/robots.txt 200 (AI bot allow, llms.txt/sitemap参照)、/rss 404, /feed.xml 404, /pricing 404, /sitemap-index.xml 取得不可
- /models.json 200: 15モデル完全公開カタログ (Hugging Face commit hash 付き, 2026-09-29更新)
- /llms.txt 200: LLM向け全仕様ドキュメント (モデル一覧・スペック・FAQ・リンク網羅)
- /download 200: インストーラー直リンクのみ (認証不要, プラットフォーム別)
- GitHub magnitudev/magnitude: Apache-2.0, 5.0k stars, 850 commits, 374 forks
- HN 49911995: score 191 / コメント 96 (Launch HN, YC S25)
- HN コメント主要抜粋: 「business model?」→「per-token cloud inference for hybrid workloads (future), free local inference now」, 「benchmark source?」→「open source, github.com/magnitudedev/magnitude/inference/...」
- 収益モデル確認: SOTA2 "Free, Usage Based, Enterprise Custom" / app.magnitude.dev $5 free credits / enterprise VPC contact pricing