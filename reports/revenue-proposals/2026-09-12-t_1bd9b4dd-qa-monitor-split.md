# Worker 実装記録: critic v138 — QA monitor署名分離 (t_1bd9b4dd)

- 日時: 2026-09-12 17:0x JST（nightly-worker run、kensho-revenue-worker）
- タスク: t_1bd9b4dd「critic v138: worker/QA monitor署名分離（wip変化での空振りLLM起動防止・再発2件）」

## 実装内容

1. **新設**: `/home/atushi/.hermes/profiles/kensho-sweeps/scripts/board_state_monitor_qa.sh`（755）
   - 共有 board_state_monitor.sh（v57系）の写しから **wip(running件数) を除去**。
   - QA実効シグナル7項目: `score|ready|blocked|prio|streak|esc|skip|dirty`
   - prio は heuristic（ready=0かつwip=0→new_proposals）を使わず `d.get("priority") or "normal"` に固定
     （wip連動を完全に切るため。QA行動は ready/blocked/dirty/streak で決まる）
   - loop_health v133新旧スキーマフォールバック、streak band化、ready sqlite算出（v57教訓:
     パラメータ化クエリ+ダブルクォートのみ）、done_total非採用（v88教訓: 単調増加除外）は継承
2. **symlink**: `~/.hermes/scripts/board_state_monitor_qa.sh` → profile側（critic/主monitorと同方式）
3. **cron差替**: `hermes cron edit 033ff6065ef7 --monitor-script board_state_monitor_qa.sh` →
   `Monitor: board_state_monitor_qa.sh (agent runs only on output change)` 確認
4. **git追跡**: profile repo commit `151ec05`（v50教訓: live monitor scriptは必ずgit追跡）
5. worker（5e8ec4984bba）は現状維持（board_state_monitor.sh）、criticは分離済（v66）→ 3役分離完備

## verification_evidence

```
$ ln -s → ls -la /home/atushi/.hermes/scripts/board_state_monitor_qa.sh
lrwxrwxrwx ... board_state_monitor_qa.sh -> /home/atushi/.hermes/profiles/kensho-sweeps/scripts/board_state_monitor_qa.sh

$ bash ~/.hermes/scripts/board_state_monitor_qa.sh   # run1
score=100|ready=2|blocked=1|prio=normal|streak=0|esc=False|skip=False|dirty=Y
$ bash ~/.hermes/scripts/board_state_monitor_qa.sh   # run2（冪等性: 完全一致）
score=100|ready=2|blocked=1|prio=normal|streak=0|esc=False|skip=False|dirty=Y

$ bash ~/.hermes/scripts/board_state_monitor.sh      # 主(w用)比較
score=100|ready=2|blocked=1|wip=3|prio=normal|streak=0|esc=False|skip=False|dirty=Y
$ diff <(main) <(qa)
1c1
< ...wip=3...
> ...(wipなし)   ← 差分は wip 除去のみ。他項目一致

$ bash ~/.hermes/scripts/board_state_monitor_critic.sh
score=100|ready=2|blocked=1|sched=5|done=0|prio=normal|streak=0|esc=False|skip=False|dirty=Y

$ hermes cron list | grep Monitor:
Monitor:   board_state_monitor_critic.sh (agent runs only on output change)
Monitor:   board_state_monitor.sh (agent runs only on output change)
Monitor:   board_state_monitor_qa.sh (agent runs only on output change)
```

## 効果測定の申し送り（QA/criticへ）

- 成功指標（カード記載）: 導入後3 tick（9/13 01:10 / 03:10 / 05:10 頃）で「wipのみ変化tick」の
  QA last_run_at 不変を確認。QA次回runは monitor 変化で起動した場合でも last_run_at 記録を追う。
- ダイヤル調整済み: QAの ready/blocked/dirty/streak 変化では従来どおり起動する（検証待ち見逃しなし）。
- 失敗時代替案（未発動）: done件数等が毎tick変動して空振りが残る場合、共有署名へ revert +
  QAプロンプト先頭「検証待ち0件なら即終了」に切替。

## 自己レビュー（git diff 151ec05）

- 追加ファイル1本のみ・既存スクリプト無変更 ✓
- timestamp/ランダム要素なし（monitor冪等性鉄則） ✓
- APIキー等の秘匿値なし ✓
- kensho repo の未コミットdiff（scripts/loop_health.sh・tests/test_loop_health.py）は
  t_296c3dbc（v137、別run#稼働中）の仕事中ファイル → 触れていない ✓

## Reflexion

```json
{"self_review":{"what_was_done":"QA専用monitor署名 board_state_monitor_qa.sh を新設し nightly-qa(033ff6065ef7) のmonitorを差替。wip除去のみ差分、2連続署名一致を実測。profile repo 151ec05 で追跡化。","what_went_well":["critic v66分離の写し設計のため実装が1スクリプト+edit1コマンドで完結","diffでwip除去以外ゼロを確認、冪等性2連続一致"],"what_could_improve":["3役署名の横並び比較ループにbash展開バグ(self-inflicted)が1回分無駄コール"],"mistakes_or_risks":["prio=normal固定はloop_healthが将来priority提供した場合に自動で追随する設計（提供時はそのまま流用）——リスク低","wip除去でQAが見るべき『検証待ち』がrunning完了瞬間にready化するため、ready次元が実質的な検証トリガとして機能。見逃し経路なし"],"learned":"monitor分離は『役割が読むべき差分だけ签名に含める』が原則。prio算出のフォールバックheuristicまで役割で分けないとwip連動が裏口から復活する","confidence":9,"verification_evidence":"2連続同一署名+diff wipのみ+hermes cron listでMonitor=board_state_monitor_qa.sh表示（すべて上方に実出力）"}}
```
