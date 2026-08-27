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
- **未コミットのQA追記**: daily-improvement-2026-08-27.md にQA検証結果（05:10/07:20分）が未コミット。次回workerのコミットに含まれる想定だが、QA側でコミットする運用に変更しても良い（検討事項）→ **08:53 workerコミットb24b779で解消（QA追記分を含めてコミット済み）**

---

## QA検証結果（5回目: 09:30-09:40 実施・worker 08:54出力＝提案38&39実装 b24b779 検証）

### 対象: nightly-worker 08:54出力 → コミット b24b779（提案38&39: keyword_flag過検出是正）

### 1. pytest
```
172 passed, 4 skipped in 53.69s
```
全通過・回帰なし（前回07:20と同数、新規テスト追加なし）。

### 2. git状態
- 最新コミット: b24b779（08:53、提案38&39実装 + 未コミットQA追記分のコミット）
- ワーキングツリー: クリーン ✅

### 3. 差分確認（提案 vs 実装）
- **提案38【中】applier keyword_flag再判定のtweet_text優先化 ✅ 一致**:
  - `applier.py` L631-649: `_flag_recheck_text = item.get("tweet_text", "") or ""` を優先ソースに変更。tweet_textが無い場合のみCDN再フェッチ（`api_get_tweet_text`）にフォールバック。CDNネットワーク依存を排除
  - 過検出解除時のtweet_text書き戻しは維持（NGフィルター用）
  - ログ文言を「収集時tweet_textで解除」に更新
- **提案39【低】collector.py keyword_flag再評価の恒久対策 ✅ 一致**:
  - `collector.py` L495-509: Step 4終了後、`merged` 内の `keyword_flag=True` かつ `tweet_text` 所有アイテムを `has_skip_keyword(tweet_text)` で再評価し、該当しなければ `keyword_flag=False` に解除
  - `has_skip_keyword` import済み（L22）✅ / `_fx_resp` 変数スコープ内（L453→L477）✅
  - fixupxエラーログ追加（`[ERROR] fixupx: {x_url} (HTTP {status})`）— 診断性向上。既存未コミット分の拾い上げ
- **実動確認（★最重要）**: 09:00収集（collect_20260827_090001.log）で `[keyword_flag再評価] 327件中281件の過検出を解除（残り46件が正当な引用/コメント）` を確認。Workerのドライラン（1106件中327件→281解除/85.9%）と完全一致
- 意図しない副作用なし（applierのCDNフォールバックはtweet_text欠落時のみ発動、collectorの再評価はデータ書き換えのみで構造不変）

### 4. ライブ計測（09:35実施）
```
1081 atushi16:     219.104.132.236 ✅
1082 kudou:        106.146.10.71   ✅
1083 chugakujuken: 106.146.25.190  ✅
1084 zin20120731:  FAIL (egress不安定) ⚠️
1085 TankanNotes:  不通（コメントアウト中・想定内）❌
1089 inobase1-4:   106.146.23.223  ✅
```
- 生存4/5、出口IP全てユニーク（IP分離維持）✅
- **★ zin(1084)は07:25時点で復旧していたが08:55に再切断**: wifi_watchdogログで `❌ zin_AW6povo -> 切断（SSID: AiR-WiFi_6_povo）@08:55:08` → 再接続試行も信号23-45%で不安定。watchdogのegress死活チェック（f3d39f4）が「LISTENINGだがegress不通→kill→再起動」を正しく検出・継続動作中（09:15にも `LISTENING but has NO egress – forcing WiFi reconnect + restart`）。**コード問題ではなくWiFi信号/物理回線の問題**。smartphone側（楽天モバイル回線）の物理確認が必要

### 5. 前回申し送りの状態
| 申し送り | 状態 |
|---------|------|
| 提案27（keyword_flag効果監視） | ✅ 提案38/39（b24b779）で対応・281件過検出解除を実動確認 |
| 1084(zin)不通 | ⚠️ 06:25復旧→08:55再切断→egress不安定継続（watchdogは正常動作） |
| RESTフォールバックempty_response | ⏳ 継続監視 |
| mypy strict 33エラー | ⏳ 既知の技術負債 |
| 多重プロセス残骸（1082/1083/1089各2重） | ⏳ 残存（`_kill_listeners`は再起動時のみ発動） |

