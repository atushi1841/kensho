# QA検証レポート nightly-qa run18（2026-09-25 22:13–23:20 JST）

## 0. 結論（3行）
- 盤面は **健全へ復帰**（ready=1 / running=4=cap / blocked=2 / done=695）。t_a38b99bc が done、t_757b8b5d が dispatch され直列チェーンが前進。
- **loop_health の score=75/WARN は「偽ペナルティ」**であることを負の対照で確定（実測: 正しい DB を渡すと `score=100 / alert=OK`）。真因は `_db_has_tasks()` が常に false を返し **DB_PATH が空の legacy DB に固定**されること（sqlite3 CLI 不在＋python フォールバックが SyntaxError）。
- 監視系の副次故障2件を同時に特定: **ゾンビ検出が常に0**（誤DB参照）／**死鎖検出の `--board` が `.hermes` に化ける**（`dirname` 推定）。既存カード t_9a4be9d7 に真因を追記した。

## 1. ループ健康度（script出力の検証）
```
$ bash ~/.hermes/profiles/kensho-sweeps/scripts/loop_health.sh | python3 -c "import json,sys;d=json.load(sys.stdin);print(d['score'],d['alert'],d['running'],d['blocked'],d['streak'],d['aux_auth_errors'],d['cap_mismatch'])"
75 WARN 4 2 0 0 False
```
- `score` 75（WARN）/ `stagnation_streak` 0 / `escalation` false / `business_ok` true / `aux_auth_errors` 0 → **判定: healthy（alert の WARN は偽）**。
- 30以下ではないため重大アラートではないが、score が 100→80→70→90→75 と動いているのは実体（応募/実装）ではなく **WIP 瞬間値と stale `started_at`** によるもの。

### 真因（負の対照つき・確定）
```
$ python3 -c "import sqlite3;print(sqlite3.connect('file:/home/atushi/.hermes/kanban.db?mode=ro',uri=True).execute('select count(*) from tasks').fetchone())"
(0,)
$ command -v sqlite3 || echo NO_SQLITE3_CLI
NO_SQLITE3_CLI
$ python3 -c "import sqlite3,sys;try:print(sqlite3.connect('file:%s?mode=ro'%sys.argv[1],uri=True).execute('SELECT count(*) FROM tasks').fetchone()[0]);except:print(0)" /home/atushi/.hermes/kanban/boards/kensho-ai-team/kanban.db
  File "<string>", line 1
    import sqlite3,sys;try:print(...)
                       ^^^
SyntaxError: invalid syntax
```
→ `_db_has_tasks()`（loop_health.sh L141-146）は sqlite3 CLI 不在時に **壊れた python ワンライナー**を使うため、空DBも実ボードDB（813 tasks）も等しく「タスク無し」と判定。結果 `DB_PATH` は `${HOME}/.hermes/kanban.db`（0 tasks）に固定される。

```
$ bash <copy of loop_health.sh with debug prints> 2>&1 >/dev/null | grep DEBUG
DEBUG _LH_DB='/home/atushi/.hermes/kanban.db' exists=True
DEBUG eff_rows=0
DEBUG by_age=[('t_757b8b5d', None, 1790256335, 24.35), ('t_fe629b9e', None, 1790318034, 7.21), ...]
DEBUG score_before_kpi=75
$ bash <same copy> --db /home/atushi/.hermes/kanban/boards/kensho-ai-team/kanban.db 2>&1 >/dev/null | grep DEBUG
DEBUG _LH_DB='/home/atushi/.hermes/kanban/boards/kensho-ai-team/kanban.db' exists=True
DEBUG eff_rows=5
DEBUG by_age=[('t_28e11c70', 1790341706, 1790319617, 0.65), ('t_757b8b5d', 1790343688, 1790256335, 0.1), ...]
DEBUG score_before_kpi=100
$ bash <same copy> --db <board db> | python3 -c "import json,sys;d=json.load(sys.stdin);print(d['score'],d['alert'])"
100 OK
```
- `effective_started_at` が空 → age 減点（L419-430）が **stale `tasks.started_at`**（t_757b8b5d = 初回dispatch 24.35h前）へフォールバックし -10/-15 = **-25**。
- 同系統の v137b 修正（`_real_deductions` は `_eff()` を使いフォールバックしない・L587-593）と**判定ソースが不一致**のまま残っている。

## 2. 検出した新規欠陥（優先度つき）
| # | 優先 | 内容 | 実測 |
|---|------|------|------|
| N1 | 高 | `_db_has_tasks()` の python フォールバックが SyntaxError → DB_PATH が空 legacy 固定 | 上記 §1 |
| N2 | 高（副次） | ゾンビ検出が誤DB参照で常に0（`zombie_task_count=0` が真偽不明） | 正DB指定時も0だが、誤DB時は**構造的に0** |
| N3 | 高（副次） | 死鎖検出の `--board` が `basename(dirname('/home/atushi/.hermes/kanban.db'))='.hermes'` に化ける（L329） | t_9a4be9d7 の JSON 解析欠陥と二重で無効 |
| N4 | 中 | 孤児run t_5dd7ba12: カード行が無いまま run 1474 が 1h40m 稼働し、完了不能な `kanban_complete` を3回試行（guard BLOCK 2〜4条件） | task_runs にのみ存在・pgrep で PID 生存 |
| N5 | 中 | 監視対象としての loop_health score が偽値を返すため、**monitor の change-detection が実体を映さない** | 前回 diff: score 80→70 は実体変化ではなく WIP/stale 由来 |

