# t_7b040302 実装記録 — evolution v65: dependency drift gate

ワーカー: kensho-revenue-worker / 2026-09-09 23:55 JST

## 実装内容

1. `/mnt/d/Project2/kensho/scripts/check_dep_drift.py`（新規・stdlibのみ）
   - pyproject.toml `[project].dependencies` を tomllib で解釈し、kensho cron 実venv
     （config.yaml `general.python` = `/home/atushi/kensho-venv/bin/python`、CLI/envで上書き可）
     の `pip list --format=freeze` 実インストール版と比較。
   - spec は `>=,<=,==,!=,~=,===,>,<` と連結（`>=1.52,<1.53`）、`.*` 接尾、数値キー比較に対応。
     判定不能（非数値version）は誤検知防止のため drift 化しない。
   - `pip check` を同 venv でサブプロセス実行し結果を同梱。
   - 出力 JSON 1行 `{"ok":bool,"drift":[...],"pip_check":"..."}`。drift あれば exit 1。
   - `--selftest`（回帰ガード）: 実 venv は読み取り専用。一時 pyproject で
     (1) `twscrape==実版`→ok (2) `twscrape!=実版`→検出 (3) 存在しないpkg→MISSING検出。
     検出成功時 exit 1（カード本文の回帰ガード規約と一致）。
2. done_guard 条件(f) 組み込み（`/home/atushi/.hermes/profiles/kensho-sweeps/scripts/kanban_done_guard.py`）
   - `dep_drift_state()`: check_dep_drift.py を実行、drift_count を条件
     `f:no_dep_drift` として評価。既存 (e) と同じ移行soft規則で
     `F_HARD_AFTER="2026-09-13"`（導入+3日 grace）までは warn のみ pass扱い。
   - 監査基盤の失敗（スクリプト不在・出力parse不能）は常に soft（誤ブロック回避）。
   - 実測時は `data/dep_drift_log.jsonl` に日次追記（success metric: daily drift line）。
     60分キャッシュ `.dep_drift_cache.json` で pip list 重複実行を回避。
   - plain 出力に `f no dep drift (pyproject vs venv)` 行、soft中は申し送り WARNING。
3. QA/日次レポート組み込み（`/mnt/d/Project2/kensho/kensho/tools/daily_pipeline_report.py`）
   - 「## 依存関係ドリフト（pyproject宣言 vs venv実インストール）」節を追加し
     `drift_count=N ok=…` の1行を毎日出力（トレンド監視）。

自動インストールは一切行わない（カードRisk欄の禁止事項準守）。

## verification_evidence

```
$ python3 /mnt/d/Project2/kensho/scripts/check_dep_drift.py; echo "rc=$?"
{"ok": true, "drift": [], "pip_check": "No broken requirements found.", "venv_python": "/home/atushi/kensho-venv/bin/python", "pyproject": "/mnt/d/Project2/kensho/pyproject.toml", "checked": {"beautifulsoup4": "4.15.0", "httpx": "0.28.1", "keyring": "25.7.0", "loguru": "0.7.3", "lxml": "6.1.1", "patchright": "1.62.3", "playwright": "1.61.0", "psutil": "7.2.2", "pydantic": "2.13.4", "pydantic-settings": "2.14.2", "pyyaml": "6.0.3", "requests": "2.34.2", "twscrape": "0.20.1"}}
rc=0
```

回帰ガード（カード本文指定の実pyproject一時書き換え版・pyyaml除く全宣言対応）:

```
$ sed -i 's/twscrape>=0.20.1/twscrape==99.99.99/' pyproject.toml && python3 scripts/check_dep_drift.py; echo "injected_rc=$?"
{"ok": false, "drift": [{"name": "twscrape", "declared": "==99.99.99", "installed": "0.20.1", "reason": "version mismatch: installed does not satisfy declared specifier"}], "pip_check": "No broken requirements found.", ...}
injected_rc=1
$ cp /tmp/pyproject.bak pyproject.toml && python3 scripts/check_dep_drift.py >/dev/null; echo "post_restore_rc=$?"
post_restore_rc=0
```

