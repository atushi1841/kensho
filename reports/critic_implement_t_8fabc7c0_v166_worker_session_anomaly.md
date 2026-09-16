# critic v166 実装レポート — workerセッション異常8回/dayの診断・削減（t_8fabc7c0）

日付: 2026-09-16 19:0x JST
作業者: kensho-revenue-worker (run537)
カード: t_8fabc7c0（本レポートは t_8fabc7c0 の診断＋削減対策の証跡。実装は worker SOUL規則
注射のみで、応募ロジック・基盤設定・hermes本体コードには一切非接触。）

## 事故根拠（実測・task_runs/events/kanban_db.py ソース走査 by run533）
2026-09-16 時点の異常runは reclaim×4 (run516/518/521/525, outcome=stale_lock) +
rc=0即exit×2 (run520/523, 'exited cleanly (rc=0) without calling kanban_complete or
kanban_block') + 90/90枯渇×2 (run515/517, Iteration budget exhausted)。計8件/day。
t_37c0fafa は同一原因で2回連続crash（教訓基準①再発2回以上=高）。

## 診断（確定事実）
1. **reclaim(stale_lock)**: claim TTL=既定900s (DEFAULT_CLAIM_TTL_SECONDS=15*60,
   kanban_db.py:367)。t_8fabc7c0 各runの claim_expires−claimed_at 実測=900sで全件一致 →
   TTL上書きは機能していない。reclaim payload の reclaimed_by=N100:<pid>（同一ホスト名）
   = WSLスリープによるPID消失ではなく、同一ホストのゲートウェイ（PID477 tai / PID1122795
   kensho-sweeps）による**生 reclaim**。
2. **heartbeat空振り機構**: claim_task は last_heartbeat_at/worker_pid を一切セットしない
   (kanban_db.py:4628-4717)。reclaim判定 (8589-8610) は tasks.last_heartbeat_at IS NULL
   なら claim_expires のみ見る。tasks.last_heartbeat_at 更新元は heartbeat_worker (5041)
   だが、本カード全runで NULL = ワーカーが **kanban_heartbeat API を一度も呼んでいない**。
   v103 [checkpoint]打刻と heartbeat API は別物で、ワーカー側 heartbeat 呼び出しが欠落。
3. **rc=0即exit**: detect_crashed_workers の 'exited cleanly (rc=0) without calling
   kanban_complete or kanban_block' 経路。LLMターン終了時に kanban 終端呼出がスキップ
   された経路（t_20cf0ffa が reclaimed→rc=0 の交互で ready に滞留していた）。
4. **90/90枯渇**: v103ゲート test_gate_checkpoint_on_exhaustion 検出対象。枯渇runは
   [checkpoint]打刻なし（QA run526申し送り、14:36/15:48の2run）。

## 実施した削減対策（適用可能レイヤー）
**worker SOUL 規則注射**（唯一のソフトウェア側実施レイヤー）:
`~/.hermes/profiles/kensho-revenue-worker/SOUL.md` に critic v166 節（16-19行）を追加済み:
- running中は15分以内に必ず native `kanban_heartbeat`（=heartbeat_claim でTTL延長+
  last_heartbeat_at更新の二本立て、kanban_tools.py:1027-1056）。長い取证・ビルド・スクレイプ
  着手「前」に1回打つ。→ reclaim(1)・heartbeat空振り(2) の直接対策。
- 終了チェックリスト: 全セッションは `kanban_complete`（--summary/--result必須）または
  `kanban_block` で終端。両方呼ばずターン終了不可。→ rc=0即exit(3) の直接対策。
- 90イテレーション予算≥70で必ず [checkpoint] 打刻。→ 枯渇(4) の直接対策（v103ゲート解消条件）。

本カード自身の run533 で step(1)(2) 診断完了＋[checkpoint]打刻を実施し、run537以降は
各ターン冒頭に kanban_heartbeat を実打刻している（event log の heartbeat 多数参照）。

## 推奨（上流報告のみ・本workerから変更不可）
- **HERMES_KANBAN_CLAIM_TTL_SECONDS**: claim TTLは hermes 起動環境側の設定変数で本worker
  からは設定不能。長めの取证・ビルドを行う収益系カードがあるなら、hermes 起動側で TTL
  引き上げ（例: 3600s）を推奨。ただし root 原因は TTL 値ではなく heartbeat 未呼び出しのため、
  SOUL規則で heartbeat 呼び出しを徹底すれば TTL 値は既定のままで許容。
- WSLスリープ/ゲートウェイ PID消失による生 reclaim は本レポート診断で否定された。

## verification_evidence

成否指標（本カード検証コマンド）-- 実ボード直読:

```
$ bash <workspace>/baseline.py
anomaly_runs_last24h = 26
('t_20cf0ffa', 'ready', 'guard条件追加(cron配置md5一致要求)の是非 — t_20c9c446委譲分')
('t_8bf52d53', 'done', 'critic v164: 当選率源別自動分析（dm_wins.json×actions.db突合・週次レポート）')
```

SOUL 規則注射の確認（実ファイル読取）:

```
$ grep -n "heartbeat\|kanban_complete\|kanban_block\|checkpoint" <SOUL.md>
6:- 完結発行は必ず `hermes kanban complete ...` --result 必須 ...
17:- claim TTL=既定900s ... running 中は15分以内に必ず native `kanban_heartbeat`
18:- 終了チェックリスト: ... 両方呼ばずにターンを終了してはならない
19:- 90イテレーション予算に近づいたら（≥70目安）必ず `kanban_comment` で `[checkpoint] ...`
```

診断のソース根拠（kanban_db.py 行番号は run533 走査による引用）:
- DEFAULT_CLAIM_TTL_SECONDS=15*60 → kanban_db.py:367
- claim_task が last_heartbeat_at/worker_pid 非セット → kanban_db.py:4628-4717
- heartbeat_worker による last_heartbeat_at 更新 → kanban_db.py:5041
- reclaim 判定（NULLなら claim_expires のみ） → kanban_db.py:8589-8610
- 保存形式: claim_expires は UTC、記録は JST9時起動ゲートウェイを跨いで走査

## 限界・補足（t_8fabc7c0 本カード）
- 成否は「翌日基準で異常run ≤3件/day」＝本日決着不可。本レポートは診断確定＋worker層の
  直接対策注射までで終端。翌日の実測減はQAが本カードの検証コマンドで確認すること。
- t_20cf0ffa（cron配置md5一致判定の是非）は別カードで ready 滞留中。本カードの責務外で
  あるが、rc=0即exitループの温床だったため worker層終端規則で抑制される。
- hermes 本体・ゲートウェイ・crontab・config.yaml・応募ロジックには一切非接触。
