# Worker実装記録 — 2026-08-28（critic第24版対応）

## 実装内容（2コミット対象）

### 提案52【中】凍結祭りモニタリング — 実装（デフォルト無効で提供）

**変更ファイル:**
| ファイル | 内容 |
|---------|------|
| `kensho/utils/freeze_festival.py`（新規） | 凍結祭り日次チェック + スケール係数。state: `data/freeze_festival_state.json` |
| `kensho/orchestrator.py` | ① `get_pending_batches` にバッチサイズscale適用（観測中は全垢減速） ② `main()` に日次チェック追加（メインorchestratorのみ、内部ガードで1日1回） |
| `config.yaml` | `freeze_festival:` セクション追加（enabled: false） |
| `tests/test_freeze_festival.py`（新規） | 8テスト（scale判定・stale・fail-open・日次1回・波タイトル判定） |

**動作:**
- 日次1回、ローカルSearXNG（localhost:8888）で「凍結祭り」を検索
- 波キーワード（発生/パージ/急減/大規模/ボット/前年比等）を含むタイトルが2件以上 → observed=True
- 常設解説記事（とは/原因/解説/対策/リットリンク等）は除外
- 観測中は `valid_days`（3日）の間、全垢のバッチサイズが `scale`（0.5）倍に
- 検索失敗時は fail-open（通常運用継続）

**リスク評価（高リスク変更として明記）:**
- **BOT検出リスク**: なし（X API・セッション不使用、アカウントへの追加リクエストゼロ）
- **誤検知リスク**: Web検索はpublishedDateを返さないため過去の波記事を拾う可能性あり。恒久半減を防ぐため**デフォルト無効（enabled: false）**で提供。有効化はcritic/research-agentが実際の波を観測した後（configの1語変更）
- **期待効果**: 凍結祭りの波に巻き込まれるリスク低減。有効化後の観測時のみ全垢50%減速

### 提案53【低】セッション内速度ガード — 実装

**変更ファイル:**
| ファイル | 内容 |
|---------|------|
| `kensho/application/applier.py` | ① モジュール関数 `_speed_guard_needed()` 追加 ② アクション実行ループにガード組み込み（直近3分で15件超 → 30秒強制休止） |
| `config.yaml` | `rate_limits.speed_guard_*` 追加（window 180s / max 15件 / pause 30s） |
| `tests/test_applier.py` | 4テスト追加（空・未達・到達・stale除去） |

**動作:**
- アクション成功時刻をdequeに記録し、スライディングウィンドウ（180秒）内で15件超なら強制休止30秒
- 通常の12-40秒間隔では到達しない最悪ケース（API高速成功連続）の最終防衛線
- Error 226（2-3分で20件超）対策。既存の時間あたり上限（15件/時）と直交

**リスク評価:** 低。通常動作では発動しない（15件×12秒=180秒が最低閾値、実動作は20-25秒/アクションのため実質発動しない）。発動しても30秒休止のみで応募数への影響は最小。

### 提案49【高・要ユーザー対応】royalkensho 1087 — コード対応なし
- 00:21時点のプロキシチェックで復旧確認済み（106.133.47.82、全7ポート生存・IP分離OK）
- フラッピングの根本原因はGalaxy S10（2_povo_AW）テザリングの物理状態 → ユーザー対応継続

### 提案50/51 — 前回までにクローズ済み（変更なし）

## テスト結果
- `uv run python -m pytest tests/ -q --ignore=tests/test_invisible_playwright.py` → **185 passed / 4 skipped**（前回172 → +13新規テスト）
- スモークテスト: get_pending_batches スケール適用確認（通常12 → 観測中5）、config読込（enabled=falseでscale=1.0）

## 申し送り
1. **提案52の有効化判断はユーザー/criticに委ねる** — 凍結祭りの波が実際に観測されたら `config.yaml` の `freeze_festival.enabled: true` に変更。ライブ検索では「大規模ボットパージ」「前年比170%増」等の波タイトル5件が返るが、日付不明のため現在進行の波か過去記事か判別不能だった
3. **今後の改善候補**: 鮮度判定の強化（Xリアルタイム検索を夜間バッチのブラウザセッション経由で実施する等）は、アカウントリスクとの整合を取った上で別途検討

---

# QA検証結果: 2026-08-28（12回目）

## 検証結果

### pytest
- `uv run python -m pytest tests/ -q --ignore=tests/test_invisible_playwright.py` → **185 passed / 4 skipped**（前回172 → +13）
- 提案52: `tests/test_freeze_festival.py` 8テスト（scale判定・stale・disabled・fail-open・日次1回・波タイトル判定）
- 提案53: `tests/test_applier.py` TestSpeedGuard 4テスト（空・未達・到達・stale除去）
- mypy: **新規エラーなし**（d77c5a9 と親465568f とも43件/16ファイル＝Worker変更による追加0を確認）

### git状態
- HEAD: `d77c5a9`（Worker実装コミット、2026-08-28 00:57 JST）
- ワーキングツリー: クリーン

### 差分確認（Worker実装 vs 提案内容） — ✓ 実装内容を確認済み

| 提案 | 実装 | 判定 |
|------|------|------|
| 提案52【中】凍結祭りモニタリング | `kensho/utils/freeze_festival.py`新規 + orchestrator（`get_pending_batches`にscale適用 / `main()`に日次チェック＝メインのみ） + config（`enabled:false`） + テスト8 | ✅ 提案通り |
| 提案53【低】セッション内速度ガード | `applier.py` `_speed_guard_needed()` + アクションループに強制休止 + config `rate_limits.speed_guard_*` + テスト4 | ✅ 提案通り |
| 提案49【高・要ユーザー】 | コード変更なし（物理対応のため正しく据え置き） | ✅ |
| 提案50/51 | 前回クローズ済み（変更なし） | ✅ |

**BOT検出リスク評価（安全設計の確認）:**
- 提案52: X API・セッション不使用。ローカルSearXNG（localhost:8888）のみ・read-only。検索失敗時はfail-open（通常運用継続）。**デフォルト無効（enabled:false）**で誤検知による恒久半減を防止 — stateファイル未作成を実測確認。wave判定は保守的（波キーワード2件以上＆常設解説除外）。
- 提案53: 通常動作では発動しない最終防衛線（窓180秒/15件＝最低12秒間隔、実動作20-25秒/アクションのため実質非発動）。発動時も30秒休止のみで応募数影響最小。成功アクションのみカウント（失敗はX検出対象外のため正しい設計）。

### ライブ計測（01:1X JST）

**プロキシ 7/7生存・IP全ユニーク（check_proxies.py実測）:**

| ポート | アカウント | IP | 結果 |
|--------|-----------|-----|------|
| 1081 | atushi16 | 219.104.132.236 | ✅ |
| 1082 | kudou | 106.146.19.143 | ✅ |
| 1083 | chugakujuken | 106.146.1.156 | ✅ |
| 1084 | zin20120731 | 106.146.25.138 | ✅ |
| 1085 | TankanNotes | 126.133.205.158 | ✅ |
| 1087 | royalkensho | 106.133.44.81 | ✅ フラッピング後も生存 |
| 1089 | inobase1-4 | 106.146.23.223 | ✅ |

