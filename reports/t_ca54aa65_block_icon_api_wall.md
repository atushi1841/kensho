# t_ca54aa65 — Apify 既存82本 Custom icon 一括設定: BLOCKED (API では設定不能)

状態: BLOCKED (kind=capability) — カスタムアイコンは Apify の **Console UI 専用** 設定であり、ストアの
Rest API v2 (`PUT /v2/actors/{actorId}` = `UpdateActorRequest`) には設定フィールドが存在しない。

## verification_evidence
- **API仕様調査**: `docs.apify.com/api/openapi.json` を全件検索し、`UpdateActorRequest` に `pictureUrl`, `iconUrl`, `customIconUrl` が存在しないことを確認（読み取り専用 `Actor` スキーマのみに存在）。
- **PUT実測**: 82本のアクターに対し `pictureUrl` を含む PUT を試行し、全件 `HTTP 400 invalid-picture-url` が返ることを確認。
  - 実行コマンド: `python3 application/apify/apply_icons.py`
  - 確認コマンド: `grep "HTTP 400" reports/t_ca54aa65_icon_apply.json`
  - スキーマ確認: `curl -s https://docs.apify.com/api/openapi.json | jq '.components.schemas.UpdateActorRequest'`
- **他URL検証**: 有効な Apify 公式 CDN の URL や GitHub Raw URL を用いた試行もすべて 400 エラーとなることを確認。
- **副作用チェック**: `store_count_before: 73` -> `store_count_after: 73` で店頭件数に変動なし。`categories`, `pricingModel`, `isPublic` の退行も 0 件であることを個別 GET で検証済み。
- **成果物**: 82本分のアクター名に対応した 256x256 PNG アイコン画像を生成し、`kensho-assets` リポジトリへ公開済み（手動設定に流用可能）。

## 結論（実測 + OpenAPI スキーマで確定）

- 対象: 既存 82 本（新規作成なし。`GET /v2/acts?limit=1000&my=1` で列挙）
- 適用試行: 82 件すべて **HTTP 400** → `invalid-picture-url: "Invalid picture URL"`
- 別フィールド試行: `customIconUrl` / `iconUrl` → `HTTP 400 schema-validation: "not allowed by the schema"`
- 正しい Apify CDN の pictureUrl（他ユーザーの Store 掲載実例、全長296文字）でも PUT すると 400 invalid-picture-url
- 原因: `UpdateActorRequest`（PUT /v2/actors/{actorId} のボディスキーマ）に picture/icon 系フィールドが
  **一切存在しない**。`pictureUrl` は読み取り側スキーマ `Actor` のみに存在する（string|null）。
  → **カスタムアイコンの設定は API では不可能。Console UI（Publishing tab → Custom icon アップロード）専用。**

## 実測証拠

### 1. 対象列挙（82本）
`GET /v2/acts?limit=1000&my=1` → data.items 82 件。全件 pictureUrl/iconUrl/customIconUrl 未設定。

### 2. apply_icons.py（前回 run816 で実行）の結果レポート
`/mnt/d/Project2/kensho/reports/t_ca54aa65_icon_apply.json`:
```
store_count_before: 73
store_count_after: 73          (変動なし: 店頭件数維持)
total_actors: 82
icon_urls_verified: 82          (生成 PNG は全件 public 200 + image/png)
icon_urls_bad: []
targets_count: 82
applied_count: 0                ← 全滅
failed_count: 82                ← 全件 HTTP 400 invalid-picture-url
```
同一ファイルの `regressions` 欄: 全 82 件とも `pictureUrl still unset`（categories / pricingModel / isPublic の
退行はゼロ → 価格・公開状態・カテゴリは一切変化していない。安全）。

### 3. スキーマ確定（openapi.json、docs.apify.com/api/openapi.json から保存: /tmp/apify_openapi.json）
- `UpdateActorRequest.properties` 16 フィールド = actorPermissionLevel, actorStandby, categories,
  defaultRunOptions, description, exampleRunInput, isDeprecated, isPublic, name, pricingInfos,
  restartOnError, seoDescription, seoTitle, taggedBuilds, title, versions
  → **pictureUrl / customIconUrl / iconUrl は一切なし**
- パスで image/picture/upload/avatar/icon/logo を含むもの: **0 件**（アップロード系 API も存在しない）
- `Actor.pictureUrl` type: `['string','null']`（読み取り専用）
  description: "URL of the Actor's icon, displayed on the Actor's page in Apify Store and Console."

### 4. 動作実測（probe_fields.py 出力要約）
| 試行 (PUT /v2/actors/{id}) | 結果 |
|---|---|
| pictureUrl = raw.githubusercontent.com/...（公開200 image/png検証済） | 400 invalid-picture-url |
| pictureUrl = images.apifyusercontent.com/（Store掲載実例・全長） | 400 invalid-picture-url |
| pictureUrl = github.com/.../raw/... | 400 invalid-picture-url |
| customIconUrl = ... | 400 schema-validation not allowed |
| iconUrl = ... | 400 schema-validation not allowed |

## 完了条件に対する判定
- 対象件数・設定成功0件・失敗82件: reports/t_ca54aa65_icon_apply.json に記録 ✓
- Store件数 73→73（変動なし）✓ / PPE維持 ✓ / 公開状態維持 ✓（個別GETで categories・pricingInfos[-1].pricingModel・isPublic を比較、全件不変）
- 全成功 actor のライブ再読込: 対象が0件のため該当なし（未適用）。live refetch は
  `/mnt/d/Project2/kensho/reports/t_ca54aa65_actor_live_refetch.json` に取得済みで、全82件の
  categories/pricingModel/isPublic/pictureUrl をスナップショット保存。
- 無理に再試行しない方針通り、再試行なし。

## 次の一手（BLOCK理由）
API ではカスタムアイコンを設定できないため、このカードは実装できない（capability blocker）。
残る選択肢:
1. **手動（推奨）**: Console UI の Publishing tab で各アクターの Custom icon をアップロード。82本分の手作業
   （またはブラウザ自動化の別途検証が必要）。kensho-assets の生成済み PNG が使える
   （`https://raw.githubusercontent.com/atushi1841/kensho-assets/main/<actor_name>.png`）。
2. **Icon 設定を諦めて t_ca54aa65 を廃止**し、fetch (version freshness) 等 API で可能な項目のみ継続。
3. Apify 側の画像アップロード用エンドポイントが追加されたら再試行（現時点 openapi では 0 件）。

生成済みアイコン基盤（make_icons.py → 82枚の256x256 PNG → kensho-assets 公開、全件 GET 200 image/png）は
成果物として維持しており、手動設定にそのまま流用できる。
