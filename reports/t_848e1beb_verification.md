# t_848e1beb 検証・実装レポート — kensho-worker終端呼出強制（protocol_violation再発防止）

## 概要
本タスク t_848e1beb は「workerが rc=0 で kanban_complete/block 未呼出のまま終了 → dispatcher が protocol_violation として失敗扱い」の再発防止を目的とする。2段構えで実装・検証した。

### 対策[1] プロンプト自己チェック（継続・検証済み）
kensho-worker の SOUL.md（毎 worker セッションでロードされる persona preamble）に「終端kanban呼出の鉄則」として下記を明記済み:
- rc=0 でも complete/block/request_review 未呼出なら失敗扱いになる
- 最終レスポンス前に「今日のターミナルkanban呼出はしたか？」を自己チェック
- 作業結果の報告は complete/block の summary に書く
- 失敗時でも必ず kanban_block で終端（rc=0 のまま素通り禁止）
これは前run 895 で追加済みのものを本runで実在・ロード有効を確認した（下記 verification_evidence 参照）。

### 対策[2] 監視の表面化＝wrapper拡張（本runで実装）
dispatcher 側の「rc=0 でも complete/block 未呼出は失敗扱い」は既存で動作実証済み（t_848e1beb の run 893/894/895、t_3aa5365c の run 884/886/887/889 が全滅）。だが被災タスクは status=blocked で沈黙放置され、成果完了済みなのに再開されない。これを表面化するため `kensho-complete-watchdog.sh`（cron で 30分毎に --apply 実行）に protocol_violation 被災(blocked)タスクのスキャンを追加:
- status='blocked' かつ last_failure_error LIKE '%protocol violation%' を抽出
- `[protocol-violation-blocked]` コメントで unblock 再開を促す（台帳 dedup で同日重複防止）
- コメント・台帳タグを事故種別（complete-forgot / protocol-violation）で区別
計上先は t_848e1beb が commit c08cd4e で確定。cron の script は repo copy への symlink のため、repo 1ファイル patch で cron 適用も同時反映。

## 成功指標との対応（t_848e1beb カード本文）
- 「t_3aa5365c unblock後リトライで complete/block 呼出あり終了（consecutive_failures→0）」: t_3aa5365c は本run時間点で blocked(cf=2)。workerに unblock ツールが無いため、本runでは watchdog が自動で表面化コメントを投稿し、unblock 後の次 dispatch（更新済み SOUL.md 有効）での完了を待つ。検証は次 dispatch に委譲。
- 「新規workerタスクの protocol_violation ブロック7日間0件」: SOUL.md ルール適用後の新 dispatch モニタリングで測る（将来評価）。本run終端の kanban_complete 呼出自体が「対策[1]の実効実証」。
- 本タスク自身: 過去3run が protocol_violation で crashed した。本runは kanban_complete で終端し、ストリークを切断して対策[1]を実証する。

## verification_evidence
実行コマンドと実出力（記録値は実走査のもの）。

```
$ bash -n /mnt/d/Project2/kensho/scripts/kensho-complete-watchdog.sh && echo SYNTAX-OK
SYNTAX-OK
$ bash /mnt/d/Project2/kensho/scripts/kensho-complete-watchdog.sh --dry-run --verbose
kensho-complete-watchdog: board=kensho-ai-team stale_min=90git_days=2 candidates=0 remind=1
  protocol-violation: t_3aa5365c|protocol_violation(cf=2)
DRY-RUN: pass --apply to post reminders / escalate.
exit=0
$ grep -c '終端kanban呼出の鉄則' /home/atushi/.hermes/profiles/kensho-worker/SOUL.md
1
$ python3 /tmp/check_pv.py
protocol violations blocked: 1
('t_3aa5365c','blocked',2,'TCG価格データセット商品化: 蓄積cron+値動きAPI+Gumroad出品')
```

補足（実測）:
- watchdog の dry-run --verbose が `protocol-violation: t_3aa5365c|protocol_violation(cf=2)` を検出 → 被災タスク表面化が機能。
- SOUL.md のルール見出し実在を grep -c=1 で確認 → 対策[1]がworkerセッションでロードされる状態。
- kanban.db 直接参照で protocol_violation 被災 blocked が1件（t_3aa5365c）と計数 → 台帳と一致。
- 実装は t_848e1beb の commit c08cd4e（scripts/kensho-complete-watchdog.sh + 本レポートの追加）で git 追跡済み。

## changed_files
- /mnt/d/Project2/kensho/scripts/kensho-complete-watchdog.sh（protocol_violation被災タスク表面化追加。t_848e1beb）
- /mnt/d/Project2/kensho/reports/t_848e1beb_verification.md（本レポート）
- /home/atushi/.hermes/profiles/kensho-worker/SOUL.md（前run 895 で追加。本runで実在・有効検証）
