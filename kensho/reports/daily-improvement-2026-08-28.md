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
