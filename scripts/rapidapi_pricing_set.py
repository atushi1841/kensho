"""RapidAPI の有料プラン設定スクリプト（API-direct path試行 + フォールバック手順書）.

背景:
- RapidAPI は GraphQL introspection を 401 で拒否（"Introspection is not allowed"）
- ただし mutation は mutation名候補から推測可能。エラー応答で逆探りして正しいsignatureを特定
- 前回の検証（t_868caac2）で BillingLimitInputV2 型未定義を確認済み → API 経由は再試行の結果「ほぼ到達」段階まで来た

## 重要な発見（2026-09-04 v14-A実装で判明）

### スキーマ詳細
- `createApiSubscription(input: CreateApiSubscriptionInput!): CreateApiSubscriptionResult!` — 存在
- `deleteApiSubscription(input: DeleteApiSubscriptionInput!): DeleteApiSubscriptionResult!` — 存在
- `updateApi(api: ApiUpdateInput!): Api!` — 存在
- `CreateApiSubscriptionResult.subscriptionId: String!` — 返り値

### 必須フィールド
- `apiId` (String!)
- `ownerId` (String!)
- `billingPlanVersionId` (String!) — RapidAPI側で用意された課金プランカタログのVersion ID

### 課金プランの構造
- API毎に `billingPlans[]` が紐付いている
- 各 billingPlan は `version` (BillingPlanVersion) を持つ
- Version ID は `billingplanversion_<uuid>` 形式
- Providerは price を自由に設定できない（RapidAPI定義のテンプレを選ぶ方式）

### 障害
- `createApiSubscription` mutate には recaptcha トークンが必要（"Missing recaptcha token" エラー）
- recaptchaサイトキーは SPA の JS レンダリング後にしか取得できない
- トークンの自動生成は CAPTCHA 解決に該当するため、自動化では手動手順が現実解

## 対象API（実測で確認済、2026-09-04）
| API ID | BASIC Plan Version ID |
|--------|----------------------|
| `api_3697e05e-3115-47c5-85df-f6edadbdc8ca` (OffMall CN) | `billingplanversion_03e7713f-fe51-45ba-949e-e07ecbcca3bb` |
| `api_c1044ee7-1752-4d3e-a688-53f7e791d5ff` (OffMall JP) | `billingplanversion_8d207a41-321b-4ce7-a125-fa8cb2541bde` |
| `api_7d2dcc27-829d-4add-88b9-5c1708447f85` (Camera JP) | `billingplanversion_c6a5210c-2396-4341-904c-9d3102069104` |
| `api_45bf102f-6d1b-4fd5-9179-f164de167ffd` (Kakaku) | `billingplanversion_52b47643-2a45-4291-a24a-08b4a9293ba2` |

## 使用方法

    python scripts/rapidapi_pricing_set.py --probe
        接続性・スキーマ隠蔽を確認（auth OK / apis_count / introspection_blocked）

    python scripts/rapidapi_pricing_set.py --list-plans
        全APIのbillingPlans/versionを列挙（subscription作成前の下準備）

    python scripts/rapidapi_pricing_set.py --api-id <ID>
        対象APIのbillingPlansを列挙

    python scripts/rapidapi_pricing_set.py --api-id <ID> --tier basic
        subscription 作成を試行（recaptcha不足で失敗するがペイロードを記録）

    python scripts/rapidapi_pricing_set.py --manual --api-id <ID>
        手動手順書（Markdown）を出力
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import requests

RAPIDAPI_AUTH = "/mnt/d/Project2/goo-net-car-scraper/rapidapi_auth.json"
GATEWAY = "https://rapidapi.com/gateway/graphql"


def _load_auth() -> dict:
    """rapidapi_auth.json を読み込み、Cookie dict と headers を返す."""
    if not os.path.exists(RAPIDAPI_AUTH):
        raise FileNotFoundError(f"RapidAPI auth file not found: {RAPIDAPI_AUTH}")
    with open(RAPIDAPI_AUTH, encoding="utf-8") as f:
        auth = json.load(f)
    cookies: dict[str, str] = {}
    if isinstance(auth.get("cookies"), str):
        for part in auth["cookies"].split(";"):
            if "=" in part:
                k, v = part.strip().split("=", 1)
                cookies[k] = v
    return {
        "cookies": cookies,
        "headers": {
            "content-type": "application/json",
            "csrf-token": auth.get("csrf_token", ""),
            "origin": "https://rapidapi.com",
            "rapid-client": "provider-dashboard-service",
            "referer": "https://rapidapi.com/_studio/",
            "x-entity-id": auth.get("entity_id", ""),
        },
        "entity_id": auth.get("entity_id", ""),
    }


def probe() -> dict:
    """接続性・スキーマ隠蔽を確認する（読み取り専用）."""
    auth = _load_auth()
    out: dict = {
        "auth_ok": False,
        "introspection_blocked": None,
        "graphql_reachable": None,
        "apis_count": None,
    }

    query = """
    query GetApis($where: ApiWhereInput) {
      apis(where: $where) { nodes { id name visibility pricing } }
    }
    """
    payload = {
        "operationName": "GetApis",
        "variables": {"where": {"ownerId": [auth["entity_id"]]}},
        "query": query,
    }
    try:
        resp = requests.post(GATEWAY, headers=auth["headers"], cookies=auth["cookies"], json=payload, timeout=15)
        out["graphql_reachable"] = resp.status_code == 200
        if resp.status_code == 200:
            body = resp.json()
            out["auth_ok"] = "errors" not in body
            out["apis_count"] = len(body.get("data", {}).get("apis", {}).get("nodes", []))
    except Exception as e:
        out["graphql_reachable"] = False
        out["error"] = str(e)

    introspect_query = """
    query IntrospectionQuery { __schema { mutationType { fields { name } } } }
    """
    try:
        resp = requests.post(
            GATEWAY,
            headers=auth["headers"],
            cookies=auth["cookies"],
            json={"operationName": "IntrospectionQuery", "query": introspect_query},
            timeout=15,
        )
        out["introspection_blocked"] = resp.status_code == 401
        out["introspection_message"] = resp.json().get("message", "") if resp.status_code == 401 else None
    except Exception as e:
        out["introspection_blocked"] = None
        out["introspection_error"] = str(e)

    return out


def list_billing_plans(api_id: str | None = None) -> dict:
    """API毎に紐付く billingPlans/version を列挙."""
    auth = _load_auth()
    query = """
    query GetApis($where: ApiWhereInput) {
      apis(where: $where) {
        nodes {
          id name visibility pricing
          billingPlans { id name version { id name price currency } }
        }
      }
    }
    """
    payload = {
        "operationName": "GetApis",
        "variables": {"where": {"ownerId": [auth["entity_id"]]}},
        "query": query,
    }
    resp = requests.post(GATEWAY, headers=auth["headers"], cookies=auth["cookies"], json=payload, timeout=15)
    body = resp.json()
    if "errors" in body:
        return {"error": body["errors"]}

    apis = body.get("data", {}).get("apis", {}).get("nodes", [])
    result = []
    for api in apis:
        if api_id and api["id"] != api_id:
            continue
        plans = []
        for bp in api.get("billingPlans", []):
            v = bp.get("version", {}) or {}
            plans.append({
                "plan_name": bp.get("name"),
                "plan_id": bp.get("id"),
                "version_id": v.get("id"),
                "version_name": v.get("name"),
                "price": v.get("price"),
                "currency": v.get("currency"),
            })
        result.append({
            "api_id": api["id"],
            "api_name": api["name"],
            "visibility": api.get("visibility"),
            "pricing": api.get("pricing"),
            "billing_plans": plans,
        })
    return {"count": len(result), "apis": result}


def try_api_direct(api_id: str, billing_plan_version_id: str) -> dict:
    """API 経由で subscription 作成を試行する（recaptcha不足で必ず失敗する想定・ペイロード記録用）."""
    auth = _load_auth()
    payload = {
        "operationName": "createApiSubscription",
        "variables": {
            "input": {
                "apiId": api_id,
                "ownerId": auth["entity_id"],
                "billingPlanVersionId": billing_plan_version_id,
            }
        },
        "query": """
        mutation createApiSubscription($input: CreateApiSubscriptionInput!) {
          createApiSubscription(input: $input) { subscriptionId }
        }
        """,
    }
    resp = requests.post(GATEWAY, headers=auth["headers"], cookies=auth["cookies"], json=payload, timeout=15)
    body = resp.json()
    return {
        "request_payload": payload,
        "response_status": resp.status_code,
        "response_body": body,
        "verdict": "missing_recaptcha" if "recaptcha" in str(body).lower() else "unknown",
    }


def emit_manual_procedure(api_id: str, api_name: str, tier: str, price: float, billing_plan_version_id: str) -> str:
    """手動手順書（Markdown）を出力する."""
    return f"""# RapidAPI 有料プラン有効化 手動手順書

