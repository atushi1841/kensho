# t_d5e647a1 検証レポート — dev.to週次パイプラインの「偽成功」根絶（収益・高）

対象カード: **t_d5e647a1**（kensho-revenue-worker）
作業日: 2026-09-25 / 実行主体: kensho-sweeps（収益worker cron run）

## 結論（t_d5e647a1）

dev.to 週次投稿パイプライン（cron d538be4f5549 / 毎週月12:00）は **401 を「公開成功」と誤報**し続け、
外部トラフィック導線が 9/6 以降**無言死**していた。t_d5e647a1 で真因3件（マスク済みキーの認証使用 /
HTTPコード未検査 / ペイロード形状）と重複投稿リスク1件を修正し、**偽成功を構造的に不可能**にした。
実キーは `.env` 側が 3 文字プレースホルダのため（要ユーザー対応・下記）、公開自体は未回復。

## 変更ファイル（t_d5e647a1）

- `devto_weekly_pipeline.py`（リポジトリ正本・全面修正）
- `tests/test_devto_weekly_pipeline.py`（新規・16テスト）
- `/home/atushi/.hermes/profiles/kensho-sweeps/scripts/devto_weekly_pipeline.py`（cron 実行実体・正本と同一バイト）
- `/mnt/d/Project2/apify-sales-funnel/blog/.published.json`（公開済み記録・重複投稿防止の初期シード）
- commit `2946a51`（コード＋テスト）

## 何が壊れていたか（t_d5e647a1 の実測）

1. `load_api_key()` が `key[:4] + "...[REDACTED]" + key[-4:]` を返し、その値を `Api-Key` ヘッダに渡していた
   → **認証は常に失敗**（24文字キーでも 21文字のマスク文字列を送信）。
2. `curl -s` の本文だけを見て `response.get("id", 0)` を `[SUCCESS]` 表示 → 401 本文でも「Published article ID=0」。
3. 公開後確認は存在しない `status_code` キーを期待しており機能していなかった。
4. 公開済み `.md` を毎週候補として拾うため、キー復旧時に**同一記事の二重投稿**が起きる状態だった。

## verification_evidence

```
$ python3 -m pytest tests/test_devto_weekly_pipeline.py -q
tests/test_devto_weekly_pipeline.py ................                     [100%]
============================== 16 passed in 9.02s ==============================
```

```
$ PATH=<stub401plain> python3 devto_weekly_pipeline.py.bak-t_d5e647a1   # 旧コード（t_d5e647a1 修正前）
[SUCCESS] Published article ID=0: How to Scrape Mercari Japan in 2026 (Prices, Listings & Sold Data — No API Key)
       URL: https://dev.to/atushi/
[INFO] Published 1/2 articles (only 1 available)
rc=0
```
→ 9/21 の cron 出力（cron/output/d538be4f5549/2026-09-21_12-11-47.md）と同一の**偽成功**を再現。

```
$ python3 -c "old.load_api_key()  # 24文字キーを .env として与える"
BEFORE old.load_api_key(): len=21 値='abcd...[REDACTED]ef01'  (24文字キーを渡しても生キーではない)
```
→ 旧実装は 21文字のマスク文字列をそのまま `Api-Key` に送っていた（=401の真因）。

```
$ python3 -c "new.load_api_key()  # 同じ24文字キー"
AFTER  new.load_api_key(): len=24 valid_format=True 表示=abcd...[REDACTED]ef01
```
→ 新実装は生キー（24文字）を返し、表示だけ `mask_key()` を通す。

```
$ DEVTO_ENV_FILE=<24文字キー> PATH=<stub401> python3 devto_weekly_pipeline.py; echo rc=$?
[FAIL] dev.to API 認証エラー HTTP 401（DEVTO_API_KEY が無効/失効）: How to Scrape Mercari Japan in 2026 ...
rc=1
送信Api-Key長: 24 / 形式: True
```
→ 同じ 401 入力で**旧=偽SUCCESS/rc=0、新=FAIL/rc=1**。送信ヘッダは生キー（24文字）であることを実測。

```
$ DEVTO_BLOG_DIR=<blog200> DEVTO_ENV_FILE=<24文字キー> PATH=<stub200> python3 devto_weekly_pipeline.py; echo rc=$?
[SUCCESS] Published article ID=888001: How to Scrape Mercari Japan in 2026 ...
[VERIFY] Article confirmed live (HTTP 200, id=888001)
[STATE] 公開済み記録を更新: <blog200>/.published.json
rc=0
```
→ 正常パスは SUCCESS + VERIFY + 公開済み記録の更新まで到達（rc=0）。

```
$ python3 devto_weekly_pipeline.py    # 本番相当（実blog + 実.env）
[SKIP] already published: devto-mercari-japan-scraper.md (id=4606013)
Found 1 markdown candidate(s) / 未公開 0
[INFO] 未公開候補はありません（新規記事の追加待ち）
rc=3
```
→ 公開済み（9/8・ID 4606013・title完全一致で確認）はスキップされ、二重投稿しない。

