# t_5dff275b 検証レポート — github_sync の push 復旧（credential不在 + index.lock競合 + 接続間欠）

- タスク: **t_5dff275b**（github_sync の push 復旧／assignee=kensho-worker）
- 発見元: t_3609e866 の統合監視検証（証跡 `reports/t_3609e866_verification.md`）
- 実装コミット: `bd4b9a4`（本レポートは同コミットの子孫）
- 実施日時: 2026-09-24 04:34〜05:10 JST

## 1. 原因（実測で確定した2要因）

| # | 事象 | 実測した原因 |
|---|------|--------------|
| ① | `could not read Username for 'https://github.com': No such device or address` | `~/.gitconfig` の credential helper が内部で `cmd.exe` を **PATH 依存で**呼んでいたため、cron の最小 PATH では解決できず credential を1行も返せない（→ git が対話プロンプトに落ちて失敗） |
| ② | `Unable to create '.git/index.lock': File exists.` | 他プロセス（並行 workstream の git 操作）と排他できていない。退避リトライ・古い lock の回収も無し |
| ③ | `Failed to connect to github.com port 443 after 134543 ms` | 接続は間欠（同一時刻の `git ls-remote` は 1.7s で成功）。ハングを切る lowSpeed 設定と再試行が無く、1回の失敗でその日が終わっていた |
| ④ | 失敗が次回に伝わらない | push 失敗時は「コミットはローカルに残留」と出すだけで、exit code/理由を構造化して残さず、次回実行で再送もしない |

## verification_evidence

### (1) cron 相当環境での credential 復旧（最小 PATH）

```
$ printf 'protocol=https\nhost=github.com\n\n' | env -i PATH=/usr/bin:/bin HOME=/home/atushi /home/atushi/.git-credential-helper-wsl.sh get
   # 修正前: (無出力)  ← credential.helper が password を返せず push が必ず auth 失敗
   # 修正後:
protocol=https
host=github.com
username=atushi1841
password=<40桁 token (gho_)>
```

### (2) cron wrapper の実走（非対話 push 成功）

```
$ env -i PATH=/usr/bin:/bin HOME=/home/atushi bash scripts/kensho_github_sync.sh
real    0m9.968s
wrapper_exit=0
```

### (3) 受入条件4: 未pushコミット0件 + push時刻が実行時刻以降

```
$ git log --oneline origin/main..HEAD
count=0

$ git reflog show origin/main --date=iso | head -3
d592d45 refs/remotes/origin/main@{2026-09-24 04:52:45 +0900}: update by push
7239dc4 refs/remotes/origin/main@{2026-09-24 04:03:00 +0900}: update by push
2c1c37a refs/remotes/origin/main@{2026-09-24 04:00:37 +0900}: update by push
```

### (4) 受入条件3: push 失敗の exit code / 理由 / 次回持ち越し

```
$ tail -12 logs/github_sync_cron.log
[sync] 2026-09-24 04:52:25 result=push_failed exit=2 reason=auth exit_code=128 attempts=2/3 credential=token(env-file:/home/atushi/.config/kensho/github-sync.env) pending=1 detail=remote: Invalid username or token. Password authentication is not supported for Git operations.
[sync] 2026-09-24 04:52:45 result=ok exit=0 reason=ok pending_before=2 attempts=1 credential=token(env-file:/home/atushi/.config/kensho/github-sync.env)
[gen] /mnt/d/Project2/kensho/docs/daily_reports/2026-09-24.md (1351 文字)
[ok] commit (attempt=1)
[carry] 前回の未push分を検出: 未push 2 件を再送する
[ok] pushed: docs/daily_reports/2026-09-24.md (attempt=1, credential=token(env-file:/home/atushi/.config/kensho/github-sync.env), pending_before=2)
[sync] 2026-09-24 04:52:45+0900 wrapper_exit=0

$ cat logs/github_sync_state.json
{
  "last_run": "2026-09-24T05:04:06",
  "last_result": "ok",
  "last_reason": "ok",
  "last_exit_code": 0,
  "last_detail": "To https://github.com/atushi1841/kensho.git",
  "pending_commits": 0,
  "consecutive_push_failures": 0,
  "last_success": "2026-09-24T05:04:06"
}
```

失敗時（意図的に不正 token を注入した負例・cron 相当 env）:

```
$ env -i PATH=/usr/bin:/bin HOME=/home/atushi GITHUB_TOKEN=invalid_token_for_test_5dff275b python3 kensho_github_sync.py --date 2026-09-24
[warn] push 失敗 (exit=128) reason=auth: remote: Invalid username or token. Password authentication is not supported for Git operations.
コミットはローカルに残留 — 次回実行時に 1 件を再送する
exit=2
```

### (5) 受入条件2: index.lock 保持中でも commit が落ちない（実リポジトリ実測）

