# QA検証結果: 2026-08-29 (QA25 — 11:10)

## 検証結果

### 1. Worker実装確認（QA24からの変更）
- **HEAD**: 935037f (critic第37版 + アンカー更新, 10:33)
- **Workerコード変更**: 実装あり（QA24=59bd186から3コードコミット）
  - `83303eb` feat(applier): 応募成立=フォロー状態+いいね（ユーザー定義2026-08-29）
  - `53b34b1` feat(applier): フォロー+いいね伴走スキップ率を5%に低減（完了率向上）
  - `b1d9855` config: like_with_follow_rate→like_with_follow_skipに変更
  - `935037f` docs(report): critic第37版 + アンカー更新
- **変更内容検証**:
  - `_is_application_complete()` — 応募成立=フォロー状態+いいね（ユーザー定義通りの実装）
  - 既フォロー検出を先行判定（いいね伴走のため）
  - いいね伴走実行（フォロー+いいね95%実行、5%自然分散スキップ）
  - gen_status_data.py: 本日応募=いいね成功数（応募成立の最終アクション）
  - test追加: TestIsApplicationComplete 8ケース
- **ワーキングツリー**: クリーン ✅

### 2. pytest
- **211 passed, 4 skipped** ✅（前回203→+9、新テスト追加確認）

### 3. 新ロジック稼働確認（生ログ）
| ログメッセージ | 件数 | 意味 |
|--------------|------|------|
| フォロー+いいね実行（応募成立条件を満たす） | 17 | 新ロジック: フォロー実行+いいね伴走 |
| いいね: フォロー済み → いいねのみで応募成立 | 29 | 既フォロー検出→いいねのみで成立 |
| フォロー済みだが確率スキップ（自然分散） | 1 | 5%自然分散スキップ（BOT対策） |
| **audit today (UTC)**: follow 31, rt 27, like 14 | 72 | いいね14件（前日比増加傾向） |

### 4. プロキシ状態
| アカウント | プロキシ | IP | 結果 |
|-----------|---------|----|------|
| atushi16 | 1081 | 219.104.132.236 | ✅ 0.2s |
| kudou | 1082 | 106.146.15.188 | ✅ 0.3s |
| chugakujuken | 1083 | (不通) | ❌ SOCKS5 code=5（後述） |
| zin20120731 | 1084 | 106.146.3.140 | ✅ 0.3s |
| TankanNotes | 1085 | 126.133.204.84 | ✅ 0.2s |
| inobase1-4 | 1089 | 106.146.17.211 | ✅ 0.3s |
| royalkensho | 1087 | 106.146.10.139 | ✅ 0.3s |

**⚠ chugakujuken(1083) フラッピング**: チェック時点でSOCKS5 CONNECT失敗（code=5）。wifi_watchdogログでは10:50-10:55にegress OK（✅ 生存）確認済み。信号強度25-42%/-85〜-92dBm（弱い）。chugakujuken_RM10JE_Sはフラッピング中（wifi_watchdog自動復旧は機能）。daily_counts: F7 RT7（08:00+10:00バッチ適用済み）

### 5. BOTシグナル監視
- code 326/327: **0** ✅
- no_follow_button: **1**（朝バッチ1垢のみ、提案68効果確認済み: 前日14→1）
- 同一ツイート: 116件 — **全て正常な[SKIP]メッセージ**（多重防止の保護動作、実際の重複アクション0件）
- 深夜アクション: なし（no_action_window 00:00〜07:00）

### 6. パイプライン状態
- collected.json: 09:11更新済み ✅（1034件）
- daily_counts: 全垢動作中: chugakujuken F7 RT7 ♥2, atushi16 F12 RT12 ♥3, kudou F5 RT4 ♥0, TankanNotes F5 RT5 ♥4, inobase1-4 F5 RT4 ♥5, zin F0 RT1 ♥0
- **⚠ royalkensho: 今日0件**（daily_counts未登録、auditにも今日0件）
  - 09:46バッチ→10:45開始（1h遅延、anchor監視項目どおり）→0成功/1エラー（ログイン失敗）
  - 11:00リトライ中、応募成立確認（✅ ツイート正常）→ 12:20判定まで監視継続

