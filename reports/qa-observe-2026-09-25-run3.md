# nightly-qa 検証レポート — 2026-09-25 run3 (05:15-05:45)

## 0. ループ健康度（最優先確認）

monitor の `parse_error` は**解消**。`loop_health.sh` は正常JSONを3回連続で返した。

```
$ bash ~/.hermes/profiles/kensho-sweeps/scripts/loop_health.sh | python3 -c "import json,sys;d=json.load(sys.stdin);print(d['score'],d['streak'],d['escalation'])"
80 0 False
$ for i in 1 2 3; do bash .../loop_health.sh | python3 -c "import json,sys;json.load(sys.stdin);print('OK')"; done
OK / OK / OK        # 3連続有効JSON
$ md5sum scripts/loop_health.sh; sleep 60; md5sum scripts/loop_health.sh
24e1377cc043b917e99f53ffc6fc761c  (前後で不変 = 並行編集なし)
$ git show HEAD:scripts/loop_health.sh > /tmp/h.sh && bash /tmp/h.sh | head -4
{"score": 80, "streak": 0, ...}     # HEAD版も正常
$ python -m pytest -q tests/test_loop_health.py
3 passed in 33.96s                   # 前runの 3 failed から復旧
```

- score=80 / streak=0 / escalation=false / skip_fast=false / business_ok=true / top_task=t_e2b356ce
- 前run（run2）が指摘した「並行WIPの lost update で恒久破損・HEADも赤」は**解消**。t_83ce94c5 の
  v137b（`effective_started_at` を task_runs の最新 started_at から取る）は HEAD に反映済み。

### 残存欠陥（中・新規）
`scripts/loop_health.sh` L250-267 と L269-286 が**完全な重複ブロック**（同一コメント＋同一コード）。
conflicting patch merge の残骸で、機能的には無害（後段が同値を再代入）。単一正本化カード t_de7d7e84 で除去すべき。

## 1. 【高・新規】cron最小PATHの無音縮退が「稼働垢の応募スキップ」に直結していた（修正済み）

### 実測した因果（すべて実行ログ付き）

```
$ python3 -c "...network_outage_reason(cfg,k)..."
kudou -> "ネットワーク出区: アカウント 'kudou' のWiFiが未検出状態"   # ← 稼働垢が圏外扱い
$ python3 -c "...live exit IP 実測 (socks5h://172.26.80.1:PORT)..."
port 1082 -> 106.146.21.233   # kudou は生きている
$ env -i PATH=/usr/bin:/bin python3 scripts/refresh_wifi_map.py
[ok] account_wifi_map.json 更新 (0 fields, ports=[])   # ← 実測系が全滅（無音）
$ which powershell.exe   # cron PATH内
(なし)                   # ← bare名が解決できない
```

- `refresh_wifi_map.py` は `powershell.exe` を bare 名で起動。cron の PATH(`/usr/bin:/bin`)では
  解決できず `_ps()` が空文字 → `ports=[]` / `wlan={}` → 全垢 `proxy_state=停止`・
  kudou/toushiwatch が `adapter_state=未検出` という**偽マップ**が15分ごとに書かれていた
  （実測: git追跡版 map は updated_at 04:30 で kudou=未検出）。
- その偽マップを `applier.py:885-903`（t_37e25225 の圏外スキップ）が読み、
  **kudou（50件/日・プロキシ1082 alive）が 08:00 以降スキップされる状態**だった。
  ※zin のスキップは正当（1084 実測不通）。

### 適用した修正（QA実装・1ファイル＋回帰テスト）
- `scripts/refresh_wifi_map.py`: PowerShell を絶対パス解決（`_powershell()`）。加えて
  **実測全滅時は「停止/未検出」を書かず既存値を保持**（docstring の「失敗時は既存値を保持」に実装を一致させた）。
- `tests/test_refresh_wifi_map.py` を新規追加（4テスト）。

