# t_3faf965b 検証証跡 — kenkaku.py v144 retry恒久モックテスト追加

タスク: t_3faf965b（QA起票元 t_a1083f51 の恒久テスト実施フォロワー）
受け入れコミット: 925b26b（tests/test_kenkaku_retry.py 1ファイルのみ・kenkaku.py不変）

## 実施内容（t_3faf965b）

`tests/test_kenkaku_retry.py` を新規追加（10テスト・ネットワーク/sleep全面mock）:

1. TestRetrySuccess — ConnectTimeout→リトライ1/2→2回目でitems取得、3アテンプト目成功も検証
2. TestFinalFailureSkipsPageOnly — 3連続失敗→最終ERRORログ1回・そのページのみスキップ・他ページ続行
3. TestNon200NoRetry — HTTP非200→fetch1回のみ・リトライ不発火・スキップログのみ（往来動作の回帰防止）
4. TestRetryConstants — _KENKAKU_MAX_RETRIES=2 / _KENKAKU_RETRY_BACKOFF=2.0 との実装整合アサーション
5. TestParseErrorNotRetried — パース例外はfetch再試行対象外（v144仕様: fetchのみリトライ）

## verification_evidence

t_3faf965b 受け入れ条件の実測出力（t_3faf965b run499 で採取、t_3faf965b 全条件対応）:

```
$ git show 925b26b --stat
commit 925b26bce9de23adae696b83ee7a6134e2880b1f
    test(scraping): QA起票 t_3faf965b — kenkaku.py v144 retry恒久モックテスト10件追加
 tests/test_kenkaku_retry.py | 231 ++++++++++++++++++++++++++++++++++++++++++++
 1 file changed, 231 insertions(+)
```
→ 収集パイレイン本体 kenkaku.py（t_3faf965b で変更してはならないファイル）は不変。テスト追加のみ＝受け入れ条件②充足

```
$ python -m pytest tests/test_kenkaku_retry.py -q --no-cov -p no:cacheprovider
collected 10 items
tests/test_kenkaku_retry.py ..........
10 passed in 2.50s
```
→ 受け入れ条件①の個別パス（t_3faf965b）。実行2.50秒＝time.sleep/requests実発火ゼロ（mock短縮の実証）

```
$ python -m pytest -q --no-cov -p no:cacheprovider
605 passed, 5 skipped, 1 failed in 40.17s
FAILED tests/test_regression_gates.py::test_gate_protocol_violation_crash
```
→ 既存605 passed+5 skippedはt_8e6c5102 backfill後の緑ベースラインから非破壊。唯一の失敗はt_c6b4e3ed由来の24h窓クラッシュカウントゲートで、テストファイル追加のみのt_3faf965bとは無因果（9/17窓roll自動消灯方針済み＝t_8e6c5102申し送り）。t_3faf965bのテスト10件は上記実行に含まれ緑。

```
$ grep -rl kenkaku tests/ --include=*.py
tests/test_regression_gates.py
tests/test_kenkaku_retry.py
```
→ 作業前は test_regression_gates.py（別タスク由来の参照のみ）でscrape_kenkaku恒久テスト0件＝QA t_a1083f51 のgrep実測どおり。t_3faf965b で解消

```
$ python -m mypy tests/test_kenkaku_retry.py 2>&1 | grep test_kenkaku_retry.py
（t_3faf965b 当該テストファイルの行は出力ゼロ＝0 error）
```
→ tests/AGENTS.md「mypy strict 0 error維持」ルール遵守（monkeypatchは文字列パス指定でattr-defined回避）

## 参照
- 実装: commit 7448138（retry本体）／ kenkaku.py L24-26定数
- QA証跡: reports/qa_run481_2026-09-15_2145.md（acad17d）
