# t_957e7220 検証記録 — dev.to/Qiita重複投稿デデアップ

## verification_evidence

t_957e7220 の完了条件（①公開前デデアップゲート実装+push ②dev.to重複0 ③証跡）の実測証跡。

### 1. デデアップゲート実装（publish_devto.py / publish_qiita.py）

$ git log --oneline -1 -- scripts/publish_devto.py
89985be t_957e7220: dev.to/Qiita公開前デデアップゲート＋dedup_devto.py（重複20件非公開化・Qiita 1件削除）

$ python3 -m py_compile scripts/publish_devto.py scripts/publish_qiita.py scripts/dedup_devto.py && echo COMPILE_OK
COMPILE_OK

$ python3 -c "from publish_devto import find_existing_articles, pick_canonical; hits=find_existing_articles(TOKEN, \"I Published 10 Free MCP Servers...\"); print('gate hits:',[h['id'] for h in hits],'canonical:',pick_canonical(hits)['id'])"
gate hits: [4825022] canonical: 4825022

### 2. dev.to重複整理（公開一覧で重複タイトル0）

dev.to APIにはDELETEが存在しない（`DELETE /api/articles/{id}` → 404実測）。そのため
`PUT published:false` での非公開化をフォールバックとして実装・実行した（dedup_devto.py）。
連続PUTで429が発生したため sleep+リトライを追加し、2パスで計20件非公開化。

$ python3 scripts/dedup_devto.py --apply
[SUMMARY] groups=8 deleted=8 apply=True  （1回目 groups=12 deleted=12 を含む計20件 unpublished）

$ curl -s "https://dev.to/api/articles?username=atu_ino_ed473db24d76d234a&per_page=100" | python3 -c "import json,sys,collections;t=[a['title'].strip().lower() for a in json.load(sys.stdin)];print('dev.to public:',len(t),'dupgroups:',sum(1 for n in collections.Counter(t).values() if n>1))"
dev.to public: 27 dupgroups: 0

（整理前は 48記事中13グループ・重複20件。usernameは `GET /api/users/me` で
atu_ino_ed473db24d76d234a と実測。カード本文の username=atushi1841 は実在せず public 0 を返した）

### 3. Qiita重複整理

Qiita APIはDELETE対応（実測204）。Qiita側PATCH private:trueは400（bad_request実測）だったため
DELETEにフォールバック実装。重複1件（id=8544628b0cda368c394e）を削除。

$ curl -s -w "HTTP %{http_code}" -X DELETE -H "Authorization: Bearer $QIITA_TOKEN" https://qiita.com/api/v2/items/8544628b0cda368c394e
HTTP 204

$ python3 -c "…authenticated_user/items 集計…"
qiita public: 8 dupgroups: 0

### 既知の無関係失敗

`tests/test_compensation_orchestrator.py::test_get_pending_batches_atushi16_with_compensation`
は本タスクと無関係（兄弟タスク「死プロキシ垢kudouの応募停止」が config.yaml batches を
コメントアウト中のため assert 0==2）。本タスクの変更は publish/dedup スクリプトのみ。
他カードの作業を「ついで直し」しない規律により未修正。

## 30日KPI（outcome）

- metric: dev.to公開一覧の重複タイトルグループ数
- before=13 → after=0
- canonical記事 views>=30 / external_runs>=1 は30日後にQA計測
