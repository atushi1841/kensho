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

---

# QA検証結果: 2026-08-29 15:10 (QA27)

## 検証結果

### 1. pytest
- **211 passed, 4 skipped** OK（QA26から回帰なし）

### 2. git状態・Workerコミット検証
- **HEAD**: d66c6b1 (docs anchor 提案79反映, 14:50)
- **QA26(13:10)以降のWorker変更**（5コミット）:
  | コミット | 内容 | 検証 |
  |---------|------|------|
  | `a3d5990` 14:08 | applier: フォロー+いいね時RTスキップ（BOTシグナル58件→0） | 注意: 後で2019715で巻き戻し |
  | `2019715` 14:19 | **巻き戻し**: RTスキップ削除。audit_bot_safety.pyの多重検出を「リプライ含むもののみ」に変更 | OK 妥当（フォロー/RT/いいね複合は当選条件充足の正常行動。ユーザー定義に整合） |
  | `5d8dd3d` 14:20 | .hermes.md 絶対ルール修正（複合アクション=正常行動） | OK 実態に整合 |
  | `dec356b` 14:32 | リプライ/返信要件ツイートを全てスキップ（ユーザー指示） | OK common.py 14語追加 + applier.py 常時フィルタ |
  | `1fec812` 14:49 | **提案79**: collector new_items_processed=全ソース合計 + new_items_by_source | OK 実装確認（下記3に問題） |
- **ワーキングツリー**: クリーン OK

### 3. 提案79の実装検証（重要）
- **collector.py 変更**: `new_items_processed = len(collected)`（全ソース合計）+ `new_items_by_source` 診断フィールド追加 — コードは正しい
- **ライブ確認**: 15:00収集ログ `collect_20260829_150001.log` で「Step 3 (knshow 0, ken-kaku 24, kenshou.club 231, cp.meikan 100, ke-ma 4, twscrape 0, chance.com 0, kensho-everyday 4, 計363件)」— **収集は正常動作を確認**（新規0件は誤診が正しかった）
- 赤 **問題発見**: バックアップ `collected.json.20260829_150824.bak` には `new_items: 363 / new_items_by_source: {...}` が記録されているのに、**現在の collected.json は `new_items_processed: 0 / new_items_by_source: None` に戻っている**。原因: applierの `save_collected_safe` がディスク再読込+マージ後に `data["collected"]=merged_items` を書き込むが、**data のメタフィールド（new_items_by_source等）は applier 側の古い in-memory data のままで上書き保存**されるため、collectorが書いた新フィールドが消える。→ 15:08:24以降の applier 保存（15:09-15:12 の多数）で上書きされた
- **影響**: 診断用メタフィールドが恒常的に消える。収集そのものは正常（バックアップに363件記録済み）。**コード修正はしない（QAは記録のみ）→ criticへ申し送り**

### 4. ライブ状態（15:10時点）
- **プロキシ: 7垢全て動作** OK — 1081=219.104.132.236 / 1082=106.146.15.188 / 1083=106.146.1.85 / 1084=106.146.2.109 / 1085=126.133.207.159 / 1089=106.146.16.128（IP分離OK）
- **L/F比率: 81.0%**（F100 / L81）— 13:10時点74%→14:20時点78.2%→**81%上昇**。目標95%未達、22:30判定へ
  - 低: chugakujuken(50%)/kudou(50%)/atushi16(68%) 高: royalkensho(171%)/TankanNotes(107%)/inobase1-4(94%)
- daily_counts: 全7垢アクションあり（chugakujuken F16RT16L8, zin F12RT13L10, atushi16 F19RT22L13, kudou F16RT14L8, TankanNotes F14RT16L15, inobase1-4 F16RT13L15, royalkensho F7RT4L12）
- automation_block.json: なし（提案76未発火=正常）

## 改善ノート保存先
- `reports/daily-improvement-2026-08-29.md`（本ファイル・QA27追記）
- `reports/improvement-anchor.md`（outcomes/next steps 更新）

## 次回への申し送り