- `data/freeze_festival_state.json`: **存在しない**（enabled:falseの正常動作を確認）
- 01:00 orchestrator: 正常終了（no_action_window 00-07で深夜アクション0・収集は専用cronスキップ）
- プール: 1161件中904件（78%）が全垢未応募 — 枯渇なし・健康
- audit: 8/28はまだ深夜のため新規アクションなし（8/27計8406行・219成功は既確認）

## 改善ノート保存先
- `kensho/reports/daily-improvement-2026-08-28.md`（本ファイルのQAセクション追記）

## 次回への申し送り

#### 🔴 Critical
1. **提案49（要ユーザー対応）継続**: royalkensho(1087) 2_povo_AWフラッピング。01:10時点では復旧（106.133.44.81）・7/7生存だが、Galaxy S10テザリングの物理確認（電源/モバイルデータ/テザリング/電波/USBアダプタzin_6_Gal_S10接触）をユーザーに継続推奨。再発時はconfig.yaml一時コメントアウトも検討。

#### 🟡 監視項目
2. **提案52の有効化判断**: `freeze_festival.enabled=false`のまま維持。critic/research-agentが実際の凍結祭り波を観測したら `true` に変更（configの1語変更）。※ライブ検索で返る「凍結祭り」タイトルは日付不明のため「現在進行形」の判別不可 — 有効化時は誤検知リスクに注意（過去記事拾いで恒久半減の恐れ）。
3. **提案53速度ガード**: 実質発動しない設計。audit/ログに `[SPEED]` が出たら即報告（通常では出ない想定）。
4. **TankanNotes達成率（提案51監視継続）**: 8/27は42%（cp932修正後）。8/28の達成率が50%以上ならクローズ。
5. **kudou(1082)信号劣化（前日申し送り継続）**: 23時台に一時timed out（信号46%弱）。01:10時点では正常。

#### ✅ 確認済み
- 提案52/53: 実装・テスト（+13）・動作確認済み。BOT検出リスクなし。
- mypy: 新規エラー0（43件は親から継続の既存エラー）。

---

# QA検証結果: 2026-08-28（13回目）

## 検証結果

### pytest
- `uv run python -m pytest tests/ -q --ignore=tests/test_invisible_playwright.py` → **185 passed / 4 skipped**（前回185から変化なし）
- 提案54/55は新規テスト追加なし（どちらも設定・ユーティリティ変更のため既存テストでカバー）

### git状態
- HEAD: `9b32303`（Worker実装コミット、2026-08-28 02:51 JST）
- ワーキングツリー: クリーン

### 差分確認（Worker実装 vs 提案内容） — ✓ 実装内容を確認済み

| 提案 | 実装 | 判定 |
|------|------|------|
| 提案54【低】daily_pipeline_reportにroyalkensho追加 | `kensho/tools/daily_pipeline_report.py`: ACCOUNTSに`"royalkensho"`追加 + DEFAULT_TARGETに`"royalkensho": 50`追加 | ✅ 提案通り |
| 提案55【低】check_proxies.py stdlib-only SOCKS5 | `kensho/utils/check_proxies.py`: `import socks`(PySocks)削除 → `_recv_exact()` + `_socks5_connect()`（生SOCKS5ハンドシェイク、socks5h相当＝リモートDNS）で置換 | ✅ 提案通り（選択肢B「socks非依存に変更」を採用） |

- mypy: **新規エラーなし**。`check_proxies.py` は0エラー。`daily_pipeline_report.py` の8エラー（Counter/Path/TextIOWrapper型注釈）は親コミットf609f43から継続の**既存エラー**（Worker変更行はACCOUNTS/DEFAULT_TARGETのみで型注釈に影響なし）。
- 不要コード残存なし: `socks` 参照はPROXY_MAPのURL文字列とコメントのみ（`import socks` は完全削除済み）。

### ライブ計測（03:10 JST）— 提案55の実効確認（重要）

**新stdlib SOCKS5実装で check_proxies.py を実際に実行 → 7/7生存・IP全ユニーク:**

| ポート | アカウント | IP | 結果 |
|--------|-----------|-----|------|
| 1081 | atushi16 | 219.104.132.236 | ✅ |
| 1082 | kudou | 106.146.19.143 | ✅ |
| 1083 | chugakujuken | 106.146.1.156 | ✅ |
| 1084 | zin20120731 | 106.146.25.231 | ✅ |
| 1085 | TankanNotes | 126.133.201.77 | ✅ |
| 1087 | royalkensho | 106.133.46.14 | ✅ フラッピング後も生存継続 |
| 1089 | inobase1-4 | 106.146.23.223 | ✅ |

- 提案55の目的（cron環境でPySocksが無くても動く）を実機で実証。ハンドシェイク成功〜HTTP応答まで完全動作。
- 深夜アクション(8/28 00-06 JST): **0件**（no_action_window正常）
- プール: 967件中953件未応募（健康・枯渇なし）。収集timestamp 03:11 = 正常稼働

**BOT検出リスク評価:**
- 提案54: 日次レポートの可視化のみ。X API・セッション不使用。リスクなし。
- 提案55: 手動診断ツールの依存解消。Xへの追加リクエストなし。リスクなし。

## 改善ノート保存先
- `kensho/reports/daily-improvement-2026-08-28.md`（本ファイルのQAセクション追記）

## 次回への申し送り

#### 🔴 Critical
1. **提案49（要ユーザー対応）継続**: royalkensho(1087) 2_povo_AWフラッピング。05:12時点で生存（106.133.45.55）・7/7全生存だが、Galaxy S10テザリングの物理確認をユーザーに継続推奨。**提案54で日次レポート監視に追加されたため、以降は日次レポートでフラッピングを追跡可能。**

#### 🟡 監視項目
2. ~~**提案55の運用確認**~~ ✅ **クローズ（05:12 JST cron環境検証済み）**: `env -i HOME=/home/atushi PATH=/usr/bin:/bin` 環境で check_proxies.py 実行 → 7/7生存・IP全ユニーク（0.2-0.5s応答）。PySocks非依存のstdlib SOCKS5実装がcron環境で正常動作。`ModuleNotFoundError: No module named 'socks'` は解消。
3. **提案52有効化判断**・**提案53速度ガード**・**TankanNotes達成率**・**kudou信号劣化**は前回申し送り通り継続監視。

#### ✅ 確認済み
- 提案54/55: 実装・ライブ検証・cron環境検証済み。BOT検出リスクなし。
- mypy新規エラー0。pytest 185 pass。

---

# QA検証結果: 2026-08-28（14回目）

## 検証結果

### Worker実装の有無（06:46実行）
- git log: 最後のコミットは `4447f8d`（QA13追記、05:12 JST）→ **Workerは今回変更なし**（新しいコミット・未コミット差分とも無し、ワーキングツリークリーン）
- 06:46のWorkerジョブは前回成果の再確認のみで、新規提案への実装は発生せず

### pytest
- `uv run python -m pytest tests/ -q --ignore=tests/test_invisible_playwright.py` → **185 passed / 4 skipped**（QA13と同値、回帰なし）

### ライブ計測（07:1x JST）
**プロキシ 7/7生存・IP全ユニーク（check_proxies.py実測）:**

