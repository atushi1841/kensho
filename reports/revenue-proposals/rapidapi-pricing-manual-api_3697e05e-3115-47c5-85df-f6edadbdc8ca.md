# RapidAPI 有料プラン有効化 手動手順書

**対象 API**: `japan-offmall-cn` (ID: `api_3697e05e-3115-47c5-85df-f6edadbdc8ca`)
**選択 tier**: `basic`
**想定月額**: `$4.99/月`（RapidAPIテンプレート設定次第）
**Billing Plan Version ID**: `billingplanversion_03e7713f-fe51-45ba-949e-e07ecbcca3bb`
**生成元**: `scripts/rapidapi_pricing_set.py`
**タスク**: t_698fc46c (v14-A)

---

## 結論

**API 経由での subscription 作成は技術的に「ほぼ到達」、ただし recaptcha トークンがボトルネック**:

1. ✅ GraphQL mutation `createApiSubscription(input: CreateApiSubscriptionInput!)` は存在
2. ✅ 必須フィールド3つ (`apiId`, `ownerId`, `billingPlanVersionId`) の signature を逆探りで特定
3. ✅ 対象APIに紐付く BillingPlanVersion ID を実測で取得
4. ❌ mutation 実行時に `Missing recaptcha token` エラー（HTTP 200 + GraphQL error）
5. ❌ recaptcha sitekey は SPA の JS レンダリング後にしか取得できない
6. ❌ トークン自動生成は CAPTCHA 解決に該当 → 自動化では手動手順が現実解

→ **唯一の現実解は Studio UI を直接操作する手順書**。

---

## 背景: RapidAPI の課金モデル

- **Provider は price を自由に設定できない**。RapidAPI が定義した Basic/Pro/Ultra テンプレートを選ぶ方式
- 課金プランの構造:
  - `billingPlan` (BASIC, PRO 等) — Provider が全API共通で使う
  - `billingPlanVersion` — バージョン（v1, V1 等）
  - `price` — RapidAPI が管理
- サブスク有効化は「対象APIに既存の BillingPlanVersion を紐付ける」だけ

## 実測で確認した対象APIの BillingPlanVersion（2026-09-04）

| API ID | Plan | BillingPlanVersion ID |
|--------|------|----------------------|
| `api_3697e05e-3115-47c5-85df-f6edadbdc8ca` (OffMall CN) | BASIC | `billingplanversion_03e7713f-fe51-45ba-949e-e07ecbcca3bb` |
| `api_c1044ee7-1752-4d3e-a688-53f7e791d5ff` (OffMall JP) | BASIC | `billingplanversion_8d207a41-321b-4ce7-a125-fa8cb2541bde` |
| `api_7d2dcc27-829d-4add-88b9-5c1708447f85` (Camera JP) | BASIC | `billingplanversion_c6a5210c-2396-4341-904c-9d3102069104` |
| `api_45bf102f-6d1b-4fd5-9179-f164de167ffd` (Kakaku) | BASIC | `billingplanversion_52b47643-2a45-4291-a24a-08b4a9293ba2` |
| `api_2e8e063d-f2a3-43de-9fe4-50d5eb16659a` (Rent) | BASIC | `billingplanversion_6e752f93-7d1d-4e9c-a178-f5c5da1d9c79` |

## 手動手順（所要時間: 約3分/API）

### 準備
- Windows Chrome で https://rapidapi.com/_studio/ にログイン（cookie 有効）

### ステップ

1. **対象 API の Pricing タブを開く**
   - URL: `https://rapidapi.com/_studio/apis/api_3697e05e-3115-47c5-85df-f6edadbdc8ca/pricing`

2. **「Enable Pricing」または「Monetize」ボタンをクリック**
   - recaptcha ダイアログが出るので手動で認証
   - Basic / Pro プランが「Active」になることを確認

3. **公開ページで価格確認**
   - `https://rapidapi.com/japan-offmall-cn` を開く
   - Basic/Pro プランが表示され、Price が表示されていれば成功

### ロールバック
- 同じ手順で「Disable Pricing」または「Remove Plan」をクリック

---

## 7日後判定基準（critic v11-B）

| メトリクス | 判定 |
|-----------|------|
| 有料サブスク契約 ≥ 1件 | 成功 → 全APIへ展開 |
| 有料サブスク 0件 かつ runs 半減以下 | 失敗 → 無料復帰 |
| 有料サブスク 0件 だが runs 維持 | 判断保留 → 別戦略検討 |

---

## 検証エビデンス（2026-09-04）

### probe 結果
```json
{
  "auth_ok": true,
  "introspection_blocked": true,
  "graphql_reachable": true,
  "apis_count": 22,
  "introspection_message": "Introspection is not allowed"
}
```

### スキーマ逆探り（mutation signature）
```
mutation createApiSubscription($input: CreateApiSubscriptionInput!) {
  createApiSubscription(input: $input) {
    subscriptionId
  }
}
```
CreateApiSubscriptionInput 必須フィールド:
- `apiId: String!`
- `ownerId: String!`
- `billingPlanVersionId: String!`

### mutation 実行結果（recaptcha欠如）
```json
{
  "errors": [
    {
      "message": "Missing recaptcha token",
      "extensions": { "code": "BAD_USER_INPUT" }
    }
  ],
  "data": null
}
```

---

**生成日時**: 2026-09-04 (v14-A)
**タスク**: t_698fc46c
**担当**: kensho-revenue-worker (5e8ec4984bba)
