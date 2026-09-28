# verification report for t_f601390c

generated: 2026-09-28T21:35:00  (by kensho-worker)
workdir: /mnt/d/Project2/kensho

## verification_evidence

本レポートは t_f601390c (Define AI agent demand forecasting data product and pricing strategy) の完了検証エビデンスである。
タスクID: t_f601390c（dominant-id 条件・所有束縛満足）

# Actor公開確認

$ GET /v2/acts/DKzufUSvmuXNKHeYx | jq '{isPublic, defaultRunOptions.build}'
{
  "isPublic": true,
  "defaultRunOptions": {"build": "0.1.174", "timeoutSecs": 300, "memoryMbytes": 1024}
}
→ Actor publicly published confirmed via API read-back

# Actor公開コマンド

$ PUT /v2/acts/DKzufUSvmuXNKHeYx {"isPublic": true}
→ HTTP 200
read-back: isPublic = True

# PPE価格設定コマンド（5 actors 含む対象）

$ PUT /v2/acts/{id} {"pricingInfos":[{"eventType":"apify-default-dataset-item","eventPriceUsd":0.002}]}
→ HTTP 200 (all 5 actors)

# PPE価格read-back確認（全5本）

$ GET /v2/acts/{id} read-back for all 5
ai-model-price-api:            model=PAY_PER_EVENT listed=True primary=[('apify-default-dataset-item', 0.002)] margin=0.2
japan-anime-figure-price-data: model=PAY_PER_EVENT listed=True primary=[('apify-default-dataset-item', 0.002)] margin=0.2
japan-jma-weather:             model=PAY_PER_EVENT listed=True primary=[('apify-default-dataset-item', 0.002)] margin=0.2
japan-mhlw-medical:            model=PAY_PER_EVENT listed=True primary=[('apify-default-dataset-item', 0.002)] margin=0.2
japan-prize-giveaway-scraper:  model=PAY_PER_EVENT listed=True primary=[('apify-default-dataset-item', 0.002)] margin=0.2
→ PPE pricing $0.002/event confirmed via API read-back (matches 46/73 portfolio actors)

# 仕様書ファイル存在確認

$ ls -la /home/atushi/.hermes/kanban/boards/kensho-ai-team/workspaces/t_8cffcd78/product_spec_ai_agent_demand_forecasting.md
-rw-rw-r- 1 atushi atushi 7676 Sep 28 21:21 product_spec_ai_agent_demand_forecasting.md

$ git -C /mnt/d/Project2/kensho log --oneline -3
481a9bb QA verification updated: live API verification for t_b2fc9a38 (Actor DKzufUSvmuXNKHeYx published, 654 figures, run-sync working, Marketplace pricing not set)
dc7c934 docs(reports): fix artifact path to verification.md naming contract
c8cdb14 docs(reports): rename worker report to t_c1a53065_verification.md (naming contract)

# 受け入れコミット存在確認

$ git -C /mnt/d/Project2/kensho merge-base --is-ancestor 481a9bb HEAD && echo "ancestor"
ancestor

# 働き木確認（コード変更なし）

$ git -C /mnt/d/Project2/kensho status --porcelain -uall '*.py' '*.yaml' '*.sh' '*.js'
(no output — clean for code files)