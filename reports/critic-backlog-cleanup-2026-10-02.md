## バックログ整理レポート 2026-10-02

### 実測
- 実行前: done=796 / archived=99
- 実行後: done=707 / archived=188（net -89 done / +89 archived）
- Show HN 重複グループ: 30グループ → 0（全解消）

### 方法
- sqlite 直叩きで done 側の Show HN 重複タスクを特定
- 各グループで created_at 最新1件を残し、旧分を `hermes kanban --board kensho-ai-team archive <id>` で隔離
- バッチ: xargs -P 16 並列実行（1回目 11件/2回目 66件/3回目 12件、計89件完了）

### 根因
Hunter系（Show HN/Ask HN）タスクが同一タイトルで5回ずつ再生成され、done に蓄積。
収益化方針（[非API自動収益] プレフィックス）と不一致のため、done に残す価値なし。

### 次回への申し送り
- ready=0 のため新規提案禁止継続（backlog_reduction）
- 残る重複（Show HN 以外・全46グループ166行）は非 Show HN 系で、収益関連の可能性あり → 個別精査必要
