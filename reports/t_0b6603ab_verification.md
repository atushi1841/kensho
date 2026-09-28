# t_0b6603ab AIエージェント需要予測データ 販売チャネル実装・公開検証

タスク: t_0b6603ab (Implement Apify/RapidAPI/Gumroad sales channel for forecasting data)
親仕様: t_f601390c / 実装物: `apify-figure-feature-vectors/` + `scripts/deploy_feature_vector_actor.py`

## verification_evidence

### 1. Actor の公開（Apify Store PPE 販売チャネル）
$ python3 scripts/deploy_feature_vector_actor.py --json-out /tmp/deploy_result.json
[1/6] found existing actor 8cCUNDwmelphhoXFs
        categories set to ['ECOMMERCE', 'DEVELOPER_TOOLS']
[3/6] build vP77I4gbM3MRAe3uX started (version None)
        build status = SUCCEEDED
        build SUCCEEDED (buildNumber 0.1.9)
[6/6] read-back verification
        actorId = 8cCUNDwmelphhoXFs
        name = japan-anime-figure-demand-features
        isPublic = True
        buildHasOutputSchema = True
        pricingModel = PAY_PER_EVENT
        datasetItemUsd = 0.002
        startEventUsd = 5e-05
        margin = 0.2

### 2. 購入者と同一経路（同期API）でのデータ納品検証
$ python3 /tmp/verify_actor_run.py
actor              = japan-anime-figure-demand-features (8cCUNDwmelphhoXFs)
isPublic           = True
categories         = ['ECOMMERCE', 'DEVELOPER_TOOLS']
pricingModel       = PAY_PER_EVENT
datasetItemUsd     = 0.002
sync run returned  = 3 item(s)
schemaVersion      = 1.0.0
featureDim         = 48
len(vector)        = 48
keys(features)     = 48
units in [0,1]     = True
coverage           = {"hasOfferDetail": true, "offerDetailRows": 2, "hasAggregatePrice": true, "hasMsrp": false, "hasJan": true}
history            = {"points": 1, "firstSeen": "2026-09-27", "lastSeen": "2026-09-27", "velocityAvailable": false}
VERIFIED: published Actor delivers 48-dim normalized feature vectors

### 3. 単体テスト（特徴ベクトル変換 24件）
$ python3 -m pytest apify-figure-feature-vectors/tests/test_feature_vectors.py -q -p no:cacheprovider
============================= 24 passed in 32.67s ==============================

### 4. 公開403の根本原因（修正前の証拠）
$ python3 /tmp/build_log.py x5ihLO9beGstJoK2R
2026-09-28T14:49:17.758Z ACTOR: Selected directory: .
2026-09-28T14:49:17.762Z ACTOR: ERROR: Schema property "input": File ".actor/.actor/input_schema.json" does not exist!

## 根本原因と修正（t_0b6603ab）

Apify は `.actor/` ディレクトリが存在すると **`.actor/actor.json` のみを読み**、その中の
`input` / `output` パスは `.actor/` からの相対で解決する。修正前は

1. `.actor/` が無くルート `actor.json` の `"output": "output_schema.json"` が
   ビルドの output schema に解決されない → 公開時に
   `403 schemas-required`（"its default build has no output schema"）で拒否。
2. ルート/`.actor/` に actor.json が二重化し、パスが `.actor/.actor/...` に解決されて
   ビルド失敗（証跡4）。

修正は「公開済みの姉妹アクター `japan-anime-figure-price-data` と同じ配置」に揃えた:

- `.actor/actor.json` … 権威ファイル。`"input": "./input_schema.json"`,
  `"output": "./output_schema.json"`, インライン `outputSchema`
  (`actorOutputSchemaVersion: 1` + template 付き `dataset`/`manifest`)
- `.actor/{input,output,dataset}_schema.json` … 実体
- `categories` は API で設定（現行 enum は `DATA`/`JAPAN` を拒否するため
  `["ECOMMERCE","DEVELOPER_TOOLS"]`。候補を順に試すフォールバックを実装）
- `storages.dataset` は現行スキーマ（`views`/`fields` 必須）に適合しないため外した。
  `.actor/dataset_schema.json` はレコード定義のドキュメントとして同梱を維持。

## 変更コミット（t_0b6603ab）
$ git log --oneline -1
8a66e14 fix(apify): publish japan-anime-figure-demand-features via .actor schema wiring

実装コミット `8a66e14`（本タスク t_0b6603ab の修正）。変更ファイルは
`.actor/actor.json`、`actor.json`、`dataset_schema.json`、
`scripts/deploy_feature_vector_actor.py`、`reports/t_0b6603ab_*`。

## 納品データ形式（公開後の実測）
- `vector`: 長さ48・[0,1] 正規化済みの固定順ベクトル
- `features`: 同名48キーの辞書（`featureNames` の順序と一致）
- `coverage.hasOfferDetail` / `history.velocityAvailable` で上流スナップショットの欠測を明示
- `FEATURE_MANIFEST`（KVストア）にスキーマ版・次元・正規化定数を出力

## 成功基準 判定（t_0b6603ab）
- Actor が Store に公開されている（`isPublic=true`） → **True** ✅
- PPE 価格が仕様どおり $0.002/event → **datasetItemUsd=0.002** ✅
- 購入者経路でデータが取得できる → **sync API で3件・48次元** ✅
- 単体テスト green → **24 passed** ✅

## 成果物
- `apify-figure-feature-vectors/.actor/actor.json`（新規: 正しいスキーマ配線）
- `apify-figure-feature-vectors/actor.json`（修正）
- `apify-figure-feature-vectors/{input,output,dataset}_schema.json`（同梱）
- `scripts/deploy_feature_vector_actor.py`（スキーマ配線・categories フォールバック・
  公開後の read-back に `buildHasOutputSchema` を追加）
- Apify Actor: `8cCUNDwmelphhoXFs` = `japan-anime-figure-demand-features`（公開済み）

## 申し送り
- `storages.dataset` を復活させる場合は現行 Apify dataset schema（`views` または
  `fields` 必須）に合わせて書き直す必要がある。
- Gumroad の一括ダウンロード販売（仕様の Secondary チャネル）は未着手。
- 同一ファイル `scripts/deploy_feature_vector_actor.py` が並行セッション
  (t_a57c6538) からも編集されていた（hotspot）。
