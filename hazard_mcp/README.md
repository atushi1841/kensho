# HazardMCP - 日本物件ハザードリスクMCP

## 概要
住所（文字列または郵便番号）を入力として、洪水・土砂・津波・液状化の4災害リスクレベル（0〜3）を構造化JSONで返すMCPサーバー。

## 技術スタック
- Python 3.11+ / MCP SDK (mcp)
- GSIジオコーディングAPI (https://msearch.gsi.go.jp/address-search/)
- 国土交通省ハザードポータル (disaportal.gsi.go.jp)

## エンドポイント
- `tools/geocode` — 住所 → 緯度経度変換
- `tools/hazard_assess` — 住所 → {flood, landslide, tsunami, liquefaction} リスク判定

## データソース
- GSI 地理院タイル（ハザードマップ）
- 内閣府・地震本部・気象庁・MLIT ハザードデータ
- 出典：国土地理院・国土交通省（CC-BY 4.0相当）

## ローカル起動
```bash
cd hazard_mcp
pip install mcp httpx aiofiles
python -m hazard_mcp
```

## Apify Actor化予定
- actor.json: usesStandbyMode + webServerMcpPath: "/mcp"
- pay_per_event.json: PPE課金（$0.005/call）
- Smithery登録でMCPレジストリ経由配布

## 開発ロードマップ
1. プロトタイプ作成（1日）— GSIジオコード + ハザード判定ロジック
2. Apify Actor化・テスト（半日）
3. Apify Store公開＋Smithery登録（半日）
4. 需要検証（1週間）— 無料クーポン配布でフィードバック

## リスク・注意点
- GSIジオコードのレート制限（10秒に10回）→ キャッシュ・リトライ実装必須
- ハザードマップは数年ごとに更新 → 定期的なデータ差分チェック
- 出力にデータ出典を明記（CC-BY 4.0要件）
