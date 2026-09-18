# チーム長期記憶 compaction レポート (20260918)

出自: Anthropic effective-context-engineering (compactionパターン)
適用: 重要(未解決/アーキテクチャ/禁止領域)を保持、解決済み/運用記録を破棄

## 集約結果
- 対象: critic/worker/qa 3 notepad lessons(+worker handoff) + loop_health
- notepad合計メモリ使用量: 2279B → 970B
- 削減率: 57%

## エントリ別 before→after
- critic/lessons: 761B → 507B
- worker/lessons: 203B → 0B
- worker/handoff: 375B → 0B
- qa/lessons: 940B → 463B


## critic / lessons  (job 4baf143523e0)
- before: 761B → after: 507B
### 保持（KEEP — 現行重要状態）
```
2026-09-18(v186-夜):
- 【要ユーザー対応】(高・継続) zin20120731 proxy:1084 egress死(9/18朝〜夜)。watchdog再起動+再アソシとも効かず「Adapter zin_AW6povo has no non-APIPA IPv4」=povo端末側。端末再起動/機内モード切替を推奨。ログイン失敗継続。
- (中) t_1593ad00(メモリcompaction)がassignee=Noneでready滞留→dispatcher永久スキップ。kensho-workerに補完割当(9/18夜)。ユーザー作成カードのassignee未設定は要注意。
```
### 退避（EVICT — 解決/運用記録）
```
2026-09-17: KENKAKU平均 16.1件 / ConnectTimeout 8件 / apply成功率 100.0%
- ボード=score100/ready3(t_455add05/t_d2b1ba39/t_1593ad00)/running1(t_c76075ca)/blocked0/streak0で健全。新規提案なし(既存バックログが問題を網羅)。
```
## worker / lessons  (job 5e8ec4984bba)
- before: 203B → after: 0B
- 保持エントリなし
### 退避（EVICT — 解決/運用記録）
```
2026-09-18: [高優先解決] rc=0 silent exit違反をsafe-wrapper.shで防止。3cronジョブ(script更新)でdispatcher再spawn無限ループ解消。t_f4698348/t_b9967b3f unblock。blocked 2→0。
```
## worker / handoff  (job 5e8ec4984bba)
- before: 375B → after: 0B
- 保持エントリなし
### 退避（EVICT — 解決/運用記録）
```
2026-09-17 run61: prio=new_proposals・wip=1→0。ready=0(自assignee実装可能タスク無し)。blocked t_55210446(Gumroad)=GUMROAD_TOKEN欠如が真因で確定・.env再確認で欠如維持。自動復旧不可・ユーザー提供待ち。他blocked 2件(t_06fdd792/t_9f37e5e3)はkensho-worker担当=着手不可。実装なし。健康度=score100/streak0/最優。
```
## qa / lessons  (job 033ff6065ef7)
- before: 940B → after: 463B
### 保持（KEEP — 現行重要状態）
```
2026-09-18:
• 【実シグナル・未解決】protocol_violation_crash_24h=1: t_455add05でworkerがrc=0 silent exit×2(182s/2651s)。カード主題がDeepSeek401修正→worker自身のLLM401鶏卵構造の疑い。次回dispatchで監視、再発ならカード分割/401時block明記を申し送り。
• 要ユーザー対応クローズ: RapidAPI見送り確定・GUMROAD_TOKEN断念(9/18方針)は再浮上させない。物理対応案件はなし。
```
### 退避（EVICT — 解決/運用記録）
```
• loop_health score=100/streak=0/blocked=0/ready=3・healthy（3測連続）。dirty=Yはworker in-flight→当run内でcommit 458c8d4により解消。
• 【検出→復旧】回帰ゲート2件をQAが復旧: empty result(t_f91d2729/t_9f37e5e3)をresult backfill / checkpoint未打刻(t_de4a3f30=archived)をledger終端除外修正(commit 19886ae)。両方green。
• t_c76075ca(test_revenue_collect 3件FAIL)解消: workerがcommit 458c8d4+report作成、58 passed。
```

## loop_health 状態スナップショット
{
  "score": 100,
  "streak": 0,
  "last_escalate_streak": 0,
  "last_low_band": 0,
  "business_ok": true,
  "escalated_at": "",
  "park_cooldown_until": 0,
  "park_after_h": "24",
  "last_park_action": "none",
  "last_park_ts": "",
  "last_park_result": "",
  "last_park_target": "",
  "last_run_ts": "2026-09-18T23:10:25+09:00",
  "escalation_active": false
}

戻し: バックアップ reports/backups/notepad-*-backup-20260918.md を
  'hermes cron notepad <job> set <key> "$(cat <file>)"' で復元（HERMES_HOME=/home/atushi/.hermes/profiles/kensho-sweeps）
