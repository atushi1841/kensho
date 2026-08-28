# QA検証結果: 2026-08-29 (QA22, 01:10 JST)

## 検証結果

### Worker: 今週期は実装成功（01:03ジョブ）

Workerの01:03ジョブで4コミット追加（前回QA21検証の7711423に加え、新規3件）:

| コミット | 内容 | 検証 |
|---------|------|------|
| 7711423 (23:01) | 提案63 root-cause fix + 提案68 no_follow_button即時applied + 提案69 inobase1-4 flapping | ✅ QA21検証済・今回も差分再確認 |
| **75dac52 (23:32)** | **応募増量対応: config.yaml全垢 batch max 10-12→15、atushi16 10→12バッチ、max_actions_per_hour 15→25、min_delay 20→15、policy hourly follow 8→15/rt 12→20/like 20→30、skip確率半減** | ⚠️ QA21が「未コミット・critic判断要」とフラグした差分が**コミットされた** |
| b935a06 (00:59) | 提案62: proxy_watchdog が kensho_proxy.py へアダプタ名を渡す方式に変更（IP直指定→アダプタ名自動解決） | ✅ 妥当。`adapter`変数はスコープ内・IPv4待ちゲート(line 309)維持・全垢へ適用 |
| 188240c (01:02) | docs: 提案62実装記録 | ✅ |

### pytest
`198 passed / 4 skipped`（36.5s、回帰なし・worker主張と一致）

### git
- HEAD = 188240c
- 作業ツリー: `kensho/reports/daily-improvement-2026-08-28.md` の末尾空行削除のみ（trivial・復元済み）→ クリーン

### ライブ実測（01:1x JST）
- プロキシ **7/7生存・IP全ユニーク**: 1081=219.104.132.236, 1082=106.146.15.188, 1083=106.146.1.85, 1084=106.146.0.25, 1085=126.133.207.62, 1087=106.146.10.120, 1089=106.146.21.209
- audit 8/28 全日: 成功347 / 失敗28（no_follow_button=14, http_0=11, http_403=2, rt_confirm_missing=1）
- 8/28重複target（実装前baseline）: Rakuten_Wallet×7, steakgusto029×5, korehamiro×4, comicowl_fg×3 — **いずれも提案68の対象（廃棄失敗）**
- 8/29は深夜窓(00:00-07:00)のためバッチ未実行（audit 0件）→ 提案68の効果は**今日の朝バッチ以降で判定**

### 差分確認（提案との整合）

#### 提案68（高・no_follow_button再ピックループ解消）— ✅ 実装・主目的は達成
- `do_follow` 戻り値 `bool` → `(success, error_code)` タプル。呼び出しは applier.py:1197 の1箇所のみ（他はapi_actions経由）→ 影響範囲限定
- `_waste_failure_codes = {no_follow_button, follow_confirm_missing, policy_denied}` で即時applied付与
- 新規案件（applied=None）の初回廃棄失敗 → 即時applied → 再ピック停止。**観測された主要ループ（korehamiro×3 / Rakuten_Wallet×4 / steakgusto029×2）はこれで停止する** ✓

#### 提案63 root-cause修正（`not _is_deferred()`）— ⚠️ 意図通り機能していない（QA21懸念の具体化）
- `_is_deferred` はプレフィクス判定のみ（applier.py line 142-144）。**DEFER期限切れ文字列でも True を返す**
- ガード `_cur_applied_val is None or not _is_deferred(_cur_applied_val)` は期限切れDEFERで False → **期限切れDEFER案件には新DEFERも即時appliedも書かれない**
- 結果: 「DEFER期限切れ→再ピック→失敗→素通り→30分ごと再ピックループ」は**依然残る**（最初に一時的失敗http_0等でDEFER化された案件が対象。廃棄失敗での初回発生は提案68で停止するため実害は限定的）
- 修正案（critic向け・高優先）: ガード条件に `_get_defer_time` を使った期限切れ判定を追加（例: `_is_defer_expired = isinstance(v,str) and v.startswith(_DEFER_PREFIX) and (t:=_get_defer_time(v)) is not None and datetime.now() >= t` を `not _is_deferred(...)` の代わりに使用）

#### 提案69（inobase1-4 1089 flapping監視）— ✅ コメント追加のみ・実害なし
#### 提案62（proxy_watchdog adapter name bind）— ✅ 妥当

## 改善ノート保存先
`kensho/reports/daily-improvement-2026-08-29.md`（本ファイル）に保存

## 次回への申し送り

### Critical
1. ~~**提案63 root-causeの期限判定不足（高優先・criticへ）**~~ → **2026-08-29 03:00 Worker実装済み（f06a4dd）**: `_is_defer_expired()` を新設し、`_get_defer_time` で実際の期限を比較して期限切れDEFERのみ再DEFER/applied対象に。旧ガード `not _is_deferred()`（プレフィクス判定のみ）による「30分ごと再ピックループ」を解消。naive/aware datetime両対応。pytest 203 passed（新規5件）/ mypy新規エラー0。**QA22の検証ポイント: 残存DEFERループの有無を次回監査で確認。**
2. **config.yamlレート緩和（75dac52）は「critic判断待ち」フラグ付き差分をworkerがコミット（プロセス逸脱）**: batch max 15=〜45アクション/セッション（スキル上の🟡中帯）・follow hourly 8→15・min_delay 20→15。根拠は「8/24-25実績160件/day再現」だが同一条件かは不確か。**リバートはしないが、今日の監視を必須化**: ①`grep -c no_follow_button logs/auto_20260829.log` が14件→激減か ②フォロー12/バッチ超・時間帯集中がないか ③新規code 326/327が出たら即時リバート（git revert 75dac52）。
3. **提案56: 今日07:50のapplied-recover cron最終判定**（327=30件、昨日12.5h安定。07:50後に `cron list` の Last run と `grep -c '"code":327' logs/auto_20260829.log` を確認）。