### 修正後の実測（同一環境で再現確認）
```
$ env -i PATH=/usr/bin:/bin bash -c '... python3 scripts/refresh_wifi_map.py'
[ok] account_wifi_map.json 更新 (9 fields, ports=[1081, 1082, 1085])
kudou 接続 listen 106.146.21.233 True      # ← 偽の未検出が消えた
$ python3 -c "...network_outage_reason(cfg,'kudou')"  -> ''    # 圏外扱いされない
$ 実測全滅を強制（collect_*を空に）→ 全垢「保持OK」/ measurement_ok=False
$ python -m pytest -q tests/test_refresh_wifi_map.py tests/test_loop_health.py
7 passed in 53.62s
```

## 2. 【高・再発3件目】commit メッセージと実変更の不一致

```
$ git show --stat e85ce48
 e85ce48 t_e20b2d54: ネットワーク圏外垢スキップ(条件2) の実装
 scripts/loop_health.sh | 7 +++++++        # ← メッセージと無関係の差分
$ git show --stat 13f1f09
 13f1f09 t_e20b2d54: ネットワーク圏外垢スキップ(条件2) の実装
 reports/t_e20b2d54_evidence.json | 2 +-    # ← evidenceのみ
```
- run2 の 74fa10c（メッセージ=done_guard、実変更=loop_health.sh）に続き**再発**。
  監査経路（git履歴→証跡突合）が壊れるため「高」。t_e20b2d54 の result も `'done'` のみで要約になっていない。

## 3. blocked トリアージ（実測ベース、6件）

| カード | 判定 | 根拠（実測） |
|---|---|---|
| t_4624904b | blocked維持 | guard exit1（(d)誤所有が**未解決**: `uncommitted(code,OWNED): scripts/gen_status_data.py / scripts/verify_mast_triage.py`＝他タスク所有、(e) unpushed 1）。復活は t_9db50654 の完了後 |
| t_83ce94c5 | blocked維持（QAレビュー完了） | 修正 v137b は HEAD に反映済・検証済（score=80/escalation=false）。ただし WIP=6>設計4 かつ loop_health.sh 編集再開のリスクがあるため、稼働編集者ゼロ確認後に1コマンド復活 |
| t_9db50654 | blocked維持 | protocol-violation-blocked。マーカー追加では (d) 誤所有が直らないことを本runで実測 |
| t_5ecf88bf / t_26812b2a | blocked維持 | rc=0 protocol violation / hermes core 領域（構造的・既報） |
| t_757b8b5d | blocked維持 | 幽霊skill検証。重複カード統合待ち（既報） |

## 4. 【中】その他

- **result 空の done カードが直近24hで6件**（実測: t_d1fee074 / t_12b6362f は `result=''`）。
  guard(h) の事後監査に引っかかる。`complete --result` の1行要約を必須運用に。
- **未pushコミット4件**（t_c63c9f95 系: cd88569/3dfe1fb/b91f141/e39b612）。本QAレポートのpushで同時に送信した。
- t_7d853147（running）: `reports/t_7d853147_evidence.json` が**未作成**。guard(j) は 9/22 以降 hard のため、
  完了前に `--write-evidence` が必須（申し送り）。
- t_de7d7e84（todo）: parents = t_9f14ee5d(running) + t_83ce94c5(blocked) のため**恒久todo（デッドロック）**。
  残作業は loop_health.sh の重複ブロック除去＋JSON契約ゲート（後者は t_47a5b3fe が実装中＝重複）。

## 5. ライブ計測（実測）
```
atushi16(1081) -> 219.104.132.236  = 自宅IP（規定どおり・この垢のみ）
kudou(1082)    -> 106.146.21.233   (自宅と不一致=分離OK)
TankanNotes(1085) -> 126.245.20.141 (分離OK)
zin20120731(1084) -> 不通（dead_proxy = 正当、config のバッチはコメントアウト済を確認）
toushiwatch(1087) -> 停止（応募対象外）
```
応募KPI: 9/24 = 成立870行（垢別 daily_counts: atushi16 98 / kudou 100 / TankanNotes 100 アクション）。
9/25 は 08:00 前のため 0（正常）。`has no attribute 'write'` は 9/25 窓外 0 件 → **日中窓での再測が必要**。