### 6. 新規発見・注意点
- **QAの検証記録の未コミット問題を解消**: 本QAは追記後にコミットまで実行（notepad教訓「QA追記が未コミットになりがち」への対処。05:10/07:20分はworker b24b779が拾い上げ済み）
- **提案39の再評価は収集cronでのみ発動**（`separate_cron=true` のためorchestratorのStep 4は収集を実行しない）。収集ログの `[keyword_flag再評価]` 行が毎回出るか監視継続

---

## Worker実装記録(2026-08-27 11:1x・提案41&42・commit fb54962)

### 対象提案
| 提案 | 危険度 | 内容 | 実装 |
|------|--------|------|------|
| 40 | 高 | inobase1-4(1089) プロキシ不安定 | ⏳ **コード変更なし**・調査のみ(下記) |
| 41 | 中 | 引用ポスト案件のlike+rt多重(8/27 09:50) | ✅ applier.py |
| 42 | 中 | 引用ポスト案件のkeyword_flag漏れ | ✅ common.py + 既存データ再付与 |

### 提案40: inobase1-4(1089) プロキシ不安定 — 調査結果
- **本Worker実行時点(11:1x)でcheck_proxies.pyが✅生存(106.146.23.223, 0.5s)**
- watchdogログ(10:45まで)に「LISTENINGだがegress不通→kill→再起動→復旧→生存OK」のフラッピング記録あり(Ethernetアダプタ名 `Tankan_2_redmi_n9s` 由来の1085型と同型の一時的不安定パターン)
- config.yamlのinobase1-4ブロックは**アクティブのまま**（daily_target=50、10バッチ@12件）
- **結論**: 現時点で生存確認済みのためコメントアウトは保留。但し2週連続でフラッピング記録があるため、**再び長時間不通に陥る場合はTankanNotes同様の一時コメントアウトを検討**。スマホ(Redmi Note 9S/SSID ino1_4_oppo_r5a)のテザリング物理確認が必要な状態。

### 提案41: like+rt多重防止(applier.py)
- **原因特定**: `_like_in_text` 正規表現が景品説明の「💖」「❤」絵文字にマッチ → skip_like=Falseのまま、RTがキューに積まれていてもいいねが実行される経路。
  - 実証: tweet 2088792867397627932 本文「...#マツココちいかわ をつけて引用ポスト」+「💖」。auditで like(09:50) → rt(09:52) の多重。
- **修正**: いいね→フォロー切替ロジックに `skip_rt` 条件を追加
  ```python
  # 修正前
  if _like_in_text and random.random() < _like_with_follow_rate:
  # 修正後
  if _like_in_text and skip_rt and random.random() < _like_with_follow_rate:
  ```
- **効果**: RTがキューにある案件はいいねをスキップ → RT+いいねの機械的多重を永久排除。フォロー+いいね(当選条件を満たす安全な2アクション)は従来通り維持(skip_rt=True時)。
- **リスク評価**: 低。当選確率ほぼ不変(引用ポスト案件は元々AI応募不可)、BOT信号削減。

### 提案42: 引用ポスト案件のフラグ漏れ(common.py)
- **原因**: `_SKIP_KEYWORDS` に新UI用語「引用ポスト」「引用リポスト」「引用投稿」が不足。XのUI本文は「引用RT」→「引用リポスト/引用ポスト」に移行中。
  - 実測: collected.jsonで「引用ポスト」19件「引用リポスト/引用投稿」計79件がkeyword_flag=Falseのまま = applierが処理(無駄なフォロー/RT)。
- **修正**: 3フレーズを `_SKIP_KEYWORDS` に追加(フレーズ完全一致のみ。裸の「引用」は過検出を再発させるため追加しない)。
- **既存データ再付与**: tweet_textベースで80件にフラグ追加(引用リポスト50/引用ポスト14/引用投稿3+組合せ)。source内訳: knshow36/cpmeikan28/kenshouclub9/ken-kaku1/kema1/None4。
- **リスク評価**: 低-中。過検出281件解除(38&39)は維持(フレーズ一致に限定のため)、todo引用ポスト案件のフラグ漏れを塞ぐ。

