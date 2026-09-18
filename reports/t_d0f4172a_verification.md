# t_d0f4172a 検証レポート — test_simple_rt_fallback.py expected=2 修正

## 提案内容
QA指摘: test_simple_rt_fallback.py の expected=2 が got=16 に悪化。
RTフォールバック分離バグの再発。

## 根因分析
テストは import 時にハードコードされた `/tmp/test_or_usage` の `data/openrouter_usage.json`
を参照するが、起点リセットが無くカウンタが実行のたびに累積していた。
実測では前回値 24 に本runの +2 が加わり got=26 となった（expected=2 は最初の1回のみ成立）。

## 修正内容
テスト冒頭で残留 usage ファイルを `unlink` してからカウンタを初期化（冪等化）。
commit 83656bf（tests/test_simple_rt_fallback.py）。

## 検証エビデンス

### 1. 失敗の再現（修正前）
```text
$ cat /tmp/test_or_usage/data/openrouter_usage.json
{"2026-09": 24}
$ python -m pytest tests/ -x -q -k rt_fallback
E   AssertionError: Expected 2, got 26
```

### 2. 修正後のソース変更点
```text
$ git show HEAD:tests/test_simple_rt_fallback.py
+ test_usage_file = test_root / "data" / "openrouter_usage.json"
+ if test_usage_file.exists():
+     test_usage_file.unlink()
```

### 3. 修正後のテスト実行（冪等性確認・2回連続）
```text
$ python3 tests/test_simple_rt_fallback.py
Constants OK
Usage logging OK: {'2026-09': 1}
Increment OK
All tests passed!
$ python3 tests/test_simple_rt_fallback.py
All tests passed!   (2回目も pass → 累積なし)
```

### 4. commit 記録
```text
$ git log --oneline -1
83656bf test(simple_rt): fix non-isolated /tmp counter accumulation in test_simple_rt_fallback
```

### 5. ruff チェック（lint/format）
```text
$ uvx ruff@0.15.20 format --check tests/test_simple_rt_fallback.py
1 file already formatted
$ uvx ruff@0.15.20 check tests/test_simple_rt_fallback.py
All checks passed!
```

## 補足
全スイートは非関連の既存失敗1件あり
（`test_regression_gates::test_gate_result_column_empty_after_v151`, offender t_9f37e5e3）。
本変更と無関係と確認済み（変更を stash した状態でも再現）。
push は github.com 443 不通のため未達（ローカル commit 済み、origin/main ref 不在 → guard 条件 e は skip）。