## 3. セキュリティ（QAが実施・完了）
- 追跡下 `config.yaml` の作業ツリーに **平文APIキーを含む無主 `providers:` ブロック**（21:29 書き込み）を検出 → 除去。
- 値は本レポートに記載しない（[REDACTED]）。
- 実測: `git show HEAD:config.yaml | grep -c <key>` = 0（**HEAD 未混入**）／`git log --all -S<key> -- config.yaml` = 空（**履歴にも不存在**）／除去後 `git status --porcelain config.yaml` = 空（HEAD と一致）。kensho コードは当該キーを参照しない（`core.config.load()` 前後で keys 21→20・差分キーは providers のみ）。
- 書き手は稼働中カードに不在（mtime 21:29 < 稼働4枚の開始 22:13）＝孤児run（t_5dd7ba12 系）の無主WIPと推定。正当な置き場は host config（`providers.freellmapi` / `fallback_providers` は既設定）。

## 4. ライブ計測（3軸の business_kpi 根拠）
```
$ python3 scripts/audit_bot_safety.py 2026-09-25
[audit_bot_safety] 2026-09-25: BOTシグナルなし (深夜ゼロ・連続なし・単独アクション)
$ tail -4 logs/auto_20260925.log
2026-09-25 22:16:47 - [OK] Session: @atushi16 OK（最終更新: 0日前）/ @kudou_aoshi OK / @zin20120731 OK / @TankanNotes OK
2026-09-25 22:16:47 - Step 5: Apply Check → 垢別起動: zin20120731 / 処理待ちのバッチなし
2026-09-25 22:16:47 - === 正常終了: 22:16:47 ===
```
- 出口IP分離: atushi16=219.104.132.236（自宅・この垢のみ）/ kudou=106.146.24.185 / TankanNotes=126.245.21.117 の **3/3 相異・重複なし**（`data/account_wifi_map.json` 22:15更新・egress_ok=true）。
- zin20120731（1084 停止）と toushiwatch（1087 停止）は**設計どおり応募停止**（ユーザー報告・回線変更待ち）＝欠陥ではない。
- リプライは `リプライ: 無効化（応募はフォロー/いいね/RTのみ）`、日次完了 46 行、aux 401 = 0。

## 5. 観点別分割検証（5観点・それぞれ独立計測）
※ 本runでは `delegate_task` が利用不可（tool_search 0件）だったため、観点ごとに**独立コマンドで個別計測**して集約した。
- コード品質 **6**: 平文キー混入（除去済・履歴汚染なし）／repo直下に `test_deadlock.py` `test_deadlock2.py` `devto_weekly_pipeline.py.bak-t_d5e647a1` の残骸（孤児runのWIP・非介入）／`pytest -q tests/test_devto_weekly_pipeline.py` **16 passed**。
- BOT検出リスク **9**: audit_bot_safety BOTシグナルなし・深夜ゼロ・リプライ無効・IP分離3/3。
- 設計一貫性 **5**: 直列化パターン（新規カード blocked→link）が機能（t_d6154f58←t_a38b99bc）／ただし「Hermes用設定をkenshoリポジトリへ書く」誤対象が再発（§3・前runの df91ceb と同型）。
- テスト充足 **5**: devto 16 passed、guard関連 11 passed。一方 `kanban_done_guard.py --selftest` は **6run連続 exit 2**（P1）。
- ライブ計測 **9**: §4 のとおり正常。zin/toushiwatch の停止は設計どおり。

```
$ timeout 400 bash ~/.hermes/profiles/kensho-sweeps/scripts/kanban_done_guard.py --selftest > /tmp/qa18.log 2>&1; echo REAL_EXIT=$?
REAL_EXIT=2
$ tail -1 /tmp/qa18.log
SELFTEST FAILED: guard did not behave as designed (e_push_gap=True d_bleed=True d_prohibited=True d_nonowned=True g_durability=False h_result=False i_config_drift=True j_write=True k_outcome=True write_report=True)
$ md5sum ~/.hermes/profiles/kensho-sweeps/scripts/kanban_done_guard.py
3ff05da446c1f1243938a0c94befa058  kanban_done_guard.py
```
- P1 の失敗は **g_durability / h_result の2条件のみ**。run17 で確定済みの真因は「セルフテストのフィクスチャが `<tid>_evidence.md` を名乗る（本番 `owns_file()` は `<tid>_verification.md` / `<tid>_evidence.json` のみ許可）」＝**テスト側ドリフト**。フィクスチャを10箇所置換したコピーは exit 0（run17実測）。カード t_aa4ee345 は本文で原因を「e079f50 のコード回帰」としているため、コメントで訂正＋修正手順を追記した。

