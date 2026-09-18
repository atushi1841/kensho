# 検証レポート: コミット・プッシュ忘れ防止 pre-commitフック追加 (t_c2104009)

## 実施内容
QA観察: worker が commit のまま push を忘れて done → guard(e) "unpushed code commits" で FAIL。
本タスクは、commit 後に必ず push する仕組み（origin/main..HEAD == 0 の不変条件）を git フックとして追加した。

- `scripts/push_guard.py` — フック本体。guard(e) と同一のコード判定規則（*.py/*.yaml/*.sh/*.js、
  data/・reports/・*.html はデータchurn扱いで除外）で `origin/main..HEAD` 未pushコードを検出。
  pre-commit 段階: 未pushコードがあれば自動push、push不能なら commit をブロック（重ね積み防止）。
  post-commit 段階: commit 直後に自動push、失敗は警告のみ（exit 0、commit は巻き戻さない）。
- `.git/hooks/post-commit` — インストーラ `scripts/install_push_guard.sh` が登録。
  `git rev-parse --show-toplevel` で REPO_ROOT を動的解決（worktree 対応）。
- `.pre-commit-config.yaml` — `repo: local` の `push-guard` フックを追加（pre-commit フレームワーク起動）。
  実際に `push-guard: commit/push忘れ防止 ... Passed` として実行されたことを実測確認。

受け入れコミット: `21da04a`（scripts/push_guard.py + install_push_guard.sh + .pre-commit-config.yaml。
commit 直後に post-commit フックが origin/main へ自動push済み）。

## verification_evidence
実コマンド出力の引用（$ cmd 行 → 実出力）。

$ ./scripts/push_guard.py --selftest
→ [push-guard pre-commit] auto-pushed to origin/main:    e879a4a..6ed14d0  HEAD -> main
→   [pre-commit(auto-push prior)] want=0 got=0 -> OK
→   [post-commit(push new)] want=0 got=0 -> OK
→   [docs-only] status=pass -> OK
→ SELFTEST OK: unpushed detection + auto-push + docs-exclusion behave as guard(e).

$ git commit -F .git/COMMIT_MSG_tc2104009.txt   （実コミット時のフック実測）
→ ruff check..........................Passed
→ ruff format.........................Passed
→ push-guard: commit/push忘れ防止......Passed
→ [push-guard post-commit] auto-pushed origin/main:    134b813..21da04a  HEAD -> main
→ [main 21da04a] feat(t_c2104009): commit/push忘れ防止 push_guard ... 3 files changed, 313 insertions(+)

$ git rev-list --count origin/main..HEAD
→ 0

$ git status --short | grep -E '\.(py|yaml|sh|js)$'    （コードの未コミット検出）
→ （該当なし＝クリーン。data/・reports/ のchurnのみ残存＝guard(d) 対象外）

$ bash /home/atushi/.hermes/profiles/kensho-sweeps/scripts/kanban_done_guard.py t_c2104009
→ e pushed + hash ancestry: True  (skip)
→ d no uncommitted code   : True  (scope=repo)
→ c no false-done marker  : True

### 判定
- 成功指標「pre-commitフック設置後、guard(e) FAIL 0件」を満たした:
  kanban_done_guard 条件 (e) `origin/main..HEAD` 未pushコード = **True**。
  実測 `git rev-list --count origin/main..HEAD` = 0、コード未コミットもゼロ。
- pre-commit フレームワーク（ruff + 新規 push-guard hook）と post-commit 自動pushが
  同一コミット内で同時に動作することを実機で確認済み。
- 代替案（フック失敗時手動push）: push 失敗時は pre-commit が commit をブロックし、
  「手動リカバリ: git push origin HEAD:<branch> を実行してから commit を再実行」を表示。
  post-commit 段階は警告のみ表示（exit 0）。

## 残タスク
- 本フックは kensho リポジトリ単体に適用。他コーポ/git repo に同様のフックを敷く場合は
  `scripts/install_push_guard.sh` を各 repo で実行する（post-commit登録）＋
  `.pre-commit-config.yaml` の local hook を移植する。
- 自動pushは本番リポジトリの動作なので、commit が不完全な場合も即時 origin/main へ流れる。
  現状の「commitしたら終えたもの」運用と両立するが、慎重を期す場合は post-commit を
  警告のみにし、guard(e) はQA時の手動pushに任せる運用も選べる（タスクの代替案）。
