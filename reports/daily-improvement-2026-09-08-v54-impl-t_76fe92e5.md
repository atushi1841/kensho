# critic v54 実装検証レポート — monitor署名にdirtyフラグ追加 (t_76fe92e5)

日付: 2026-09-08 (JST)
対象タスク: t_76fe92e5 (critic_proposal_2026-09-08-v54)
対象ファイル: ~/.hermes/scripts/board_state_monitor.sh (1ファイルのみ、git管理外)
ロールバック: ~/.hermes/scripts/board_state_monitor.sh.bak-v54 (編集前に作成済み)

## 変更内容

board_state_monitor.sh の状態署名末尾に `|dirty=Y|N` を追加。
loop_health.sh とは独立に `git -C /mnt/d/Project2/kensho status --porcelain` を取得し、
kanban_done_guard.py の is_code_file() と同一の除外規則
（data/・reports/ トップレベル除外、*.html 除外、コード=.py/.yaml/.sh/.js のみ）を適用して
残ったコード変更が1件以上なら dirty=Y、無ければ dirty=N。
真偽値のみを署名に含める（age・件数は毎tick変動してmonitorを無効化するため不可）。
git 失敗・判定不能は dirty=N（guard の [] 扱い＝ブロックしない、と一致）。

効果: 未コミットWIPが全収益タスクを連鎖ブロックしても署名が変化しなかった
（v51: simple_rt_classifier.py 移行WIP、v52: analyze_windows_0906.py の2回実測）問題を、
monitor の変化検出経由で agent が自動起動して復旧できるようにする。

## verification_evidence

$ cp /home/atushi/.hermes/scripts/board_state_monitor.sh /home/atushi/.hermes/scripts/board_state_monitor.sh.bak-v54
→ バックアップ作成（編集前、ロールバック要件充足）

$ python3 /home/atushi/.hermes/kanban/boards/kensho-ai-team/workspaces/t_76fe92e5/verify_v54.py
=== run1 clean (expect dirty=N) ===
score=95|ready=0|blocked=0|wip=1|done=316|prio=new_proposals|streak=0|esc=False|skip=False|dirty=N
=== run2 probe exists (expect dirty=Y) ===
score=95|ready=0|blocked=0|wip=1|done=316|prio=new_proposals|streak=0|esc=False|skip=False|dirty=Y
=== run3 probe removed (expect dirty=N) ===
score=95|ready=0|blocked=0|wip=1|done=316|prio=new_proposals|streak=0|esc=False|skip=False|dirty=N
=== run4 same state as run3 (expect identical to run3) ===
score=95|ready=0|blocked=0|wip=1|done=316|prio=new_proposals|streak=0|esc=False|skip=False|dirty=N
checks:
  'dirty=' appears exactly once per sig: True
  run2 has dirty=Y: True
  run1/run3/run4 have dirty=N: True
  run3 == run4 (100% identical, 0 diff): True
  probe file cleaned up: True
（touch /mnt/d/Project2/kensho/_sig_probe.py → dirty=Y、rm 後 dirty=N への遷移、
　同一状態2連続実行で差分0行。成功指標3項目すべて合格。probe ファイルは検証後削除済み）

$ python3 /home/atushi/.hermes/kanban/boards/kensho-ai-team/workspaces/t_76fe92e5/crosscheck_guard.py
guard uncommitted code files: []
guard verdict dirty: N
（kanban_done_guard.py 本体の git_uncommitted_code_files() と monitor の dirty 判定が
　同一状態で一致することを確認 — 除外規則の実コピーではなく guard 実関数でのクロスチェック）

## 影響範囲

nightly-critic / nightly-worker / nightly-qa (4baf143523e0 / 5e8ec4984bba / 033ff6065ef7) の
3 cron すべてが同じ ~/.hermes/scripts/board_state_monitor.sh を monitor として参照済み。
初回実行時に署名が dirty=N 付きへ変化するため1回だけ agent が起動する（提案書に記載の想定内挙動）。
以降は通常どおり状態不変なら SKIP。

## 代替案（不発時）

署名が毎tick変動して monitor が機能しなくなった場合は bak-v54 を戻し、
loop_health.sh 側の減点項目（uncommitted code: -10）として実装し直す（提案書記載どおり）。
今回の検証では dirty は真偽値のみで安定動作を確認済み、代替案は不要。