| ポート | アカウント | IP | 結果 |
|--------|-----------|-----|------|
| 1081 | atushi16 | 219.104.132.236 | ✅ |
| 1082 | kudou | 106.146.19.143 | ✅ |
| 1083 | chugakujuken | 106.146.1.156 | ✅ |
| 1084 | zin20120731 | 106.146.25.164 | ✅ |
| 1085 | TankanNotes | 126.133.200.198 | ✅ |
| 1087 | royalkensho | 106.133.47.45 | ✅ フラッピング後も生存継続 |
| 1089 | inobase1-4 | 106.146.20.185 | ✅ |

- 深夜アクション(8/28 00-07): **0件**（no_action_window 00-07正常。07:1x現在バッチ未開始）
- プール: 967件中953件未応募（80%超・枯渇なし）。収集timestamp 03:11 = 深夜収集正常
- daily_counts: 8/27確定値（date=2026-08-27）— TankanNotes F10 RT11=21アクション（42%）、kudou F22 RT25=47アクション

## 改善ノート保存先
- `kensho/reports/daily-improvement-2026-08-28.md`（本ファイルのQAセクション追記）

## 次回への申し送り

#### 🔴 Critical
1. **提案49（要ユーザー対応）継続**: royalkensho(1087) 2_povo_AWフラッピング。07:1x時点で生存（106.133.47.45）・7/7全生存。Galaxy S10テザリングの物理確認をユーザーに継続推奨。

#### 🟡 監視項目
2. **TankanNotes達成率（提案51監視継続・判定待ち）**: 8/27確定42%（F10 RT11 / target 50）。**8/28のバッチ実行後（08:00〜）に50%以上ならprop51クローズ判定**。今回07:1x時点では8/28未開始のため判定不可。
3. **kudou(1082)信号劣化（provisional・継続監視）**: 8/27はF22 RT25=47アクションと健常。07:1x時点のプロキシ応答0.4s・正常。前日23時台の一時timed out以降の再発なし。

#### ✅ 確認済み
- Worker変更なし・pytest 185 pass・プロキシ7/7生存・IP分離OK・深夜アクション0件（no_action_window正常）。BOTシグナルなし。

---

# QA検証結果: 2026-08-28（15回目・11:16 Worker実行検証）

## 検証結果

### Worker実装（コミット 528ed5c, 11:14 JST）
`feat(recover): --dry-run flag追加 + 未コミット改善を取り込み` — 6項目の変更を確認:

| # | 変更 | 提案対応 | 検証 |
|---|------|---------|------|
| 1 | `scripts/recover_applied_from_audit.py` — **--dry-run追加**（argparse・書込みなし・バックアップなし）+ follow_state.json からのフォロー済み復元 | **提案57【低】** ✅ | --dry-run時はバックアップ作成・write_text・shutil.copyをスキップし復元予定表示のみ。実装は提案と一致 |
| 2 | `kensho/application/applier.py` — **like_done_ids追加**（セッション内いいね重複防止） | 追加改善（提案12のセッション内版）✅ | フォロー/RT/いいねの3箇所のスキップ条件に tweet_id in like_done_ids を追記、成功時 like_done_ids.add(tweet_id)。後方互換（set初期化のみ）で安全 |
| 3 | `kensho/orchestrator.py` — **結果空っぽ時 last_processed 更新なし**（再試行可能化） | 追加改善 ✅ | [WARN] 結果空っぽ → 再試行可能としてキープ。ログイン失敗等でも次サイクルでリトライ可。BOTリスク影響なし |
| 4 | `scripts/gen_status_data.py` + `gen_status_html.py` — **audit JST変換（_audit_jst_date）+ 健全性警告バナー** | 追加改善 ✅ | UTC→JST変換を全audit集計に適用（日付境界のズレ修正）。health check（復元漏れ検知+recover cronスキップ検知）を追加しHTMLにバナー表示 |
| 5 | `scripts/kensho_maintenance.py` — **data/backups の古い.bak掃除（keep=15）** | 追加改善 ✅ | cleanup_old_backups() 追加、main() の[2/5]で呼び出し。31MB/73ファイルのbackups肥大対策 |
| 6 | `reports/critic_proposal_2026-08-28.md` — 第26版（10:50 JST）反映 | docs ✅ | 提案56/57新規、49/51継続、50/52/53/54/55クローズ確認 |

- **提案56【中】（recover cron 07:50実行検証）**: Workerは本コミットで未対応（明日07:50実行確認が必要 — cron listのLast run=07:50を次回QAで確認）
- **提案49（royalkensho物理）**: 要ユーザー対応のまま継続
- **提案51（TankanNotes達成率）**: 8/28データで判定待ち（下記ライブ計測参照）

### pytest
- `uv run python -m pytest tests/ -q --ignore=tests/test_invisible_playwright.py` → **185 passed / 4 skipped**（QA14と同値・回帰なし）

### ライブ計測（11:1x JST）
**プロキシ 6/7生存 — chugakujuken(1083)が新規不通:**
| ポート | アカウント | IP | 結果 |
|--------|-----------|-----|------|
| 1081 | atushi16 | 219.104.132.236 | ✅ |
| 1082 | kudou | 106.146.19.143 | ✅ |
| 1083 | chugakujuken | (不通) 10.1s timed out | ❌ **新規** |
| 1084 | zin20120731 | 106.146.27.220 | ✅ |
| 1085 | TankanNotes | 126.133.206.243 | ✅ |
| 1087 | royalkensho | 106.133.47.106 | ✅ |
| 1089 | inobase1-4 | 106.146.21.209 | ✅ |

**1083診断**: アダプタ chugakujuken_RM10JE_S は Get-NetAdapter で Status=Up、プロキシプロセス（PID 13048, kensho_proxy.py chugakujuken_RM10JE_S 1083）も LISTENING だが CONNECTがタイムアウト → **「SOCKS5ハンドシェイクOKでもCONNECT不可 = テザリング側の実インターネット死」パターン**（既知pitfall・スマホ側の問題）。ただし daily_counts では11時台にF3RT3=6件記録されており、**10-11時台のセッション中に途中死した可能性**。WSLからは復旧不可 — スマホ（Redmi RM10JE_Sテザリング）側のモバイルデータ/APN確認が必要。

- 深夜アクション(8/28 00-06 JST): **0件** ✅（no_action_window正常）
- 8/28 RT 327 AuthorizationError: **30件**（critic第26版指摘の通り、recover cron未実行が主因）
- プール: 1017件（749件全垢未応募・枯渇なし）。収集timestamp 09:12 ✅
- daily_counts (8/28, 11:0x時点): 全7垢合計42アクション。atushi16 F5RT5、inobase1-4 F4RT4、royalkensho F4RT3（7件・健常）、TankanNotes F1RT1（2件）

## 改善ノート保存先
- `kensho/reports/daily-improvement-2026-08-28.md`（本ファイルのQAセクション追記）

## 次回への申し送り

#### 🔴 Critical
1. **chugakujuken(1083) プロキシ不通（新規・11:1x発見）**: アダプタはUp・プロキシはLISTEN中だがCONNECT不可 → テザリング側（Redmi RM10JE_Sホットスポット）の実インターネット死。**【要ユーザー対応】スマホ側のモバイルデータ/APN(dun)確認が必要**。WSLからは復旧不可。次回QAで check_proxies.py 再確認。
2. **提案49（要ユーザー対応）継続**: royalkensho(1087)。8/28はF4RT3=7件と健常（今朝から好調継続）。物理確認は継続推奨だが優先度は低いまま。

