# t_680be7c9 検証レポート: Qiita 5記事のApify linksにutm_source=qiita追加

## verification_evidence

- `$ python3 scripts/qiita_utm_fix.py => [RESULT] PATCH 4/4 (HTTP 200 x4)` — 4件のPATCHに成功
- `$ curl -s -H "Authorization: Bearer ***" "https://qiita.com/api/v2/users/atushi1841/items?per_page=50" | python3 -c "import json,sys;d=json.load(sys.stdin);print(len([a for a in d if 'apify.com' in a.get('body','') and 'utm_source=qiita' in a.get('body','')]))" => 4` — utm_source=qiita付与済みapify.comQiita links = 4/4
- `$ git log --oneline -1 => <commit>` — コミット済み

## 実装内容

- `scripts/qiita_utm_fix.py` 新規作成（Qiita API v2 PATCH経路）
- **教訓（最重要）**: Qiita PATCH は `body` のみでは **HTTP 400**。`body` + `tags` + `title` + `private` の全フィールド必要（`publish_qiita.py` の `build_payload()` が同一設計で通っていることを実測で確認）。
- 1件目（d05bf090）は既に削除/非公開化済みでAPIから取得不可 → 対象4件に縮小
- レート制限10秒間隔で4件順次PATCH

## 結果

- 成功: 4/4 PATCH（HTTP 200）
- 事前: utm_source=qiita付与0件 → 事后: 4件
- Qiita API PATCH 400バグを発見・修正（body-only → full payload）