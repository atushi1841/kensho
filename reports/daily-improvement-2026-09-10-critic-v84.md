# nightly-critic v84 (2026-09-10 06:2x JST)

## 前回申し送りの効果検証
- t_acb11377 (devto_weekly_pipeline.py 未追跡) は完全解決。worker fbf755a でコミット (pre-commit ruff gate 通過)、QA v83 が独立検証 (pytest 533 passed + 4 skipped, cron d538be4f5549 パス解決, push 完了)。
- 残る最終受入ゲート = 9/14 12:00 JST の cron d538be4f5549 初回実行 (exit 0 + drafts >= 1)。

## 新規提案 (1件)
- t_4e88dfeb: devto weekly pipeline 9/14 first-run verification。ready=0 供給不足 (new_proposals priority) に対応。
- 成功指標: cron 実行 exit_code=0, Error 0件, dev.to drafts 1件以上
- 検証コマンド: `hermes cron list 2>&1 | grep -A 12 devto` + `git ls-files | grep -c devto_weekly_pipeline.py`
- 代替案: API/トークン失敗時は blocked + [USER-ACTION-REQUIRED] (Dev.to API key rotation)、再び未追跡化したら HIGH でエスカレーション
- scheduled (9/14) に仮置き: それまで QA に着手させない

## 教訓追加 (実測)
- `hermes kanban schedule` の実構文は位置引数のみ。SKILL.md 記載の --unblock-date / --reason フラグは実在せず、SKILL.md 自体を修正済み。

## 健康度
score=95, streak=0, blocked=0, ready=0, sched=5, done=374, dirty=N

## 継続監視
- 【要ユーザー対応】TankanNotes proxy 1085 dead day6: USB物理再挿入のみ (ソフトでは解決不可)
