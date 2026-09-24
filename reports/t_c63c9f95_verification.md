# verification_evidence

## タスク: t_c63c9f95

## 1. watchdog 最小PATH インシデント復活（実測）

```
$ bash -n /home/atushi/.hermes/profiles/kensho-sweeps/scripts/kensho-cron-watchdog.sh; echo $?
0
```

```
$ env -i HOME=/home/atushi PATH=/usr/bin:/bin bash /home/atushi/.hermes/profiles/kensho-sweeps/scripts/kensho-cron-watchdog.sh
🔴 cron失敗インシデント検出（3件）

【未通知】3件:
  🆕 9aede4_589a6c2ad76d
  🆕 9aede4_da8157505e9a
  🆕 9aede4_4548a002ef2d

⚠️ cron 無音欠火 1ジョブ / 計1回 （min-severity=medium as_of=2026-09-25T04:56+09:00 lookback=26.0h grace=120.0m）
  [high] d340ec02d57e kensho-ai-team-daily-evolution ... missed=1回 ... last_run=2026-09-25T04:54:18...
  対処: `hermes cron run <job_id>` で取り戻し実行し、欠火の原因を調べる

EXIT=0
```

## 2. 出力長制約 プロンプト反映（実測）

```
$ grep -n '2KB以内' /home/atushi/.hermes/profiles/kensho-sweeps/scripts/kensho-research-agent.py
398:    lines.append("- 応答全体は2KB以内に収め、詳細は reports/ に write_file で保存し、チャット本文に長文を書かないこと")
```

## 3. d340ec02d57e 復旧状況

cron側セッション（kensho-revenue-worker cron job, background pid 659843）が `hermes cron run d340ec02d57e` を実行中。本カード t_c63c9f95 では重複実行せず、cron側に終端確認を委譲。

## 4. 変更ファイル

- `scripts/kensho-cron-watchdog.sh` lines 6,7: `hermes` → `/home/atushi/.local/bin/hermes`（絶対パス化）
- `scripts/kensho-research-agent.py` line 398: `【出力形式】` 下に 2KB 出力制約追記

## 5. 検証コマンド

- `bash -n /home/atushi/.hermes/profiles/kensho-sweeps/scripts/kensho-cron-watchdog.sh; echo $?` → 0
- `env -i HOME=/home/atushi PATH=/usr/bin:/bin bash /home/atushi/.hermes/profiles/kensho-sweeps/scripts/kensho-cron-watchdog.sh` → watchdog実行 confirmed
- `grep -n '2KB以内' /home/atushi/.hermes/profiles/kensho-sweeps/scripts/kensho-research-agent.py` → 398: constraint added

cross-task reference: d340ec02d57e is handled separately by cron-side session.