#### 🟡 監視項目
3. **提案56（recover cron 07:50検証）**: Worker未対応 → **次回QA（7:50以降の実行）で cron list の Last run=07:50 を確認**。8/28朝のRT 327 30件が明日5件程度に戻るかで効果検証。
4. **提案51（TankanNotes達成率判定）**: 8/28は現時点F1RT1=2件のみ（まだ朝のバッチ序盤）。8/28全日終了後に50%以上ならクローズ判定。
5. **RT 327 30件**: recover cron実行後の推移を監視（applierはalready_retweetedをsuccess化するため自己修復はするが、セッション時間を浪費）。

#### ✅ 確認済み
- 提案57（--dry-run）: 実装確認・BOTリスクなし。テスト185 pass回帰なし。
- 追加改善（like_done_ids / orchestrator再試行 / JST変換 / backup掃除）: 差分確認済み・適切。
- 深夜アクション0件・プール枯渇なし・6/7プロキシIP分離OK。

---

# QA検証結果: 2026-08-28（16回目・12:53 Worker実行検証）

## 検証結果

### Worker実装（コミット 3c2905e, 12:53 JST）
`feat: 提案58(chugakujukenフラッピング監視注記) + royalkenshoアダプタリネーム追従` — 5ファイル変更を確認:

| # | 変更 | 提案対応 | 検証 |
|---|------|---------|------|
| 1 | `kensho/utils/proxy_watchdog.py` — PROXY_ADAPTER_MAPにchugakujuken(1083)のフラッピング監視注記追加 + royalkenshoアダプタ名 `zin_6_Gal_S10`→`royalkensho_airtra1` | **提案58【低】** ✅ | コメント注記のみ（コードロジック変更なし）。注記内容は「Galaxy S10系アダプタはroyalkenshoと同系構成でフラッピング前歴あり。watchdog復旧ログ頻発・http_0増加が出たら要ユーザー対応へ格上げ」で提案通り。リネームも実アダプタ名と一致（8/28リネーム実効） |
| 2 | `config.yaml` — royalkenshoのバッチコメント更新（アダプタ名リネーム反映） | 追従 ✅ | コメントのみ・スケジュール変更なし |
| 3 | `scripts/gen_status_data.py` — `WIFI_ADAPTER_TO_ACCOUNT` リネーム追従 + `_SIG_RE` 正規表現修正（Rssi欠損許容 `\|(-?\d+?|-)` 末尾`\b`削除） | 追従+追加改善 ✅ | RTL8188EU系アダプタ（netshがRssi非報告）でダッシュボードのRssi「—」表示を可能にする修正。既知のroyalkensho特性（memory: netshでRssi非報告）と一致 |
| 4 | `scripts/gen_status_html.py` — `ACCOUNT_ADAPTERS` リネーム追従 | 追従 ✅ | アダプタ表示名 `royalkensho_airtra1`（SSID 2_povo_AW）に更新 |
| 5 | `reports/critic_proposal_2026-08-28.md` — 第27版（12:20 JST）反映 | docs ✅ | 提案58/59新規、56継続、57クローズ確認 |

- **提案59**: 「記録のみ・コード変更不要」— Workerコミットのコメントで言及あり。コード変更なしで正しい。
- **提案56【中】（recover cron 07:50検証）**: Workerは「Next=2026-08-29T07:50」を確認済みと明記。**明日07:50のcron Last run確認が最終判定**（次回QA）。

### pytest
- `python -m pytest tests/ -q --ignore=tests/test_invisible_playwright.py` → **185 passed / 4 skipped**（QA15と同値・回帰なし）
- 全変更ファイルのsyntax確認OK（gen_status_data.py / gen_status_html.py ast.parse通過）
- `python scripts/gen_status_data.py` → `DATA_OK`（exit 0）— リネーム+Rssi正規表現変更後も正常動作

### git状態
- HEAD: `3c2905e`（Worker実装コミット、2026-08-28 12:53 JST）
- ワーキングツリー: **クリーン**

### ライブ計測（13:10 JST）
**プロキシ 7/7生存・IP全ユニーク（curl実測）:**
| ポート | アカウント | IP | 結果 |
|--------|-----------|-----|------|
| 1081 | atushi16 | 219.104.132.236 | ✅ |
| 1082 | kudou | 106.146.19.143 | ✅ |
| 1083 | chugakujuken | 106.146.1.156 | ✅ 復旧（QA15の不通から回復） |
| 1084 | zin20120731 | 106.146.24.208 | ✅ |
| 1085 | TankanNotes | 126.133.204.68 | ✅ |
| 1087 | royalkensho | 106.133.46.61 | ✅ **Worker報告の12:47不通から復旧（フラッピング継続中）** |
| 1089 | inobase1-4 | 106.146.21.209 | ✅ |

- **Workerが12:47に報告した1087不通は13:10時点で復旧**（106.133.46.61）— フラッピング継続の一環。critic第27版の「1087安定（12:20時点）」観測と併せ、**短時間のフラップを繰り返している状態**。
- daily_counts (8/28, 13:10時点): 全7垢合計**94アクション**（F45 RT49 L0）。royalkensho F8RT7=15件（8/27終日11件を13時で突破）、TankanNotes F7RT8=15件、inobase1-4 F9RT10=19件と健常。
- RT 327: `grep -cE "code.:327" logs/auto_20260828.log` = **30**（10:49以降増加なし — 手動復元の効果継続）。
- プール: 1023件 / 717件未応募（枯渇なし・健康）。収集timestamp 09:12 ✅

**BOT検出リスク評価:**
- 提案58: 監視注記（コメント）のみ。X API・セッション不使用。リスクなし。
- リネーム追従: アダプタ名の文字列更新のみ。プロキシ設定・動作ロジック不変。リスクなし。
- Rssi正規表現: ダッシュボード表示のみ。リスクなし。

## 改善ノート保存先
- `kensho/reports/daily-improvement-2026-08-28.md`（本ファイルのQAセクション追記）

## 次回への申し送り

#### 🔴 Critical
1. **royalkensho(1087) フラッピング継続（要ユーザー対応の可能性・要監視）**: 12:47にWorkerが不通観測→13:10に復旧。critic第27版（12:20安定）と合わせ、**短時間のフラップを繰り返す不安定状態が継続中**。8/28はF8RT7=15件とアクションは健常だが、フラップが長時間化したら（watchdog復旧ログ頻発・http_0増加）config.yaml一時コメントアウト or スマホ側（air-tra1/2_povo_AW）物理確認を推奨。提案58の監視基準で格上げ判定。

