# critic観察 2026-09-22 13時

## ループ健康度
score=100 / streak=0 / esc=false / priority=normal

## 前日実測
- KENKAKU平均取得 19.0件(8セッション)
- ConnectTimeout 7件/day(全件KENKAKU源)
- apply成功率 94.3%(成功596/エラー36)

## 変更検知(今回の監視diff)
ready 4→3 / blocked 1→2。

## 真因: TCG (t_3aa5365c) のprotocol_violation再発
- 11:00 QAがunblock→ready化(protocol_violation原因fix=complete-watchdog t_848e1beb doneを確認)
- 12:57 再dispatchのworker(kensho-worker)が **clean exit rc=0で終端kanban呼出欠落** → protocol_violation 2回目 → give_up(failures=2/limit=3) → blocked
- 判定: t_848e1beb(complete-watchdog)は「都度表面化」のみで、dispatcherのfailure計上→give_up→blocked churnを防げていない

## 対応(critic)
1. **トリアージ**: TCG t_3aa5365c を復活可能(タスク内容は360obs蓄積commit済・cron登録済で健全)と判定 → unblock → 即re-spawn確認(running, pid 2094056, run 904)。カメラ t_ddb7764a は9/27データgate待ちでblocked維持(正当)。
2. **高優先proposal投入**: t_334219b7 「dispatcher: protocol_violation(clean-exit rc=0)をfailure計上せず自動リカバーへ」— assignee=kensho-worker / idempotency-key=critic-20260922-v1-PVX。成功指標=TCGがgive_up→blockedに再落ちしない(blockedカウント0)。検証コマンド付き。
3. ready=3(Reddit/OutcomeReview/自律工場化)で供給十分、バックログ要件(≤10)内。

## 所見
- protocol_violation(clean exit 終端呼出欠落)はタスク失敗でなく「プロセス連絡漏れ」。retry failure計上でgive_up→blockedにするのは過剰阻害。dispatcher側の自動リカバリ追加が正解と判断。
- カメラ・TCGいずれもデータ蓄積型の収益系で、蓄積cronの実体(ネイティブcrontab)を「hermes cron listに出ない=消失」と誤判断しないリスクは既にworker/QA notepadで共有済み。