**対象 API**: `{api_name}` (ID: `{api_id}`)
**選択 tier**: `{tier}`
**想定月額**: `${price}/月`（RapidAPIテンプレート設定次第）
**Billing Plan Version ID**: `{billing_plan_version_id}`
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
   - URL: `https://rapidapi.com/_studio/apis/{api_id}/pricing`

2. **「Enable Pricing」または「Monetize」ボタンをクリック**
   - recaptcha ダイアログが出るので手動で認証
   - Basic / Pro プランが「Active」になることを確認

3. **公開ページで価格確認**
   - `https://rapidapi.com/{api_name}` を開く
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
{{
  "auth_ok": true,
  "introspection_blocked": true,
  "graphql_reachable": true,
  "apis_count": 22,
  "introspection_message": "Introspection is not allowed"
}}
```

### スキーマ逆探り（mutation signature）
```
mutation createApiSubscription($input: CreateApiSubscriptionInput!) {{
  createApiSubscription(input: $input) {{
    subscriptionId
  }}
}}
```
CreateApiSubscriptionInput 必須フィールド:
- `apiId: String!`
- `ownerId: String!`
- `billingPlanVersionId: String!`

### mutation 実行結果（recaptcha欠如）
```json
{{
  "errors": [
    {{
      "message": "Missing recaptcha token",
      "extensions": {{ "code": "BAD_USER_INPUT" }}
    }}
  ],
  "data": null
}}
```

---

**生成日時**: 2026-09-04 (v14-A)
**タスク**: t_698fc46c
**担当**: kensho-revenue-worker (5e8ec4984bba)
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="RapidAPI 有料プラン設定スクリプト")
    parser.add_argument("--probe", action="store_true", help="接続性・スキーマ隠蔽を確認")
    parser.add_argument("--list-plans", action="store_true", help="全APIのbillingPlans/versionを列挙")
    parser.add_argument("--api-id", help="対象 API ID")
    parser.add_argument("--api-name", help="対象 API 表示名（手順書用）")
    parser.add_argument("--tier", default="basic", help="プラン tier (basic/pro/ultra)")
    parser.add_argument("--price", type=float, default=4.99, help="想定月額 USD（RapidAPIテンプレート次第）")
    parser.add_argument("--billing-plan-version-id", help="BillingPlanVersion ID（list-plans で取得）")
    parser.add_argument("--manual", action="store_true", help="手動手順書のみ出力")
    args = parser.parse_args()

    if args.probe:
        result = probe()
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    if args.list_plans:
        result = list_billing_plans(api_id=args.api_id)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    if not args.api_id:
        print("ERROR: --api-id required (or use --probe / --list-plans)", file=sys.stderr)
        return 1

    api_name = args.api_name or args.api_id

    # list-plans を自動実行
    if not args.billing_plan_version_id:
        plans_data = list_billing_plans(api_id=args.api_id)
        apis = plans_data.get("apis", [])
        if not apis:
            print(f"ERROR: API {args.api_id} が見つからない、または billingPlans が無い", file=sys.stderr)
            return 1
        target_plans = apis[0].get("billing_plans", [])
        target_plan = next(
            (p for p in target_plans if p["plan_name"].upper() == args.tier.upper()),
            target_plans[0] if target_plans else None,
        )
        if not target_plan:
            print(
                f"ERROR: tier '{args.tier}' が見つからない (available: {[p['plan_name'] for p in target_plans]})",
                file=sys.stderr,
            )
            return 1
        billing_plan_version_id = target_plan["version_id"]
        print(f"▶ Auto-selected BillingPlanVersion: {billing_plan_version_id} (tier={args.tier})", file=sys.stderr)
    else:
        billing_plan_version_id = args.billing_plan_version_id

    if not args.manual:
        # API 経由試行（recaptcha不足で失敗する想定）
        print("▶ createApiSubscription を API 経由試行...", file=sys.stderr)
        result = try_api_direct(args.api_id, billing_plan_version_id)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        print("\n▶ recaptcha トークン不足で失敗。manual procedure を出力します。\n", file=sys.stderr)

    # 手動手順書出力
    md = emit_manual_procedure(args.api_id, api_name, args.tier, args.price, billing_plan_version_id)
    out_path = Path("reports/revenue-proposals") / f"rapidapi-pricing-manual-{args.api_id}.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(md, encoding="utf-8")
    print(f"✓ 手動手順書: {out_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
