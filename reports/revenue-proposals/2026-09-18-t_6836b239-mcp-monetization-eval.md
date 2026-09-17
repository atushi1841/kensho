# MCP Server 課金化（API Gateway化）実装前検証／調査レポート — t_6836b239

日時: 2026-09-18 (JST) ｜ ワーカー: kensho-revenue-worker

## 結論
**既存 japan-market-mcp は Apify 上で既に「公開 ＋ APIトークン認証 ＋ PPE課金（$0.001/call）」でモネタイズ済み。認証・課金レイヤーの新規実装は不要。**

カード成功指標の検証ドメイン `registry.mcp.so` は **NXDOMAIN（存在しない）** のため、指定検証コマンドは実行不能（前提崩れ）。実在する主要MCPディレクトリは **mcp.so**（DR72）で、japan-market-mcp は未掲載（404）。掲載は無料GitHub issue か **$39 有料申込** の選択が必要 → 人間判断に委ねる。

## 実測証拠
### 1. Apify 上で既に公開＋モネタイズ
`GET /v2/acts/57SNehd4cHNFyUCj3`（Authorization付き 実測）:
- `isPublic: true`
- `pricingInfos`: `PAY_PER_EVENT`, 各ツール `$0.001`, `apifyMarginPercentage 0.2`（開発者取り分80%）, 2026-08-10 開始
- `stats.totalRuns: 601`, `totalUsers: 2`（累計）, 直近30日 public run=0

### 2. MCPエンドポイントは認証必須（APIキー課金モデル実装済み）
`curl https://57SNehd4cHNFyUCj3.apify.actor/mcp` → **HTTP 401** `api-token-missing`（Apify APIトークン必須）。ユーザー自前のトークンを `Authorization: Bearer` で渡す従量課金。

### 3. registry.mcp.so は NXDOMAIN
`getent hosts registry.mcp.so` → 解決不可。カードの `curl registry.mcp.so/server/japan-market-mcp | jq '.public'` は存在しないホストを叩く前提で物理的に成功不可。

### 4. MCPディレクトリ掲載状況
- `mcp.so/server/japan-market-mcp` → **404（未掲載）**
- 申込: mcp.so/submit → Repository URL + 無料issue または **Paid $39**

## 推奨
- 課金化は完了済み。残課題は **発見可能性（mcp.so掲載）** と **直近30日public run=0**（外部評価証拠の欠如）。
- mcp.so 掲載の有料($39)／無料(issue)の選択は運営判断が必須 → 本カード完了時にQA/運営へ委譲し、人間のGO待ち。

## verification_evidence
証跡は報告本体（# 実測証拠 1-4）と下記実測ログ。対象: japan-market-mcp / Apify Actor 57SNehd4cHNFyUCj3 / task t_6836b239。実行時刻 2026-09-18 (JST)。

$ curl -s https://api.apify.com/v2/acts/57SNehd4cHNFyUCj3 -H "Authorization: Bearer $APIFY_TOKEN" | jq '{isPublic, pp: .pricingInfos[0]}'
→ isPublic:true, pricingModel:PAY_PER_EVENT, unitPricePerEvent:$0.001, apifyMarginPercentage:0.2, totalRuns:601, totalUsers:2

$ curl -s https://57SNehd4cHNFyUCj3.apify.actor/mcp -o /dev/null -w "%{http_code}"
→ 401

$ getent hosts registry.mcp.so
→ (NXDOMAIN / exit 2, 解決不可)

$ curl -s -o /dev/null -w "%{http_code}" https://mcp.so/server/japan-market-mcp
→ 404

## 検証コマンド引用（原文）
```
$ GET https://api.apify.com/v2/acts/57SNehd4cHNFyUCj3  → isPublic:true, PAY_PER_EVENT $0.001, 601runs
$ curl https://57SNehd4cHNFyUCj3.apify.actor/mcp       → 401 api-token-missing
$ getent hosts registry.mcp.so                          → NXDOMAIN
$ curl https://mcp.so/server/japan-market-mcp           → 404
```
