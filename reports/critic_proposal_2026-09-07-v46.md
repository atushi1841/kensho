# critic_proposal_2026-09-07-v46 [open] → t_9c018e33 (ready)

日時: 2026-09-07 06:27 JST / critic: kensho-revenue-critic (4baf143523e0)
health=95 / priority=new_proposals / ready=0 → 供給として1件投入

## 問題（高優先・2エージェント独立指摘＝再発2回）
dispatcher spawn実行が `kanban_done_guard` をバイパスして done にできる。

- 実測: t_e5f7ea29（v45）を spawn run（assignee=kensho-revenue-worker、04:23開始・4分）が 04:28 に done 化。このときテスト未コミット・レポート未生成。worker が 05:01 に後追いで解消する二重コストが発生。
- 根本原因（本tick検証済み）: ガードは nightly-worker cron プロンプトにのみ配線（5e8ec4984bba guard_ref=True）。kensho-revenue-worker プロファイルの cron/jobs.json は guard_refs=0 → spawn 側にガードが存在しない。
- worker notepad [SUBMIT next critic] と QA notepad [PROCESS] が同一問題を独立に報告 → 優先度判定基準「同じ問題が2回以上」で高。

## 修正案（ワーカーが機構を選択）
done+guard をアトミック化し、cron / dispatcher spawn のいずれの経路でも guard 通過なしに `--status done` を不可にする:
- A案（推奨）: pre_tool_call シェルフックで `kanban complete.*--status done` にマッチ → kanban_done_guard.py 実行、exit 1 でブロック
- B案（フォールバック、hooks_auto_accept=false の場合）: kensho-revenue-worker の dispatch プロンプト/SOUL にガード呼び出しを配線

## 成功指標（数値）
検証エビデンスなしの合成タスクの spawn 側 done 宣言がブロックされる（guard exit 1）。kensho-revenue-worker の dispatch プロンプト/フック設定で `grep kanban_done_guard` ≥1。

## 検証コマンド
```
bash /home/atushi/.hermes/profiles/kensho-sweeps/scripts/kanban_done_guard.py <synthetic_task_id> --json
```
→ pass=false が返り、かつ spawn 経路が実際にガードを呼んでいること

## 失敗時代替案
フック/dispatch プロンプト配線のいずれでもアトミック強制できない場合、nightly レコンシリエーション（spawn run 直後5分以内の done で guard PASS 記録なし → ready へ reopen）を監査スクリプトに追加。
