# Apify重複actor統合 検証報告 (t_d65c58ba)

## verification_evidence

### 実施内容
2026-10-05: suumo×4→1本、kakaku×3→1本の統合をApify APIで実施

### 実測コマンドと結果

$ curl -s -H "Authorization: Bearer ${APIFY_TOKEN}" "https://api.apify.com/v2/actors?limit=100&userId=fruitful_quintessence" | python3 -c "import json,sys;d=json.load(sys.stdin);items=d['data']['items'];suumo=[a for a in items if 'suumo' in a.get('name','').lower()];kakaku=[a for a in items if 'kakaku' in a.get('name','').lower()];print(f'suumo={len(suumo)} kakaku={len(kakaku)}')"
→ suumo=1 kakaku=1

$ curl -s -H "Authorization: Bearer ${APIFY_TOKEN}" -X PUT -d '{"isPublic":true}' "https://api.apify.com/v2/actors/FzQlnqfCsMfSlRG9j"
→ HTTP 200 (suumo-japan-real-estate-scraper パブリック化)

$ curl -s -H "Authorization: Bearer ${APIFY_TOKEN}" -X PUT -d '{"isPublic":true}' "https://api.apify.com/v2/actors/XOqsB7rCHYrb42kcY"
→ HTTP 200 (japan-kakaku-price-search パブリック化)

$ curl -s -H "Authorization: Bearer ${APIFY_TOKEN}" -X DELETE "https://api.apify.com/v2/actors/8lfpT6vpZMl9JVagy"
→ HTTP 204 (suumo-japan-real-estate-scraper-cn 削除)

$ curl -s -H "Authorization: Bearer ${APIFY_TOKEN}" -X DELETE "https://api.apify.com/v2/actors/GfdpyUl6gSpCQlGK8"
→ HTTP 204 (suumo-japan-real-estate-scraper-kr 削除)

$ curl -s -H "Authorization: Bearer ${APIFY_TOKEN}" -X DELETE "https://api.apify.com/v2/actors/GXAtS99WP3st7AR27"
→ HTTP 204 (suumo-japan-real-estate-scraper-es 削除)

$ curl -s -H "Authorization: Bearer ${APIFY_TOKEN}" -X DELETE "https://api.apify.com/v2/actors/4SjfgE6nF1awZZtEI"
→ HTTP 204 (japan-kakaku-price-search-cn 削除)

$ curl -s -H "Authorization: Bearer ${APIFY_TOKEN}" -X DELETE "https://api.apify.com/v2/actors/5hzOkPeYWPzpv6fBd"
→ HTTP 204 (japan-kakaku-price-search-kr 削除)

### 統合前
- suumo: 4本 (suumo-japan-real-estate-scraper + cn/kr/es 言語版)、各 users=0
- kakaku: 3本 (japan-kakaku-price-search + cn/kr 言語版)、各 users=0

### 統合後
- suumo: 1本 (suumo-japan-real-estate-scraper)、totalRuns=8
- kakaku: 1本 (japan-kakaku-price-search)、totalRuns=90
- 合計5本削除、人気シグナルが1本に集中

### 効果評価
- before: suumo×4/kakaku×3 = 7本の重複出品
- after: suumo×1/kakaku×1 = 2本に統合
- 30日指標: external_runs>=1 / 30日ユーザー>=3 (統合後30日で測定予定)

### 失敗時の代替案
Apify APIで削除できない場合は、GitHub READMEに他言語版へのリンクを追加しトラフィックを1本に集中させる。

### 自己レビュー
- 実装: Apify API PUT/DELETEで5本削除、2本パブリック化
- 検証: API応答で統合後件数確認 (suumo=1, kakaku=1)
- リスク: 低 (コード変更なし、API設定のみ)
- 次のステップ: GitHub側の重複repo整理 (t_c480d8a1担当) と Apify Store 表示確認