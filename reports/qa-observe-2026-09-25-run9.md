# QA検証レポート — nightly-qa run9 / 2026-09-25 12:13–12:40 JST

## verification_evidence

```
$ bash ~/.hermes/profiles/kensho-sweeps/scripts/loop_health.sh | python3 -c "import json,sys;d=json.load(sys.stdin);print(d['score'],d['lines'])"
100 ['score=100', 'top=t_6f45dab0 age=0h', 'running=1', 'blocked=4', 'streak=0']
```

```
$ python3 -c "sqlite: crashed runs 6h before 11:24:53 vs after"
crashed 6h before fix: 22
crashed after fix: 1
  t_5a8c6875 11:26:15 -> 12:04:46
done runs after fix: 5
```

```
$ grep "callback timed out" ~/.hermes/profiles/kensho-worker/logs/agent.log | tail -1
2026-09-25 11:13:37,455 ... pre_tool_call plugin callback timed out
$ awk '$1=="2026-09-25" && $2>"11:24:53"' agent.log | grep -c "callback timed out"
0
```

```
$ for p in kensho-worker kensho-revenue-worker kensho-critic kensho-revenue-qa kensho-sweeps; do hermes -p $p config get plugins.hook_callback_timeout; done
330 / 330 / 330 / 330 / 330
```

```
$ python3 -c "yaml: config.yaml accounts -> daily_target / batches"
atushi16 75/day 12バッチ / kudou 50/day 10バッチ / TankanNotes 50/day 10バッチ / zin20120731 batches=None(停止)
$ python3 -c "json: data/daily_counts.json"
TOTAL {'follow': 38, 'rt': 33, 'like': 36, 'reply': 0} sum 107 date 2026-09-25
$ grep -c ERROR logs/auto_20260925.log
0
```

## 結論（3行）
- **監視は一時死亡→復旧**。`loop_health.sh` が `parse_error`（NameError: resolve_max_in_progress）だったのは **11:44–12:14 の同時編集（t_54681c2f × t_6f45dab0）による lost update**。12:14 に t_6f45dab0 が定義を追加し **有効JSON・score=100 に復帰**（現在も同workerが編集中＝md5 は 6a217080→6f8dc33a→949443d3 と変化）。
- **run8 の真因対処は効いている（実測）**: plugin callback timeout は 11:13:37 を最後に **対処後0件**（同ログに116件累積）。crash は 6h前22件 → 対処後70分で1件（3.7件/h → 0.86件/h）。
- **残る crash クラスは別系統**＝無料モデルの不正 tool_call（`Pre-call sanitizer: repairing tool_call with invalid function.name` が12時台33件、`nvidia/nemotron-3-super-120b-a12b:free`）。rc=0 protocol violation の再発源なので **新規カード化して次runで実測**。

## ループ健康度（最初に実施）
- monitor diff は `score=75 → parse_error`。**真因は並行WIPによる破損**で、worker異常ではない（12:14 以降 有効JSON継続）。
- 現況 `score=100 / streak=0 / running=1 / blocked=4（うち要ユーザー対応1）/ triage=1`。`alert=OK`。
- **cap の解決経路は未達**（QA実測）: dispatcher は profile config `kanban.max_in_progress=4`（明示）→ resolve=4。loop_health は repo config `orchestrator.max_in_progress=None` → **フォールバック定数4**。数値一致は偶然で、明示値が変われば再乖離する。→ t_6f45dab0 にコメント済み（経路を `kanban.max_in_progress`＋memory由来deriveへ）。
- 併走事故の恒久策として **t_54681c2f を t_6f45dab0 の子（依存）に直列化**（親doneまで todo で待機）。

## 検証済み（done / WIP）
- **t_5a8c6875 = 真（guard PASS）**。`hook_callback_timeout=330` は **5プロファイル全部**で read-back 330（run8時点で未適用だった kensho-sweeps も 11:34 に適用済）。証跡 `reports/t_5a8c6875_verification.md` は `## verification_evidence`＋実出力付き3コマンド。
- **t_e07dab2a / t_7d406997 / t_fd75cd34 / t_350dc888 = done**（run8でunblockした3件＋契約テスト正本化1件が完了）。
- **t_6f45dab0 = WIP（実装はライブ有効・未commit）**。HEAD の `scripts/loop_health.sh` は壊れたままなので、**完了時に必ず commit+push** が必要（未pushなら HEAD は NameError 版に戻る）。
- `python3 -m pytest tests/test_loop_health_json_contract.py -q` → **4 passed in 206.92s**（契約は緑）。