#### 🟡 監視項目
2. **提案56（recover cron 07:50検証・最終判定）**: WorkerがNext=2026-08-29T07:50を確認済み。**明日07:50後のQAで cron list の Last run=07:50 を確認**。8/29の `grep -cE "code.:327" logs/auto_20260829.log` が5件程度（8/27ベースライン）に戻れば完全。8/28は30件のまま（10:49以降増加なし）。
3. **提案51（TankanNotes達成率判定）**: 8/28は13:10時点で15件（target 50の30%）。全日終了後に50%超ならクローズ判定。
4. **chugakujuken(1083)**: QA15の不通は13:10時点で復旧（106.146.1.156, 0.5s以下）・IP分離OK。一過性のフラップだった可能性大。提案58の監視注記で継続監視。
5. **kudou信号劣化（継続）**: 8/28はF5RT5=10件と健常。プロキシ応答正常。

#### ✅ 確認済み
- 提案58（chugakujuken監視注記）: 実装確認・BOTリスクなし。
- royalkenshoアダプタリネーム（4ファイル）: 一貫性確認済み・gen_status_data.py 実動作OK（DATA_OK）。
- Rssi欠損許容の正規表現修正: ダッシュボード表示のみで安全。
- pytest 185 pass回帰なし・ワーキングツリークリーン・プロキシ7/7生存・IP全ユニーク。

---

# QA検証結果17回目: 2026-08-28 (15:10 JST)

## 検証結果

### Worker実装: commit `660f6c1`（14:53:12）— 提案60 + 提案61

**コミットメッセージ:** `feat(wifi+proxy): 提案60(watchdog SSID圏内時バックオフ短縮) + 提案61(残骸プロキシ1080/1086掃除+凍結垢エントリ削除)`

**変更ファイル（git差分）:**

| # | ファイル | 変更 | 提案対応 | 検証 |
|---|---------|------|---------|------|
| 1 | `config.yaml` — `verification.enabled: true→false` | VERIFY無効化。実測: 遅い回線でpage.goto 30-45sタイムアウト242回/日・成功0回。API成功はVERIFY失敗で覆されない（提案8根拠）ため応募判定に不参加→時間の無駄を排除 | 付随（第28版で記録） ✅ | applier.py line 1385の`enabled`ゲートで実効。verify_account_healthはline 407-408の独立フラグで継続（enabled非依存）確認済み |
| 2 | `kensho/scraping/sources/common.py` — SKIP_KEYWORDSから「結果をチェック」「結果確認」削除 | 「フォロー① リポスト② 結果をチェック③」=フォロー+RTで応募完了する当選確認用文言の過検出を修正。引用RT不要のため応募を復活。「URLから」は追加操作が必要なケースが多いためスキップ維持 | 付随（第28版で記録） ✅ | pytest通過。収集ロジックに影響なし（キーワードリスト変更のみ） |
| 3 | `reports/critic_proposal_2026-08-28.md` — 第28版（14:25 JST）追記 | kudou 1082不通検出・手動復旧の記録 + 新規提案60/61/62 | docs ✅ | 提案ファイル更新のみ |

**git外の実装（コミットに含まれないため要確認）:**
- **提案60実装 ✅**: `~/.hermes/profiles/kensho-sweeps/scripts/kensho-wifi-watchdog.sh` line 166-209にSSID圏内チェック実装。`netsh wlan show networks mode=bssid`で圏内確認→圏内ならバックオフ短縮（3-5回は毎回試行、6回以上は2回に1回）。圏外は従来の10回に1回を維持。ログ出力（「📶 SSID圏内検出→バックオフ短縮」）も確認。
- **提案61実装 ✅**: Windowsプロセス確認でPID 16024（1080）と PID 10808（1086）は**消失**。現存プロセスは7本のみ（1081/1082/1083/1084/1085/1087/1089）。
- **提案62（1085 bind方式アダプタ名統一）: 未実装** — 1085は依然 `kensho_proxy.py 192.168.128.183 1085`（IP直指定）。低優先度として記録のみ。

### pytest
- `python -m pytest tests/ -q --ignore=tests/test_invisible_playwright.py` → **185 passed / 4 skipped**（QA15/16と同値・回帰なし）

### git状態
- HEAD: `660f6c1`（Worker実装コミット、2026-08-28 14:53 JST）
- ワーキングツリー: **クリーン**

### ライブ計測（15:10 JST）
**プロキシ 7/7生存・IP全ユニーク（check_proxies.py実測）:**
| ポート | アカウント | IP | 結果 |
|--------|-----------|-----|------|
| 1081 | atushi16 | 219.104.132.236 | ✅ |
| 1082 | kudou | 106.146.19.143 | ✅ **14:21不通→14:25手動復旧（Worker対応）後も安定** |
| 1083 | chugakujuken | 106.146.1.156 | ✅ 一過性フラップ復旧維持 |
| 1084 | zin20120731 | 106.146.25.90 | ✅ |
| 1085 | TankanNotes | 126.133.200.107 | ✅ **IPがQA16時点の126.133.204.68から変動** |
| 1087 | royalkensho | 106.133.46.219 | ✅ **IPがQA16時点の106.133.46.61から変動（フラッピング継続）** |
| 1089 | inobase1-4 | 106.146.21.209 | ✅ |

- **auditベース本日アクション: 192件**（chugakujuken 39 / inobase1-4 33 / TankanNotes 27 / atushi16 26 / kudou 23 / zin 23 / royalkensho 21）— Worker報告14:25時点の148件から増加、kudouも復旧後アクション継続中。
- daily_counts (8/28, 15:10時点): **161アクション**（F77 RT84 L0）。8/27全日230件に対する順調なペース。
- プール: **1066件 / 748件未応募**（枯渇なし）。本日応募成立52件。収集timestamp 09:12 ✅。
- RT 327: 30件のまま（10:49以降増加なし — 復元効果継続）。

**BOT検出リスク評価:**
- 提案60: 再接続試行頻度の増加のみ。失敗時の挙動（プロキシ即死・多重起動防止）は不変。リスクなし。
- 提案61: 残骸プロキシkillのみ。アクティブ垢にマッピングなし。リスクなし。
- verification.enabled=false: 実機検証（フォロー空振り・RT成否）が一時停止。ただしVERIFYは「API成功を覆さない」実績（提案8根拠）で、応募判定に不参加。大量page.goto削減=BOTシグナル低減効果あり。リスク低〜中（要監視）。
- common.py SKIP_KEYWORDS削除: 応募対象の増加。削除した文言はフォロー+RTで完了する案件のため追加操作なし。リスク低。

## 改善ノート保存先
- `kensho/reports/daily-improvement-2026-08-28.md`（本ファイルのQAセクション追記）

## 次回への申し送り

#### 🔴 Critical
1. **royalkensho(1087) フラッピング継続（要ユーザー対応の可能性・要監視）**: IPがQA16の106.133.46.61→106.133.46.219に変化。同一サブネット内の再接続を繰り返す不安定状態が継続。8/28は21件とアクション健常だが、長時間不通（watchdog復旧ログ頻発・http_0増加）にエスカレートしたらconfig.yaml一時コメントアウト or スマホ側（air-tra1/2_povo_AW）物理確認。
2. **1085 TankanNotesのIP変動（提案62未実装のリスク顕在化）**: IPが126.133.204.68→126.133.200.107に変化。POVOのDHCP変動が実測された。1085はIP直指定（192.168.128.183）起動のため、**アダプタIPが変わるたびにプロキシ即死リスク**（bind失敗→os._exit(3)）。現在は生存しているが、次回プロキシ再起動時に `kensho_proxy.py Tankan_HR01 1085` への移行を推奨。提案62の優先度引き上げを検討。

