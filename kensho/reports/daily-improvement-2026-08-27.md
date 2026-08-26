# 日次改善ノート: 2026-08-27

## Critic分析（2026-08-27 00:45 実施）
- 提案24【高】keyword_flag過検出是正 — cpmeikan/kenkakuのHTMLコンテキスト誤判定（288件）をapplierでCDN tweet-text再判定により是正
- 提案25【中】成功計の計算基準変更 — auditベース259件が重複RT55件を含み水増し。実ユニーク約204件（daily_counts 113F+85RT+6L）
- 提案26【低】1084(zin)監視継続 — 8/26 22:20 WiFi切断、8/27 00:45時点35回連続失敗バックオフ中
- 提案27【低】keyword_flag実装効果の監視

## Worker実装（コミット済み）
| コミット | 内容 | 提案対応 |
|---------|------|---------|
| b70b5d4 (8/26 23:30) | keyword_flag実装: collector.py設定 + common.py _SKIP_KEYWORDS精緻化 + kenshouclub.pyコンテキスト判定化 + applierスキップ | 前日提案（引用RT/コメント除外） |
| f4c2ce1 (8/27 01:21) | 提案24: applier CDN再判定 + 提案25: action_history重複除外 | 24, 25 |
| 70f5174 (8/27 01:22) | 実装記録の報告追記 | — |

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
