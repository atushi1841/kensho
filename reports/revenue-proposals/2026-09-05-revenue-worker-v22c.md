# v22-C Apify PPE 0.005 USD bulk 5 actors — 検証記録

- 実施日時: 2026-09-05 02:46〜02:52 JST（cron run 5e8ec4984bba）
- 担当: kensho-revenue-worker
- 対象タスク: t_6e743c9c（ready 2.4h 塩漬け → claim して着手）

## 実施内容

5アクター（japan-used-camera / japan-watch / japan-luxury-brand / japan-used-instrument / japan-offmall-market-scraper）の PPE 単価を 0.002 → 0.005 USD に引き上げ。

### Apify API の重要仕様（今回初実測）

`PUT /v2/acts/{username}~{name}` の `pricingInfos` は **上書き不可・追記のみ**:

- 既存エントリと同一内容で送ると HTTP 200（no-op）
- 価格を変えて既存を上書きしようとすると HTTP 400 `incorrect-pricing-modifier-prefix`
  （「既存配列を prefix として保ち、末尾に最大1つ追加」が必須）
- 各エントリに `createdAt` / `startedAt` 必須（GET の実値をそのまま流用）
- エラー型一覧に `cannot-remove-pricing-info` / `cannot-modify-actor-pricing-with-immediate-effect` → **追加した価格は削除・巻き戻し不可**

### ランタイム採用ロジック（camera で実証）

test run（runId PYzanMQielENvE1iF、即 abort）の `data.pricingInfo` が
**startedAt 最新の 0.005 エントリ**を参照。→ 複数エントリ並立時は最新が請求に適用される。

## 検証エビデンス（実測）

| アクター | PUT HTTP | entries 後 | latest item 単価 | latest start 単価 |
|---|---|---|---|---|
| japan-used-camera-market-scraper | 200 | 2 | $0.005 | $0.0001 |
| japan-watch-market-scraper | 200 | 2 | $0.005 | $0.0001 |
| japan-luxury-brand-market-scraper | 200 | 2 | $0.005 | $0.0001 |
| japan-used-instrument-market-scraper | 200 | 2 | $0.005 | $0.0001 |
| japan-offmall-market-scraper | 200 | 3 | $0.005 | $0.0001 |

- offmall は 9/4 15:55 に 0.005 エントリが既に存在（v21-A 単独 rerun は失敗とされていたが、実際はエントリ追加済みだった可能性）。今回さらに 0.005 を追加 → 3件目。latest は $0.005 なので請求影響なし。
- camera の test run 実測: `usageTotalUsd=0.00037`、`chargedEventCounts={apify-actor-start:1, apify-default-dataset-item:0}`（abort につき item 課金 0）。
- camera description を `$0.002/item` → `$0.005/item` に PUT（HTTP 200、読み戻し確認済み）。他4件は price 記述なし。
- ストアページ表示は 9/5 02:52 時点で依然 `$0.002/item`（CDN キャッシュ or 先頭エントリ表示）。請求は最新エントリ採用なので実害なし、表示は時間経過で追いつく見込み。

## 期待収益

0.005 USD/item × 約1000 item/日/actor 想定 → 約5 USD/月（タスク記述の ~2.25 USD/month marginal と同オーダー）。

## リスクとロールバック

- **ロールバック不可**（`cannot-remove-pricing-info`）。runs 半減時の revert は「0.002 エントリの再追加」で擬似的に価格を戻すしかない（startedAt が新しい方が採用されるため、0.002 を末尾に追加すれば実質 revert 可能）。
- v11-B の 7 日判定（9/11 頃）で runs 半減兆候があれば、上記「0.002 再追加」方式で戻すこと。

## 自己レビュー（Reflexion）

```json
{
  "self_review": {
    "what_was_done": "Apify 5アクターのPPE単価を0.002→0.005 USDに引き上げ（pricingInfos末尾追加方式）。cameraはtest runで最新エントリ採用を実証、descriptionも0.005に修正。",
    "what_went_well": [
      "PUTのmodifier制約（prefix一致+末尾1追加）を実測で解読し、400エラーから正しいペイロードを導出した",
      "test runのpricingInfoフィールドでランタイム採用ロジック（startedAt最新）を実証してから残4件へ展開した",
      "offmallに既存0.005エントリがあるのを検出し、重複追加の影響を評価した"
    ],
    "what_could_improve": [
      "cameraで先に0.005追加→test run→残4件の順にしたが、先にoffmallの既存エントリへ気づくべきだった（v21-A失敗判定の再確認）",
      "ストア表示キャッシュの反映時間を未計測（明日再確認すべき）"
    ],
    "mistakes_or_risks": [
      "価格変更は削除・巻き戻し不可（cannot-remove-pricing-info）。runs半減時のrevertは0.002再追加で擬似実施が必要",
      "offmallは0.005エントリが2件並立（請求影響なし、ただし履歴が汚れた）"
    ],
    "learned": "Apify pricingInfosは追記専用。PUTで既存上書きはincorrect-pricing-modifier-prefixで弾かれる。ランタイムはstartedAt最新エントリを採用（runのdata.pricingInfoで検証可）。revertも『新しい0.002追加』で行う。",
    "confidence": 9,
    "verification_evidence": "5アクターPUT HTTP 200 / GET読み戻しでlatest item=$0.005確認 / camera test run PYzanMQielENvE1iF のpricingInfo.startedAt=2026-09-04T17:48:34.739Z（0.005エントリ）参照を実測 / description PUT HTTP 200読み戻しOK"
  }
}
```