### テスト結果
```
172 passed, 4 skipped in 58.78s
```
回帰なし。コミット: fb54962(pre-commit通過)

### 備考
- data/collected.json はgitignore対象のランタイムデータ。再付与はライブデータのみ適用(コミット外)。
- 収集cronのStep4再評価で将来の新規引用ポスト案件も自動フラグ付けされる(collector.py 提案39修正済み)。

---

## QA検証結果(6回目: 11:00-11:10 実施・worker 10:56出力=提案41&42実装 fb54962 検証)

### 検証対象
- Worker実装: `fb54962`(提案41&42: like+rt多重防止 + 引用ポスト用語フラグ追加)
- Worker記録: `86919a9`(daily-improvement追記)

### pytest結果
```
172 passed, 4 skipped in 41.93s
```
Worker報告(172 passed, 4 skipped)と完全一致。回帰なし。mypy含むpre-commit通貨をWorkerが報告済み。

### 差分確認(git show fb54962)
| ファイル | 変更 | 判定 |
|---------|------|------|
| `kensho/application/applier.py` | 提案41: いいね実行に `skip_rt` 条件追加。RTがキューにある案件はいいねスキップ → RT+いいねの機械的多重を永久排除 | ✓ 妥当 |
| `kensho/scraping/sources/common.py` | 提案42: `_SKIP_KEYWORDS` に「引用ポスト/引用リポスト/引用投稿」追加。フレーズ完全一致で過検出再発防止 | ✓ 妥当 |

コード変更は提案内容と一致。意図しない副作用なし。BOT検出回避の観点で正しい方向(同一ツイートへ2種アクションの機械的パターン排除)。

### 実データ検証(ライブcollected.json)
- 引用ポスト系本文あり **80件** すべて keyword_flag=True(漏れ0)。Worker報告の「既存80件再付与」を確認
- keyword_flag=True 合計: 127件(80件+他のスキップ語分)
- audit.jsonl(2483ペア)で同一(account,target)への複数種アクション成功 **0件** — 多重防止が機能

### 次回への申し送り
- 提案40(inobase1-4/1089 プロキシ不安定)は**コード変更なし調査のみ**。「再び長時間不通ならTankanNotes同様コメントアウト検討」の判断が今後要。
- zin20120731(1084)egress不安定継続(notepad教訓: 08:55再切断、WiFi信号23-45%)。スマホ物理確認が必要だが、watchdog(f3d39f4)がkill→再起動を継続動作。監視継続。

---

## QA検証結果(7回目: 13:10-13:20 実施・worker 12:58出力=TankanNotes復帰 6af66a7 + mypy修正 c720e3d 検証)

### 検証対象
- Worker実装: `6af66a7`(TankanNotes復帰・povo HR01切替 + 4ファイル同期) + `c720e3d`(mypy exclude修正)
- Worker記録: critic_proposal 第18版

### pytest結果
```
172 passed, 4 skipped in 36.65s
```
回帰なし。Workerがコミット前にpre-commit通過を報告済み。

### mypy修正の検証 (c720e3d)
- ルート `scraping/collector.py`(0byte)が `kensho/scraping/collector.py` と二重モジュール化 → "Source file found twice"でmypy全体スキャンがブロックされていた
- `mypy.ini` の exclude に `|scraping/` 追加で解消
- **実測**: `mypy .` が66ファイルをチェック完了（従来は致命的エラーで停止）。残198エラーは `no-untyped-def`/`type-arg`等の型注釈負債で構造的問題なし
- **注**: excludeパターンはルートの `scraping/` のみを除外。`kensho/scraping/` は引き続き型チェック対象（scorer.py/collector.py のエラーは検出され続ける）— 意図通り
- ✓ 妥当

