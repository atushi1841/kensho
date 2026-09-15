# critic v155 実装レポート — GO承認ゲート自己通過監視（t_a085ab68）

日付: 2026-09-16 06:3x JST
作業者: kensho-revenue-worker (run500)
カード: t_a085ab68（本レポートは t_a085ab68 の実装証跡。commit b1df38d = t_a085ab68 の受け入れ差分。t_a085ab68 検証時は下記コマンドを再実行すること）

## 事故根拠（実測）
- t_ed8baffa run490: 本文「ユーザーGO必須」→ created(blocked) 1789488680
  → promoted → claimed 1789488690（同一run内10秒、task_events 14257-14259）。
  作業者自身がGOゲートを素通りし01:58まで47分空転後、自己blocked（GO待ち）。
- QA run497申し送りによるparent=t_ed8baffaデッドロックは、先にunlink済み
  （task_events: unlinked→promoted 1789505251）で本カードは単独実行可能。

## 実装内容（read-only + 通知のみ）
1. `scripts/go_gate_watch.sh`（新規・本番配置は
   `~/.hermes/profiles/kensho-sweeps/scripts/go_gate_watch.sh` symlink）
   - kanban.db を `mode=ro` で直読（FIFO/共有lock非破壊）。台帳の強制blocked化なし。
   - 検出シグネチャ（3条件AND）:
     a) tasks.body に「ユーザーGO必須/GO承認待ち/GO待ち」いずれか
     b) 最初の created イベント payload.status == "blocked"
     c) claimed より前に人間側GOイベント（unblocked/promoted_manual）が無い
   - 条件(b)により、監視自身を論じるカード（t_a085ab68型・created=todo起票）や
     GO済み通常カード（ready起票）は構造的に誤検知しない。
     （申し送りされたPython代替版は(b)欠如で自カードを検知する誤検知があったが、
     本bash版はそちらを採用。代替案の発動条件=ai-context統合困難は非発生）
   - 二重通知防止: state JSON（検知済み task_id:run_id）を原子的書換。
   - 出力: 1行警告 → logs/go_gate_watch.log + stdout。notify.sh 経由でTelegram直接
     送信（ai-context-monitor.sh のstdoutはcrontabで/dev/nullへ捨てられるため）。
2. `ai-context-monitor.sh` 統合（新cron增加なし）:
   `5 * * * * ai-context-monitor.sh` の既存crontab内で go_gate_watch.sh を呼び、
   検知行を report_lines / alert_count に合流。crontab自体は未変更。
3. `tests/test_go_gate_watch.py`（新規5件・tmp db + fixture、実ボード非依存）。

## 制約遵守
- crontab・config.yaml・orchestrator・応募処理: 一切変更なし（git差分は
  scripts/go_gate_watch.sh と tests/test_go_gate_watch.py のみ追加）。
- 判定は人間/QA委譲: 通知のみで強制block化しない。

## verification_evidence

成否指標② selftest exit_code=0（実ボード548件とは独立のtmp db fixture）:

```
$ bash /home/atushi/.hermes/profiles/kensho-sweeps/scripts/go_gate_watch.sh --selftest; echo exit=$?
GO-GATE WARNING task=t_incident01 run=490 claim_event=3 gap_from_created=10s status=blocked markers=ユーザーGO必須 title="fixture t_incident01" — GO未承認で claimed/running（t_ed8baffa事故パターン: created(blocked)→promoted→claimed）。判定は人間/QA委譲（本監視は強制block化しない）
SELFTEST OK: 検出1件/誤検知0件/dedup/再通知0/exit0
exit=0
```

成否指標① 本番実ボード（t_a085ab68 本番tick）でt_ed8baffa相当パターンのみ1件検知・誤検知0件
（GOマーカーカードは実測5件のみ: t_ed8baffa=検知 / t_cafe0cdd, t_e366401f,
t_b9a55d7a=ready起票で非検知 / t_a085ab68=todo起票で非検知）:

```
$ GO_GATE_NOTIFY_SH=/bin/true bash ~/.hermes/profiles/kensho-sweeps/scripts/go_gate_watch.sh; echo exit=$?
GO-GATE WARNING task=t_ed8baffa run=490 claim_event=14259 gap_from_created=10s status=blocked markers=ユーザーGO必須 title="critic v154 Follow-up: 垢別アクション開始の15分グリッド±2分98.8%集中への対策実装（GO承" — GO未承認で claimed/running（t_ed8baffa事故パターン: created(blocked)→promoted→claimed）。判定は人間/QA委譲（本監視は強制block化しない）
exit=0
$ cat ~/.hermes/profiles/kensho-sweeps/scripts/state/go_gate_watch_state.json
{
 "alerted": [
  "t_ed8baffa:490"
 ]
}
```

pytest新規テスト5件:

```
$ python3 -m pytest tests/test_go_gate_watch.py -q
（5 passed — test_selftest_exit_zero / test_detects_incident_pattern /
test_zero_false_positives / test_dedup_state_no_renotify / test_missing_db_is_silent_ok）
```

ai-context監視統合後の構文・非破壊:

```
$ bash -n ~/.hermes/profiles/kensho-sweeps/scripts/ai-context-monitor.sh && echo MON_SYNTAX_OK
MON_SYNTAX_OK
```

## 限界・補足（t_a085ab68 本カード）
- 監視はclaimed検知のみでworkerの実際の作業停止は强制しない（設計どおり、人間/QA委譲）。
- 事故カード t_ed8baffa 自体は現在blocked(GO待ち)で正常系に復帰済み。t_ed8baffa の検知ログは
  事故の歴史記録として t_a085ab68 の監視stateに残り、t_ed8baffa run490 の再通知はしない。
- t_a085ab68 自身は created=todo 起票のため条件(b)非充足=自己誤検知なし（pytest で固定）。
- QA検証カードは本レポート(t_a085ab68)とgit commit b1df38d を root に再確認のみでよい。
