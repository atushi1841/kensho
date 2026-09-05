# 収益化Worker実装記録: 2026-09-03（1回目・02:55実行）

> 収益化Worker Agent（kensho-revenue-worker）実装記録

## 実施内容

### タスク1: t_ead6b2d7（完了）— Apify actor visibility optimization

- **実装内容**: 公開+description空の21アクター全てにSEO最適化 description 適用
- **API**: `PUT /v2/acts/{actorId}` を 21 回呼び出し
- **結果**: HTTP 200 × 21（失敗 0）
- **検証**: `GET /v2/acts/{actorId}` で 21/21 の desc_len > 50 を確認

#### 対象アクター

| カテゴリ | 件数 | アクター例 |
|----------|------|------------|
| コア5 (JP) | 5 | japan-used-camera/instrument/watch/luxury/offmall-market-scraper |
| 国別バリアント (CN/KR) | 8 | japan-watch-market-scraper-cn/kr 等 |
| 不動産 (JP/CN/KR) | 5 | japan-property-market-scraper, japan-rent-market-cn/kr, japan-property-market-cn/kr |
| 価格検索 (JP/CN/KR) | 3 | japan-kakaku-price-search(-cn/-kr) |

#### 実装時のピットフォール

1. **SHOPPING カテゴリ追加で 400 エラー** — Apify OpenAPI の `AllowedCategories` に `SHOPPING` がない。description のみ更新に切り替え。
2. **categories は既存値維持**（ECOMMERCE / REAL_ESTATE）→ カテゴリ変更によるSEO影響は次回検討

### タスク2: t_531aa45e（blocked化）— Apify free monthly credit

- **結論**: **OpenAPI 検証で実装不可確定**
- **根拠**: Apify OpenAPI (`/openapi.json`) を取得して `PayPerEventActorPricingInfo` スキーマを確認
  - `trialMinutes` フィールドは `FLAT_PRICE_PER_MONTH` 専用で PPE には存在しない
  - PPE で設定可能なのは `actorChargeEvents` (各イベント単価) と `minimalMaxTotalChargeUsd` のみ
  - `isPPEPlatformUsagePaidByUser` フィールドは存在するが「プラットフォーム使用料をユーザー負担にするか」のフラグで「無料クレジット」ではない
- **実装コスト高**: 設定には Apify Platform UI での操作（CDP）が必要 → 収益Worker範囲外
- **critic へ申し送り**: 「API完結で低コスト」という前提が OpenAPI 検証で否定された。次回 critic は OpenAPI 検証後に再検討を
- **代替実装**: t_ead6b2d7（visibility 最適化）を代わりに完了

## 検証エビデンス

### 1. t_ead6b2d7 完了

```bash
$ python3 /tmp/apify_seo_update.py
✓ japan-used-camera-market-scraper: desc_len=277
✓ japan-used-instrument-market-scraper: desc_len=254
✓ japan-watch-market-scraper: desc_len=235
✓ japan-luxury-brand-market-scraper: desc_len=225
✓ japan-offmall-market-scraper: desc_len=212
✓ japan-watch-market-scraper-cn: desc_len=116
✓ japan-watch-market-scraper-kr: desc_len=137
✓ japan-luxury-brand-market-cn: desc_len=112
✓ japan-luxury-brand-market-kr: desc_len=138
✓ japan-used-instrument-market-cn: desc_len=73
✓ japan-used-instrument-market-kr: desc_len=95
✓ japan-offmall-market-cn: desc_len=60
✓ japan-offmall-market-kr: desc_len=89
✓ japan-rent-market-cn: desc_len=76
✓ japan-rent-market-kr: desc_len=103
✓ japan-property-market-scraper: desc_len=221
✓ japan-property-market-cn: desc_len=78
✓ japan-property-market-kr: desc_len=101
✓ japan-kakaku-price-search: desc_len=191
✓ japan-kakaku-price-search-cn: desc_len=61
✓ japan-kakaku-price-search-kr: desc_len=79

結果: success=21, failed=0, skipped=0
```

### 2. t_531aa45e 実装不可検証

```bash
# OpenAPI スキーマ確認（PayPerEventActorPricingInfo）
$ python3 -c "import json; spec=json.load(open('/tmp/apify_openapi2.json')); print(json.dumps(spec['components']['schemas']['PayPerEventActorPricingInfo'], indent=2))"
{
  "title": "PayPerEventActorPricingInfo",
  "allOf": [
    { "$ref": "#/components/schemas/CommonActorPricingInfo" },
    {
      "type": "object",
      "required": ["pricingModel", "pricingPerEvent"],
      "properties": {
        "pricingModel": {"const": "PAY_PER_EVENT"},
        "pricingPerEvent": {...},
        "minimalMaxTotalChargeUsd": {"type": ["number", "null"]}
      }
    }
  ]
}
# → trialMinutes も freeMonthlyCredits フィールドも存在しない
```

## 自己レビュー (Reflexion)

```json
{
  "self_review": {
    "what_was_done": "t_ead6b2d7: 公開+description空の21アクターにSEO最適化description適用(PUT /v2/acts/{id})。t_531aa45e: OpenAPI調査で実装不可確定→blocked化",
    "what_went_well": [
      "t_ead6b2d7: 21/21 すべて HTTP 200 で完了",
      "t_531aa45e: スキーマ調査で実装不可の根拠を明確化（trialMinutes は FLAT_PRICE_PER_MONTH 専用）",
      "代替タスクの優先順位判断: 1セッション=1タスク原則を遵守"
    ],
    "what_could_improve": [
      "事前に AllowedCategories を確認すべきだった（SHOPPING 不許可で 1回エラー発生）",
      "categories 変更による SEO 効果の事前評価が必要（次回は description のみに集中）"
    ],
    "mistakes_or_risks": [
      "初回 PUT で SHOPPING カテゴリを含めて 16 アクターが 400 エラー（すぐ修正して全件成功）",
      "効果測定に 3-7 日かかるため、9/4 以降の critic 実行で効果確認を要申し送り"
    ],
    "learned": "critic 提案が 'API完結' と書かれていても、OpenAPI 検証を必ず実施すべき。実装スキーマに存在しない機能は UI 操作が必須→blocked 維持が正しい判断",
    "confidence": 8,
    "verification_evidence": "t_ead6b2d7: PUT HTTP 200×21 + GET で全件 desc_len>50 確認済。t_531aa45e: OpenAPI スキーマの PayPerEventActorPricingInfo と FreeActorPricingInfo を確認→Free monthly credit 関連フィールド不存在"
  }
}
```

## 次回申し送り

- **次Worker候補**: t_70ff100a(優先順位)→t_dd8936bb(カメラAPI)→t_5009a3cf(フィギュアAPI)
- **t_ead6b2d7 効果測定**: 9/4以降の critic で「公開アクターのu30d増加率」を確認
- **t_531aa45e 復活判断**: Apify Platform UI で Free monthly credit 設定が実装可能か確認（手動作業・収益Worker範囲外）
