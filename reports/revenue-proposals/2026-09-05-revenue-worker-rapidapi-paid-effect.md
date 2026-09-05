# RapidAPI 有料プラン 2週間効果測定 — 導入 (t_868caac2)

タスク: t_868caac2（収益化提案: RapidAPI公開APIへの有料プラン導入テスト FREEMIUM→PAID。2週間で効果を測定）
実施: 2026-09-05 JST（baseline 取得日）
対応Worker: kensho-revenue-worker

## 目的と分担

本体カード t_868caac2 は次の2つを指示していた:
1. GraphQLで公開API1本に PAID プランをテスト設定 ← **価格設定は並行カードが実施済み**
   - t_bcd0e525(v17-B): API-direct(GraphQL)で japan-offmall-cn / japan-camera に 3-tier 設定
   - t_60f5b5de(v11-A 再開): goo-net JP の full PAID化を実行中（free 500K tier 退役）
2. **2週間で効果を測定する** ← 本タスクが実装したのはこの「測定」部分

測定期間: baseline 2026-09-05 から 2週間（〜9/19）。日次で scripts/rapidapi_paid_effect.py を実行し
state に point 追加 → kensho_revenue_collect.py が revenue-daily.json に日次添付。

## 経緯・並行カードとの結合（重要）

実施中に並行カード t_25a7704e(v26-1) が同じファイルを拡張・commit(6631fee) した:
- scripts/rapidapi_paid_effect.py を consumer/orphan モデル（`current` フラグ）に拡張し、
  対象を v26-1 で有料化した5本（japan-kakaku/rent/watch/luxury/instrument）含む計8本に拡大。
- 本タスクの測定スクリプトは v26-1 が canonical として保有 → **本タスクは上書きせず整合**。
  消費者向け(現在)バージョンと DB 残骸(orphan)を区別する v26-1 の方が正確。

**本タスク固有の非重複貢献 = daily収集への配線**:
- kensho_revenue_collect.py の attach_rapidapi_paid_effect_keys()（HEAD に無かった唯一の欠落）
  → revenue-daily.json に当日の有料プラン効果を日次添付。v18-B の attach と同一パターン。
- 既存/新規 state 両形式に互換（attapi で 8 API を実測確認：paid_plan=True / 有効単価一致）
- tests/test_rapidapi_paid_effect.py を canonical measure_api に整合（11件パス）

## 実装した測定基盤（読み取り専用・mutationなし）

測定本体 scripts/rapidapi_paid_effect.py は v26-1 が canonical（本タスクの初期実装が基盤）。
本タスクが追加したのは collector への日次配線（下記）。
- 各 API（japan-used-car / japan-offmall-cn / japan-camera）の tier(BASIC/PRO/ULTRA) ごとに:
  - ACTIVE バージョン一覧（単価・period・購読者数）
  - 実効単価（billinglimit.overageprice / perusageprice の実体）
  - 有料subscriber数 / 無料(月500K)subscriber数
  - hygiene 警告: 同一 tier の複数 ACTIVE（単価競合）/ 有料・無料共存（無料逃げ込み）
- 出力: data/rapidapi_paid_effect_state.json（日付キーで point 追加・直近30日保持）
- 認証: /mnt/d/Project2/goo-net-car-scraper/rapidapi_auth.json（既存クレデンシャル再利用）

改修: scripts/kensho_revenue_collect.py
- attach_rapidapi_paid_effect_keys(): revenue-daily.json エントリに当日の有料プラン効果を添付
  （v18-B の attach_apify_ppe_external_views_keys と同一パターン・純粋読み取り）
- main() に組み込み

テスト: tests/test_rapidapi_paid_effect.py（11件）— ネットワーク非依存
- 無料月500K判定（hard/soft）、per-call単価取得、hygiene警告(consumer/orphan)、attachロジック(fallback含む)

## Baseline 測定結果（2026-09-05 実測・読み取り専用）

全 8 API（v26-1 の5本含む）に PAID プラン（$0.001/0.005/0.01）を設定済み。
consumer(消費者向けcurrent) 版で購読者0、有料プランは稼働（paid_plan_active=True）。
しかし各 API の BASIC には無料 MONTHLY-500K の **orphan(非current)版が残存**しており、
既存購読者はオーファン版に掴まっている（無料逃げ込みリスク）。実効単価はおおむね下記:

| API | vis | BASIC | PRO | ULTRA |
|-----|-----|-------|-----|-------|
| japan-used-car | PUBLIC* | $0.001 | $0.005** | $0.01 |
| japan-offmall-cn | PRIVATE | $0.001 | $0.005 | $0.01 |
| japan-camera | PUBLIC | $0.001 | $0.005 | $0.01 |
| japan-kakaku/rent/watch/luxury/instrument | PUBLIC | $0.001 | $0.005 | $0.01 |

*v26-1 で新設・有料化した5本。**goo-net(japan-used-car) PRO は v11-A/v17-B での乱積みで
過去 ACTIVE 版が複数（$0.00003〜$0.02）残るが、consumer=now 版は $0.005 で正常。
visibility は GraphQL で値が不安定な field 挙動あり（非依存）。

### 重要な発見（有料化を妨げる実測事実）

1. **無料オーファン版が各APIのBASICに残存**: 全 API で builder/DB に無料 MONTHLY-500K
   バージョンが残る（consumer ではない=市場で今は選択不可。だが既存購読者はオーファン版に掴まったまま）。
   実収益 $0 の原因。free tier 退役(削除)が完了するまで有料転換は進まない。
2. **goo-net(japan-used-car) に過去の単価乱積み**: v11-A/v17-B の updateBillingPlan 連打で
   PRO に多数の ACTIVE 版（$0.00003〜$0.02）が残存。consumer=now は $0.005 で正常だが、
   状態としては汚れており将来の価格変更時に曖昧になりうる。機会を見てクリーン化推奨。
3. **既存無料購読者はオーファン版から転換不能**: paid_effect では consumer 購読者0。
   free 版に掴まった購読者は free tier 削除(退役)時に解約/移行の決断を迫られる。

→ 測定基盤は正常稼働・実測値取得。**有料収益($>0)の発生は free tier 退役後に初めて観測可能**。

## 検証レコード
- reports/revenue-proposals/rapidapi-paid-effect-20260905_072213.json（実測値・全 tier 詳細）
- data/rapidapi_paid_effect_state.json（baseline point 保存）
- pytest: tests/test_rapidapi_paid_effect.py + test_revenue_collect.py 全パス（23件）
- mypy --follow-imports=skip scripts/rapidapi_paid_effect.py: 0 error
  （rapidapi_pricing_set.py の type-arg 警告は commit 9e2a4a3 以前の既存もの・本タスク対象外）

## 運用

日次収集（kensho_revenue_collect）が state を読み revenue-daily.json に添付。2週間後（〜9/19）に
paid subscriber 数・有料プラン稼働状況の推移を revenue-daily.json の rapidapi_paid_effect キーで評価。
コスト: 読み取りのみ（GraphQL 数クエリ/日）。
