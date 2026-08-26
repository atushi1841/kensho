# 日次改善ノート: 2026-08-27

## Critic分析（2026-08-27 00:45 実施）
- 提案24【高】keyword_flag過検出是正 — cpmeikan/kenkakuのHTMLコンテキスト誤判定（288件）をapplierでCDN tweet-text再判定により是正
- 提案25【中】成功計の計算基準変更 — auditベース259件が重複RT55件を含み水増し。実ユニーク約204件（daily_counts 113F+85RT+6L）
- 提案26【低】1084(zin)監視継続 — 8/26 22:20 WiFi切断、8/27 00:45時点35回連続失敗バックオフ中
- 提案27【低】keyword_flag実装効果の監視

## Worker実装（コミット済み）
| コミット | 内容 | 提案対応 |
|---------|------|---------|
| b70b5d4 (8/26 23:30) | keyword_flag実装: collector.py設定 + common.py _SKIP_KEYWORDS精緻化 + kenshouclub.pyコンテキスト判定化 + applierスキップ | 前日提案(引用RT/コメント除外) |
| f4c2ce1 (8/27 01:21) | 提案24: applier CDN再判定 + 提案25: action_history重複除外 | 24, 25 |
| 70f5174 (8/27 01:22) | 実装記録の報告追記 | — |
| 2e7fb31 (8/27 02:49) | 提案28: daily_target導入 + レポート基準変更 | 28 |
| f3d39f4 (8/27 05:05) | watchdog egress死活チェック + 多重LISTENING掃除の恒久化(申し送り#3実装) | 申し送り#3 |

## Worker実装記録(2026-08-27 05:05・申し送り#3・f3d39f4)

### 背景(申し送り#3)
「watchdog再起動判定にegress死活チェック(SOCKS5 CONNECT試行)を組み込む恒久対策が未実装。1085型の多重LISTENING積み上がり再発防止のためWorkerに優先実装を依頼」

### 実測で確認した問題(実装前に発見・スコープ拡大)
wifi_watchdogをcroneq環境(env -i PATH=/usr/bin:/bin)で実行したところ、**1085にkensho_proxy.pyが13+プロセス多重稼働**(全PIDがLISTENINGを回し合い、LISTENING PIDが次々入れ替わる)を確認。LISTENING PIDだけをkillする方式では取り残しが生じ、無限に積み上がる。TankanNotes(1085)はconfigコメントアウト中なのにwatchdogがポートを監視し続け、「LISTENINGだがegress不通→kill→再起動」のチャーンも誘発していた。

### 変更内容
| ファイル | 変更 |
|---------|------|
| `kensho/utils/proxy_watchdog.py` | `_kill_listeners`を強化: LISTENING PIDのみでなく、**CommandLineに `kensho_proxy` + ポート番号を含む全プロセスをkill**(Get-CimInstance方式)。`restore_dead_proxies`再起動前に呼ぶ |
| `tests/test_proxy_watchdog.py` | 新規テスト3件(killコマンド照合/タイムアウト/OSError) |
| `~/.hermes/profiles/kensho-sweeps/scripts/kensho-wifi-watchdog.sh` | 生存判定を「netstat LISTENINGのみ」→「SOCKS5 egress死活」に変更。egress不通のLISTENINGはkillして再起動。inactiveなTankanNotesをADAPTERSから除外 |

### 期待効果
- 1085型の「LISTENINGだが実疎通なし」を確実に検出して復旧
- 再起動前の全kensho_proxy killで多重LISTENING積み上がりを恒久防止
- 死んだinactiveスクの無限チャーン停止(リソース節約)

### 実測証跡
- `_kill_listeners(1085)`後: listeners 0 / 該当kensho_proxy 0(WSL→Windowsで確認)
- watchdog実行: active垢(kudou/chugakujuken/inobase1-4)を「egress OK」で生存判定、zin(1084)はバックオフ継続、TankanNotesはチャーンなし

### リスク評価
- 【低】タイムアウト時は0返却でkillしない(fail-safe)
- 【低】venv消失(127)時は生存扱いで従来挙動維持(誤キル防止)
- 対象はkensho_proxy.pyプロセスのみ。他プロセスには影響なし

## QA検証結果（01:23-01:35 実施）

### 1. pytest
```
169 passed, 4 skipped in 46.64s
```
全通過。Workerコミット前後で件数変化なし（回帰なし）。

### 2. git状態
- ワーキングツリー: クリーン ✅
- 前日申し送り「keyword_flagがapplier側のみコミット・collector側未コミット（依存不整合）」→ **b70b5d4で解消済み**。collector.py / common.py / kenshouclub.py / migrate_keyword_flag.py 全てtracked・コミット済みを確認

### 3. 差分確認（提案 vs 実装）
- **提案24【高】✅ 一致**: applier.py 630-648行 — keyword_flag=True時にtweet_id抽出→api_get_tweet_text→has_skip_keyword再判定。CDN本文にキーワードなければ「収集時誤判定」として処理継続＋tweet_text書き戻し。提案の「CDN再判定でキーワードなければ処理継続が安全」判断をそのまま実装
- **提案25【中】✅ 一致（代替案採用）**: 提案は「daily_countsベースへ変更 or auditから重複除外」。実装は後者の「(day,account,action_type,target)重複排除」方式。表示系のみの変更でパイプライン影響なし
- **提案26【低】✅ 監視継続**: コミットメッセージに「1084(zin) 01:00時点も不通（no_action_window中）」と記載
- **提案27【低】**: 本QAでベースライン確認（下記ライブ計測）。効果判定は8/27朝バッチ後の次回レポート

### 4. ライブ計測
| 項目 | 結果 | 判定 |
|------|------|------|
| プロキシ出口IP | 1081=219.104.132.236 / 1082=106.146.10.71 / 1083=106.146.25.190 / 1089=106.146.26.95 | ✅ 全IPユニーク |
| 1084 (zin) | 不通（WiFi切断継続、8/26 22:20〜） | ⚠ 提案26監視継続 |
| 1085 (TankanNotes) | 不通（configコメントアウト済み・正常） | ✅ 想定内 |
| collected.json | 1145件 / keyword_flag True=329 (28.7%) / False=816 | — |
| keyword_flag=True applied率 | 24.3%（80件）— 修正前データ | ⏳ 修正効果は8/27以降 |
| 8/26 audit重複 | success 241 / ユニーク165 / 重複ペア55 / 余剰76 | ✅ 提案25の修正前ベースライン確認 |
| 収集 | 21:00最終「0成功/0エラー/421合計」（新規なし=プール枯渇の正常状態） | ✅ 毎時動作 |

### 5. 前日申し送りの確認
| 申し送り | 状態 |
|---------|------|
| keyword_flag collector側未コミット | ✅ 解消（b70b5d4） |
| watchdog再起動判定にegress死活チェック | ⏳ 未実装・継続申し送り（1085多重LISTENINGは全kill→クリーン再起動で解決済み） |
| RESTフォールバックempty_response | ⏳ 継続監視（19:07はデプロイタイミングアーティファクトと判明、残存は1件/2件レベル） |
| mypy strict 33エラー | ⏳ 既知の技術負債（AGENTS.md 0 errorと乖離中・exclude設定で解決可） |

## 新規発見・注意点（QA観察）
1. collected.jsonの`timestamp`が17:09のまま（21:00収集は新規0件でtimestamp未更新の模様）。実害なし（collect_*.logで毎時動作確認済み）だが、収集停止と誤認するリスク。監視上の軽微な問題として記録
2. 収集プール枯渇傾向（421候補中0新規）。夜間の正常状態だが、8/27昼の収集で新規が入らなければ応募数低下の要因になり得る

## 保存場所
- 本ノート: `kensho/reports/daily-improvement-2026-08-27.md`
- Critic提案: `reports/critic_proposal_2026-08-27.md`

## 次回への申し送り
1. **【監視】提案27**: keyword_flag過検出是正（提案24）の効果を8/27のapplied率で確認。keyword_flag=True 329件のapplied率が24.3%（修正前）から適正に上昇しているか。ただしTrue件数の増減（収集時の新規フラグ付け）も併せて見ること
2. **【監視】1084(zin)**: 8/27 08:00最初のバッチ前に復旧確認。不通継続ならTankanNotes同様のconfigコメントアウト検討（提案26）
3. **【設計】watchdog再起動判定**: LISTENINGのみでなくegress死活（SOCKS5 CONNECT試行）を再起動判定に組み込む恒久対策が未実装。1085型の多重LISTENING積み上がり再発防止のためWorkerに優先実装を依頼
4. **【既知】mypy strict 33エラー**: exclude設定で解決可能な状態。AGENTS.mdの「0 error」と乖離しているため、次回Workerで対応検討
5. **【情報】collected.json timestamp**: 収集0新規時にtimestampが更新されない（17:09のまま）。収集停止の誤診断を防ぐため、collection cron側でtimestamp更新 or ログ参照の運用を明文化

---

## QA検証結果（2回目: 03:10-03:14 実施・提案28検証）

### 対象: 提案28【中】バッチ消化率の計画基準を日次目標（daily_target）に変更（commit 2e7fb31 @ 02:49）

### 1. pytest
```
169 passed, 4 skipped in 43.28s
```
前回（01:23）と同じ件数。提案28は表示系のみの変更で回帰なし。

### 2. git状態
- ワーキングツリー: クリーン ✅
- 最新コミット: 2e7fb31（提案28実装）

### 3. 差分確認（提案 vs 実装）
- **提案28【中】✅ 一致（方法A採用）**: 提案の推奨方法A（config.yamlに `daily_target` フィールド追加）をそのまま実装
  - `config.yaml`: atushi16=75 / kudou・chugakujuken・zin20120731・inobase1-4=50 / TankanNotes=50（コメントアウト内）
  - `kensho/tools/daily_pipeline_report.py`: `planned = sum(batches[].max)` → `targets.get(acct, 50)`。`targets` dictはconfigから `daily_target`（未設定なら `DEFAULT_TARGET`、更に未定義なら50）を解決（68-75行）。ハードコードされたデフォルト50のフォールバックも備える
  - 意図しない副作用なし（ACCOUNTS・n_batches・by_acct集計ロジックは不変）

### 4. ライブ計測（実際にレポート実行・8/26データ）
```
## バッチ計画 vs 実績
- atushi16: 目標75件/10バッチ → 実績55件（73%）
- kudou: 目標50件/10バッチ → 実績53件（106%）   ← 修正前44%（誤警告）→106%
- chugakujuken: 目標50件/10バッチ → 実績50件（100%）
- zin20120731: 目標50件/8バッチ → 実績46件（92%）
- TankanNotes: 目標50件/0バッチ → 実績5件（10%）⚠️ コメントアウト済みで想定内
- inobase1-4: 目標50件/10バッチ → 実績50件（100%）
```
提案の期待効果（kudou 44%→106%）を実測で確認。誤警告4垢が解消し、atushi16の73%未達のみが警告として残る（正しい挙動）。

### 5. 前回申し送りの状態
| 申し送り | 状態 |
|---------|------|
| 提案27（keyword_flag効果監視） | ⏳ 8/27朝バッチ後のレポートで確認（前回から変化なし） |
| 1084(zin)不通 | ⏳ 夜間切断継続（8/27 03:12時点もレポートに実績なし） |
| watchdog egress死活チェック | ⏳ 未実装・継続 |
| RESTフォールバックempty_response | ⏳ 継続監視（8/26最終: 31件） |
| mypy strict 33エラー | ⏳ 既知の技術負債 |

### 6. 新規発見・注意点
- 収集プール枯渇傾向は継続（8/26 21:00 0新規）。8/27朝〜昼の収集で新規が入らなければ応募数低下の要因。→ 前回申し送り#5のとおり
- 提案28の `targets.get(acct, 50)` は未設定アカウントを暗黙に50で扱う。将来ACCOUNTSに垢を追加する際はconfigの `daily_target` も同時に設定すること（設定漏れでもクラッシュしないが、目標値がデフォルト50になる）。

---

## QA検証結果（3回目: 05:10-05:20 実施・watchdog egress恒久化 f3d39f4検証）

### 対象: 申し送り「watchdog再起動判定にegress死活チェック（LISTENINGのみの再起動防止）」（commit f3d39f4 @ 05:01）

### 1. pytest
```
172 passed, 4 skipped in 44.13s
```
前回（03:10）169→172に+3（新規テスト3件）。全通過・回帰なし。

### 2. git状態
- ワーキングツリー: クリーン ✅
- 最新コミット: 7eb934a（Worker実装記録追記）
- 実装コミット: f3d39f4（watchdog egress恒久化）

### 3. 差分確認（申し送り vs 実装）
- **申し送り「watchdog再起動判定にegress死活チェック」✅ 一致**:
  - `_kill_listeners(port)` 新規追加（proxy_watchdog.py line 91-119）: `Get-CimInstance` でCommandLineに `kensho_proxy` + ` <port>\s*$` を含むプロセスを全てkill → その後 `Get-NetTCPConnection` のLISTENING PIDもkill。1085型13重起動の掃除方式（skill「プロキシ多重起動の掃除方法」）を採用
  - `restore_dead_proxies` の再起動前に `_kill_listeners(port)` を呼ぶ（line 309）— 多重LISTENING積み上がり防止
  - `PS` 定数（フルパス、line 39）使用 — cron環境（PATH=/usr/bin:/bin）対応
  - テスト3件: `test_kill_listeners_invokes_powershell` / `test_kill_listeners_handles_timeout` / `test_kill_listeners_handles_oserror` — 全通過 ✅
  - 意図しない副作用なし（_check_egress・_adapter_ipv4・_restoreロジックは不変）

### 4. ライブ計測（05:15実施）
```
1081 atushi16:     219.104.132.236 ✅
1082 kudou:        106.146.10.71   ✅
1083 chugakujuken: 106.146.25.190  ✅
1084 zin20120731:  不通（継続）     ❌
1089 inobase1-4:   106.146.26.95   ✅
```
- 生存4/5、出口IPは全てユニーク（IP分離維持）✅
- **注意**: 1082/1083/1089に各2重のkensho_proxyプロセスが残存（旧多重起動の残骸）。`_kill_listeners`は「再起動時」にのみ発動するため、egress生存中の残骸は自動掃除されない。実害なし（LISTENINGは機能・IP分離も正常）だが、恒久クリーンアップを望むなら再起動トリガーだけでなく定周期の掃除パスも検討余地あり

### 5. 前回申し送りの状態
| 申し送り | 状態 |
|---------|------|
| watchdog egress死活チェック恒久化 | ✅ f3d39f4で実装・検証済み（本ラン） |
| 提案27（keyword_flag効果監視） | ⏳ 8/27朝バッチ後（08:00以降）で確認 |
| 1084(zin)不通 | ⏳ 夜間切断継続（05:15時点も不通・78回超バックオフ） |
| RESTフォールバックempty_response | ⏳ 継続監視（8/26最終: 31件） |
| mypy strict 33エラー | ⏳ 既知の技術負債 |

### 6. 新規発見・注意点
- **既存の多重プロセス残骸は自動掃除されない**: `_kill_listeners`は再起動時にのみ発動。egress生存中の多重プロセス（1082/1083/1089各2重）はそのまま残る。BOT検出リスクはないが、リソース上の雑味。stop_proxies.ps1全kill→クリーン再起動で解消可能
- **1084(zin) 78回超バックオフ継続**: 朝08:00バッチで復旧確認。不通継続ならconfigコメントアウト検討（Critic提案29のとおり）
- **TankanNotesアダプタ名変更**（Tankan_8iP6s → Tankan_2_redmi_n9s）: proxy_watchdog.py の PROXY_ADAPTER_MAP/WIFI_SSID_MAP には反映済み（line 21, 30）✅。start_proxies系とgen_status_html.pyの更新は未確認（コメントアウト中で実害なし・優先度低）

---

## QA検証結果（4回目: 07:20-07:35 実施・夜間worker 06:48出力検証）

### 対象: nightly-worker 06:48出力（コミット新規なし・報告追記のみ）

### 1. pytest
```
172 passed, 4 skipped in 32.96s
```
前回（05:10）と同数。新規コード変更なしのため回帰なし。

### 2. git状態
- 最新コミット: 7eb934a（05:05、Worker実装記録追記）— 06:48 workerは新規コミットなし
- ワーキングツリー: `kensho/reports/daily-improvement-2026-08-27.md`（05:10 QA追記分）+ `reports/critic_proposal_2026-08-27.md` が未コミット。**QA追記分をコミットし忘れている状態**（実害なし・次回workerコミット時に含まれる見込み）

### 3. 差分確認（提案 vs 実装）
- 06:48 worker出力は既存内容の再掲（f3d39f4 watchdog egress恒久化の報告）。新規実装なし → 差分確認対象なし

### 4. ライブ計測（07:25実施）
```
1081 atushi16:     219.104.132.236 ✅
1082 kudou:        106.146.10.71   ✅
1083 chugakujuken: 106.146.25.190  ✅
1084 zin20120731:  106.146.14.220  ✅ ← ★復旧（8/26 22:20切断 → 8/27 06:25回復）
1085 TankanNotes:  不通（コメントアウト中・想定内）❌
1089 inobase1-4:   106.146.26.95   ✅
```
- 生存4/5、出口IP全てユニーク（IP分離維持）✅
- **★ zin(1084)復旧を確認**: wifi_watchdogログで 06:25 に `✅ zin_AW6povo -> 接続済み` + `✅ プロキシ1084(zin_AW6povo) 生存（egress OK）`。f3d39f4のegress死活チェックが正常動作し「接続済みだがegress不通」を正しく判定→復旧検出。プロセスは同一PID 17128のまま（アダプタ側の復旧でありプロセス再起動なし）
- **プロキシ多重プロセス**: 1082/1083/1089の各2重残骸は依然残存（05:10と同じ・`_kill_listeners`は再起動時のみ発動のため）
- **1086(inobase1-1)**: LISTENING 1だがegress不通（凍結垢の残骸プロキシ。configからは除去済みのため実害なし）

### 5. 前回申し送りの状態
| 申し送り | 状態 |
|---------|------|
| watchdog egress死活チェック恒久化 | ✅ f3d39f4で実装・検証済み（本ランでzin復旧検出を実証） |
| 提案27（keyword_flag効果監視） | ⏳ 8/27朝バッチ後（08:00以降）で確認 |
| **1084(zin)不通** | ✅ **復旧（06:25）**。申し送りクローズ。08:06最初のバッチで動作確認予定 |
| RESTフォールバックempty_response | ⏳ 継続監視 |
| mypy strict 33エラー | ⏳ 既知の技術負債 |

### 6. 新規発見・注意点
- **zin復旧により5垢全部がアクティブに**: atushi16/kudou/chugakujuken/zin/inobase1-4 の5垢で08:00以降のバッチがフル稼働見込み。zinの最終応募は8/26 21:17（切断前）なので、8/27 08:06バッチで再開確認
- **06:48 workerは報告のみで新規実装なし** — 2時間おきworkerのうち実装は05:01(f3d39f4)で完了。次回実装は次サイクルのcritic提案待ち
- **未コミットのQA追記**: daily-improvement-2026-08-27.md にQA検証結果（05:10/07:20分）が未コミット。次回workerのコミットに含まれる想定だが、QA側でコミットする運用に変更しても良い（検討事項）
