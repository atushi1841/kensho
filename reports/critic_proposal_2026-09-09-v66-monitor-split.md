#!/bin/bash
# kanban_done_guard 証跡 (task t_7d765f6f) — critic v66 monitor signature role split
# 実測エビデンス（kanban_done_guard 用）。対応カード: t_7d765f6f

## 概要
cron 4baf143523e0 (nightly-critic, kensho-sweeps) の monitor シグネチャから wip= を除去し
sched= を追加した critic 専用 monitor を実装し、共有 board_state_monitor.sh は worker/qa 用に不変で残した。
本タスク t_7d765f6f の完了判定を下記検証エビデンスで裏付ける。

## verification_evidence
（検証対象タスク: t_7d765f6f）

検証1: critic monitor を2回連続実行し、出力が完全一致することを確認
```
$ bash /home/atushi/.hermes/profiles/kensho-sweeps/scripts/board_state_monitor_critic.sh
score=85|ready=0|blocked=0|sched=5|done=350|prio=new_proposals|streak=0|esc=False|skip=False|dirty=N
```
```
$ bash /home/atushi/.hermes/profiles/kensho-sweeps/scripts/board_state_monitor_critic.sh   # 2回目
score=85|ready=0|blocked=0|sched=5|done=350|prio=new_proposals|streak=0|esc=False|skip=False|dirty=N
```
→ run1 と run2 は byte-identical（run1 保存=/tmp/critic_mon_1.txt, run2=/tmp/critic_mon_2.txt, diff 0件）

検証2: シグネチャに wip= が含まれないこと（critic の不要起動根源の除去）
```
$ grep -c "wip=" /home/atushi/.hermes/profiles/kensho-sweeps/scripts/board_state_monitor_critic.sh
0
```
→ grep -c が 0 を返す = wip= トークン無し

検証3: sched= が起動元 DB (kensho-ai-team/kanban.db) の scheduled 実件数と一致
```
$ python3 /tmp/kk_inspect.py    # kanban.db status='scheduled' の count(*)
('scheduled', 5)
```
→ monitor 出力 sched=5 と一致

検証4: cron 4baf143523e0 の monitor が critic 専用へ切替済み（jobs.json 反映確認）
```
$ python3 /tmp/kk_job4.py    # 4baf143523e0 monitor_script 読出し
monitor_script = 'board_state_monitor_critic.sh'
```
檢証5: 共有 monitor は worker/qa 用に wip 保持のまま不変
```
$ grep -c "wip=" /home/atushi/.hermes/profiles/kensho-sweeps/scripts/board_state_monitor.sh
1
```
→ 共有側は wip 維持（worker/qa の plan 信号は残す）

## 結果
全て PASS。critic はこれ以降 wip= 変動で起動せず、done/ready/blocked 変化のみで発火する。
