# kensho-complete-watchdog.sh — 実装後の自動チェックメカニズム (kanban t_fc908068)

## 目的
workerが実装を済ませたのに `kanban_complete / kanban_block` を呼び忘れたまま
status=running 残留する「完了忘れ」を自動検知し、リマインドする。

## 変更ファイル
- scripts/kensho-complete-watchdog.sh (本メカニズム, 新規)
- インストール: ~/.hermes/profiles/kensho-revenue-worker/scripts/ へシンボリックリンク
- crontab: `*/30 * * * * bash ... --apply` 追加

## 検知ロジック
完了忘れシグネチャ (mycritic v166 / SOUL.md と同じクラッシュ原因
"worker exited cleanly without calling kanban_complete"):
1. tasks.status IN ('running','in_progress')
2. worker_pid が死んでいる or NULL
3. last_heartbeat_at が STALE_MIN(既定90分)以上古い
実装完了の客観証拠: (a) 直近2日以内の git コミットに task_id を含む
(b) リポジトリに未コミットのコード変更(.py/.yaml/.sh/.js)がある

## 検証 (2026-09-17)
### 1. 構文
`bash -n` => OK
### 2. 実ボード dry-run (両runningタスク heartbeat直近) => silent rc=0
- 完了忘れ無し => サイレント(空stdout), コメント投稿なし。期待通り。
### 3. テストDB に stale heartbeat注入 (t_9f37e5e3 を7200s前へ)
- dry-run --verbose => candidates=1 remind=1, `t_9f37e5e3|git_dirty` を検出
### 4. fresh heartbeat 注入 => silent rc=0 (誤検知なし)
### 5. apply をhealthyボードで => rc=0, ledger作成なし, コメント投稿なし
### 6. 台帳 upsert dedup (同日同taskで2回) => 1行のみ (重複防止)
### 7. install 検証: symlink先から bash 実行 => rc=0

## 検証コマンド(受理条件)
`hermes kanban --board kensho-ai-team list --status in_progress --json | jq 'length'`
現在値: 0 (running=2 は完了忘れでなく実行中の正常セッション, heartbeat更新中)
→ 完了忘れによる滞留は既にゼロ。本メカニズムが30分毎に監視して予防。

## ロールバック
`git revert <commit>` で scripts/kensho-complete-watchdog.sh を除去 +
`crontab -l | grep -v kensho-complete-watchdog | crontab -` で cron 解除 +
symlink 削除 (~/.hermes/profiles/kensho-revenue-worker/scripts/kensho-complete-watchdog.sh)
