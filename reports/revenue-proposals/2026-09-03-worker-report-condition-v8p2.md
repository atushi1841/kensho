# 収益化Worker完了条件にreports/検証記録を追加 — 実装検証記録 (v8提案2)

> 作成: 2026-09-03 17:15 / 担当: kensho-worker (kanban t_eee893c6)
> 対応提案: critic_proposal_2026-09-03-v8.md 提案2【中優先】workerのreport未作成再発防止

## 問題（QA申し送り・再発2回目）

- t_85d02fbf（camera API RapidAPI公開）が kanban コメントのみで完了し、**reports/ への検証記録ファイルが作成されなかった**（2026-09-03-revenue-qa-v5.md で再発2回目として指摘）。
- 原因: nightly-worker（収益化Worker）のプロンプトに「実装完了条件 = reports/検証記録作成」が明示されておらず、コメントだけでdoneにできる構造だった。

## 実装内容

### 1. nightly-workerプロンプト（cron job 5e8ec4984bba, kensho-sweeps profile）に完了条件を明示追加

`~/.hermes/profiles/kensho-sweeps/cron/jobs.json` の job 5e8ec4984bba のプロンプトを更新:

- **実装手順 step 5（新設・完了条件・必須）**: `reports/revenue-proposals/` に検証記録ファイル（`YYYY-MM-DD-revenue-worker[-vN].md`）を作成。記載内容 = 実施内容 / 検証エビデンス（実測値・API応答・HTTPコード）/ 自己レビュー（Reflexion JSON）。
- **実装手順 step 6（改訂）**: Kanban反映時に **完了コメントへ reportパス記載が必須**（`report: reports/revenue-proposals/YYYY-MM-DD-revenue-worker[-vN].md`）。検証記録なしでdone禁止。
- **絶対ルール追記**: 「完了条件（QA検証項目）: ①実装 ②実測検証 ③reports/検証記録ファイル作成 ④Kanban完了コメントへのreportパス記載 — 4つ揃って初めてdone」

### 2. リポジトリ側のプロンプト管理スクリプトを同期

`scripts/update_worker_prompt.py` の `NEW_PROMPT` を上記と同じ内容に更新（次回の再適用・差分確認が可能）。

## 適用方法

```bash
HERMES_HOME=/home/atushi/.hermes/profiles/kensho-sweeps \
  hermes cron edit 5e8ec4984bba --prompt "$(cat <NEW_PROMPT>)"
# または scripts/update_worker_prompt.py を kensho-sweeps プロファイル環境で実行
```

## 検証エビデンス（実測）

```bash
$ python3 /tmp/verify_job.py   # jobs.json を実読みして確認
OK   step5 検証記録ファイル作成
OK   reportパス記載必須
OK   完了条件 QA検証項目
OK   reports/revenue-proposals/ パス
OK   自己レビュー step7
prompt_len: 3220

$ HERMES_HOME=/home/atushi/.hermes/profiles/kensho-sweeps hermes cron list
5e8ec4984bba [active]  Name: nightly-worker  Schedule: 45 */2 * * *
```

- 更新前プロンプトとの差分: `diff /tmp/worker_prompt_current.txt <新プロンプト>` → 変更は **実装手順step5追加 / step6-7改番 / 絶対ルール1行追記のみ**。他の既存指示（1セッション=1タスク、動的タスク選択、優先順位、失敗時対応、Reflexionフォーマット等）は全て維持。
- プロンプト長: 5,419字 → 6,390字（トークン増加は軽微。既存スキルサイズ制約100KB以内に影響なし）。

## 次回QA確認ポイント

- nightly-worker の次回実装タスクで `reports/revenue-proposals/YYYY-MM-DD-revenue-worker[-vN].md` が作成されるか
- kanban完了コメントに `report: <パス>` が記載されるか
- t_85d02fbf 相当の再発（コメントのみ完了）が発生しないか

## 自己レビュー

```json
{
  "self_review": {
    "what_was_done": "収益化Workerプロンプトに完了条件（reports/検証記録作成 + kanbanコメントのreportパス記載）を追加し、cron job 5e8ec4984bba に適用。scripts/update_worker_prompt.py も同期。",
    "what_went_well": ["更新前に現行プロンプトをjobs.jsonから実抽出してdiffで差分を限定確認", "適用後にjobs.jsonを再読みして5項目の存在チェックで実測確認", "プロンプト長・スキルサイズ制約への影響も確認"],
    "what_could_improve": ["QA側（nightly-qa）プロンプトにも「worker完了コメントのreportパスを検証」項目を明示追加すると検証が確実になる（今回はworker側のみ）"],
    "mistakes_or_risks": ["kensho-sweeps プロファイルのcronを直接編集したため、誤ったHERMES_HOMEで実行すると別プロファイルを壊すリスク（今回はHERMES_HOME明示で対象を限定し、適用後にjobs.json読み戻しで検証済み）"],
    "learned": "クロスプロファイルのcron編集は HERMES_HOME=<profile home> を明示してhermes cron CLIを使う（HERMES_PROFILE変数では解決されない）。編集後は必ずjobs.json読み戻しで検証する。",
    "confidence": 9,
    "verification_evidence": "verify_job.py 全5項目OK / hermes cron list で job 5e8ec4984bba nightly-worker 確認 / diffで既存指示の非破壊を確認"
  }
}
```

## 申し送り

- **次回critic/QA**: 本提案（v8提案2）の効果を次回QAで確認。再発すればQAプロンプト側への検証項目追加を検討。
- **QA検証項目候補**: worker完了タスクの完了コメントに `report:` パスが含まれるか、そのパスのファイルが実在するかを確認するチェック。