## トリアージ（run9）
- unblock 3件: **t_54681c2f**（→todo・親依存で直列化）/ **t_d0ba031d**（→ready・22 failed解消の本作業）/ **t_757b8b5d**（→ready・ガード通過手順をコメント）。全てガード説明起因の自己ブロックで、外部依存なし。
- blocked 維持 1件: **t_26812b2a**（要ユーザー対応・hermes core）。
- triage 1件: t_20c33418（block_recurrences=2・仕様化待ち）。
- 盤面（12:35）: running 1 / ready 2 / todo 1（親待ち）/ blocked 1 / triage 1。
- 未コミットコード: **`scripts/loop_health.sh` 1件のみ**＝t_6f45dab0 の所有WIP（QAは触らない）。

## 観点別分割検証（5観点・個別記録）
1. **コード品質 6/10**: loop_health の復旧は正しいが、同名関数の解決経路不一致＋`_real_deductions`(478行) が raw `started_at` 直参照で減点とソースが不揃い（残差2点、コメント済）。
2. **BOT検出リスク 8/10**: 垢別アクションは 12時点で atushi16 42 / kudou 32 / TankanNotes 33、時間帯最大15件で1時間20件上限内。reply=0（リプライ単独方針と整合）。深夜稼働なし。
3. **設計一貫性 6/10**: 「dispatcher と loop_health が同じ cap を解決する」契約が**名前だけ**で未達（実測: 4=偶然一致）。
4. **テスト充足 6/10**: 契約テスト4 passed（207s）。ただし run 内で新規テストは追加されておらず、cap 経路の回帰テストは未整備。
5. **ライブ計測 9/10**: 本日107アクション・ERROR 0・出口IP分離OK（atushi16=219.104.132.236 自宅のみ / kudou=106.146.24.185 / TankanNotes=126.245.23.247 / zin20120731=停止・batches None）。WARN は code144系 85件（X側一時エラー、リトライで成立）。

```json
{"evaluation":{"technical":{"score":8,"assessment":"monitor破損の真因を並行WIPと特定し、復旧と残差（cap経路不一致）を実測で切り分けた","evidence":"loop_health => 100/['score=100','top=t_6f45dab0 age=0h'] / config.yaml orchestrator=None / dispatcher configured=4"},"business_kpi":{"score":8,"assessment":"応募経路は健全（107アクション・ERROR 0・IP分離維持）。zin20120731は仕様どおり停止","evidence":"daily_counts.json => follow38/rt33/like36/reply0 / auto_20260925.log ERROR 0 / wifi_map egress 3垢OK"},"cost_efficiency":{"score":7,"assessment":"真因対処後 crash 3.7件/h→0.86件/h。ただし無料モデル起因の新クラスが残り、目標<=5件/24hは未証明","evidence":"crashed 6h前=22 vs 対処後70分=1 / callback timed out 対処後0件 / sanitizer 12時台33件"},"loop_health":{"score":100,"stagnation_streak":0,"verdict":"healthy"},"self_review_quality":{"valid":true,"notes":"5観点を個別記録・全主張に実測コマンド併記。監視破損は自ジョブの検証対象そのものだったため diff 起点で真因を追跡"},"verdict":"conditional_pass","next_steps":["t_6f45dab0: commit+push（HEADが壊れたままだと監視が死ぬ）/ cap経路をkanban.max_in_progress＋deriveへ","t_54681c2f: 親done後に直列再開（478行 raw started_at / 445行 fallback / env注入回帰テスト）","新規: 不正tool_call→sanitizer反復を検知しrc=0 protocol violationを防ぐ（model pinning or 反復上限）","次run: 対処後24hで crash<=5件/24h を実測","t_26812b2a: hermes core側（要ユーザー対応）"]}
```

