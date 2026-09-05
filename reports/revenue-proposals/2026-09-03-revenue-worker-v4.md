# Revenue Worker Report — t_edc8919c（dmm outputSchema準備）

**実施日時**: 2026-09-03 21:15 JST
**タスクID**: t_edc8919c
**タイトル**: 収益提案 Apify非公開3アクターの公開化
**担当**: kensho-revenue-worker

## タスク概要

Apify非公開アクターの公開化で発見性向上を図る。タスク名義の3アクター（japan-rent-market / camera-cn / camera-kr）は**全員public化済み**（API実測で確認）。実質残る非公開収益アクターは rakuten-market-scraper と dmm-scraper。本セッションでは、公開の前提となる **outputSchema欠如というブロッカーの解消（dmm-scraper）** を実装した。

## 実装前の状態（Before）

### 3名義アクター: 全員 public 済み（実測 GET）
- japan-rent-market-scraper → isPublic=True
- japan-camera-market-cn-scraper → isPublic=True
- japan-camera-market-kr-scraper → isPublic=True

### 残る非公開収益アクター（実測: 64本中6本非公開、うち収益系3本）
| アクター | 非公開理由 | 状態 |
|---------|-----------|------|
| rakuten-market-scraper | 日次公開上限5件（HTTP 429） | 前回outputSchema追加済 + rebuild成功（0.1.2）、公開は明日 |
| **dmm-scraper** | **schemas-required（outputSchema欠如）** | **本セッションで解消** |
| japan-figure-plamo-resale-price-stats | tagged-build-required | 未対応 |

## 実装内容

dmm-scraper（Apify actor id: nUm22B2guMo8vXom6）に `.actor/actor.json` を新規作成し、outputSchema（DMMItemの出力フィールド: cid/title/category/price_jpy/maker/series/genre/release_date/cast/review_star_avg等18項目）を定義。

### 変更ファイル
- `/mnt/d/Project2/dmm-scraper/.actor/actor.json`（新規）

### エラー経緯（実測）
1. **build 0.1.6 FAILED**: outputSchemaのproperty typeに integer/number を使った → **Apify validatorは全type="string"必須**であると判明
   - `price_jpy`, `review_star_avg`, `review_count` を string に修正
2. **build 0.1.7 FAILED**: 入力スキーマ参照パス誤り → `.actor/`配下はrepo配下の相対パスが必要。`./INPUT_SCHEMA.json` → `../INPUT_SCHEMA.json` に修正
3. **build 0.1.8 SUCCEEDED** ✅

### Git
- commit `75932ae`（outputSchema追加 + type修正 + path修正）を `origin/main` にpush（cmd.exe Windows認証）

## 検証エビデンス

### build成功（実測）
```
POST /v2/acts/nUm22B2guMo8vXom6/builds?version=0.1&useCache=0
→ HTTP 201, buildID rQhjSQx11mtmRQjCC
buildNumber 0.1.8, status=SUCCEEDED, finished 2026-09-03T12:07:33Z
```

### 公開Publishトライ（実測）
```
PUT /v2/acts/nUm22B2guMo8vXom6  {"isPublic": true}
→ HTTP 429 {"error":{"type":"daily-publication-limit-exceeded",
   "message":"You've reached the daily limit of 5 Actor publications. Try again in 24 hours."}}
```

**重要**: 以前は publish を試すと `{"type":"schemas-required"}`（outputSchema欠如）だったが、今回は **429（日次公開上限）** に変わった。outputSchemaブロッカーは解消され、唯一の残ブロッカーは「日次5件上限」のみ。明日以降（24h後）に公開可能。

### アクター状態確認
```
name: dmm-scraper, isPublic: False（公開待ち）
defaultRunOptions build: latest（0.1.8 が最新タグ）
```

## 自己レビュー (Reflexion)

```json
{
  "self_review": {
    "what_was_done": "タスク名義の3アクターが全員public済みと実測確認した上で、残る非公開収益アクター dmm-scraper の outputSchema欠如（schemas-required）という公開ブロッカーを解消。.actor/actor.json に全18フィールドのoutputSchemaを追加し、build 0.1.8をSUCCEEDEDにした。rakuten同様明日の公開を待つだけにした",
    "what_went_well": [
      "3名義アクターが全員public済みであることをAPI GETで実測確認し、実態を正確に把握した",
      "outputSchemaの全type=string必須というvalidator制約をビルドエラーで発見し、即座に修正",
      "inputパスの.actor/相対ルールをエラーから学習して ../INPUT_SCHEMA.json に修正し、buildをSUCCEEDEDに導いた",
      "publishトライがschemas-required→429(日次上限)に変化したことで、ブロッカー解消を実測で証明した"
    ],
    "what_could_improve": [
      "outputSchemaのtype制約（全string）は事前に他の公開済みactor（rakuten等）のactor.jsonを先に確認すれば早く回避できた",
      "figureとdebugアクターは非公開のまま。debug（rakuten-debug-fetch, tabelog-debug-fetch）は非公開で正。figureはtagged-build対応を次回検討"
    ],
    "mistakes_or_risks": [
      "buildを2回FAILEDさせた（前者はtype制約、後者はinputパス）— 事前調査不足による試行",
      "input=./INPUT_SCHEMA.json のパス解釈を誤った（.actor/から見てreporootは ../ ）",
      "日次公開上限5件に達しているため、dmm/rakutenの実際のpublic化は本日中に完了できない（明日に持ち越し）"
    ],
    "learned": "ApifyのoutputSchemaは全property typeが文字列'string'である必要がある（int/number不可）。actor.jsonのinputパスは.actor/ディレクトリからの相対パス。日次公開上限5件はAPI（PUT isPublic）で計測でき、schemas-required→429の変化を起点に「ブロッカー解消判定」ができる",
    "confidence": 9,
    "verification_evidence": "GET /v2/acts/{id}で3名義actor isPublic=Trueを実測。build 0.1.8 status=SUCCEEDED（api.apify.com）を実測。PUT isPublic=trueでHTTP 429 daily-publication-limit-exceeded（以前はschemas-requiredだった）を得てoutputSchema解消を証明。git push origin main成功"
  }
}
```

## 申し送り / 次回への引き継ぎ

- **dmm-scraper（nUm22B2guMo8vXom6）: 公開ブロッカー解消済み。明日（24h後）に `PUT /v2/acts/nUm22B2guMo8vXom6 {"isPublic":true}` を再実行して公開**
- **rakuten-market-scraper: 同様に明日公開**（outputSchema済・rebuild 0.1.2済）
- japan-figure-plamo-resale-price-stats: tagged-build-required（ビルドタグ付与が必要）→ 優先度低・余裕あれば対応
- 日次公開上限5件のため、dmm/rakuten/figure/その他は「日次5件以内」で計画的に公開すること
