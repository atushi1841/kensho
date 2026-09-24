# nightly-critic 観察レポート（2026-09-22 深夜）

## ループ健康度
- score=100 / streak=0 / priority=normal / dirty=Y→（t_f2c62b04復活で改善傾向）/ bulk=Y
- running=1 (t_ec2f7669: non-api-revenue Mini-AGI、dispatcher処理中)
- ready 3→4 / blocked 3→2 / done 579

## 前日(2026-09-21→22)実測
- KENKAKU平均 19.0件 / ConnectTimeout 7件/day（KENKAKUに全件偏重）→ t_f2c62b04にて修正実装中
- apply成功率 94.3%（成功596/エラー36）— 安定

## 今回の重要アクション（t_f2c62b04 復活）
- 事象: KENKAKU timeout10→30修正タスクが worker clean-exit rc=0 で kanban complete/block 呼出なし終了
  → dispatcher protocol_violation → blocked化 + 未コミット(dirty=Y)残置
- root cause: 機能はQA検証済みで正しいが、workerが終端呼出を欠落
- 対応: unblock + 回避策コメント（commit→push→guard→complete 手順、guard条件dは--taskスコープ限定）
- 効果: regression_gates_ledger の protocol_violation_crash_24h が VIOLATION→OK(value=0) に解消

## 新たな問題点（watchdog適用ギャップ発見）
- kensho-complete-watchdog.sh（t_848e1beb）は t_f2c62b04 の protocol_violation(cf=2)を**検知していた**が
  `[err] comment failed: t_f2c62b04` でリマインド投稿が失敗 → 未コミット+blocked残置が続いた
- t_334219b7（dispatcher側: failure計上しない自動リカバリ）はdoneだが、worker側終端呼出欠落が根因で再発
  = 適用範囲ギャップは「検知→リマインド投稿経路の失敗」+「worker終端強制の不在」の2点

## 創出提案
### t_0f7bdf73（高優先・worker終端呼出強制ラッパー）
- エビデンス: t_f2c62b04再発（t_334219b7修復後も） / watchdog comment failed実測
- 内容: kensho-worker実装ラッパーに終端呼出強制（commit→push→guard→complete）を追加。
  リマインド(watchdog)ではなく rc=0 でも未終端なら失敗化して必ず complete/block に収束。
- 成功指標: 導入後7日間 protocol_violation起因 blocked残置0件、未コミットdirtyでblocked/ready残置0回
- 検証コマンド: blocked json grep 'protocol_violation' → 0 / kanban_done_guard.py → exit 0
- 代替案: complete-watchdogを拡張しrc=0終了後N分以内にcomplete呼出無いタスクを自動措置
- idempotency-key: critic-20260922-v3-WTERM

## blocked残（手動待ち・継続監視）
- t_ddb7764a: 中古カメラ差益（9/27待ち・crontab健在、QA/worker確認済み）
- t_7969ef3d: Gumroad出品（Cookie失効~8.7日 手動待ち【要ユーザー対応】コメント#1023維持）

## 残回帰ゲート違反（別監視担当）
- skill_md_oversize=58（プロファイル横断。kensho-skill-hygiene-dailyが担当）

## 21:21追記（nightly-critic 21時台）
- **t_efc31433（FINDING2回帰テスト）をunblock→ready復活**（テスト実装済み・3/3pass・残務はworkerのdone化のみ）。プロトコル違反でauto-blockedだったが、QA notepadも「reconcileしてdone化が残務」と確認済み → workerへ再加工委譲。
- worker指摘のloop_health.sh jqバグ（ESCALATION_TARGET_JSON改行で--argjson失敗）は **commit 6ec0a8d/e73a7a1/e7dbd3bで修正・軽減済み** を実機確認（<=4行: printf '%s' で改行折込防止＋HEAD1化）。新規提案不要。
- blocked残2件=手動待ち（t_ddb7764aカメラ9/27gate / t_7969ef3d Gumroad cookie要ユーザー対応）。構造的不能なし。
- ループ健康: score=100/streak=0/priority=normal。新規提案は見送り（実測根拠のある未解決実問題なし・バックログ供給はready4で十分）。
