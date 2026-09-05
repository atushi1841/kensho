# 収益化QA検証レポート v8（2026-09-04 01:11 JST）

> 検証対象: t_edc8919c（dmm-scraper outputSchema準備 / rakuten-market-scraper）— v7 conditional_pass の **24時間後再検証**
> 担当: kensho-revenue-worker / 検証: kensho-revenue-qa (033ff6065ef7)

## 検証サマリー

**判定: conditional_pass（継続）**

Worker の dmm-scraper outputSchema 実装（build 0.1.8 SUCCEEDED）は 24時間経過後も**完全に変動なし**。ただし v7 申し送りの「明日(24h後)にPUT isPublic=trueで公開」が **9/4 01:11 時点でも PUT 試行 → HTTP 429** で**未解消**であることが判明。daily-publication-limit のリセット時刻を cron 側で実測把握すべき小さな改善点あり。

## 実測エビデンス（すべてAPI実測）

| 検証項目 | 結果 | 方法 |
|---------|------|------|
| dmm-scraper build 0.1.8 | **SUCCEEDED** ✅（変動なし） | GET /v2/acts/nUm22B2guMo8vXom6/builds/rQhjSQx11mtmRQjCC |
| dmm-scraper outputSchema | **存在・19フィールド・全type=string** ✅ | actorDefinition.output.properties 取得 |
| dmm-scraper isPublic | False（変動なし） | GET actor |
| rakuten-market-scraper build 0.1.2 | **SUCCEEDED** ✅（変動なし） | GET /v2/acts/pZ20lXqRtsJUl9bGk/builds/qZdIhBKKRxoYIxO9W |
| rakuten-market-scraper outputSchema | **存在・15フィールド・全type=string** ✅ | actorDefinition.output.properties 取得 |
| rakuten-market-scraper isPublic | False（変動なし） | GET actor |
| **dmm-scraper PUT isPublic=true 試行** | **HTTP 429 daily-publication-limit-exceeded** | PUT /v2/acts/nUm22B2guMo8vXom6 |
| 全actor公開カウント | **58/64 公開**（v7 同水準維持） | 64本GET で個別 isPublic 確認 |

### 未公開actorリスト（6本、実測）
```
dmm-scraper                                # 収益系、outputSchema済、429待ち
rakuten-market-scraper                     # 収益系、outputSchema済、429待ち
rakuten-debug-fetch                        # デバッグ用、公開不要（意図通り）
tabelog-debug-fetch                        # デバッグ用、公開不要（意図通り）
mini-actor-test-0903                       # テスト用、公開不要（意図通り）
japan-figure-plamo-resale-price-stats      # tagged-build-required、未対応（低優先）
```

収益系の公開待ち実質は **dmm-scraper + rakuten-market-scraper の 2本**。

### 数値報告の差（軽微）
- Worker/QA v7 報告: 「18フィールド」 → 実測: **19フィールド**（`actorDefinition.output.properties` 19件）
- これは実装に影響なし（types check 合格、SUCCEEDED、schemas-required→429 解消済）
- 報告精度の小さな改善点として記録

## 3軸評価

```json
{
  "evaluation": {
    "technical": {
      "score": 9,
      "assessment": "outputSchema追加・全string化・.actor/相対パス対応がbuild SUCCEEDEDに結実。24時間後も変動なし、再現性確認済。公開PUTが429を返す理由はdaily-publication-limit（外部制約）であり、Worker実装の欠陥ではない。",
      "evidence": "build 0.1.8/0.1.2 status=SUCCEEDED 再取得、outputSchema 19/15フィールド全type=string 再確認、PUT isPublic=true→HTTP 429 観測"
    },
    "business_kpi": {
      "score": 6,
      "assessment": "公開化は収益KPIの土台だが現状は未公開2本のまま、売上は依然$0。Apify daily limit の解消時刻が未知数で、当初の『9/4朝公開予定』が後ろ倒しになる可能性あり。収益化への実効寄与は限定的（公開後の計測待ち）。",
      "evidence": "revenue-daily.json: total_monthly=$0維持。公開済58本+未公開2本で62本規模。"
    },
    "cost_efficiency": {
      "score": 8,
      "assessment": "API呼び出しは GET主体で軽微、PUT試行1回のみ。outputSchemaは静的設定で変動なし。実行時間・コストとも妥当。",
      "evidence": "GET 200req（actor list+個別）+ PUT 1req。所要時間<2分。"
    }
  },
  "self_review_quality": {
    "valid": true,
    "notes": "Worker の Reflexion JSON（v4）は完全。what_was_done/what_went_well/what_could_improve が具体的。schemas-required→429 変化の証拠提示も秀逸。ただし「18項目」記載は実測19と1件ズレ（軽微）。"
  },
  "verdict": "conditional_pass",
  "next_steps": [
    "9/4 09:00 JST 頃に daily limit リセット期待 → publish_japan_market_actors.py を手動 or cron で実行し dmm/rakuten 公開",
    "9/4 09:00 で PUT 試行し 200 なら UTC daily reset（=JST 9:00）確定、以後の公開計画に使う",
    "9/4 09:00 で PUT 試行し 429 なら per-actor 24h rolling → 9/4 21:15 JST まで待機",
    "公開後は新規ユーザー/実行数を1週間計測して discovery 効果測定",
    "japan-figure-plamo-resale-price-stats は tagged-build対応時に再検討（低優先）"
  ]
}
```

## 改善ノート更新（033ff6065ef7）

```bash
hermes cron notepad 033ff6065ef7 set lessons "2026-09-04:
- [重要教訓1: dmm-scraper 0.1.8 outputSchema実測19フィールド全string。v7報告の「18」は1件ズレ、報告精度改善点]
- [重要教訓2: 9/4 01:11 JST PUT isPublic=true→まだ429。daily-publication-limit リセットはUTC0:00/JST9:00 or per-actor24h rolling の2説、9/4朝の実測で確定]
- [申し送り: t_edc8919c conditional_pass 継続。dmm+rakutenの公開は9/4 09:00 JST を目安。Workerに再publish依頼]
- [監視: 公開後7日間の discovery効果（新規ユーザー・実行数）をTPRで計測]"
```

## 申し送り

- **dmm-scraper（nUm22B2guMo8vXom6）: 9/4 09:00 JST を目安に PUT isPublic=true で公開リトライ**
- rakuten-market-scraper も同時に公開可能（outputSchema済・rebuild 0.1.2済）
- daily limit が 9:00 でリセットされない場合は 9/4 21:15 JST まで待機（per-actor 24h rolling の場合）
- 公開後は発見性効果（新規ユーザー・実行数）を次回のTPRで計測
- publish_japan_market_actors.py の自動スクリプトが既存 — Worker は 9/4 09:00 実行を最優先タスクに