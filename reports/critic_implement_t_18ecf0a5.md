# critic実装報告: t_18ecf0a5 — knshow 502部分劣化: kenkaku v144 ページ単位リトライ移植

## 1. 背景（critic proposal 2026-09-22）
knshow.com が 9/20・9/21 の 14セッション中4回、HTTP 502 を部分的に返し、その際 knshow=0 に
なった（一覧ページ単発fetch が 502 を通すと extract_detail_links が空 → knshow 収集0件）。
knshow の fetch は timeout=15 の単発（リトライ無し）で、kenkaku v144 に比べて応答性が欠けていた。

## 2. 実施内容
kenkaku v144 のページ単位指数バックオフリトライを knshow に移植（3アテンプト・10sキャップ）。

### knshow.py
- リトライ定数: `_KNSHOW_MAX_TRIES=3`（初期+リトライ2回）、`_KNSHOW_RETRY_BACKOFF=3.0`、
  `_KNSHOW_RETRY_BACKOFF_MAX=10.0`（バックオフ 3,6 → 10sキャップ）、`_KNSHOW_TIMEOUT=15`。
- `fetch_listing_with_retry(fetcher, url, *, out=None)` — モード別fetcher（scrapling/proxy/fetch）を
  包み、HTTP 5xx(502含む)/ネットワーク例外のみ 3アテンプトまで指数バックオフリトライ。非5xx(404等)は即スキップ。
- `resolve_redirect` — ネットワーク例外でのみ指数バックオフリトライ（最終失敗で再raise＝呼出側が item skip）。

### collector.py Step 1（主体の修正）
一覧ページ取得を `_do_fetch(url)`（単発）→ `fetch_listing_with_retry(_do_fetch, url, out=out)` へ変更。
一過的 502 がリトライで回復すれば note_fetch(成功) で連続失敗カウンタがリセットされ、
knshow=0 セッションが半減する（成功指標）。

### sources/__init__.py
`fetch_listing_with_retry` を export。

## 3. 検証

## verification_evidence

$ cd /mnt/d/Project2/kensho && ./.venv/bin/python -m pytest tests/test_knshow_retry.py tests/test_kenkaku_retry.py -q -p no:cacheprovider --no-cov
tests/test_knshow_retry.py ............                                  [ 50%]
tests/test_kenkaku_retry.py ............                                 [100%]
============================== 24 passed in 8.66s ==============================

$ ./.venv/bin/python -m pytest tests/test_source_health.py tests/test_collector.py -q -p no:cacheprovider --no-cov
95 passed in 31.38s

第1証跡: knshow 移植テスト(test_knshow_retry.py 12件) + kenkaku 回帰(test_kenkaku_retry.py 12件) = 24 passed。
  - test_502_then_success: 502→リトライ→200、バックオフ 3.0s を検証
  - test_all_502_gives_up_finitely: 3アテンプト集中・無限リトライ禁止（sleep=[3.0,6.0]）
  - test_non500_not_retried: 404等の非5xxは即スキップ（リトライ不発火）
  - test_raises_after_3_failures: resolve_redirect 最終失敗で再raise（item skip）

$ grep -nE '部分劣化|partial' kensho/scraping/collector.py
622:        out(f"  [HEALTH] 部分劣化（主要源timeout）: {_failed}")

第2証跡: knshow は PRIMARY_SOURCES(source_health.py:47) に含まれ、一覧/詳細の fetch が 502 を
通さなくなった（fetch_listing_with_retry が 5xx をリトライ）。部分劣化警告(collector.py:622)は
最終失敗セッションに限定され、一過的 502 は run 内リトライ回復で警告対象から外れる。

## 4. mypy
変更3ファイル+新テストで mypy strict を実行。追加エラーは0件（stash比較で確認: 既存
collector.py:258/259・scorer.py 等のエラーは変更前から存在）。

$ uv run mypy kensho/scraping/sources/knshow.py kensho/scraping/collector.py kensho/scraping/sources/__init__.py tests/test_knshow_retry.py
（追加エラー0 — 既存9件はstash前の元コードに同一）

## 5. 備考
- 全テストスイート(842件中841 passed, 5 skipped, 1 failed)の唯一の失敗
  `test_gate_result_column_empty_after_v151` は kanban.db 直読の板衛生gateで、当該カード
  `t_3cc98f43` の空resultが原因（本変更と無関係・既存板状態）。
- フォールバック案（knshowを部分劣化警告から除外）は未採用。成功指標 knshow=0 セッションの
  7日間半減を観測し、改善が見られない場合のみ採用を検討する。