```
$ curl -s -o /dev/null -w "%{http_code}" -H "Api-Key: <現行.envの値>" https://dev.to/api/articles/me
401
$ curl -s -o /dev/null -w "%{http_code}" https://dev.to/api/articles/4606013
200
```
→ 現行キーは実 API で 401（値は非表示）。公開済み記事は認証不要の GET で 200。

```
$ md5sum devto_weekly_pipeline.py ~/.hermes/profiles/kensho-sweeps/scripts/devto_weekly_pipeline.py
e4e866609ffd22beee478dadf7c28f5c  devto_weekly_pipeline.py
e4e866609ffd22beee478dadf7c28f5c  /home/atushi/.hermes/profiles/kensho-sweeps/scripts/devto_weekly_pipeline.py
```
→ cron が実行する profile scripts 側と repo 正本が同一（テストでも一致を固定）。

```
$ git log --oneline -1
2946a51 fix(revenue): t_d5e647a1 dev.to週次パイプラインの偽成功を根絶 — 認証にマスク済みキーを送っていた真因を修正＋HTTPコード検証＋重複投稿防止
```

## Outcome Review（t_d5e647a1 の KPI）

- 401/HTTP失敗時の偽成功報告率: **before=100% → after=0%**（旧=SUCCESS表示 / 新=FAIL＋rc≠0）
- 認証ヘッダに生キーが載る率: **before=0% → after=100%**（before 送信長21=マスク / after 24=生キー）
- 公開済み記事の二重投稿ガード: **before=0件 → after=1件検出**（`.published.json` の SKIP 実測）
- 失敗の可視化（終了コード）: **before=常に0 → after=0/1/2/3 の契約**

## 要ユーザー対応（t_d5e647a1 で検出）

【要ユーザー対応】`.env` の `DEVTO_API_KEY` が 3 文字のプレースホルダ（実 API で 401 実測）。
- 推奨アクション: dev.to ダッシュボード → Settings → API Keys で新キーを発行し、`/mnt/d/Project2/kensho/.env` の
  `DEVTO_API_KEY` に設定（1回の作業で週次投稿が再開。値は当方で取得・保持しません）。
- 復旧後は `python3 devto_weekly_pipeline.py` が rc=0（SUCCESS+VERIFY）になることを1回実測すれば完了。
- あわせて「未公開候補0件（rc=3）」は新規記事の追加（フェーズ2）で解消します。
- **おすすめですすめます（GOで実行/対応をお願いします）**。

## 自己レビュー（Reflexion / t_d5e647a1）

```json
{"self_review":{"what_was_done":"t_d5e647a1: dev.to週次パイプラインが401を[SUCCESS] ID=0と誤報していた真因（マスク済みキーをApi-Keyヘッダに使用）を修正し、HTTPコード検査・id検証・docs準拠の{\"article\":{...}}ペイロード・公開済み記録による重複防止・終了コード契約0/1/2/3を実装。テスト16件と実測5経路（旧コード偽成功の再現/新コード401=rc1/200=rc0/本番相当rc3/実API401）で検証し、commit 2946a51。","what_went_well":["旧コードの偽成功をスタブcurlで完全再現し、before/afterを同一入力で対比できた","マスク値を認証に使う真因をload_api_key()の戻り値長（21 vs 24）で定量的に示せた","公開済み記事をAPI GETのtitle一致で確認してから.published.jsonをシードし、二重投稿を実測で防いだ","cron実行実体（profile scripts側）とrepo正本の一致をテストで固定した"],"what_could_improve":["write_fileが既読判定で2回拒否され、スクラッチ経由のcpに切り替えるまで時間を使った（先にread_fileで全読み→write_fileの順を守る）","スタブcurlのDATAログ実装を忘れ、テスト1件を後から修正した（スタブ設計を先に確定すべき）"],"mistakes_or_risks":["残リスク: .envの実キーは未取得のため公開は未回復（要ユーザー対応として明示）","残リスク: 終了コード3（未公開候補0件）は週次でcronがerror表示になりうる。放置ではなく新規記事追加（フェーズ2）で解消する設計とした","旧cronジョブはLLMモードのため、スクリプトのrc≠0が last_status に反映されるかは次回9/28の実測で確認が必要"],"learned":"『本文がJSONとして読める』ことは成功の証明ではない。成功判定はHTTPコードと必須キー（id）で行い、失敗を終了コードに写像して初めてcronが嘘をつかなくなる。認証情報のマスクは表示層にのみ適用し、認証経路にマスク値を流してはならない。","confidence":9,"verification_evidence":"pytest 16 passed / 旧コード: [SUCCESS] ID=0 rc=0 再現 / 旧load_api_key len=21(マスク) vs 新len=24(生キー) / 401スタブ: [FAIL] HTTP 401 rc=1・送信ヘッダ長24 / 200スタブ: SUCCESS+VERIFY rc=0 + .published.json更新 / 本番相当: [SKIP] already published rc=3 / 実API: /articles/me=401, /articles/4606013=200 / md5 repo==profile e4e86660… / commit 2946a51"}}
```
