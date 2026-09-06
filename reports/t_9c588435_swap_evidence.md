# t_9c588435 — 入れ替え決定の検証エビデンス（2026-09-06 19:4x JST）

## 目的
RapidAPI owner 上限（PUBLIC 最大20本）超過により公開できなかった
Japan Used Camera Price Stats API (JP) = api_e19e373c-049e-462b-bd7c-c5acf9b65770 を
公開するため、ユーザー決定(2026-09-06 19:29)に従い公開中21本から最下位の冗長言語版を
PRIVATE化して枠を空け、JP を PUBLIC にした。

## 判断根拠（実データ）
- data/revenue-daily.json (2026-09-06): RapidAPI 22本すべて FREEMIUM、
  revenue_estimate.rapidapi_monthly = 0、全API paid subscriber = 0（無料 subscriber 各1名のみ）。
  → 全APIの実収益は $0 で同格。ユーザー手順どおり「Apify Store アクターと重複度が高く
    冗長な言語版」を最下位候補とした。
- 冗長言語版 PUBLIC 11本のうち、backing Apify アクターの直近 usage が最小の2本 =
  camera-cn (japan-camera-market-cn-scraper, 6 runs) と camera-kr (japan-camera-market-kr-scraper, 6 runs)。
  どちらも対象 JP と同 family で、JP 版が漏れていることを含めて冗長。→ 入れ替え対象に選定。
- 対象:
  - PRIVATE化: api_daeb465c (camera CN) / api_9e1f6683 (camera KR)
  - PUBLIC化: api_e19e373c (camera JP 本命)
- 公開漏れ: 同名 family の CN/KR が PUBLIC のまま JP のみ PRIVATE = publication leak 確定。
  廃止予定等の意図的 PRIVATE 根拠なし。

## 操作
mutation 前に全22本の visibility を data/rapidapi_publish/visibility_swap_backup.json へバックアップ（QA v38教訓）。
updateApi で 3 本を順に visibility 変更（CN→PRIVATE, KR→PRIVATE, JP→PUBLIC）。

## 検証エビデンス（3件以上・実コマンド出力）
### E1: scripts/rapidapi_swap_private_public.py --verify
  PUBLIC total = 20  (expect 20)
  camera JP api_e19e373c-... = PUBLIC  (expect PUBLIC)
  privatized api_daeb465c = PRIVATE
  privatized api_9e1f6683 = PRIVATE
  VERIFY_PASS = True

### E2: scripts/rapidapi_list_apis.py（全22本）内の対象行
  camera JP: {"id":"api_e19e373c-...","name":"Japan Used Camera Price Stats API",...,"vis":"PUBLIC"}
  camera CN: {"id":"api_daeb465c-...","name":"... (Chinese)",...,"vis":"PRIVATE"}
  camera KR: {"id":"api_9e1f6683-...","name":"... (Korean)",...,"vis":"PRIVATE"}

### E3: PRIVATE 件数
  $ python3 scripts/rapidapi_list_apis.py | grep -c '"vis": "PRIVATE"'  ->  2（入れ替え2本）

### E4: PUBLIC 件数
  $ python3 scripts/rapidapi_list_apis.py | grep -c '"vis": "PUBLIC"'  ->  20（上限内）

### E5: 対象 API 単体の可視性
  $ python3 scripts/rapidapi_list_apis.py | grep -F 'japan-used-camera-price-stats-api"'
  -> 1行: api_e19e373c ... vis PUBLIC

## 結果と後続
- 本タスクの成功条件（PUBLIC総数=20 かつ camera=PUBLIC）を充足。
- 元bodyの「grep -c PRIVATE → 0」は上限超過前の単純公開を想定した旧条件。
  今回のユーザー決定（入れ替えで枠を空ける）により PRIVATE=2（入れ替え分）が正。
- 無料 tier（FREEMIUM）のまま。有料プラン・subscriber への影響なし（paid sub 0名のみ）。