## 6. 3軸評価
```json
{"evaluation":{"technical":{"score":7,"assessment":"盤面は復帰（ready1/running4=cap/blocked2）。ただし監視層に新規P1（DB_PATH固定でscore偽75・ゾンビ検出死・死鎖--board化け）とguard selftest 6run赤","evidence":"_LH_DB=legacy/eff_rows=0/score75 vs --db指定で100/eunched N1-N3/selftest exit2"},"business_kpi":{"score":9,"assessment":"3垢正常終了・深夜ゼロ・リプライ無効・日次46完了・IP分離3/3","evidence":"audit_bot_safety BOTシグナルなし/22:16:47正常終了/egress 3/3相異/aux401=0"},"cost_efficiency":{"score":6,"assessment":"孤児runがカード無しで1h40m稼働し完了不能なcompleteを3回試行（成果自体は landed）。P1修正カードは親待ちで未着手","evidence":"task_runs run1474 running/pgrep 65553/52b9b77+7dc9288 はpush済"}},"loop_health":{"score":100,"stagnation_streak":0,"verdict":"healthy"},"self_review_quality":{"valid":true,"notes":"全判定に$コマンドと生出力。scoreは負の対照（--db指定）で偽ペナルティと確定。実行中WIP（loop_health.sh/orphan_run_reaper.py）には非介入"},"verdict":"conditional_pass"}
```

## 7. 申し送り
1. **【高・確定】N1 修正**: `_db_has_tasks()` L144 のワンライナーを heredoc 版 python に置換（`try:` をセミコロン後に置けず SyntaxError）。検証1行: `bash loop_health.sh --db ~/.hermes/kanban/boards/kensho-ai-team/kanban.db | python3 -c "import json,sys;print(json.load(sys.stdin)['score'])"` が 100 になること（現状の既定解決では 75）。**ただし loop_health.sh は現在 t_28e11c70 が編集中のため非介入**（直列化ルール）。既存カード t_9a4be9d7 にコメント済。
2. **【高】P1（guard selftest）**: 修正カード t_aa4ee345 は親 t_757b8b5d（running）待ち。真因はテスト側フィクスチャ命名で、`owns_file()` を緩めるのは不可（偽PASS穴が再開）。
3. **【高】孤児run t_5dd7ba12**: 成果は landed（52b9b77 = scripts/kanban_dep_deadlock_guard.py 237行 + loop_health.sh、7dc9288 = 検証レポート、push済）だが**カード行が存在しないため盤面に記録が無い**。t_9ea4b148（running・`scripts/orphan_run_reaper.py` 作成中）で完了扱いにするのを推奨。
4. **【中】score/streak の判定ソース不一致**: age減点（L419-430）は stale `started_at` へフォールバックし、`_real_deductions`（L587-593）はフォールバックしない。同一スクリプト内で健康判定が2系統に割れている（t_28e11c70 が扱う cap 2系統と同型）。
5. **【中】repo直下の残骸**（`test_deadlock.py` `test_deadlock2.py` `devto_weekly_pipeline.py.bak-t_d5e647a1`）は孤児runのWIP。孤児の終了処理後に一括整理。

## 8. 【要ユーザー対応】（おすすめですすめます／GOで対応します）
- **【高・継続】t_0893da33「gateway再起動」は無人実行させない**: 親3枚のうち t_1be2f1cf / t_081a89c0 が done になり、残る親は t_26812b2a（blocked）**のみ**。ここを閉じると即 ready＝無人で gateway 再起動が走り AIチームが停止する。実測では **aux 401 = 0 が継続**しており再起動は不要。推奨=①この1枚を `needs_input` のまま維持、または②「再起動不要な反映確認」へ書き換えて閉じる。**おすすめですすめます（GOで実行/対応をお願いします）**。

## verification_evidence
```
$ python3 -c "import sqlite3;c=sqlite3.connect('/home/atushi/.hermes/kanban/boards/kensho-ai-team/kanban.db');print([(s,c.execute('select count(*) from tasks where status=?',(s,)).fetchone()[0]) for s in ('ready','todo','running','blocked','done')])"
[('ready', 1), ('todo', 7), ('running', 3), ('blocked', 2), ('done', 695)]
$ bash ~/.hermes/profiles/kensho-sweeps/scripts/loop_health.sh | python3 -c "import json,sys;d=json.load(sys.stdin);print(d['score'],d['alert'])"
75 WARN
$ bash /home/atushi/.hermes/profiles/kensho-sweeps/cache/scratch/lh_debug.sh --db /home/atushi/.hermes/kanban/boards/kensho-ai-team/kanban.db | python3 -c "import json,sys;print(json.load(sys.stdin)['score'])"
100
$ python3 scripts/audit_bot_safety.py 2026-09-25
[audit_bot_safety] 2026-09-25: BOTシグナルなし (深夜ゼロ・連続なし・単独アクション)
$ git show HEAD:config.yaml | grep -c "(APIキー値は非記載)"
0
```
── QA run18 / 2026-09-25 23:2x JST
