# Revenue Worker Run — 2026-10-02 23:00 JST

## タスク
- t_5bcadceb: Apify Actor タグ設定（tags 0/86 → 全Actorへ関連タグ付与）

## 調査・検証結果

### 結論: tagsフィールドはApify APIに存在しない
- `PUT /v2/actors/{id} {"tags":["test"]}` → **400 schema-validation: "tags is not allowed by the schema"**
- `GET /v2/actors/{id}` のレスポンスキー: categories, seoTitle, seoDescription... だが `tags` キーは含まれない
- `taggedBuilds` はビルド識別タグであり検索タグとは無関係

### Apify Store検索の可視性決定要因
1. **categories** — クライアントでフィルタ可能。84/86 actorsに Specific カテゴリ設定済み（t_c33b809a Phase1完了）
2. **seoTitle / seoDescription / description** — 既存SEOスクリプトで最適化済み
3. **name / README** — ソースコードから自動生成

tagsフィールドは**実装されていない**ため、「tags 0/86」は**誤った前提**に基づくタスク。

### 未設定のcategories（2件）
| Actor | name | isPublic | categories |
|-------|------|----------|------------|
| 1 | kensho-sweep-mcp | True | null |
| 2 | my-actor-1 | False | null |

my-actor-1 は private actor なので外してよい。
kensho-sweep-mcp は public MCP server なので `MCP_SERVERS` or `DEVELOPER_TOOLS` が適切。

### トークン状態
- Cron環境: `APIFY_TOKEN` 未設定（token len=0）→ 直接PUT不可
- 前回worker run（21:46）: 同じエラー、トークン取得方法は不明
- 手動で `export APIFY_TOKEN=apify_api_xxx` 後に `python3 scripts/apify_category_specific.py --apply` 実行要

## アクション
- t_5bcadceb に調査結果コメントを追加（完了）
- pseudo-done候補として critic へ提案渡す

## 自レビュー
```json
{
  "self_review": {
    "what_was_done": "t_5bcadceb 調査—tags非存在を確認、comments追加",
    "what_went_well": ["tags schema-validation 実APIで検証済み", "categories未設定actor特定済み"],
    "what_could_improve": ["トークン取得経路が不明—次回 confirm"],
    "mistakes_or_risks": ["kanban comment 初回で bash quoting エラー→タイムアウト"],
    "learned": "tagsフィールドは存在しない。categories設定はトークン次第で可能。",
    "confidence": 9,
    "verification_evidence": "PUT tags→400, PUT categories(my-actor-1)→403, GET users/me→401(token未設定)"
  }
}
```
