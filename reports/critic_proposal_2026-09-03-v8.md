# Kensho Critic 改善提案 — 2026-09-03（第8回・16:30分析）

> 分析対象: 9/3 16:22時点 collected/audit/kensho-status.html 実データ + cron状態 + Kanban
> 結論: **懸賞パイプラインは正常稼働継続（BOT0・エラー率1.4%・全垢キャップ内・kudou復帰）。ただし applied復元漏れ警告が16:15時点でも残存（TankanNotes 11件）し、t_bdd9a0f5「日中定期復元」がcronに反映されていない疑い。**

## 6項目チェックリスト（16:22時点・実測）

| 監視項目 | 値 | 判定 |
|---------|-----|------|
| RT成功率 | 101成功/1失敗（rt_confirm_missing） | ✅ 99% |
| target=n/a消滅 | エラー4件中 n/a 起因なし | ✅ |
| 過フォロー・多重 | 全垢キャップ内（atushi16 85・zin 61・Tankan 78・kudou 38・chugaku 34） | ✅ |
| 過集中 | hourly全垢≤15（prop94有効） | ✅ |
| いいね比率 | 29〜37%（全垢適正帯） | ✅ |
| エラー率 | 4件/294件 = **1.36%**（目標20%未満） | ✅ |
| 応募稼働 | 5垢すべて本日成功アクションあり | ✅ kudou復帰 |

## 観測1（最重要）: applied復元漏れ警告が残存 — t_bdd9a0f5の実装がcron未反映の疑い

- **警告バナー（16:15）**: kensho-status.html に「applied復元漏れ: TankanNotes 11件 (audit成功済みなのにapplied=null)」が**まだ表示されている**。
- **t_bdd9a0f5はKanban done**（"applied recovery hourly"）だが、`hermes cron list` で kensho-daily-applied-recover のスケジュールは **`50 7 * * *`（07:50の1日1回）のまま**。hourly実行のcron/フックが存在しない。
- **実測**: `recover_applied_from_audit.py --dry-run` → 復元予定54エントリ。16:21時点のcollectedで TankanNotes None=802。→ 根本修正(7e07247, 15:13)デプロイ後も、既存汚染分が復元されず翌07:50まで放置される状態。
- **リスク**: 復元が1日1回のため、日中の再汚染は常に翌朝まで残る。警告バナー常時表示 + 翌日再ピックの潜在リスク。

## 観測2: kudou復帰・chugakujukenはエラー3件（一過性）

- kudou 1082: 本日38件成功（F12/R13/L13）。wifi_watchdog 16時台「接続済み 信号59%」「egress OK」→ **前回のoffline状態から復帰**。
- chugakujuken 1083: 34件成功だが no_follow_button×2 + no_like_button×1（12:26-12:31頃、一過性）。

## 新規提案

### 提案1【高優先】t_bdd9a0f5の実装差分確認と日中復元の有効化
- **根拠**: 警告が16:15時点で残存。cronスケジュールが07:50のまま = Kanban doneと実装が乖離している疑い。dry-runで54件復元可能を確認済み。
- **内容**: workerは t_bdd9a0f5 の実装内容（cron変更 or フック追加 or コード内定期化）を確認し、**実際に日中（例: 各正時+30分）の復元実行が動く状態**にする。動いていないなら cronジョブ追加（`kensho-daily-applied-recover` を `30 * * * *` 等に変更 or 新規hourlyジョブ）。
- **優先度**: 高（警告継続・再ピック潜在リスク）／ **危険度**: 低（既存スクリプトのスケジュール変更のみ・冪等性確認済み）

### 提案2【中優先】workerのreport未作成再発防止（QA申し送り反映）
- **根拠**: QA notepad「t_85d02fbf worker report未作成(再発2回目)」。プロセス欠陥が再発。
- **内容**: workerの実装完了条件に「reports/への検証記録作成」を明示追加。Kanbanコメントに reportパスを必ず記載。
- **優先度**: 中／ **危険度**: 低

### 提案3【低優先】kudou復帰の継続監視
- **根拠**: 本日38件成功・egress OKで復帰確認。ただし過去フラッピング実績あり。
- **内容**: 数日間の安定を確認するまで「復帰監視」継続。再び圏外になったら【要ユーザー対応】で報告。
- **優先度**: 低（監視継続）／ **危険度**: なし

## 監視継続
1. **applied復元漏れ**: 提案1の効果を次回確認（警告バナー消滅・TankanNotes None減少）。
2. **kudou/chugakujuken フラッピング**: 両垢とも本日は復帰・稼働。物理回線の安定性は継続監視。
3. **収益パイプライン**: QA監視の actors_public 乖離(22vs25)は収益側criticのスコープ。
4. **toushiwatch 1087 / inobase1-4 1089**: configコメントアウト継続（変更なし）。
