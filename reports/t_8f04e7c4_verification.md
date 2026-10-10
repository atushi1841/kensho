# Verification Evidence for t_8f04e7c4

## 背景
Qiita article 897f8d90b1be3514d0b8 に Apify Actor 8件へのリンクとUTMパラメータを追加。
タスクID: t_8f04e7c4

## verification_evidence

### 実測1: GET 現状確認（変更前）
```
$ curl -s -H "Authorization: Bearer $QIITA_TOKEN" "https://qiita.com/api/v2/items/897f8d90b1be3514d0b8" | python3 -c "import json,sys,re;d=json.load(sys.stdin);print(len(re.findall(r'https://apify.com', d.get('body',''))))"
0
```

### 実測2: スクリプト実行
```
$ python3 scripts/qiita_table_links.py
[INFO] old apify.com links: 0
[INFO] new apify.com links: 8
[OK] PATCH HTTP 200
[VERIFY] post-PATCH apify.com links: 8
[OK] verification passed
```

### 実測3: GET 反映確認（変更後）
```
$ curl -s -H "Authorization: Bearer $QIITA_TOKEN" "https://qiita.com/api/v2/items/897f8d90b1be3514d0b8" | python3 -c "import json,sys,re;d=json.load(sys.stdin);print(len(re.findall(r'https://apify.com', d.get('body',''))), len(re.findall(r'utm_source=qiita', d.get('body',''))))"
8 8
```

## 成功指標
- apify.com links: 0 → 8 ✅
- utm_source=qiita: 0 → 8 ✅

## 変更ファイル
- `scripts/qiita_table_links.py` — 新規作成（t_8f04e7c4専用スクリプト）
