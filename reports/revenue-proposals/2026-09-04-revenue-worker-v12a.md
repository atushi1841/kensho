# 2026-09-04 Revenue Worker — t_19bca94c Apify PPE課金ライブ検証（v12-A）

## 実施内容
1. **PPE設定のライブ検証**（critic要求: pricingInfos API + Store表示 + 20%マージン）
   - Apify API: `GET /v2/acts/{id}` で5アクターの `pricingInfos` を実測
   - Apify Store公開ページ: `curl https://apify.com/fruitful_quintessence/<actor>` で価格表示を確認
2. **検証経路の障害発見・修復**: revenue-daily.json の 9/4 00:20 エントリが `actors_ppe=0`（billing/price/actual_nameフィールド欠落）→ 原因はプロファイル側コピーの古い収集スクリプト（9/2版、t_1323b323修正前）が `kensho-revenue-report.sh` のフォールバックで実行されていたこと。プロファイルコピーを最新版へ同期し、再収集で ppe=25 を回復。

## 検証エビデンス（実測）

### 1. pricingInfos API（HTTP 200・5アクター全件）
| アクター | ID | pricingModel | dataset-item単価 | actor-start単価 | Apifyマージン |
|---|---|---|---|---|---|
| japan-used-camera-market-scraper | mQaZFo6up4YZKepC3 | PAY_PER_EVENT | $0.002 (primary) | $0.00005 | 20% |
| japan-watch-market-scraper | gMqdrS2evpcybSZc2 | PAY_PER_EVENT | $0.002 (primary) | $0.00005 | 20% |
| japan-luxury-brand-market-scraper | b0vuqa3ESvy2mOwFB | PAY_PER_EVENT | $0.002 (primary) | $0.00005 | 20% |
| japan-used-instrument-market-scraper | yN1R26HrV6C2MBKas | PAY_PER_EVENT | $0.002 (primary) | $0.00005 | 20% |
| japan-offmall-market-scraper | Zh4kqcS4dYPWpFzBd | PAY_PER_EVENT | $0.002 (primary) | $0.00005 | 20% |

### 2. Store公開ページ（ユーザー表示・HTTP 200）
- 全5ページに `Pay per event — $0.00005/run + $0.002/item` が表示されていることをcurl実測（`$0.002` が各ページ2箇所出現）
- 公開URLのユーザー名は `fruitful_quintessence`（`atushi1841` は404 — 教訓notepadと一致）

### 3. 収益イベント発火状況
- runs API: 直近の実行は全て自分（userId=VMz6nlpHoGIjTeSXS）の定期実行のみ。外部ユーザーによる課金イベント発火はまだ0件（9/5-9/11監視対象）

### 4. 修復後のrevenue-daily.json（9/4 05:00再収集）
- `actors_ppe=25 / actors_free=0 / actors_public=25`（camera runs=60, watch=54, luxury=53, instrument=54, offmall=122）
- pytest tests/test_revenue_collect.py: **22 passed**（4:42）

## 自己レビュー（Reflexion）
```json
{
  "self_review": {
    "what_was_done": "t_19bca94c: Apify PPE課金のライブ検証（pricingInfos API 5アクター実測 + Store公開ページの価格表示curl確認 + 20%マージン確認）。併せて検証経路の障害（プロファイル側コピーの古い収集スクリプトによるactors_ppe=0）を修復しrevenue-daily.jsonを回復。",
    "what_went_well": ["API・Store表示・集計ファイルの3層でエビデンス取得", "ppe=0異常の原因（profile側stale copy）を即座に特定しバックアップ後に修復", "pytest 22 passedで回帰なしを確認"],
    "what_could_improve": ["kensho-revenue-report.shがプロジェクト側でなくプロファイル側コピーを参照する二重管理構造自体は残存（将来リファクタ候補）", "pytest実行に282秒かかりセッション時間を圧迫"],
    "mistakes_or_risks": ["なし（変更はプロファイルスクリプト同期のみ、バックアップ2種+revenue-daily.json.bak保持済み）"],
    "learned": "cronのフォールバック収集は別コピーを実行していることがある。集計値が急に0/欠落したら『どのパスのスクリプトが走ったか』を最初に疑う。",
    "confidence": 9,
    "verification_evidence": "pricingInfos API HTTP200: 5アクター全件 PAY_PER_EVENT $0.002/item + $0.00005/run + margin 0.2 / Storeページcurl: 'Pay per event — $0.00005/run + $0.002/item' 表示確認 / revenue-daily.json 9/4 05:00: actors_ppe=25 / pytest 22 passed"
  }
}
```

## 申し送り
- 次回収集（9/5 00:20 reportフォールバック or 7:05 cron）で ppe=25 が維持されることを確認すること（維持されていれば修復完了、QAへ）
- 9/5-9/11: runs APIで外部ユーザー実行（≠VMz6nlpHoGIjTeSXS）が出たら課金発火。revenue-daily.jsonのactors_ppeと併せて監視
- t_4de26f84（PPE適用タスク）はt_79c58629で適用済みかつ本検証でライブ確認済み→次回workerでdone化判断可
