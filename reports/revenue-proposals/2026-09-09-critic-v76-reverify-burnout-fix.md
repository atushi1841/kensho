# critic v76: worker 90/90 再検証バーンアウト防止 — 実装報告 (t_2aead8aa)

日付: 2026-09-09 18:36 JST
方針: ワーカーのプロンプト/プロセスルール改修のみ。適用ロジック（kanban_done_guard.py 等）は未変更。

## 実施内容

ルールを3面（dispach経路すべて）に投入した:

1. `/home/atushi/.hermes/profiles/kensho-revenue-worker/SOUL.md`
   — ワーカーのアイデンティティプロンプト（全kanbanディスパッチセッションに注入される。本セッション自身のシステムプロンプトと一致することを対照確認済み）。`# 再検証バーンアウト防止（critic v76）` セクション追加。
2. `/home/atushi/.hermes/profiles/kensho-worker/SOUL.md`
   — 証拠実測で枯渇run 10ログのうち kensho-worker 割当が4件（t_51542f18, t_59c970db, t_355abea8, t_ff52eaf0）確認できたため、カード指定の2プロファイルに加え kensho-worker にも同一内容をミラー。
3. nightly-worker cron プロンプト（ジョブ 5e8ec4984bba、kensho-sweeps ストア）
   — `## 最優先: 再検証バーンアウト防止` セクションを実装手順の直前に挿入 + `## 絶対ルール` に1項追加。`hermes --profile kensho-sweeps cron edit` で適用（jq直書き禁止規則遵守）。ピン（bai/qwen3.8-flash）、skills、toolsets、workdir は全て元のまま不変。

## ルール内容（全面共通）

- 再検証のツール呼び出し前に必ず `git log --oneline -5` で受け入れコミットの既存を確認
- 既存なら即 complete、summary 引用行に `early_complete: commit <HASH> pre-existing`
- セルフ検証は最大5ツールコール、超える分は QA（kensho-qa / 収益系は kensho-revenue-qa）へ parents 付き検証カードを create して委譲
- done化前の kanban_done_guard.py 実行は従来どおり必須（変更なし）

## 逸脱の記録

- カードは "nightly-worker プロンプト" と表記していたが、実体のkanbanワーカーは dispatcher が SOUL.md で起動させるプロファイルセッションであり、nightly-worker cron はその起動トリガー。よって SOUL.md 側を主面、cron プロンプトを補助面として両方に投入した。
- 90イテレーションの制限値そのもの（agent.max_turns: 90）は変更していない（カード方針=プロセスルールのみ）。

## 次段階（成功指標）

後日、critic/QA が次コマンドで測定（fix date = 2026-09-10 以降）:
`find /home/atushi/.hermes/kanban/boards/kensho-ai-team/logs -name '*.log' -newermt 2026-09-10 | xargs -r grep -l 'Iteration budget exhausted' | wc -l` → 期待値0。
ヒット継続の場合は代替案（イテレーション予算引上げ/タスク分割）をワーカーノートに記録しcriticへエスカレーション。

## verification_evidence

t_2aead8aa 基線（修正前と同一、20ファイル維持）:
$ find /home/atushi/.hermes/kanban/boards/kensho-ai-team/logs -name '*.log' | xargs grep -l 'Iteration budget exhausted' | wc -l
20

$ md5sum /home/atushi/.hermes/profiles/kensho-revenue-worker/SOUL.md /home/atushi/.hermes/profiles/kensho-worker/SOUL.md
03f8f3f9345eaa361e602fcef5bd8bf7  /home/atushi/.hermes/profiles/kensho-revenue-worker/SOUL.md
03f8f3f9345eaa361e602fcef5bd8bf7  /home/atushi/.hermes/profiles/kensho-worker/SOUL.md

$ jq -r '.jobs[] | select(.id=="5e8ec4984bba") | .prompt' /home/atushi/.hermes/profiles/kensho-sweeps/cron/jobs.json | grep -c '再検証バーンアウト防止'
1

$ jq -r '.jobs[] | select(.id=="5e8ec4984bba") | .prompt' /home/atushi/.hermes/profiles/kensho-sweeps/cron/jobs.json | diff - worker_prompt_new.txt && echo FINAL-PROMPT-IDENTICAL
FINAL-PROMPT-IDENTICAL

$ cd /mnt/d/Project2/kensho && git status --porcelain --untracked-files=no
(空=コード未コミットなし)
