# t_64f60f04 検証レポート — applier.py `_multi_response_record` log 汎容化（callable 対応）

## 背景
`kensho/application/applier.py` `_apply_impl` 内の成立直後呼び出し `_multi_response_record(tweet_id, account_key, cfg, out)` が、
`out`（L945 定義の closure 関数）を渡していた。`_multi_response_record` 側は `log.write(msg)`（L527-528）と仮定していたため、
`AttributeError: 'function' object has no attribute 'write'` が発生。成立直後例外 → `errors += 1`、
`save_collected_safe` 飛び、`failure_tracker.record_failure` 梗 → `[CEILING]` break と連鎖で
同一キャンペーンが完全に死んでいた（9/24 実測 50件/17URL）。

## 修正（1行＋汎容化、commit 1d2a644）
1. **呼び出し元（L2415）**: `_multi_response_record(tweet_id, account_key, cfg, out)` → `... cfg, log)`。
   `log` は `_apply_impl` の引数で None / LogWriter(.write) のいずれでも可（L804-807 の `if log:` ガード済）。
2. **受信側（L527-528）**: `if log is not None: log.write(msg)` → 汎容化。
   ```
   _emit = log.write if hasattr(log, "write") else (log if callable(log) else None)
   if _emit is not None:
       _emit(msg)
   ```
   None / LogWriter / callable のいずれでも例外化せず検知できる。将来の認配線でも死なない。

## verification_evidence

```
$ git log --oneline -1
1d2a644 fix(applier): t_64f60f04 _multi_response_record log 汎容化（callable 対応）
```

```
$ grep -n "_multi_response_record" kensho/application/applier.py
466:def _multi_response_record(tweet_id: str, account_key: str, cfg: dict, log: Any, state_path: Path | None = None) -> int:
2415:                        _multi_response_record(tweet_id, account_key, cfg, log)
```

```
$ grep -n "_emit" kensho/application/applier.py
529:                _emit = log.write if hasattr(log, "write") else (log if callable(log) else None)
530:                if _emit is not None:
531:                    _emit(msg)
```

```
$ python3 -m pytest tests/test_applier.py tests/test_knshow_cloudflare.py -q --no-cov
======================== 116 passed in 80.99s (01:20) ========================
```

```
$ python3 -m pytest tests/test_applier.py::TestMultiResponse::test_callable_log_does_not_crash -xvs
tests/test_applier.py::TestMultiResponse::test_callable_log_does_not_crash PASSED
```

## 成功指標
- `pytest tests/test_applier.py tests/test_knshow_cloudflare.py -q` = 0 failed, 116 passed（修正前 115 passed）
- 新規テスト `test_callable_log_does_not_crash`：callable / None / LogWriter の3パターンを assert
- 呼び出し元に `out` を渡すパターン（旧バグ）が残されていない（`grep "_multi_response_record(tweet_id, account_key, cfg, out)"` = 0）
- mypy strict: 0 error（`invisible_core/prefs.py` の構文エラーは venv 外の別ファイル、対象外）
- 24h 後:`grep -rc "has no attribute 'write'" logs/2026-09-25/` = 0 全ファイル

## スコープ外（触らない/checkoutしない）
- `scripts/kensho_revenue_collect.py` / `tests/test_revenue_collect.py` / `scripts/gen_status_data.py` / `scripts/loop_health.sh` / `scripts/audit_bot_safety.py`
  → t_fda64102 の作業中であり、本カードの done guard 条件(d) では「所有归来不能 → repo-wide fail-safe」が発火。
  兄弟タスクの done を巻き添えでFAILさせないため、これらは **手を_touchしない**（タスク本文も明記）。
- `data/` / `reports/` / `*.html` → データ churn として除外済。