擬似競合プロセスが `.git/index.lock` を 25s 保持した状態で同期を実行:

```
$ bash /tmp/lock_race_demo.sh 25
=== 1) 擬似競合プロセス起動（index.lock を 25s 保持） ===
[holder] created /mnt/d/Project2/kensho/.git/index.lock pid=385936
-rwxrwxrwx 1 atushi atushi 0 Sep 24 04:58 .git/index.lock
=== 2) その状態で github_sync を実行（retries=8 / backoff=2s） ===
wrapper_exit=0
=== 3) index.lock 残留確認 ===
ls: cannot access '.git/index.lock': No such file or directory
=== 4) ログ末尾 ===
[sync] 2026-09-24 05:04:06 result=ok exit=0 reason=ok pending_before=1 attempts=3 credential=token(env-file:/home/atushi/.config/kensho/github-sync.env)
[ok] commit (attempt=6)
[ok] pushed: docs/daily_reports/2026-09-24.md (attempt=3, ...)
[sync] 2026-09-24 05:04:06+0900 wrapper_exit=0
```

`commit (attempt=6)` = 退避リトライで競合を抜けた（前回実測の即死 `git 操作失敗 (128): index.lock File exists` の再発なし）。
`push (attempt=3)` = 接続失敗2回を再試行して成功（③の間欠接続対策が実働）。

### (6) 回帰テスト

```
$ python3 -m pytest tests/test_kensho_github_sync.py -p no:cacheprovider --no-cov -q
32 passed in 3.56s

$ .venv/bin/python -m pytest -p no:cacheprovider --no-cov -q   # 全体
2 failed, 1023 passed, 4 skipped in 229.71s
```

全体の2件は `tests/test_regression_gates.py` の kanban DB 直読ゲート（result 空 / サイレント終了の再発検知）で、
本変更（github_sync の git 配線）とは無関係のボード状態検知。新規32件は全て pass。

### (7) guard 条件(i) cron配置drift

```
$ python3 scripts/kensho_script_drift_check.py --json
{"ok": true, "checked": 51, "drift": 0, "missing": 0, "untracked_git_outside": 41, "allowed_intentional": 1, "fails": []}
```

## 実装内容（変更ファイル）

| ファイル | 変更 |
|----------|------|
| `kensho_github_sync.py` | credential源の解決（repo外 env ファイル → PATH非依存化した GCM helper）、`GIT_TERMINAL_PROMPT=0` 強制、`flock` 直列化、`index.lock` 退避リトライ＋stale回収（保持プロセスは /proc で確認）、push の lowSpeed 設定＋network/timeout のみ再試行、失敗理由の分類（auth/network/rejected/index_lock_busy/timeout）、exit code/理由/理由クラスを `logs/github_sync_cron.log` と `logs/github_sync_state.json` に記録、未push分を次回実行で再送 |
| `scripts/kensho_github_sync.sh` | `set -e` をやめて exit code を必ずログに残す、`GIT_TERMINAL_PROMPT=0`/`GCM_INTERACTIVE=never` を export |
| `scripts/git-credential-kensho-env.sh` | 環境変数 token を返す credential helper（token を含まない・コミット可） |
| `scripts/make_github_sync_env.py` | GCM から token を取得して repo 外 `~/.config/kensho/github-sync.env`（600）を生成（値を stdout に出さない） |
| `tests/test_kensho_github_sync.py` | 32件の回帰テスト（credential解決順 / 理由分類 / lock 退避・stale回収・保持中は不可侵 / flock 排他 / push 再試行 / 状態持ち越し / 生成は常に実施） |

## 制約の遵守

- **生成の可用性**: push が失敗しても当日レポートは必ず生成（テスト `test_main_records_commit_failure` で
  commit 失敗時も `docs/daily_reports/<date>.md` が存在することを検証）。負例でも `[gen] ... (1351 文字)` を実測。
- **token はコミットしない**: token は repo 外 `/home/atushi/.config/kensho/github-sync.env`（mode 600）にのみ存在。
  repo 内の helper は環境変数を読むだけで token 文字列を持たない（`git status` 上も未追跡・未コミット）。
- **コード変更はコミット済み**: `bd4b9a4`（`*.py`/`*.sh` 5ファイル）。

## 未達成・申し送り

- 「`docs/daily_reports/` が7日連続 push」の再判定は本カードの観測対象外（再監視カードが担当）。本カード時点の実測は
  2026-09-24 分の push 成功（`git log --format='%h %ci %s' origin/main -3 -- docs/daily_reports/` で当日分が
  `14e7a23 2026-09-24 04:58:49 +0900 docs: 稼働サマリー 2026-09-24 (auto)` として origin/main 到達）。
- 接続の間欠性そのもの（WSL↔GitHub）は環境要因で、本実装は「失敗しても持ち越して次回再送」で吸収する設計。