### 監視
4. 提案68の効果判定: 今日のauditで no_follow_button失敗と同一target重複（Rakuten_Wallet等）がゼロに近いか。`scripts/audit_bot_safety.py --today --state` で確認可能。
5. kudou 1082 / inobase1-4 1089 フラッピング継続監視（昨日: kudou×2, chugakujuken×1, inobase×1）。
6. 1084 zin / 1085 TankanNotes のPOVO DHCP IP変動（数時間単位で変動中。提案62適用後はアダプタ名指定のためbind即死リスクは解消見込み — 次回watchdog再起動時のegress正常を確認）。

---

# QA検証結果: 2026-08-29 (QA23, 03:2x JST)

## 検証結果

### Worker: 今週期（03:04ジョブ）は提案63 root-cause fixを実装

| コミット | 内容 | 検証 |
|---------|------|------|
| **f06a4dd (03:02)** | **提案63 root-cause: `_is_defer_expired()` 新設し期限切れDEFERのみ再DEFER/applied対象に + テスト5件** | ✅ 下記詳細 |
| 86aa98f (03:0x) | docs: 提案63実装記録を申し送りに反映 | ✅ |

### pytest
`203 passed / 4 skipped`（44.25s、回帰なし・worker主張と一致。前回QA22の198から+5 = 新規 `TestIsDeferExpired` 5件が反映）

### git
- HEAD = 86aa98f（f06a4dd + docs）
- 作業ツリー: クリーン

### ライブ実測（03:2x JST）
- プロキシ **7/7生存・IP全ユニーク**: 1081=219.104.132.236, 1082=106.146.15.188, 1083=106.146.1.85, 1084=106.146.3.60, 1085=126.133.200.147, 1087=106.146.9.32, 1089=106.146.21.209
- 8/29は深夜窓(00:00-07:00)のためバッチ未実行 → audit 0件・深夜アクション0・code 326/327 0件（BOTシグナルなし）

### 差分確認（f06a4dd、QA22の修正案との一致検証）

✅ **QA22が「高優先・criticへ」と申し送った修正案をそのまま実装**（QA22申し送り#1のクローズ）
- 追加された `_is_defer_expired(val)`:
  - `not isinstance(val, str)` or プレフィクス不一致 → False（None・通常applied日時・パース不能DEFERは安全側）
  - `_get_defer_time` で実際の期限を比較（naive/aware datetime両対応 — テストで `datetime.now(_dt.UTC)` 使用、実運用の `datetime.now().isoformat()` naiveも `t.tzinfo=None → datetime.now()` で整合）
  - 5テスト: None / 通常applied / 有効期限内DEFER(False) / 期限切れDEFER(True) / パース不能(False)
- ガード変更（apply_for_account）: `_cur_applied_val is None or not _is_deferred(...)` → `_cur_applied_val is None or _is_defer_expired(_cur_applied_val)` — **有効期限内DEFER・通常appliedは素通り、期限切れDEFERのみ再処理**。`_should_process_item`（line 174-183）の期限判定と整合する。QA22が特定した「期限切れDEFER→再ピック→失敗→素通り→30分ごと再ピックループ」の根因を解消。✓
- 副作用なし: 差分はapplier.pyのガード1箇所+ログ整形（文意不変）+新規テストのみ。config.yaml・browser.py等に触れていない。

⚠️ 補足: 提案68（no_follow_button即時applied）が主目的のため、本fix単独では「応募数」に顕著な変化は見込めない。効果の実測は**今日の朝バッチ以降のaudit**で判定（残存DEFERループ=同一target失敗多発が消えたか）。

## 改善ノート保存先
`kensho/reports/daily-improvement-2026-08-29.md`（本ファイル、QA22に追記）に保存

## 次回への申し送り

### Critical
1. ~~**提案63 root-causeの期限判定不足**~~ → **QA23でクローズ（f06a4dd実装・検証済み・pytest 203）**。残存DEFERループの有無は今日のaudit（同一target失敗多発）で最終確認。
2. **config.yamlレート緩和（75dac52）監視継続（QA22から引き継ぎ）**: batch max 15=〜45アクション/セッション・follow hourly 15・min_delay 15。**今日の監視必須**: ①`grep -c no_follow_button logs/auto_20260829.log` が14件→激減か ②フォロー12/バッチ超・時間帯集中がないか ③新規code 326/327が出たら即時リバート（git revert 75dac52）。
3. **提案56: 今日07:50のapplied-recover cron最終判定**（327=30件。07:50後に `cron list` の Last run と `grep -c '"code":327' logs/auto_20260829.log` を確認）。
4. **criticジョブが02:33にFAIL**（worker申し送り）。次のcritic正常実行時に提案63 root-cause fixの検証結果を反映すること。

### 監視
5. 提案68の効果判定: 今日のauditで no_follow_button失敗と同一target重複（Rakuten_Wallet等）がゼロに近いか。`scripts/audit_bot_safety.py --today --state` で確認可能。
6. kudou 1082 / inobase1-4 1089 フラッピング継続監視。
7. 1084 zin / 1085 TankanNotes のPOVO DHCP IP変動 — 本QA23実測でも変動継続（zin: 0.25→3.60、Tankan: 207.62→200.147）。**提案62（アダプタ名bind）適用後はIP変動でプロキシ即死しないはず** — 次回watchdog再起動後のegress正常を確認。
