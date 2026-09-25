# t_d18ac029 検証レポート（nightly-qa / 2026-09-25 15:2x JST）

対象カード: **t_d18ac029** — invisible-playwright が4系統すべて未宣言（browser.py:1082 が遅延 import・実 venv は git commit 2184f6f3 の 0.2.0）→ venv 再構築で X 応募が即死。

## 結論

- **t_d18ac029 は受入基準を全項目で満たした**（成功指標4点すべて PASS）。
- worker の実装は 3 系統（pyproject.toml / requirements.txt / uv.lock）まで完了していたが、**4系統目の requirements-lock.txt が未記入**のまま guard 条件 (a)(b)(d) で blocked になっていた。
- QA（nightly-qa）が **requirements-lock.txt へカード指定の PEP 508 直接参照を1行補完**し、4系統すべてを実機で再検測した（推測なし・すべて実行ログ付き）。
- コミット `5acefe7`（t_d18ac029）を作成し push 済み（origin/main 先端 = `02a31ae`）。バージョンアップは行っていない（カードの「アップグレード禁止」遵守）。

## verification_evidence

$ grep -c "invisible-playwright" pyproject.toml requirements.txt requirements-lock.txt
pyproject.toml:1
requirements.txt:1
requirements-lock.txt:1

$ grep -n "invisible-playwright" uv.lock
649:name = "invisible-playwright"
715:    { name = "invisible-playwright" },
753:    { name = "invisible-playwright", git = "https://github.com/feder-cr/invisible_playwright.git?rev=2184f6f3c296e5bedcf1539914b3a7d307ce9fe0" }

$ /home/atushi/kensho-venv/bin/python -m pytest tests/test_dep_declaration.py -q
2 passed in 27.78s

$ python3 scripts/check_dep_drift.py
ok: True, drift: 0 (exit 0 / pip_check "No broken requirements found.")

$ /home/atushi/kensho-venv/bin/python -c "import importlib.metadata as m;print(m.version('invisible_playwright'))"
0.2.0

$ cat /home/atushi/kensho-venv/lib/python3.12/site-packages/invisible_playwright-0.2.0.dist-info/direct_url.json
{"url": "https://github.com/feder-cr/invisible_playwright.git", "vcs_info": {"commit_id": "2184f6f3c296e5bedcf1539914b3a7d307ce9fe0", "vcs": "git"}}

$ git log --oneline -1 5acefe7
5acefe7 feat(deps): invisible-playwright を4系統で宣言 (pyproject/requirements/requirements-lock/uv.lock) + 回帰テスト (t_d18ac029)

$ git status --porcelain -uall | grep -E '\.(py|sh|js|yaml)$'
(該当なし = 未コミットのコード変更 0件)

## 変更内容（t_d18ac029 のスコープ）

- `pyproject.toml`: `[project.dependencies]` に `invisible-playwright @ git+https://github.com/feder-cr/invisible_playwright.git@2184f6f3c296e5bedcf1539914b3a7d307ce9fe0` を追加（PEP 508 直接参照・PyPI 名指定は不採用 = 0.25.5 の偽装挙動差回避）。
- `requirements.txt`: 同一 commit の直接参照を追記。
- `requirements-lock.txt`: 同一 commit の直接参照を追記（**QAが補完した1行**。requirements-lock.txt を読むコードは `grep -rn requirements-lock --include=*.py --include=*.sh --include=*.js --include=*.yaml .` = 0件のため、既存パイプラインへの影響なし）。
- `uv.lock`: invisible-playwright 0.2.0 を `source = { git = ...?rev=2184f6f3... }` で再解決（PyPI 版ではないことを実測確認）。
- `tests/test_dep_declaration.py`: browser.py:1082 の遅延 import と pyproject 宣言（パッケージ名・commit・git URL）を静的に検証する回帰テスト2件。

## Outcome Review

metric=invisible-playwright宣言系統数（pyproject/requirements/requirements-lock/uv.lock の4系統中） before=0 → after=4（達成率 0% → 100%）
metric=check_dep_drift drift件数 before=0 → after=0（宣言追加後も既存検査は緑のまま）

## 残リスク（t_d18ac029 の完了後も監視すべき点）

- `scripts/check_dep_drift.py` の `checked` 一覧に invisible-playwright が含まれていない（git 直接参照のため `parse_pyproject_deps` の版比較対象外）。= **venv から invisible-playwright が消えても drift ゲートは検知しない**。カード要求3のとおり当該スクリプトは触らず（並行WIP回避）、次カード候補として記録する。
- repo 内 `.venv` は invisible_playwright **0.8.3**、実運用 `/home/atushi/kensho-venv` は **0.2.0** と版が割れている（本カードのスコープ外・既知）。