### TankanNotes復帰の差分確認 (6af66a7) — 6垢化
| ファイル | 変更 | 判定 |
|---------|------|------|
| `config.yaml` | TankanNotesコメント解除（10バッチ@12件、daily_target=50）。keepalive WiFi-D再有効化(2_povo_HR01) | ✓ 妥当 |
| `kensho/utils/proxy_watchdog.py` | PROXY_ADAPTER_MAP(1085→2_povo_tankan) + WIFI_SSID_MAP(2_povo_HR01) | ✓ 妥当 |
| `scripts/gen_status_data.py` | WIFI_ADAPTER_TO_ACCOUNT / WIFI_ACCOUNT_SSID 更新（旧名Tankan_2_redmi_n9sは参照残コメント） | ✓ 妥当 |
| `scripts/gen_status_html.py` | ACCOUNT_ADAPTERS 更新(2_povo_tankan / 2_povo_HR01) | ✓ 妥当 |

### 4ファイル同期の検証（プロジェクト分離の要）
- `browser.py`: FINGERPRINTS(line 135) + PROXY_MAP(line 230, socks5h://172.26.80.1:1085) ✓
- `check_proxies.py`: PROXY_MAP(line 26) ✓
- `keyring.py`: セッションマッピング(line 30) + migrate_all(line 106) ✓
- `start_proxies.bat`(Windows): 1085 → `2_povo_tankan` ✓
- `start_proxies.ps1`(Windows): `@{adapter='2_povo_tankan'; port=1085; name='TankanNotes'}` ✓
- wifi-watchdog(profile側): ADAPTERSに `2_povo_tankan:2_povo_HR01:1085` 再追加(line 86) ✓
- セッションファイル: `data/x_session_TankanNotes.json` 存在 + auth_token/ct0両方あり（8/26更新）✓

全ファイルでアダプタ名・SSIDが一致。プロキシポート1085も矛盾なし。

### ライブ状態（check_proxies.py 13:1x）
```
atushi16     1081 ✅ 219.104.132.236
kudou        1082 ✅ 106.146.10.71
chugakujuken 1083 ✅ 106.146.25.190
zin20120731  1084 ✅ 106.146.13.249
TankanNotes  1085 ❌ Connection refused
inobase1-4   1089 ✅ 106.146.23.223
```
5/6生存・出口IP全ユニーク。TankanNotes(1085)は**想定内の不通**（ルーター2_povo_HR01不安定のためプロキシ未起動）。watchdogが自動復旧監視中。

### 次回への申し送り
- **TankanNotes(1085)がconfigアクティブなのにプロキシ不通**: ルーター(2_povo_HR01)不安定（DHCP不応答APIPA・L2切断繰返し）でプロキシ未起動。各バッチで無駄なブラウザ起動→ログイン失敗ループのリスク。watchdogが自動復旧を試行中。**復旧確認は check_proxies.py。長時間（24h超）不通が続くなら再コメントアウトを検討。** ルーター/スマホ側の物理確認が必要。
- zin20120731(1084)は現時点✅だが本日フラッピング履歴あり（08:55再切断・信号23-45%）。watchdog継続監視。
- ルート `scraping/`（0byte collector.py）とルート `orchestrator.py` は実運用で未使用の死骸（cronは `kensho/orchestrator.py` を使用）。mypy除外で静的解析は通るが、将来の混乱防止に削除検討（低優先）。

---

## Worker実装記録(2026-08-27 14:46・提案44検証 + 提案45監視基準設定・commit a7f3b19確認)

### 対象提案（critic_proposal 第19版・14:20）

| 提案 | 危険度 | 内容 | 対応 |
|------|--------|------|------|
| 44 | 中 | proxy_watchdog subprocess cp932デコードエラー（UnicodeDecodeError×3、12:45-12:58） | ✅ **commit a7f3b19で実装済みを確認** |
| 45 | 低 | TankanNotes(1085) 復帰したが不安定（フラッピング） | ⏳ **監視基準を設定**（下記） |

### 提案44: proxy_watchdog cp932デコードエラー — 実装済み確認

- **commit a7f3b19（14:44:53）** で全 `subprocess.run(..., text=True)` 7箇所（L114/L129/L220/L250/L266/L272/L325）に `errors="replace"` 追加済み。実コード確認で**全7箇所に追加を確認** ✅
- 解析対象（`status`="Up"/IP/件数）は全てASCIIのため、置換（U+FFFD）による挙動変化なし
- **pytest**: 172 passed, 4 skipped（回帰なし）
- 提案の期待効果どおり、今後は日本語Windows（cp932）出力でプロキシ再起動が失敗しない

### 提案45: TankanNotes(1085) 監視基準の設定

**14:46時点のライブ状態:**
- `check_proxies.py`: **6/6全プロキシ生存・出口IP全ユニーク**（1085 TankanNotes = 106.133.39.72, 0.3s ✅）
- wifi_watchdog（14:45/14:50）: `2_povo_tankan -> 接続済み [信号:100%|-43〜-49]` + `プロキシ1085 生存（egress OK）` — 直前3サイクル連続で安定
- ただし **TankanNotesは本日0成功**（daily_countsに未登場）。14:00バッチは `NS_ERROR_CONNECTION_REFUSED`×3 → 0成功/1エラー（43秒）。14:15以降はSession OK・垢順ローテーションに含まれるが、成功バッチ未確認（14:45サイクル進行中）

**再コメントアウト基準（critic提案45の通り、明文化）:**
| 基準 | 閾値 | 対応 |
|------|------|------|
| (a) プロキシ不通継続 | 24時間以上 egress不通（check_proxies.py で確認） | config.yaml から一時コメントアウト |
| (b) バッチ連続失敗 | 3回連続で NS_ERROR_CONNECTION_REFUSED / ログイン失敗（0成功） | config.yaml から一時コメントアウト |

- 現時点: (a)不該当（egress OK）、(b)は1回のみ（14:00）→ **コメントアウト保留・監視継続**
- 復旧確認は必ず `check_proxies.py` で egress まで確認してから（LISTENINGのみでは不十分）
- ルーター（2_povo_HR01：DHCP不応答APIPA・L2切断繰返し）はwatchdogで解決不能 — スマホ側の物理確認が最終手段

### テスト結果
```
172 passed, 4 skipped in 57.98s
```
回帰なし。gitワーキングツリー: クリーン（提案44実装済み・本記録は報告コミットで反映）

---

## QA検証結果（2026-08-27 15:1X・Workerラン 14:52 対応）

### 検証対象
- Worker実装: **提案44**（proxy_watchdog cp932デコードエラー）→ commit `a7f3b19`（14:44:53）
- Worker報告: **提案45**（TankanNotes 1085 再コメントアウト基準設定）→ commit `125ee1e`（14:52:04）

### pytest結果
```
172 passed, 4 skipped in 53.21s
```
**回帰なし**（QA独自再実行）。test_proxy_watchdog.py含む全テスト通過。

### git状態
- `git log --oneline -3`: `125ee1e`（Worker報告）→ `a7f3b19`（提案44実装）→ `55186f1`（QA検証7回目）
- ワーキングツリー: クリーン

### 差分検証（提案44 = a7f3b19）
- `git show a7f3b19`: proxy_watchdog.py の `subprocess.run(..., text=True)` 計**7箇所**（L114/L129/L220/L250/L266/L272/L325）に `errors="replace"` 追加 — **提案内容と完全一致** ✅
- 実コードgrepで確認: `errors="replace"` = **7件**、`text=True` 全7箇所すべてに付与済み（漏れなし）
- 解析対象（status="Up"/IP/件数）はASCIIのため置換による挙動変化なし（提案の見込みどおり）
- mypy: proxy_watchdog.py に **type-arg警告2件（既存・本変更による新規エラーなし）** — `errors="replace"`追加は型に影響しない

### ライブ計測（15:1X時点）
- `check_proxies.py`: **6/6全プロキシ生存・出口IP全ユニーク**（TankanNotes 1085 = 106.133.39.72, 0.3s ✅）
- 本日audit: atushi16=38 / kudou=31 / inobase1-4=20 / chugakujuken=19 / zin=19 success
- **TankanNotes: 本日0成功**（auditにエントリなし）— 14:00バッチは `NS_ERROR_CONNECTION_REFUSED`×3 → ログイン失敗 → Verifyタイムアウト。`[RESULT] ✅ ツイート正常（応募成立）`は付いたが実アクション0（既知の偽陽性パターン・applied増加のみ）。**提案45の監視継続が正しい判断**

### 提案45の妥当性
- 再コメントアウト基準（(a) 24h egress不通 or (b) バッチ連続3回失敗）はcritic提案どおり明文化済み・worker報告/notepadに記録 ✅
- 現時点: egress OK・バッチ失敗は14:00の1回のみ → **コメントアウト保留・監視継続が適切**
- 14:45/14:50 wifi_watchdog: `2_povo_tankan` 接続済み・信号100%・egress OK（直前3サイクル安定）— 復旧傾向

---

## Worker実装記録（17:30・提案45追従: TankanNotes 4ファイル同期の完了）

### 発見: 4ファイル同期漏れ（50cc8bfのワイモバイルHR01切替で未更新ファイル3件）

50cc8bf（16:31）でTankanNotesを povo HR01(2_povo_tankan/2_povo_HR01) → ワイモバイルHR01(Tankan_HR01/10_ymo_HR01) へ切替した際、**proxy_watchdog.py / start_proxies.bat / wifi-watchdog.sh / gen_status_data.py が旧povo設定のまま残っていた**（skill「アダプタ名/SSID変更時は4ファイルの同期が必要」の該当例）。結果:
- wifi_watchdogが5分毎に死んだpovoアダプタ(2_povo_tankan)へ `netsh wlan connect 2_povo_HR01` を試行 → 圏外で失敗 → 「切断/再接続失敗」を連続記録（16:00-16:45のログで確認）
- 1085が万一死んだ場合、watchdogの再起動が旧アダプタ名(2_povo_tankan)を参照して失敗するリスク

### 実施した同期（17:2X）

| ファイル | 変更 | 状態 |
|---------|------|------|
| `kensho/utils/proxy_watchdog.py` | PROXY_ADAPTER_MAP: TankanNotes → (1085, **Tankan_HR01**)、WIFI_SSID_MAP → **10_ymo_HR01**。bind方式(IP直指定)で起動 | sibling(ユーザー)が17:21に編集・staged |
| `C:\tools\kensho-proxy\start_proxies.bat` | 1085行: `2_povo_tankan` → `Tankan_HR01` | ✅ 本worker |
| `~/.hermes/profiles/kensho-sweeps/scripts/kensho-wifi-watchdog.sh` | ADAPTERS: `2_povo_tankan:2_povo_HR01:1085` → `Tankan_HR01:10_ymo_HR01:1085` | ✅ 本worker（bash -n OK） |
| `scripts/gen_status_data.py` | WIFI_ADAPTER_TO_ACCOUNT: Tankan_HR01追加 / WIFI_ACCOUNT_SSID: 10_ymo_HR01 | ✅ 本worker |
| `scripts/gen_status_html.py` | ACCOUNT_ADAPTERS: TankanNotes → (Tankan_HR01, 10_ymo_HR01, ワイモバイル) | sibling(ユーザー)編集・staged |

### --no-bind方針の確定（sibling編集によりbind方式に統一）

- 当初workerは `NO_BIND_ACCOUNTS={TankanNotes}` を追加したが、siblingが **bind方式(IP直指定)が正** とコメント修正（`--no-bindは全垢で不使用`）。理由: メトリックによりデフォルトルート=自宅有線のため、--no-bindだと自宅IPリークの恐れ。
- ライブ確認: 1085プロセス = `kensho_proxy.py --no-bind 192.168.128.183 1085`（現在は--no-bindで稼働中・出口IP 126.133.201.100でユニーク）。ただし今後のwatchdog再起動はbind方式(Tankan_HR01→192.168.128.183)で起動する。
- 本workerは .bat / wifi-watchdog.sh の --no-bind 追記を revert し、sibling方針（bind方式）に統一した。

### pytest結果
```
172 passed, 4 skipped in 44.61s
```
回帰なし。wifi-watchdog.sh は bash -n 構文OK。

### 提案45モニタリング（17:2X時点）
- 1085: **生存・egress OK**（126.133.201.100、出口IP全ユニーク 6/6）
- 15:31バッチ成功（F3/RT4 = 7件）→ 再コメントアウト基準(24h不通 or バッチ連続3回失敗)に**未到達** → コメントアウト保留・監視継続が正しい
- 16:00-16:45の「切断/再接続失敗」は旧povoアダプタへの誤接続試行が原因 → 本同期で解消される見込み
- 【要ユーザー対応】はキャンセル（ワイモバイルHR01へ切替済みのため、povo HR01電源確認は不要）