### Critical
1. **提案79のメタフィールドがapplier保存で消える（新発見）** — collectorが `new_items_by_source` を書いても、applierの `save_collected_safe`（state.py）が古い in-memory data を保存するため上書き消滅。診断フィールドが機能しない。修正候補: `save_collected_safe` でメタフィールドをディスクから保持（`data` の該当キーが無い場合 `current` の値を使う）or collectorの保存を最後に行う
2. **提案77（L/F比率）: 22:30終日判定** — 15:10時点81%（上昇継続）。kudou(50%)/chugakujuken(50%)/atushi16(68%)が低く要因切り分け
3. **chugakujuken(1083) フラッピング継続監視** — 【要ユーザー対応候補】

### 監視継続
1. **提案76（Error 226）初発動の監視** — 未発火（正常）。発動時は `data/automation_block.json` 確認
2. **zin1084(air-tra1)**: 安定（106.146.2.109）
3. **リプライ/返信スキップ（dec356b）**: 収集17件が対象・うち6件は無駄応募済み。今後のSKIP増加を監視

---

# QA検証結果: 2026-08-29 (QA28 - 17:15)

## 検証結果

### 1. pytest
- **213 passed, 4 skipped** OK（前回211->+2 = 提案81のテスト2件追加、回帰なし）

### 2. Worker実装確認（提案81, 71c098c）
- **差分検証OK**: `kensho/application/state.py` の `save_collected_safe` に、マージ後に `new_items_processed / new_items_by_source / total_on_page / timestamp` をディスク current から補完するロジック追加（16:51コミット）。テスト `TestSaveCollectedSafeMeta` 2件追加。提案QA27の申し送りと一致する意図どおりの実装

### 3. ライブ計測（17:10）
- **L/F比率: 83.9%**（F118 / RT116 / L99、audit JST集計）: 15:10時点81%->83.9%上昇継続。低: chugakujuken(55.6%)/kudou(60%)/atushi16(72.7%)。高: royalkensho(155.6%)/inobase1-4(100%)/TankanNotes(105.9%)
- **proxy: 6/7垢OK** - **chugakujuken(1083)が不通**（SOCKS5 connect failed code=5）。15:10時点では動作していたが17:10で不通。フラッピング悪化の可能性【要ユーザー対応候補】
- **提案81の実環境効果: 未確定** - 17:10:07の収集保存では new_items_by_source=dict（433件）が書かれたが、17:11台の保存で None に戻ったケースあり。16:45起動の古いプロセス（kudouバッチ）が補完なしで上書きした可能性。次サイクル（全プロセス新コード化）後の再検証が必要
- daily_counts: 全7垢アクションあり・error=0・BOTシグナルなし
- automation_block.json: なし（提案76未発火=正常）

### 4. git状態
- HEAD: `4fefd9a`（docs anchor 提案81反映）/ 直前 `71c098c`（提案81実装）/ `d27f028`（QA27 report）
- ワーキングツリー: クリーン

## 改善ノート保存先
- `reports/daily-improvement-2026-08-29.md`（本ファイル・QA28追記）
- `reports/improvement-anchor.md`（outcomes/next steps 更新）

## 次回への申し送り

### Critical
1. **提案81（メタ永続化）: 実環境効果の再確認が必要** - コード実装は正しいが、17:11台の保存で new_items_by_source が None に戻るケースを確認（バックアップ171147=None, 171148=dict と混在）。16:45起動の古いコードプロセス（kudou）が補完なしで上書きした可能性が高い。**次サイクル（17:15以降・全プロセス新コード）で collected.json の new_items_by_source が残存するか再検証**。消える場合は並列プロセスの in-memory data 競合 or 補完コードの例外パスを疑う
2. **chugakujuken(1083): 17:10時点で不通**（SOCKS5 code=5、15:10は動作）: フラッピング悪化【要ユーザー対応候補】。wifi_watchdog の自動復旧を監視
3. **提案77（L/F比率）: 22:30終日判定** - 17:10時点83.9%（上昇継続、目標95%未達）。kudou(60%)/chugakujuken(55.6%)/atushi16(72.7%)が低く要因切り分け

### 監視継続
1. **提案76（Error 226）初発動の監視** - 未発火（正常）
2. **zin1084(air-tra1)**: 安定（106.146.29.40）
3. **提案79の残課題**: 提案81で解決予定。次サイクルで確認