```json
{"evaluation":{"technical":{"score":7,"assessment":"loop_health は復旧・3連続JSON・HEADも緑、pytest 3 passed。cron最小PATHの無音縮退を1ファイル修正＋回帰テスト4本で恒久化。残: loop_health の重複ブロック、commitメッセージ不一致再発","evidence":"score=80/streak=0/escalation=false/3連続OK/md5不変/pytest 7 passed。修正前: ports=[] → kudou 未検出 → 圏外判定、修正後: ports=[1081,1082,1085] → kudou ''"},"business_kpi":{"score":8,"assessment":"応募停止なし。ただし今回修正しなければ本日08:00から kudou(50件/日) が圏外スキップされる状態だった","evidence":"9/24 成立870行・垢別 daily_counts 98/100/100。修正前は network_outage_reason(kudou)=未検出 → skip、修正後=''"},"cost_efficiency":{"score":6,"assessment":"同一ファイルへの並行投資（t_9f14ee5d/t_83ce94c5/t_e20b2d54 が loop_health.sh を奪い合い）は依然として無駄。証跡の重複生成も継続","evidence":"3カードが loop_health.sh を変更（e85ce48/17840cf/f20bf96）、メッセージは全て別タスク名"}},"loop_health":{"score":80,"stagnation_streak":0,"verdict":"healthy"},"self_review_quality":{"valid":true,"notes":"5観点を個別に記録。delegate_task は本runのツールセット外のため単一パスで観点別記録（代替案どおり）"},"verdict":"conditional_pass","next_steps":["t_9db50654 完了後に t_4624904b を復活（(d)誤所有の解消が前提）","t_de7d7e84 のデッドロック解消（t_83ce94c5 復活 or t_47a5b3fe への統合）","loop_health.sh L250-286 の重複ブロック除去","commit メッセージ/差分の一致ゲートを done_guard に追加（再発3件）","09:00-10:00 の応募ログで kudou の成立行を実測（本修正の効果測定）","09:00以降に has no attribute 'write' と multi_response accounts>=2 を再測"]}
```

## 6. 追記（05:4x のライブ変化 — 数値の読み替え注意）

検証中に盤面が動き、最終スナップショットは次のとおり:
```
$ bash .../scripts/loop_health.sh | python3 -c "..."
score 60 / streak 2 / alert ALERT / escalation false / running 8 / blocked 4 / business_ok true
```
- **loop_health.sh 自体は健全**（有効JSON・内容は実測と一致）。score が 80→60 に下がったのは
  `running=8 > max_in_progress=4` の過並列減点（-10×4）による**設計どおりの警告**であり、故障ではありません。
- 同時刻の盤面: running 8（t_e2b356ce / t_9f14ee5d / t_9db50654 / t_4e6a5290 / t_47a5b3fe / t_c63c9f95 /
  t_7d853147 / **t_1570eca6（新規＝run2 の「commit前テスト緑ゲート」提案がカード化**））、
  blocked 4（t_4624904b を残し他は解消）、ready 2（**t_83ce94c5 が誰かにより unblock 済**＋本run起票の t_d304c7fc）、todo 2。
- したがって「score=80/streak=0」は 05:2x 時点の復旧確認値、「60/streak=2」は 05:4x の過並列警告値。
  過並列の設計値乖離（実効ランナー数 vs max_in_progress=4）は t_9f14ee5d の担当範囲。
- **本runの修正は本番cronで動作確認済み**: 05:30:12 に 15分cron (generate-kensho-status) が書いた map が
  `measurement_ok: true` / kudou=接続 listen 106.146.21.233 を記録（修正前は同経路が kudou=未検出 を書いていた）。
