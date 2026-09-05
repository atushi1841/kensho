# RapidAPI goo-net JP 有料化・free 500K tier 退役の検証 — t_60f5b5de (v11-A)

実施: 2026-09-05 JST　対応Worker: kensho-revenue-worker
対象: goo-net JP = Japan Used Car Price Stats API (api_e093340e)（＋同構造の offmall-cn / japan-camera も同時検証）
手段: RapidAPI 内部 GraphQL API-direct（CDP 不使用）。rapidapi_auth.json 再利用。

## 目的（カード/UNBLOCK指示の再確認）

- 「goo-net JP に PAID プラン導入 → 7日計測」が本体。
- UNBLOCK: 「clean createBillingPlan + free 500K tier 退役 → full PAID化」。
- 前提 t_868caac2「GraphQLでは課金設定不可 → CDP必須」は、既に t_698fc46c(v14-A) と t_bcd0e525(v17-B) で反証済み（API-direct で課金は書ける）。本検証もそれに一致。

## 実測結果（2026-09-05 ライブ読取）

全3API・全 tier で **current 版の単価はすべて有料で LIVE**：

| API | BASIC current | PRO current | ULTRA current |
|-----|--------------|-------------|---------------|
| japan-used-car (goo-net JP) | $0.001 | $0.005 | $0.01 |
| japan-offmall-cn | $0.001 | $0.005 | $0.01 |
| japan-camera | $0.001 | $0.005 | $0.01 |

→ **goo-net JP の有料化は current 価格レベルでは既に達成済み**。新規購読者には FREE 選択肢は無い
（free 500K 版はすべて `current=False`＝販売対象外の履歴版）。

### 残留物（現状の実測）

- BASIC に **free 500K MONTHLY 版が旧版として共存**（current=False）。購読者 1人（既存・無料転換不能）が free 版に乗ったまま。
  - goo-net: 2 free 版（うち1版に購読者1）。offmall: 1版（購読者1）。camera: 1版（購読者1）。
- PRO に **単価競合する旧 ACTIVE 版が複数残留**（current=False）。goo-net 6版 / offmall 2版 / camera 1版。

## 退役が API のみで不可能な実証理由

`deleteBillingPlans(ids: [ID!]!)` は RapidAPI で唯一の削除ミューテーション。
- 引数は `ids: [ID!]!` のみ（追加引数なし）。
- これは **プラン単位（billingplan_xxx）** の削除。同一プラン内に free 版と有料 current 版が
  同居するため、プラン削除すると有料 current も消える（破壊的・不可）。
- version 単位の削除ミューテーションは存在しない（deleteBillingPlanVersion は None）。
- free/旧版 version id を `deleteBillingPlans(ids=[...])` に渡すと **FORBIDDEN
  「You are not authorized to perform this action」** を返す。
- `upsertBillingPlanAndVersion` は入力が `{apiId, apiName, apiVersionId, apiVersionName, providerName}`
  のみ（価格/limit を運ばない）ため退役の手段にならない。

→ **free 500K / 旧 ACTIVE 版の「version単位退役」は Studio UI（ブラウザ/CDP）でのみ可能**。
本セッションでは CDP9222 起動なし・cua/UI自動化不能（スキル: rapidapi-studio-publishing）のため未実施。

## 実装（安全・冪等・再実行可能）

`scripts/rapidapi_pricing_set.py` に `--retire-free-tier [--apply]` を追加:
- 各プランを「有料 current 保持」で保護。純 free プランのみ `deleteBillingPlans` で削除試行。
- 有料 current 併存プランはプラン削除せず `studio-ui-required`（version単位退避が要る旨）に分類。
- dry-run 既定。実測の DRY-RUN: goo-net BASIC(2 free / sub1) と PRO(6旧版) は
  studio-ui-required、ULTRA は none。破壊的削除は一切発生しないことを確認。
- レコード: reports/revenue-proposals/rapidapi-retire-free-tier-20260905_075208.json

## 結論と推奨

1. **goo-net JP（＋他2本）の有料化は成立**（current 価格=全PAID）。測定は既存
   `scripts/rapidapi_paid_effect.py` の日次収集で継続中（baseline 2026-09-05、〜9/19）。
2. 残る「free 500K / 旧 ACTIVE 版の削除」は**収益上の新規ブロッカーではない**（current のみ販売）が、
   整理のため **1回の Studio UI 操作**（ブラウザで free/旧版を無効化 or 削除）が望ましい。
   これは人 or CDP可用ブラウザでの手動手順。削除 API が FORBIDDEN であることを踏まえ、UI 一定の
   手順書（各プランの有料 current を確認 → 非 current の free/旧版を消す）が必要。

## 検証レコード
- reports/revenue-proposals/rapidapi-retire-free-tier-20260905_075208.json
- reports/revenue-proposals/rapidapi-retire-free-tier-20260905_075058.json
