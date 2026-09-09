# critic v79 実装レポート — done_guard 条件(d) cross-task bleed 修正 (t_9206eee8)

日付: 2026-09-10 (run340)
作業者: kensho-revenue-worker

## 実施内容

`kanban_done_guard.py` に `--task` フラグを追加し、条件(d) の未コミットコード検査を
タスク所有ファイルに限定した。並行 workstream 由来の dirty ファイルが
finish 可能なタスクを巻き込んでブロックする問題（2026-09-09 t_88b6d325 の QA
override 事例、t_7b040302 WIP + scripts/dm_scan.py が汚染源）の恒久対策。

- 所有帰属 = `git log --all --grep=<task_id>` が触れたパス + タスク body/title に
  列挙されたパス（相対一致 or ベースネーム一致）
- 所有外の dirty → `foreign_uncommitted_code_files` として WARNING 表示のみ、ブロックしない
- レグレッションガード維持: 自分の所有コード未コミットは BLOCK（v31/v55）
- 帰属判定不能（git 不能 / 所有パスゼロ）→ repo-wide へ fail-safe
- 既定（フラグ無し）は従来通り repo-wide 検査 → hooks 互換維持
- セルフテスト `_selftest_d_bleed()` 追加（bleed pass / own-dirty block / failsafe の3シナリオ）

コミット: kensho-sweeps repo 46d5651（scripts/kanban_done_guard.py +
tests/test_kanban_done_guard.py の2ファイルのみ。他 dirty は別 workstream のため意図的に未踏）

## 発見した罠（テストfixture）

`t_dscope01` という非hexのタスクIDをfixtureに使うと、v47 の `TASK_ID_RE`
（`t_[0-9a-f]{8,}`）がIDを認識できず dominant-id 規則で証跡所有判定が失敗する。
本番の kanban task ID は全て hex だが、テストは実ID形式に合わせる必要あり。
→ fixture を `t_deadbe01` に修正しコメントで明文化（テスト側のみ、guard 仕様は正しい）。

## verification_evidence

$ python3 /home/atushi/.hermes/profiles/kensho-sweeps/scripts/kanban_done_guard.py --selftest
→ SELFTEST OK (d_bleed): bleed scenario pass, own-dirty blocked, undecidable failsafe to repo-wide / SELFTEST OK: (e)+(d) works / EXIT=0（success metric 1・2 実証）

$ cd /home/atushi/.hermes/profiles/kensho-sweeps && python3 -m pytest tests/ -q
→ 16 passed in 0.69s（run339作の v79 回帰テスト5本込み、全パス）

$ git -C /home/atushi/.hermes/profiles/kensho-sweeps log --oneline -1
→ 46d5651 feat(guard): done_guard condition (d) task-scoped ownership fix --task flag (critic v79, t_9206eee8)

$ git -C /mnt/d/Project2/kensho status --porcelain -uall
→ data/reports/html のみ（コードdirtyゼロ、条件d対象外）

## 残課題（QAへ委譲）

success metric 3「cond(d) QA override ゼロを7日間」は時間経過監視であり、
QA の定期監査（t_fef285a1 系 cron）で追跡中。本カードでは実装+自己検証まで。
monitor 署名の dirty=N 化（448bc4d）で汚染源自体は除去済み（コメント参照）。
