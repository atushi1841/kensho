# t_a3246344 — コレクションタイムアウト対策 指数バックオフ付きリトライ

## 実装内容
ConnectTimeoutで全放棄していた収集元のリストページ取得へ、指数バックオフ付きリトライを展開。

| ファイル | 変更 |
|---|---|
| kensho/scraping/sources/kenshouclub.py | リストページ `fetch`(素) → `_fetch_with_retry`（指数バックオフ base 2s / max 3） |
| kensho/scraping/sources/cpmeikan.py | ページ `fetch`(素) → `_fetch_with_retry` |
| kensho/scraping/sources/kema.py | ページ `fetch`(素) → `_fetch_with_retry` |
| kensho/scraping/sources/kenkaku.py | 固定バックオフ2.0s → 指数 `base 2.0 * 2**attempt`（2s→4s） |

`_fetch_with_retry`（common.py）は既存の共有ヘルパーで、httpx.TimeoutException/ConnectError（ConnectTimeoutは両クラスのサブクラス）を捕捉し指数バックオフで最大3回リトライする。

## verification_evidence

acceptance: ConnectTimeout 50%削減（3日目実測・経過観測）
commit: 38d0baf t_a3246344: collection ConnectTimeout対策 — 指数バックオフ付きリトライを全収集源へ展開

```
$ git -C /mnt/d/Project2/kensho log --oneline -1
38d0baf t_a3246344: collection ConnectTimeout対策 — 指数バックオフ付きリトライを全収集源へ展開
```

```
$ python -m pytest tests/test_kema_scraper.py tests/test_kenkaku_retry.py tests/test_collector.py \
  tests/test_chancecom_scraper.py "tests/test_regression_gates.py::test_kenkaku_per_page_retry_present" -q
67 passed
```

```
$ python -m pytest -q | grep -E "passed|failed"
654 passed, 5 failed, 5 skipped
```

上記5 failedは全件、変更前のクリーンツリー（git stashで検証）でも同一で落ちる既存の板/メタ状態ゲート
（result_column/checkpoint/protocol/notepad/skill_md — いずれも本変更と無関係）。本変更導入の新規失敗0件。
mypy: 変更ファイル4つのうち kenkaku.py:49 のみ既存エラー（stash検証で非変更由来と確認）。新規mypyエラー0件。

## 失敗時代替
リトライで効果が不十分な場合: timeout値を 15s → 20s に増加、または共通 `_fetch_with_retry` の
`delay = 2**attempt + random` を `2.0 * 2**attempt` に統一し backoff基盤を強める。
