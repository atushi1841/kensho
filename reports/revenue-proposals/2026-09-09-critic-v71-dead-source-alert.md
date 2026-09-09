# critic v71: 収集ソースのサイレント死を自動検知（dead-source alert）

[status: open]
日付: 2026-09-09 12:3x（critic 4baf143523e0）
優先度: 高（自動復旧阻害+効率低下。判定基準②「自動復旧を阻害」= 死んだソースが誰にも検出されず2日以上放置）

## エビデンス（実測）
- `XClIdGen creation attempt 3/3 failed` → 「twscrape無効化」が **collect_20260907_110001.log 以降30ログ連続**（9/7 11:00〜、約50時間）。twscrape取得は全回0件。
- インストール済み twscrape 0.20.1 はPyPI最新（v0.20.1 2026-08-25リリース）→ アップグレードでは解決しない上流要因（X側JS変更）。graceful degradation（cp.meikan/kenshou.club代替）は設計通りだが、**代替に回った事実がどこにも記録されず、Kanbanにも提案にもならなかった**（観測ギャップ）。
- 付随: fixupx の dead URL `x.com/frontier_k/status/2094291340540399946` が毎収集で再試行→HTTP 404（9/9 5ログ+9/8にも同一、14+回連続）。ブラックリスト化されず無駄ループ。
- 比較健全なソース: kema は12:00収集で56件取得（v69 ke-ma.net統合は有効、 VERIFY項目クローズ）。

## 実装内容
1. `kensho_collect.py` 末尾（または backfill 同様 cronスクリプト）に dead-source チェックを追加：収集ログ/状態JSONでソース別取得件数+エラー種別を記録し、**同一ソースが12収集連続で0件（または同一例外の連続）なら、重複排除付きで `hermes kanban create` にタスク自動投入 + 収集ログに `[DEAD-SOURCE]` 明示**。
2. fixupx の永続404 URLは「失敗3回でブラックリスト」（data側キー）して毎回の再試行を止める。

## 成功指標（数値）
- twscrape相当の死活変化発生時、**24時間以内に dead-source タスクが1件生成**（重複は0件）
- frontier_k 404 の再試行回数が収集あたり **1→0**（ blacklist化後3収集ログで確認）
- 既存収集の rc は 0 を維持（アラート機能で収集自体は止めない）

## 検証コマンド
`bash -lc "cd /mnt/d/Project2/kensho && ls logs/collect_2026*.log | tail -3 | xargs grep -c 'DEAD-SOURCE'"` → 導入後、連続0件ソースがあれば ≥1 を返し、対応タスクが kanban list に存在すること。fixupx側は `grep -c frontier_k logs/collect_20260909_1[3-5]*.log` が 0。

## 失敗時の代替案
自動タスク投入がhermes CLI認証等で失敗するなら、`[DEAD-SOURCE]` をレポートログに残すだけでも可（critic側が毎tickでgrepして拾う運用に縮退）。

## ロールバック
git revert 1コミット（収集本体ロジックには触れない追加機能のみ）。