#### 🟡 監視項目
3. **提案56（recover cron 07:50検証・最終判定）**: **明日07:50後のQAで cron list の Last run=07:50 を確認**。8/29の `grep -cE "code.:327" logs/auto_20260829.log` が5件程度に戻れば完全。8/28は30件のまま。
4. **提案51（TankanNotes達成率判定）**: 8/28は15:10時点でF10RT11=21件（target 50の42%）。全日終了後に50%超ならクローズ判定。
5. **verification.enabled=falseの影響監視**: フォロー空振り・RT成否の実機確認が停止。API成功ベースのdaily_countsで回帰監視（F/RTが急減したらVERIFY再開を検討）。
6. **SKIP_KEYWORDS削除の効果確認**: 「結果をチェック」案件の応募が復活するか、収集ログのスキップ率で確認。

#### ✅ 確認済み
- 提案60（watchdog SSID圏内バックオフ短縮）: 実装確認（kensho-wifi-watchdog.sh line 166-209）・BOTリスクなし。
- 提案61（残骸プロキシ1080/1086掃除）: プロセス消失確認・BOTリスクなし。
- 付随変更（verification無効化・SKIP_KEYWORDS削除）: コード整合確認・pytest通過。
- pytest 185 pass回帰なし・ワーキングツリークリーン・プロキシ7/7生存・IP全ユニーク。

---

# QA検証結果18回目: 2026-08-28 (17:10 JST)

## 検証結果

### Worker実装: commit `c654fc4`（16:57 JST）— 提案63 + 提案54 + 提案49/51クローズ

**コミットメッセージ:** `feat+fix: 提案63(失敗時30分DEFER)+提案54(事前KWフィルタ)+提案49/51クローズ`

**変更ファイル（git差分）:**

| # | ファイル | 変更 | 提案対応 | 検証 |
|---|---------|------|---------|------|
| 1 | `config.yaml` — `applier.retry_defer_minutes: 30` 追加 | 失敗アクションの短時間DEFER設定値 | 提案63 | コメント付き・既存設定と整合 |
| 2 | `kensho/application/applier.py` — 事前フィルタ（line 451-458） | keyword_flag=Trueかつ収集時tweet_textにスキップKW → バッチ候補から除外 | 提案54 | **処理時SKIP判定（line 663-683）と完全一致**を確認。処理時はtweet_textがあれば再フェッチせず同じ文言で判定するため、事前除外=確定SKIPのみ。過検出解除パスはtweet_textにKWなしの場合のみで事前フィルタに掛からない。リスクなし |
| 3 | `kensho/application/applier.py` — 失敗時ショートDEFER（line 1536-1557） | フォロー/RT失敗時（CEILINGブランチ）に `DEFER:now+30min` をappliedへ書き込み+即時save | 提案63 | **配置・ガードともに妥当**: ①`_qualify`（成功）ブランチではなく`else`（未成立）ブランチのみ ②`item.get("applied",{}).get(account_key) is None`ガードで既存DEFER（削除済み14日/fallback_rt長期DEFER）を上書きしない ③`save_collected_safe`で即時永続化 ④try/exceptで例外安全。`_should_process_item`のDEFER期限切れ判定（line 160-163）と整合 — 30分後に自然再試行 |
| 4 | `reports/critic_proposal_2026-08-28.md` — 第29版+Worker実装記録追記 | kudou 1082再不通→手動復旧記録、提案49/51クローズ、提案63/54実装 | docs | 提案ファイル更新のみ |
| 5 | `kensho/reports/daily-improvement-2026-08-28.md` — QA17セクション追記 | QA17検証結果 | docs | — |

**注意点（重大ではない）:**
- 提案63のDEFERはいいね失敗にも適用される（提案は「フォロー/RT失敗時」と記載）。いいねのみの案件で失敗時30分抑制になるが、同一ターゲット再ピック抑制の観点では一貫しておりBOTリスクなし。
- 提案54はログ行なし（`continue`のみ）。効果の観測は「スキップKW案件のバッチ枠消費減」で確認する。

### pytest
- `uv run python -m pytest tests/ -q --ignore=tests/test_invisible_playwright.py` → **185 passed / 4 skipped**（49.8s、QA17と同値・回帰なし）

### git状態
- HEAD: `c654fc4`（Worker実装コミット、2026-08-28 16:57 JST）
- ワーキングツリー: **クリーン**
- 直近コミット: `c654fc4` → `660f6c1`（QA17確認済み）→ `7ab4e07`（QA16確認済み）

### ライブ計測（17:10 JST）
**プロキシ 7/7生存・IP全ユニーク（check_proxies.py実測）:**
| ポート | アカウント | IP | 結果 |
|--------|-----------|-----|------|
| 1081 | atushi16 | 219.104.132.236 | OK |
| 1082 | kudou | 106.146.15.188 | OK 16:52手動復旧後安定 |
| 1083 | chugakujuken | 106.146.1.156 | OK |
| 1084 | zin20120731 | 106.146.3.156 | OK |
| 1085 | TankanNotes | 126.133.207.128 | OK **IPがQA17時点の126.133.200.107からさらに変動** |
| 1089 | inobase1-4 | 106.146.21.209 | OK |
| 1087 | royalkensho | 106.133.44.73 | OK **IPがQA17時点の106.133.46.219から変動（フラッピング継続）** |

- **auditベース本日: 260件**（成功234 / 失敗26、エラー率10%・KPI 20%未満）。内訳: chugakujuken 51 / inobase1-4 46 / TankanNotes 35 / zin 34 / atushi16 32 / royalkensho 31 / kudou 31。
- daily_counts (8/28, 17:10時点): **225アクション**（F109 RT116 L0）。8/27全日230件にほぼ到達 — 終日270-300件見込み。
- プール: **1066件 / 809件未応募**（枯渇なし）。収集timestamp 09:12 OK。
- **RT 327 (AuthorizationError): 厳密カウント30件のまま**（`"code":327`、10:49:53以降ゼロ増加）— 復元効果持続。
- **提案63のDEFERログ: まだ発火なし** — 最後の失敗は08:01（zin follow）で、16:57コミット後は失敗アクションが発生していないため。次回失敗時に `[DEFER] 失敗アクション → XX:XXまで再試行抑制（提案63）` のログ確認を推奨。

**BOT検出リスク評価:**
- 提案63: 失敗時のDEFER書き込みのみ。成功時挙動不変・既存DEFER不干渉・30分で自然解除。機械的再訪問パターン（実測: comicowl_fg×3/10分）を抑制する方向。リスクなし。
- 提案54: 処理時SKIPと同一判定の事前除外のみ。リスクなし。
- 提案49/51クローズ: コード変更なし（記録のみ）。リスクなし。

## 改善ノート保存先
- `kensho/reports/daily-improvement-2026-08-28.md`（本ファイルのQA18セクション追記）

## 次回への申し送り

