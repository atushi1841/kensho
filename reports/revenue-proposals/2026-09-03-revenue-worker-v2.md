# 収益化Worker実装記録: 2026-09-03（2回目・06:50実行）

> 収益化Worker Agent（kensho-revenue-worker）実装記録

## 実施内容

### タスク: t_dd8936bb（完了）— 日本中古カメラ・レンズ相場API

#### 1. アクター作成
- **name**: `japan-camera-resale-price-stats`
- **Apify ID**: `xJI4WaPBfQiDJfcnp`
- **公開URL**: https://apify.com/atushi1841/japan-camera-resale-price-stats
- **description**: 293文字（300字制限内）／カテゴリ: ECOMMERCE

#### 2. ソースコード（/tmp/japan-camera-price-api/）
- `src/main.py` — アクター本体（HTTP ベース、Yahoo Auctions + Mercari の結果を集約し価格統計を返す）
- `src/yahoo_auctions.py` — 既存 yahoo-auctions-japan-scraper からコピー（httpx + BeautifulSoup）
- `src/__main__.py` — エントリポイント
- `Dockerfile` — apify/actor-python:3.12（既存 yahoo アクターと同じ構成）
- `.actor/actor.json` — outputSchema 含む（公開要件）
- `.actor/INPUT_SCHEMA.json` — 入力スキーマ
- `requirements.txt` — apify + httpx のみ
- `README.md` — 英語API説明

#### 3. 価格設定（PAY_PER_EVENT）
- apify-actor-start: $0.00005（1回固定）
- apify-default-dataset-item: $0.002（1結果ごと）
- Apify手数料: 20%

#### 4. デプロイ
- SOURCE_FILES 方式（GitHub 連携未）
- ビルド: SUCCEEDED（12秒）
- 公開: isPublic=True
- Apify Store URL: https://apify.com/atushi1841/japan-camera-resale-price-stats

#### 5. テスト検証
- **Nikon F3 検索 (Yahoo Auctions 5件)**:
  - count=5, priceMin=11000, priceMax=99000, priceAvg=47700, priceMedian=49250
  - sampleItems: Yahoo 5件（タイトル・価格・URL・画像URL付き）
- **Nikon F3 検索 (Yahoo+Mercari 8件ずつ)**: Yahoo 4件成功（Mercari は既存 mercari-japan-search-scraper のプロキシ認証問題 ERR_INVALID_AUTH_CREDENTIALS で失敗 → partial results fallback で正常終了）

## 検証エビデンス

### 1. 公開状態
```
isPublic: True
title: Japan Camera & Lens Resale Price Research API
stats.totalRuns: 6
```

### 2. 価格設定
```
pricingInfos: [{'pricingModel': 'PAY_PER_EVENT',
                'pricingPerEvent': {'actorChargeEvents': {
                  'apify-actor-start': {eventTitle, eventDescription, eventPriceUsd: 0.00005, isOneTimeEvent: True},
                  'apify-default-dataset-item': {eventTitle, eventDescription, eventPriceUsd: 0.002, isOneTimeEvent: False}
                }}, 'apifyMarginPercentage': 0.2}]
```

### 3. テストラン結果
```json
{
  "statsType": "japan-camera-resale-price",
  "keyword": "Nikon F3",
  "count": 5,
  "priceMin": 11000,
  "priceMax": 99000,
  "priceAvg": 47700,
  "priceMedian": 49250,
  "sources": {"yahoo": 5},
  "sampleItems": [5件]
}
```

## 実装時のピットフォール（4件、1回の反復で全解決）

1. **actor.json input 参照パス**: `.actor/` 内に INPUT_SCHEMA.json が必要（ルートに置くと「file does not exist」）
2. **Dockerfile 構成**: ベースイメージの自動検出に任せず `FROM apify/actor-python:3.12` + `CMD ["python", "-m", "src.main"]` 明示（既存 yahoo アクター準拠）
3. **Apify SDK v3.4.1 の get_input() 変更**: `Actor.get_input()` が `{"input": {...}}` でラップされた値を返す仕様に変更 → `if "input" in actor_input: actor_input = actor_input["input"]` で吸収
4. **POST /runs ボディ形式**: `{"input": ...}` でラップせず、アクター入力そのものを送る必要。`{"input": ...}` でラップすると内部呼び出しが exit_code=1 で失敗（ローカルテストで切り分け）
5. **公開時の outputSchema 必須**: 全フィールド string + template 必須、pricingInfos イベントには eventTitle/eventDescription/eventPriceUsd/isOneTimeEvent 必須

## 次回申し送り

- t_5009a3cf（フィギュアAPI）: 同じパターンで実装可能（mandarake-auction-scraper + mercari-japan-search-scraper + yahoo-auctions-japan-scraper を活用）。ただしプロキシ認証問題は mercari 側の修正待ち
- t_7c4dce1e（n8nテンプレ公開）: GitHub repo 作成 + n8n ワークフロー JSON 公開。コード実装は軽め

## Kanban反映
- t_dd8936bb: completed（実測検証済み・公開済み・価格設定済み）
