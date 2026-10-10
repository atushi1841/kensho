# t_680be7c9 検証レポート: Qiita 4記事のApify linksにutm_source=qiita追加

## verification_evidence

$ python3 scripts/qiita_utm_fix.py
[INFO] 4 candidates
[1/4] PATCH 9a4702ddb89927ae1223 (懸賞1,842件の自動応募ログを全部集計したら...) ... OK (HTTP 200)
[2/4] PATCH ca99332b17cb07ac26ae (懸賞3件の自動応募ログを全部集計したら...) ... OK (HTTP 200)
[3/4] PATCH b9395dd0b95f0b6112b4 (懸賞7件の自動応募ログを全部集計したら...) ... OK (HTTP 200)
[4/4] PATCH 5b8258cf6b0f8c333449 (懸賞112件の自動応募ログを全部集計したら...) ... OK (HTTP 200)
[RESULT] PATCH 4/4

$ curl -s -H "Authorization: Bearer ***" "https://qiita.com/api/v2/users/atushi1841/items?per_page=50" | python3 -c "import json,sys;d=json.load(sys.stdin);print(len([a for a in d if 'apify.com' in a.get('body','') and 'utm_source=qiita' in a.get('body','')]))"
4

$ git log --oneline -1
e3c23db t_680be7c9: Qiita UTM fix — 4 articles updated, guard pass

## 実装内容

- `scripts/qiita_utm_fix.py` 新規作成（Qiita API v2 PATCH経路）
- **教訓**: Qiita PATCH は `body` のみで **HTTP 400**。`body+tags+title+private` 全フィールド必須
- 1件目（d05bf090）は削除済みでAPI取得不可 → 対象4件に縮小
- レート制限10秒間隔で4件順次PATCH成功

## 結果

- 成功: 4/4 PATCH（HTTP 200）
- 事前: utm_source=qiita付与0件 → 事后: 4件
- commit: e3c23db
- guard: pass（evidence.json 生成）