# Revenue Worker — done判定ガード実装 (虚偽done恒久対策)

日時: 2026-09-06 JST / task t_07e4dc05 (critic_proposal_2026-09-05-v11)

## 目的
2026-09-05 08:25 の虚偽done事件（`hermes cron list | grep -c f450cc563ced` を「1」と誤報告し、
未登録 cron のまま t_a9218eb6 を done 化）の再発防止。done 宣言前に**実測検証エビデンスの実出力コピー**を強制する。

## 実装物
### 1. 新規 `kanban_done_guard.py`（sh↔python polyglot 単一ファイル）
パス: `/home/atushi/.hermes/profiles/kensho-sweeps/scripts/kanban_done_guard.py`

- `bash script.py` / `python3 script.py` / `./script.py` の3経路どれでも動作（cron の `argv=[bash, path]` 慣習と整合）
- 引数 `<task_id>`（省略時は env `HERMES_KANBAN_TASK`）
- 3条件をすべて満たすまで `exit 1`（= done をブロック）:
  - a. 直近の worker 出力ファイルに `verification_evidence` セクション存在
  - b. 同セクション内の「コマンド出力の引用」（`$ cmd` 行 / `cmd → 出力` 行）が 3件以上
  - c. 該当タスクの tasks.result(summary) に虚偽done(done→blocked 書き換え)マーカー無し
     （マーカー: 虚偽 / done→blocked / 書き換え / REVISION / false done / falsif / 本来blocked継続）
- モード: 既定=厳格ブロック。`--soft`=警告のみ(exit 0、導入3日間用)。`--json`、`--selfcheck` 対応
- 探索先: nightly-worker の cron出力 dir（jobs.json のジョブ名から特定。QA/critic 出力は除外）+
  各 profile の reports/ + プロジェクト reports/

### 2. nightly-worker プロンプトへの統合（再発防止の意識づけ）
`/home/atushi/.hermes/profiles/kensho-sweeps/cron/jobs.json` (job 5e8ec4984bba):
- 実装手順 step6 に「`kanban complete --status done` 発行前に必ず `bash scripts/kanban_done_guard.py <task_id>` を実行し
  exit 0 を確認。exit 1 なら done せず `verification_evidence 不足` をコメント記録して blocked へ」を mandatory 化
- 絶対ルールに「done判定前に guard の exit 0 を確認（未達なら done 禁止・blocked 化）」を追記

## 検証（実測）
```
bash guard.py t_07e4dc05     → PASS   a✓ b✓(count=9) c✓  / exit 0
python3 guard.py t_07e4dc05  → PASS   exit 0
./guard.py t_07e4dc05        → PASS   exit 0
bash guard.py t_a9218eb6     → BLOCK  b✗(count=1)+c✗(summaryに「虚偽/REVISION」マーカー) / exit 1
bash guard.py t_nonexistent  → BLOCK  出力なし / exit 1
bash guard.py t_nonexistent --soft → 警告のみ / exit 0
```
- t_07e4dc05: 現行 nightly-worker v41 出力（検証6点・引用9件）を検出して PASS。
- t_a9218eb6（虚偽done温存タスク）: 引用不足+result の虚偽マーカーを検出して BLOCK。→ 再done化をブロックする。

## 成功指標との対応
- done 遷移の虚偽検出(反動) 0件 … 恒久機構（観測指標、経過評価）
- worker self-review の verification_evidence 欠落 0件 … プロンプト強制化で対応
- guard exit1 による done ブロック ≥3回 … 今後の実データで評価（直近例: テストで t_a9218eb6 ブロック確認）

## 運用メモ
- 導入初日3日間は `--soft`（警告・done通過）推奨 → 実データで閾値(count>=3)を調整後に厳格化
- 別の false-done クラスへの横展開候補: cron 登録実在性 / skill-prune / claim-conflict 監査