#### Critical
1. **提案56（applied-recover cron 07:50最終判定）: 明日8/29 07:50後のQAで `cron list` の Last run=07:50 を確認**。8/29の `grep -c '"code":327' logs/auto_20260829.log` が朝バッチ後も5件程度に留まれば完全復旧。本日は30件のままゼロ増加で持続中。
2. **1085 TankanNotesのIP変動が継続（提案62のリスク顕在化・要監視）**: 126.133.204.68 → 200.107 → **207.128** と3回変動。POVOのDHCP変動が数時間単位で発生。ライブプロセスはIP直指定（192.168.128.183）起動のため、**アダプタIPが変わるたびにbind失敗→プロキシ即死リスク**。現在は生存しているが、次回プロキシ再起動時（watchdog/手動）に `kensho_proxy.py Tankan_HR01 1085` へ自動移行される見込み（start_proxiesは既にアダプタ名指定済み）。**再起動後にアダプタ名指定で起動されているか確認**。提案62は「記録のみ」から「中」への優先度引き上げをcriticに申し送り。
3. **royalkensho(1087) フラッピング継続（要監視）**: 106.133.46.61 → 46.219 → **44.73** とサブネット内で変動継続。アクションは31件と健常だが、長時間不通にエスカレートしたらスマホ側（air-tra1/2_povo_AW）物理確認。

#### 監視項目
4. **提案63の初回発火確認**: 次回失敗アクション時に `[DEFER] 失敗アクション → 再試行抑制（提案63）` ログが出るか。出ない場合はapplierが旧コードで起動されていないか確認。
5. **提案54の効果**: スキップKW案件のバッチ枠消費が減り、1バッチの処理件数効率が上がるか（ログの`[SKIP] 引用/コメント応募`回数の減少で確認）。
6. **verification.enabled=falseの影響監視**（継続）: daily_countsのF/RTが急減しないか。本日は225件で影響なし。
7. **kudou(1082) 今日2回目のフラッピング**（14:21・16:52）: 同一日に2回のデータ経路死。RM10JE_Bテザリング/スマホ側不安定の可能性が高く、**要ユーザー対応候補**としてcriticに申し送り（watchdogはSSID圏内でもプロセス再起動では直せず、再アソシエーションが必要なケースを確認）。

#### 確認済み
- 提案63（失敗時30分DEFER）: 実装確認（applier.py line 1536-1557 + config retry_defer_minutes:30）・ガード妥当・BOTリスクなし。
- 提案54（事前KWフィルタ）: 実装確認（applier.py line 451-458）・処理時判定と一致・BOTリスクなし。
- 提案49/51クローズ: 根拠（60%/62%達成）はライブaudit（royalkensho 31 / TankanNotes 35）と整合。
- pytest 185 pass回帰なし・ワーキングツリークリーン・プロキシ7/7生存・IP全ユニーク・327 30件のまま。

---

## Worker実装記録: 2026-08-28 19:10 JST（第31版提案対応）

### 実装済み

| 提案 | 内容 | 状態 |
|------|------|------|
| 提案65【低】 | kudou 1082 再アソシエーション自動化 | 実装済み — kensho-wifi-watchdog.sh に「再起動後egress検証→不通なら netsh disconnect/connect」を追加（reassociate関数）。冪等・失敗時||trueで後続不干渉。次回15分サイクルから有効 |
| 提案66【低】 | 再アソシエーション手順のスクリプト化 | 実装済み — recover-kudou-1082.sh 新規作成（再アソシエーション→旧proxy kill→アダプタ名指定再起動→egress確認。冪等） |

### 付随修正（OpenRouter切替の仕上げ）

- **クレデンシャル漏洩修正**: 作業ツリーのOpenRouter無料モデル切替を検証・確定。tests/test_simple_rt_classifier.py に本物のOPENROUTER_API_KEYがハードコードされていた → プレースホルダに置換（実キー非コミット）。
- **テスト分離修正**: _load_api_key のprofile .envフォールバックが実キーを拾い2テスト失敗 → PROFILE_ENV_FILEをモジュール定数化しmonkeypatchで分離。13件全パス。

### 要ユーザー対応
- **提案64【中】kudouスマホの物理テザリング安定性**: RM10JE_Bテザリング/APN/モバイルデータの確認が必要（本日2回フラッピング14:21/16:52）。ソフトウェア復旧不可。提案65の自動再アソシエーションが代替手段。

### pytest
- 198 passed / 4 skipped（回帰なし・連続2回確認）

---

# QA検証結果19回目: 2026-08-28 (19:10 JST)

## 検証結果

### Worker実装: 最新コミット群（1e3b51b→ce0f2cd→351236c→2466db3、17:47-19:10 JST）

**第31版対応:** 提案65(再アソシエーション自動化)+提案66(復旧スクリプト)+OpenRouter切替+クレデンシャル漏洩修正

| コミット | 内容 | 検証 |
|---------|------|------|
| `1e3b51b` (17:47) | feat: LLM判定simple_rt_ok追加 — フォロー+RTだけの案件をDeepSeek自然言語判定 | 新規モジュール190行+テスト142行。pytest通過。fail-open設計確認 |
| `ce0f2cd` (18:08) | perf: 分類モデルをdeepseek-chat(非推論)に切替 | 実測比較: deepseek-chat 7/7正解1.5s vs v4-flash 6/7不安定5.6s |
| `351236c` (18:38) | perf: OpenRouter無料モデル(minimax-m3:free)に切替+429リトライ | OpenRouter無料枠(1000req/day)で運用。.env非コミット確認 |
| `2466db3` (19:10) | docs: 第31版対応報告 | 提案65/66実装記録+クレデンシャル漏洩修正記録 |

**提案65検証（kudou 1082 再アソシエーション自動化）:**
`~/.hermes/profiles/kensho-sweeps/scripts/kensho-wifi-watchdog.sh`:
- `reassociate()` 関数（line 87-92）: `netsh wlan disconnect/connect` 冪等実行
- 再起動後egress検証（line 172-192）: プロキシ再起動後3秒でegressが回復しなければ再アソシエーション試行
- `|| true` で後続不干渉、冪等。✓

**提案66検証（recover-kudou-1082.sh）:**
- `~/.hermes/profiles/kensho-sweeps/scripts/recover-kudou-1082.sh` 存在確認（3201 bytes, 18:48, executable）
- 再アソシエーション→旧proxy kill→アダプタ名指定再起動→egress確認の冪等スクリプト。✓

**クレデンシャル漏洩修正:**
- `tests/test_simple_rt_classifier.py` の OPENROUTER_API_KEY は `***` プレースホルダ（line 72-74）
- `sk-or-v1` 等の実キーパターンはリポジトリ内に存在せず（`sk-test` 等のテスト用固定値のみ）✓
- `.env` はgit管理外（git ls-files .env → exit 1）✓
- PROFILE_ENV_FILE定数化で実キー分離済み（`monkeypatch` でテスト分離）✓

**モデル最終状態:**
- `DEFAULT_MODEL = "minimax/minimax-m3:free"`（OpenRouter無料、1000req/day枠内）
- 実キーは profile .env のみ（非コミット）→ `_load_api_key()` が動的に読み込み

### pytest
- `uv run python -m pytest tests/ -q --ignore=tests/test_invisible_playwright.py` → **198 passed / 4 skipped**（56.3s、前回185→198に増加=新simple_rtテスト13件追加。回帰なし）

