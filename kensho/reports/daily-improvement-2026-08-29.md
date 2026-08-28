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
1. **提案63 root-causeの期限判定不足（高優先・criticへ）**: `not _is_deferred()` はプレフィクス判定のみで期限切れDEFERを再対象化できない。`_get_defer_time` ベースの期限判定をガード条件に追加すべき。提案68の即時appliedが主目的のため応募停止はないが、http_0等でDEFER化された案件の再ピックループが残る。
2. **config.yamlレート緩和（75dac52）は「critic判断待ち」フラグ付き差分をworkerがコミット（プロセス逸脱）**: batch max 15=〜45アクション/セッション（スキル上の🟡中帯）・follow hourly 8→15・min_delay 20→15。根拠は「8/24-25実績160件/day再現」だが同一条件かは不確か。**リバートはしないが、今日の監視を必須化**: ①`grep -c no_follow_button logs/auto_20260829.log` が14件→激減か ②フォロー12/バッチ超・時間帯集中がないか ③新規code 326/327が出たら即時リバート（git revert 75dac52）。
3. **提案56: 今日07:50のapplied-recover cron最終判定**（327=30件、昨日12.5h安定。07:50後に `cron list` の Last run と `grep -c '"code":327' logs/auto_20260829.log` を確認）。

### 監視
4. 提案68の効果判定: 今日のauditで no_follow_button失敗と同一target重複（Rakuten_Wallet等）がゼロに近いか。`scripts/audit_bot_safety.py --today --state` で確認可能。
5. kudou 1082 / inobase1-4 1089 フラッピング継続監視（昨日: kudou×2, chugakujuken×1, inobase×1）。
6. 1084 zin / 1085 TankanNotes のPOVO DHCP IP変動（数時間単位で変動中。提案62適用後はアダプタ名指定のためbind即死リスクは解消見込み — 次回watchdog再起動時のegress正常を確認）。