## 改善ノート保存先
- `reports/daily-improvement-2026-08-29.md`（本ファイル）

## 次回への申し送り

### Critical（12:20判定への申し送り）
1. **75dac52（レート緩和）最終判定**: 12:20全垢バッチ後。基準（no_follow_button減少, フォロー12超/バッチ減少, code 326/327=0, 同一ツイート=0）は全クリア中。継続濃厚
2. **royalkensho 朝バッチ遅延**: 09:46→10:45開始（1h遅延確認済み）→初回0成功。11:00リトライ中。12:20までにdaily_countsに反映されるか要監視

### 監視継続
1. **chugakujuken(1083) フラッピング**: 信号25-42%/-85〜-92dBm。wifi_watchdog自動復旧は機能中。chugakujuken_RM10JE_Sの弱信号問題。必要なら物理確認（スマホ側）
2. **zin1084(air-tra1)**: 106.146.3.140で安定。F0 RT1（08:00バッチのみ）。11:03バッチは未確認
3. **新ロジック（応募成立=フォロー+いいね）効果**: いいね成功数が本日応募数の基準になる。12:20時点でのいいね件数とフォロー件数の比率（95%目標）を確認

---

# QA26 検証結果: 2026-08-29 13:10

## 検証結果

### 1. pytest
- **211 passed, 4 skipped**（53.76s）— 回帰なし（QA25と同数）

### 2. Workerコミット検証: 8cbc746（12:52, 提案76+78）
- **提案76（Error 226検知+自動一時停止）** — ✓ 実装内容を確認済み
  - `api_actions.py`: `_is_automation_block`（code 226+文言パターン） / `mark_automation_block`（15〜60分ランダム、tmp+os.replace原子書込） / `is_automation_blocked`（期限切れ自動クリア） / `get_automation_block_minutes` 追加
  - 検知組込: api_like（GraphQL 200-errors / GraphQL 403 / REST 403 の3点）、api_rt（2点）、api_follow_by_screen_name（2点）＝計7検知点
  - `applier.py`: ループ開始時に `is_automation_blocked` チェック → ブロック中は即打ち切り
  - 実装は提案内容と一致。検知→即停止→15〜60分待機の設計どおり
- **提案78（連座リスク棚卸し文書化）** — ✓ 実装内容を確認済み
  - `docs/ACCOUNT_LINKAGE_ANALYSIS.md`（122行）: 7垢のリンク要因表・atushi16分離戦略・凍結シナリオ損失限定・防御11項目・緊急時チェックリスト
  - 最重要リスク「同一WSLゲートウェイIP（172.26.80.1）」明記、ゲートウェイ分離が次の鍵

### 3. ライブ状態（13:10時点）
- **automation_block.json なし** = Error 226未発火（正常。検知機構は待機状態）
- **royalkensho: daily_counts反映確認** ✅ — F4 RT4 L7（hourly 11:9 / 12:6）。12:20判定項目クリア
- **L/F比率: 74%**（F66 / L49）— 12:20時点66%→上昇。目標95%未達のため22:30判定継続
- daily_counts: 全7垢動作中（chugakujuken F9 RT9 L3, atushi16 F13 RT15 L6, kudou F9 RT7 L2, TankanNotes F10 RT12 L12, inobase1-4 F12 RT12 L12, zin F9 RT10 L7）

## 改善ノート保存先
- `reports/daily-improvement-2026-08-29.md`（本ファイル・QA26追記）
- `reports/improvement-anchor.md`（outcomes/next steps 更新）

## 次回への申し送り

### Critical
1. **提案77（L/F比率）: 22:30終日判定** — 13:10時点74%（12:20時点66%から上昇）。atushi16(46%)/kudou(22%)が低い。22:30まで監視継続
2. **chugakujuken(1083) フラッピング継続監視** — アクションは正常（F9 RT9 L3）だが信号弱のため物理確認候補【要ユーザー対応候補】

### 監視継続
1. **提案76（Error 226）初発動の監視** — 検知機構は実装済・未発火。発動時は `data/automation_block.json` と audit error="automation_blocked" を確認
2. **zin1084(air-tra1)**: 本日F9 RT10 L7で活発。安定
3. **新ロジック効果**: L/F比率95%目標への追い込み状況を22:30判定に反映
