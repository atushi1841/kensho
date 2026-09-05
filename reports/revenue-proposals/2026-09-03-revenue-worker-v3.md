# Revenue Worker Report — t_9f532022

**実施日時**: 2026-09-03 17:00 JST
**タスクID**: t_9f532022
**タイトル**: 収益提案: japan-market-mcp へのクロスセル導線追加
**担当**: kensho-revenue-worker

## タスク概要

`japan-market-mcp` Actor (id: 57SNehd4cHNFyUCj3, runs=587, japan-market-mcp全体最多) の description と seoDescription に、他のPPE専用スクレイパーアクター (camera/watch/luxury等) への誘導文を追加。実装コスト低、発見性向上を狙う。

## 実装前の状態 (Before)

`description`: "MCP server letting AI agents (Claude, Cursor, ChatGPT) compare used-good prices across Japanese shops in one call: cameras, luxury watches, brands, instruments, OffMall, Kakaku.com, used cars. Ideal for reseller arbitrage and market research."

- 文字数: 242
- クロスセル導線: なし（汎用的な機能説明のみ）

`seoDescription`: "AI-agent MCP server comparing used-good prices across Japan shop pairs: cameras, luxury watches, brands, instruments, used cars, Kakaku.com. Reseller arbitrage & market research."

- 文字数: 152
- クロスセル導線: なし

## 実装内容

### 変更1: description (300文字以内)

**新description**: "MCP server for AI agents (Claude, Cursor, ChatGPT) comparing used-good prices across Japanese shops. Cross-shop + standalone PPE Actors for cameras, watches, luxury, instruments, cars, Kakaku, OffMall."

- 文字数: 201
- クロスセル要素: 「Cross-shop + standalone PPE Actors」 + 各カテゴリ名を列挙し、詳細スクレイパーへの興味を誘導

### 変更2: seoDescription (200文字以内)

**新seoDescription**: "AI-agent MCP server for Japanese used-good prices: cameras, watches, luxury, instruments, cars, Kakaku, OffMall. Pair with fruitful_quintessence standalone PPE Actors for bulk."

- 文字数: 176
- クロスセル要素: 「Pair with fruitful_quintessence standalone PPE Actors for bulk」 — Apify Store検索で同じpublisherのスタンドアロンPPEアクターに直接遷移する文言

## 検証エビデンス

### API呼び出し結果

```
HTTP 200 (PUT /v2/acts/57SNehd4cHNFyUCj3)
```

### 再読み出し検証 (GET /v2/acts/57SNehd4cHNFyUCj3)

```
HTTP 200
description: 'MCP server for AI agents (Claude, Cursor, ChatGPT) comparing used-good prices across Japanese shops. Cross-shop + standalone PPE Actors for cameras, watches, luxury, instruments, cars, Kakaku, OffMall.'
seoDescription: 'AI-agent MCP server for Japanese used-good prices: cameras, watches, luxury, instruments, cars, Kakaku, OffMall. Pair with fruitful_quintessence standalone PPE Actors for bulk.'
```

### スキーマ制約 (実測)

- `description`: 最大300文字 → 新201文字で収まる
- `seoDescription`: 最大200文字 → 新176文字で収まる
- `readmeSummary`: 編集不可（schema-validation error）→ description/seoDescriptionに分けた

### エラー履歴

- 1回目: descriptionにクロスセル追加で601文字 → 400 error (must be ≤300)
- 2回目: seoDescriptionに246文字追加 → 400 error (must be ≤200)
- 3回目: トークン1文字typo（apify_api_F...）→ 401 error → 再実行
- 4回目: 201/176文字で両方収まる → 200 success

## 自己レビュー (Reflexion)

```json
{
  "self_review": {
    "what_was_done": "japan-market-mcp Actor (57SNehd4cHNFyUCj3) の description と seoDescription にクロスセル導線を追加し、standalone PPE Actorsへの誘導文を挿入した",
    "what_went_well": [
      "APIスキーマ制約（description ≤300, seoDescription ≤200）を実測で確認し収まる文字数で実装",
      "readmeSummaryが編集不可と判明→即座に代替手段（description/seoDescription）に切り替えた",
      "GET再読み出しでdescription/seoDescriptionの新文字列が反映されていることを実測確認"
    ],
    "what_could_improve": [
      "APIスキーマの文字数制限を事前調査すれば3回のエラー試行を避けられた",
      "クロスセル文言を入れる際、各standalone Actorへの直接ハイパーリンクがdescriptionに入らなかった（300/200文字制限のため）。可能ならpublisher横断ページや個別ActorページへのURL言及も追加したい",
      "MCPエンドポイント（https://fruitful-quintessence--japan-market-mcp.apify.actor）からdiscovery経路で読めるタグやキーワード強化の余地あり"
    ],
    "mistakes_or_risks": [
      "トークン1文字typo（apify_api_F）で401エラー。シェルのコピペ履歴管理を強化すべき",
      "description変更によりSEO上の既存キーワードランキングが変動する可能性 → 1週間程度はruns数/search流入を監視"
    ],
    "learned": "Apify Actor descriptionは300/200文字制限がある。readmeSummaryは編集不可。スキーマ検証は最初に既存Actorに対するOPTIONSまたはGET結果のレスポンスから推測できる。トークンtypo防止策として、CLI実行前に必ず環境変数$APIFY_TOKENで展開させるか、tokenファイルから読み込む形にすべき",
    "confidence": 8,
    "verification_evidence": "PUT API response HTTP 200 + GET再読み出しで description='MCP server for AI agents...Cross-shop + standalone PPE Actors...' / seoDescription='AI-agent MCP server for Japanese used-good prices...Pair with fruitFul_quintessence standalone PPE Actors for bulk.' が両方とも反映済（/tmp/japan_mcp_verify.json）"
  }
}
```

## 申し送り / 次回への引き継ぎ

- 効果測定は1-2週間後（runs数推移・search流入）を確認すること
- description変更でSEO順位が落ちた場合は旧テキストに戻すロールバック手段を確保
- 他の高runs MCP/Scraper Actorにも同パターンのクロスセル導線を展開する価値あり（t_a4b1f89e MCPサーバー化と組み合わせると効果倍増）