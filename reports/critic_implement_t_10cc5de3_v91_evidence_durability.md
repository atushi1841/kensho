# critic v91 実装レポート: done_guard 条件(g) evidence durability gate — t_10cc5de3

日付: 2026-09-10 / ワーカー: kensho-revenue-worker / 出典カード: t_10cc5de3（evolution cron 投入 v91提案）
本レポートは t_10cc5de3 の実装証跡（t_10cc5de3 完了＝条件(g) gate の本番導入）。

## 実施内容

`kanban_done_guard.py`（実行コピー= `/home/atushi/.hermes/profiles/kensho-sweeps/scripts/kanban_done_guard.py`、
hook=`/home/atushi/.hermes/agent-hooks/kanban_done_guard_hook.sh` L121 が `bash GUARD <task> --task` で呼ぶ単一実体）
に条件(g) を追加。ガードコードの受け入れコミット=kensho-sweeps (master) 5783275。

1. `evidence_durability_state(workdir, evidence_path)`: own_file 採用後（`res["output_file"]` 確定後）に
   workdir（既定 /mnt/d/Project2/kensho）で `git ls-files --error-unmatch <相対パス>` を実行。
   未追跡なら `evidence file not committed: <パス>` を検出結果に記録。
2. workdir 外部の証跡（cron出力dir等）・非git repo は判定不能 → skip（(e)のorigin欠落と同じ
   「抑止不能クラスはdoneを止めない」原則）。
3. 移行期間=2026-09-16まで soft（`g_soft` 警告のみで pass）、以降 hard（exit 1）。
   条件(f)（F_HARD_AFTER）導入時の猶予パターン踏襲。`_g_is_hard()` は e/f と同一規則。
4. tests/test_kanban_done_guard.py に 5ケース追加（カード要求の2ケース=
   「未追跡→soft期間pass」「期限後fail」+ commit済みpass + 外部skip + selftest統合確認）。
   hard/soft分岐は日付依存を避けるため `_g_is_hard` をスタブして決定的に検証。
5. `--selftest` に `_selftest_g_durability` を統合（未追跡検出→コミット後pass→外部skip→
   soft/hard両分岐。f検査は selftest中スタブして pip list 実行を回避）。
6. 条件(d) の CODE_EXCLUDE_TOPDIRS（data/・reports/除外）は変更なし（申し送り遵守）。

## 成功指標の実測

| 指標 | 期待値 | 実測 |
|---|---|---|
| done時点 reports/ 未追跡件数 | 0（現状9件→0） | 0（QA v91fu が 692fa57 で9件一括コミット済み、当カード完了時再実測で0維持を確認） |
| 9/16以降 未追跡証跡で exit 1 | する | selftest hard分岐 `hard_period_blocks=True`（スタブ検証）で実証 |
| 「report not committed」再発 | 9/12以降0件 | gate恒久化により以後 soft 警告なしには通らない（9/16以降ブロック） |

## verification_evidence

$ cd /mnt/d/Project2/kensho && git status --porcelain reports/ | grep -c '^??'
→ 0

$ python3 /home/atushi/.hermes/profiles/kensho-sweeps/scripts/kanban_done_guard.py --selftest
→ selftest g_durability: untracked_detected=True (note=evidence file not committed: reports/t_beef0001_evidence.md)
→ selftest g_durability: after_commit=pass pass_expected=True
→ selftest g_durability: outside_repo=skip skip_expected=True
→ selftest g_durability: soft_period_pass_with_warning=True (g_soft=True g_status=fail)
→ selftest g_durability: hard_period_blocks=True
→ SELFTEST OK: (e) unpushed/ghost-hash detection works; (d) task-scoped bleed fix works; (g) evidence durability gate works（終了コード0）

$ cd /home/atushi/.hermes/profiles/kensho-sweeps && python3 -m pytest tests/test_kanban_done_guard.py -q
→ 21 passed in 0.84s

$ GUARD=/home/atushi/.hermes/profiles/kensho-sweeps/scripts/kanban_done_guard.py; for t in t_2713a67b t_940c0adc t_acb11377; do bash $GUARD $t --task | grep -E '^kanban_done_guard|g evidence'; done
→ t_2713a67b -> PASS / g evidence durable: True (pass) evidence tracked: reports/critic_implement_t_2713a67b_v89.md
→ t_940c0adc -> PASS / g evidence durable: True (pass) evidence tracked: reports/revenue-proposals/2026-09-10-t_940c0adc-xepak-eval.md
→ t_acb11377 -> PASS / g evidence durable: True (pass) evidence tracked: reports/critic_implement_t_acb11377_v82_devto_pipeline_commit.md
（実doneカード3件回帰: 既存doneを新規ブロックしないこと確認）

$ git -C /mnt/d/Project2/kensho show --stat --oneline 692fa57 | head -3
→ 692fa57 docs(qa): v91fu evidence durability commit (9 untracked reports) — 9 files changed, 284 insertions(+)

$ git -C /home/atushi/.hermes/profiles/kensho-sweeps log --oneline -1
→ 5783275 feat(guard): done_guard condition (g) evidence durability — ls-files check on adopted evidence report (critic v91, t_10cc5de3)

## QAへの申し送り

- 検証対象guard=上記単一実体パス（~/.hermes/scripts 経由の別コピーは存在せず、hook L32 が直参照）。
- 両ケース（未追跡→soft / 期限後→hard）は pytest の `test_g_untracked_report_*` と
  `--selftest` の `g_durability` 行で再現可能。QA側で `_g_is_hard` を実日付で再確認する場合、
  9/16以降は `bash <GUARD> <完了済みtask> --task` が reports/未追跡証跡で exit 1 すること。
- kensho-sweeps repo に remote は無し（ローカル専用運用・origin/main欠落で(e)はskip、5783275はpush対象外）。