自己テスト（twscrape!=installed 注入検出 + MISSING検出 + 正常系ok）:

```
$ python3 scripts/check_dep_drift.py --selftest; echo "selftest_rc=$?"
selftest dep_drift: healthy_ok=True (twscrape==0.20.1, checked=2)
selftest dep_drift: injected_!=_drift_detected=True (drift=['twscrape'])
selftest dep_drift: missing_pkg_detected=True
SELFTEST OK: drift injection detected -> exit 1 (per card regression guard)
selftest_rc=1
```

done_guard 条件(f) 動作（実クローンで warn 経路は上と同機構・統合実行の証跡）:

```
$ bash /home/atushi/.hermes/profiles/kensho-sweeps/scripts/kanban_done_guard.py t_c1ec5f8b
  e pushed + hash ancestry: True  (ok)  0 unpushed commits | hashes: no hashes cited
  f no dep drift (pyproject vs venv)     : True  (ok drift=0)  drift_count=0: No broken requirements found.
$ bash /home/atushi/.hermes/profiles/kensho-sweeps/scripts/kanban_done_guard.py --selftest; echo "e_selftest_rc=$?"
SELFTEST OK: guard BLOCKs fabricated unpushed code commits (exit 1 = detection works, per card verification command)
e_selftest_rc=1
```

日次 drift line（QA/パイプレンレポート実出力・t_7b040302 新規節）:

```
$ /home/atushi/kensho-venv/bin/python kensho/tools/daily_pipeline_report.py 2026-09-08
## 依存関係ドリフト（pyproject宣言 vs venv実インストール）
- drift_count=0 ok=True | pip_check: No broken requirements found.
```

日次ログ実体（data/dep_drift_log.jsonl に自動追記済み）:

```
$ cat data/dep_drift_log.jsonl
{"ts": 1788964644, "date": "2026-09-09", "ok": true, "drift_count": 0, "note": "No broken requirements found."}
```

静的検査・テスト:

```
$ /home/atushi/kensho-venv/bin/ruff check kensho/tools/daily_pipeline_report.py scripts/check_dep_drift.py
All checks passed!
$ /home/atushi/kensho-venv/bin/mypy scripts/check_dep_drift.py --ignore-missing-imports
Success: no issues found in 1 source file
$ /home/atushi/kensho-venv/bin/python -m pytest -x -q --tb=short -p no:cacheprovider
532 passed, 5 skipped in 87.57s (0:01:27)
```

（mypy kensho/tools/daily_pipeline_report.py の type-arg 9件は git stash 検証で
本変更前から存在する既存エラーと確認済み。新規コードは0エラー。）

## 宣言版 vs 実測版の現状（drift=0 確認）

- twscrape 宣言>=0.20.1 / 実0.20.1 ✓（v77 QA修正後）
- patchright 宣言==1.62.3 / 実1.62.3 ✓
- playwright 宣言>=1.52 / 実1.61.0 ✓（requirements.txt の <1.53 pin と pyproject 未pin の
  既存不整合は checker の対象外=pyproject宣言との比較のみ。要ユーザー判断のため申し送り）

## 申し送り

- playwright の requirements.txt pin（>=1.52,<1.53）と venv 実1.61.0 は不整合。
  checker は pyproject 宣言のみ見る仕様なので検出0。requirements.txt も第2ソース化するかは
  critic/QA判断（v65 カード仕様のスコープ外なので拡張として申し送り）。
- 条件(f) の hard 化は 2026-09-13 以降自動的に有効（F_HARD_AFTER）。
- 他セッションの dm_scan.py / dm_probe.py が作業ツリーに未コミットで存在する
  （本タスクと無関係・所有セッションに委譲、guard条件(d)はこのため本タスク完了時に
  本変更3ファイルのみをコミットして対処）。