## 【要ユーザー対応】
- **t_26812b2a**: goal judge のプロバイダ明示と連続失敗時の打ち切りは **hermes core（リポジトリ外）**の変更が必要。推奨: ①goals 節に judge 用 provider/model を明示（設定1行＋read-back）②judge が N回連続失敗で goal ループを blocked＋通知に倒す（core側 50行程度）。**おすすめですすめます（GOで実行します）**。

## 追記（12:40–12:45 実測）: 復旧したが偽alarmを再発 — 真因は「影武者DB」を掴む DB_PATH 解決

```
$ bash ~/.hermes/profiles/kensho-sweeps/scripts/loop_health.sh | python3 -c "import json,sys;d=json.load(sys.stdin);print(d['score'],d['lines'],'streak',d['streak'])"
65 ['score=65', 'top=t_757b8b5d age=14h', 'running=5', 'blocked=1', 'streak=1'] streak 1
```

```
$ python3 -c "sqlite task_runs: t_757b8b5d の現行run"
t_757b8b5d running 09-25 12:25:46      # 実age 0.3h
tasks.started_at = 09-24 22:25          # 初回dispatch値（stale）
```

```
$ python3 -c "sqlite counts: 2つのDB"
/home/atushi/.hermes/kanban.db                        tasks 0    runs 0      # ← 空（9/24 21:18）
/home/atushi/.hermes/kanban/boards/kensho-ai-team/kanban.db tasks 779 runs 1406 / t_757b8b5d runs 4
```

- 真因: `loop_health.sh:80` `DB_PATH="${HERMES_KANBAN_DB:-$HOME/.hermes/kanban.db}"` が**存在するだけの空レガシーDB**を指し、`:131` のボードDB自動検出は「`$DB_PATH` が存在しない時だけ」走る → `effective_started_at`（task_runs由来）が常に空 → `tasks.started_at` へフォールバックし、復活カードに **-25（>6h -10 + >12h -15）の偽減点**。
- 影響: score 65（<70＝alert帯）＋ `streak=1` → **誤エスカレーション経路が再点火**。zombie_task_count も同じ理由で常に0（検知能力ゼロ）。
- 修正（最小）: DB_PATH を「(a) `--db` (b) `HERMES_KANBAN_DB` (c) `~/.hermes/kanban/boards/<board>/kanban.db` の tasks>0 のもの (d) レガシー」の順に解決し、**空DBなら加減点をskip**（run取得0件で age 減点しない）。→ t_6f45dab0 / t_54681c2f に申し送り済み。
- 併せて観測: **running=5 が cap=4 を超過**（kensho-worker が4並列、`max_in_progress_per_profile: 2` 未反映）。実効dispatcher設定は gateway プロセスが読むため **gateway 再起動が必要**（9/24からの宿題）。負荷で done guard wall time が伸びた既往（13.4s→37.5s）があり、crash再発リスク。**【要ユーザー対応】gateway 再起動（GOで実行）**。

## 追記2（12:34 実測）: 修正が巻き戻り、監視は再び parse_error
```
$ md5sum scripts/loop_health.sh ; git show HEAD:scripts/loop_health.sh | md5sum
6a21708011003ede91b528869129ef63  scripts/loop_health.sh
6a21708011003ede91b528869129ef63  -        # HEAD=壊れたNameError版と完全一致（差分ゼロ）
$ bash ~/.hermes/profiles/kensho-sweeps/scripts/loop_health.sh 2>&1 | tail -2
loop_health: analysis failed
score=0 / alert=ERROR
```
- 12:14 に動いていた修正（`def resolve_max_in_progress` + effective化）は **12:29:39 の巻き戻しで消失**（mtime 12:29:39、def=0行）。
- t_6f45dab0 は 12:31:38 に**再spawn 済み**（heartbeat 生存・pid 53491）。カード自身の受入基準が「有効JSON」なので、完了には復旧が必須。**未pushのまま終わると監視は死んだまま** → カードに「復旧＋DB_PATH修正＋commit/push」を明記して申し送り済み。
- QAは**このファイルを書いていません**（所有は t_6f45dab0）。writer 1人を守るため介入せず、申し送りと次runでの実測に委ねる。