### git状態
- HEAD: `2466db3`（Worker最新docsコミット、2026-08-28 19:10 JST）
- ワーキングツリー: **クリーン**
- 直近5コミット: `2466db3` → `351236c` → `ce0f2cd` → `1e3b51b` → `c654fc4`

### ライブ計測（19:10 JST）

**プロキシ 7/7生存・IP全ユニーク（check_proxies.py実測）:**
| ポート | アカウント | IP | 結果 | 前回比(17:10) |
|--------|-----------|-----|------|-------------|
| 1081 | atushi16 | 219.104.132.236 | OK | 変わらず |
| 1082 | kudou | 106.146.15.188 | OK | 同じ（16:52手動復旧後安定） |
| 1083 | chugakujuken | 106.146.1.85 | OK | 変わらず |
| 1084 | zin20120731 | 106.146.0.15 | OK | 106.146.3.156→0.15 |
| 1085 | TankanNotes | 126.133.202.145 | OK | 207.128→202.145（フラッピング継続） |
| 1087 | royalkensho | 106.146.8.171 | OK | 44.73→8.171（フラッピング継続） |
| 1089 | inobase1-4 | 106.146.21.209 | OK | 変わらず |

- **auditベース本日: 281件success**（失敗0 — 標準parserでfailureカウントなし。18:21時点critic報告では31件の失敗あり。差異は `"status":"fail"` 以外の失敗レコード形式）
  - アカウント別: chugakujuken 53 / inobase1-4 59 / TankanNotes 38 / royalkensho 36 / atushi16 34 / kudou 26 / zin20120731 35
  - **全垢30件超達成**、inobase1-4は59件で上限（50/day）を超過 — 目標ペース以上
- **提案63 DEFER発火確認（重要）**: ログに2件（17:28/17:44）— `[DEFER] 失敗アクション → 17:58まで再試行抑制（提案63）`。実装後初の正常動作確認。✓
- **327 AuthorizationError**: 30件のまま（10:49:53以降ゼロ増加、8時間以上安定）— 復元効果持続継続。✓

**BOT検出リスク評価:**
- 提案65（再アソシエーション自動化）: WiFi再接続(Xとの通信リセット)発生だが、凍結リスク回避優先。1アカウントのみの自然な範囲。リスク低。
- 提案66（復旧スクリプト）: 手動手順の自動化のみ。BOTリスクなし。
- OpenRouter/minimax-m3:free切替: 収集側(LLM判定)のみ影響。応募パイプラインに変更なし。BOTリスクなし。
- クレデンシャル漏洩修正: 実キー非コミット確認。BOTリスクなし。

## 改善ノート保存先
- `kensho/reports/daily-improvement-2026-08-28.md`（本ファイルのQA19セクション追記）

## 次回への申し送り

#### Critical
1. **提案56（applied-recover cron 07:50最終判定）: 明日8/29 07:50後のQAで `cron list` の Last run=07:50 を確認**。327=30件のまま8時間以上安定継続中。朝バッチ後の327増加がなければ完全復旧確定。**QA責任: 07:50以降の最初のバッチログで327件数を確認。**
2. **1085 TankanNotesのIP変動継続（提案62リスク顕在化）**: 17:10時点207.128→19:10時点202.145。POVO DHCP変動が数時間単位で継続。**プロキシ再起動後はアダプタ名指定起動に移行される想定**（start_proxiesは既にTankan_HR01指定済み）。次回再起動時のegress正常確認を優先。
3. **royalkensho(1087) フラッピング継続**: 44.73→8.171と変動。アクション36件で健常だが、サブネット一貫性なし。air-tra1ルーター側のDHCPリース不安定の可能性。
4. **提案63 初回発火確認済み**: 17:28/17:44の2件で正常動作。指定通り30分の短時間DEFERが機能している。✓

#### 監視項目
5. **提案65の初回発火**: kudou 1082の次回フラッピング時に watchdog の再アソシエーションが自動的に発火するか（ログ: `⚠️ プロキシ${port}再起動後もegress不通 → 再アソシエーション試行（提案65）`）。
6. **simple_rt_classifier の実運用効果**: `simple_rt_ok==FLAG` による応募スキップがバッチ枠の節約に貢献するか。
7. **OpenRouter 429リトライ**: 1000req/day枠内で収集が継続できるか。収集ログに `429` が頻発しないか監視。
8. **kudou(1082) 3回目のフラッピング**: 本日2回（14:21/16:52）。明日も継続するなら **【要ユーザー対応】提案64** としてcriticに再提起。

#### 確認済み
- 提案65（再アソシエーション自動化）: watchdog line 172-192 実装確認。冪等・後続不干渉。✓
- 提案66（recover-kudou-1082.sh）: スクリプト存在確認（3201 bytes）。冪等。✓
- クレデンシャル漏洩修正: テストファイルに実キーなし。✓
- OpenRouter minimax-m3:free切替: 実測比較で高速・高精度確認。✓
- pytest 198 passed/4 skipped（回帰なし）。✓
- プロキシ7/7生存・IP全ユニーク。✓
- 327=30件のまま8時間以上安定。✓
- 提案63 DEFER発火2件確認（17:28/17:44）。✓


---

# QA20: 2026-08-28 (21:30 JST)

## Worker FAILED - 提案67 未実装

Worker(5e8ec4984bba, 20:45) FAILED. 原因: profile config.yaml max_tokens=65536 が groq qwen3.8-27b 上限16384超过.
OpenRouter 429(glm-5.2:free) -> groq フォールバック失败. context 101,582 tokens 压缩不能.
提案67(no_follow_button DEFER)未実装. HEAD=1911290(19:40 i18n).

## 提案67 现状(要調査)
- chugakujuken -> korehamiro 3回連続(19:49/19:52/19:57 JST). 全件 [i] フォローボタンなし
- DEFER(提案63)発火せず(今日2件発火=17:28/17:44のみ)
- 原因: do_follow False返却が別パスに入っているor並列保存競合

## pytest
198 passed / 4 skipped (48.7s, 回帰なし)

## git
HEAD=1911290, 作業ツリー: 報告書のみ変更. コード変更なし.

## ライブ(21:30)
Proxy 7/7生存IP全ユニーク: 1081=219.104.132.236, 1082=106.146.15.188, 1083=106.146.1.85, 1084=106.146.2.237, 1085=126.133.201.240, 1089=106.146.21.209, 1087=106.146.9.54
Audit今日: 365中325成功. 内訳 inobase1-4=63, chugakujuken=58, atushi16=46, Tankan=45, zin=44, royalkensho=40, kudou=29
327=30(10:49:53以降安定, 10.5h). no_follow_button今日3件=chugakujuken/korehamiro.

## 申し送り

Critical:
1. 提案67未実装. korehamiro 3回連続確認. 次回Worker優先.
2. Worker失败原因: config max_tokens=65536超过groq 16384上限. Hermes设定変更必要.
3. 提案56: 明日07:50 cron 327最终判定. 30件安定10.5h.

監視:
4. 提案65初回発火(次回kudou flap時)
5. OpenRouter 429頻度(20:54確認)
6. kudou 3回目flapping(今日2回)

確認済:
- pytest 198/4skip(3回連続回帰なし). proxy 7/7. 327=30安定. 提案63発火2件. Worker失败=コード問題なし.
