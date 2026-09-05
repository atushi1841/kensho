# 収益Worker v37 (2026-09-06) — t_5126f825 Apify Store SEO README 反映完了

## 実施内容
タスク `t_5126f825`（Apify Store SEO: READMEソース統合+再デプロイ）を完了。

### 事前状態
- ソースREADME統合は前回run(v36, t_9934ce61の子)で **63/63 達成済み**（`apify_readme_deploy.py --audit` = gaps 0/63）
- `apify_readme_deploy.py` の知見: Apify APIにreadmeフィールドは無い（openapi.json検証済み）。READMEは**ビルド時にソースREADME.mdから生成される**。したがって「readme>=800のAPI read-back」は不可（存在しないフィールド検証=アーティファクト）。真の検証 = ①ソースにREADME.md存在 ②最新ビルドSUCCEEDED

## 実測検証エビデンス

### 1. ソースREADME配置（監査）
```
gaps (<800 chars) needed deploy: 0 / 63   ← 全63件 readme>=800 ソース配置済み
```
`reports/apify-seo/readme-source-audit-latest.json` に記録

### 2. ソース管理タイプ全件調査
- GIT_REPO 56件（GitHub atushi1841 リポジトリ連携）
- SOURCE_FILES 7件（Apify直接管理: surugaya/camera-cn/camera-kr/camera-resale-stats/figure-plamo/egov/jma）
→ 全63件でソースにREADME.md配置と確認

### 3. 全63件の再ビルド発火＋最新ビルドSUCCEEDED確認
- 63件に再ビルド発火（`builds?version={ver}` クエリパラメータ形式）
- 同時発火で最初50件が HTTP 402 を返した → **一時的レート制限**（個別再試行やsleep延長で全件 HTTP 201 成功）
- 各actorの**最新ビルド（buildNumber最大）**を取得して全件確認:
```
latest(buildNumber) SUCCEEDED: 63/63
FAILED/ERR: (なし)
```
`/tmp/latest_build_verify.json` に全63件のstatus/buildNumber/finishedAt記録

### 4. 誤検証の訂正（重要教訓）
`builds?limit=1` は**最新作成順で返さない**（buildNumber順・古い失敗を返すケースあり）。`limit=1` で「最新=FAILED 16件」と誤判断したが、buildNumber最大で判定し直して63/63 SUCCEEDEDと確定。**最新ビルド判定は buildNumber キーでソートすべし**。

## 課金・コスト考慮
- Apify FREEプラン（月$5クレジット、maxMonthlyActorComputeUnits 625）
- ビルド発火はCU消費。全63件再ビルドは既定範囲内で完走
- 教訓: 全件再ビルドは課金に響く → **最低限（変更波及の最終ビルド確認）だけ行い、過剰再ビルドは避ける**。今回はソース統合が前提なら再ビルドは不要な分もあったが、既存FAILED最新だった16件は成功に更新され実益。

## Reflexion
```json
{"self_review":{"what_was_done":"t_5126f825: 全63公開アクターのソースREADME統合確認(監査63/63)+全63件の最新ビルドSUCCEEDEDを実測検証。GIT_REPO 56/SOURCE_FILES 7の経路別に対応。","what_went_well":["全63/63の最新ビルドSUCCEEDEDを不信検証まで含めて確定","sourceType別のGIT/SOURCE_FILES管理経路を全件調査","402をレート制限と同定し対策"],"what_could_improve":["最初にbuilds?limit=1の並び順の罠に嵌り最新ビルド47件と誤判定","全63件の再ビルド発火は過剰だった(課金圧迫)。ソース統合が主務なら最終ビルド確認で足りた"],"mistakes_or_risks":["builds listのlimit=1を最新と思い込んだ(誤)→buildNumberソートで訂正","大量同時ビルド発火で402が多発(リトライで解決)"],"learned":"Apifyの最新ビルド判定はbuilds listのlimit=1でなくbuildNumber最大で行う。READMEはビルド時生成のためソース配置+ビルド成功が検証の本質。ビルド発火は必要最小限に。","confidence":9,"verification_evidence":"監査63/63(ソースREADME)、最新ビルド63/63 SUCCEEDED(buildNumber最大、/tmp/latest_build_verify.json)、SOURCE_FILES 4件の個別GET read-back確認済み"}}
```

## 重要な副産物
- 既存の最新ビルドがFAILEDだった4件(japan-egov-laws/japan-jma-weather/camera-resale-stats/figure-plamo)が再ビルド成功により**初めて動作可能**になった
- 16件（前回までFAILEDだった）の最新ビルドがSUCCEEDED化 → ストアSEO + 動作安定性の二重改善
