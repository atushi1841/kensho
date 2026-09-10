# critic v87 実装レポート — Apify agentic/x402 whitelist rollout (t_370e65d0)

日付: 2026-09-10 (JST) / ワーカー: kensho-revenue-worker run 354
成果物: reports/agentic-whitelist-2026-09.md (commit 9b11b6d)
follow-upカード: t_8646bcf9（残PPE gaps MCP 2件のwhitelist申請）

## 結論

critic v87の成功指標「isWhiteListedForAgenticPayments=True が 1 → >=6」は
**62件**で達成済み。有効化アクションは不要だった（Apify側がPPE収益化アクター
を既にrollout済み）。API経由の自己有効化は不可能と実証:
`PUT /v2/acts/{id}` に `allowsAgenticUsers` → 400 schema-validation。
残ギャップは PPE の MCP 2アクターのみ → follow-upカードへ切り出し。

## verification_evidence

スキャンは canonical script（workspaceの verify_v87.py）で再実行。以下は実測出力。

$ cd /home/atushi/.hermes/kanban/boards/kensho-ai-team/workspaces/t_370e65d0 && python3 verify_v87.py
my public actors: 72 | wl=True: 62
NOT whitelisted: ['ai-model-price-api', 'eurostat-indicators', 'japan-corporate-numbers', 'japan-egov-laws', 'japan-jma-weather', 'japan-market-mcp', 'japan-mhlw-medical', 'japan-prize-giveaway-scraper', 'mandarake-surugaya-mcp', 'world-bank-indicators']
allowsAgenticUsers=true mine: 62
allowsAgenticUsers=false mine: 10

$ cd /home/atushi/.hermes/kanban/boards/kensho-ai-team/workspaces/t_370e65d0 && python3 characterize.py
WL=True   pricing models: Counter({'PAY_PER_EVENT': 62})
WL=False  pricing models: Counter({'FREE': 8, 'PAY_PER_EVENT': 2})
mandarake-surugaya-mcp              id=xUYsD13SVHHRFQS1H model=PAY_PER_EVENT public=False
japan-market-mcp                    id=57SNehd4cHNFyUCj3 model=PAY_PER_EVENT public=False

$ cd /home/atushi/.hermes/kanban/boards/kensho-ai-team/workspaces/t_370e65d0 && python3 keys_scan.py
agentic-ish keys: {'isWhiteListedForAgenticPayments': True}
community allowsAgenticUsers=true fetched=988 reported_total=1000 mine=0

$ python3 probe_toggle.py  # run 353のAPIプローブ（workspace probe.log に記録保持済み）
GET status 200
keys with 'gent' or 'x402': []
PUT allowsAgenticUsers -> 400 {"error": {"type": "schema-validation", "message": "Invalid value provided in updatedActor: allowsAgenticUsers is not allowed by the schema Received true"}}
actor-update model agentic-ish fields: []

検証要点:
- store フィルタ `username=fruitful_quintessence&allowsAgenticUsers=true` → count=62、
  フラグスキャン（wl=True 62）と一致。baseline 1（14:20）は虚数だった。
- community フィルタの count=1000 は上限キャップ（skip=1000で追加0件）→総数と読まない。
- 8 FREEアクターは False/不在で正常（whitelistはPPE収益化と相関）。MCP 2件のみPPEでFalse。

## 残課題と引き継ぎ

t_8646bcf9: japan-market-mcp (57SNehd4cHNFyUCj3) / mandarake-surugaya-mcp
(xUYsD13SVHHRFQS1H) の dashboard トグル確認 or Apify support/Discord 申請。
rakuten-japan-mcp は True のため PPE-MCP 形式自体は対象外ではない。
