# t_2e20f1ef — 収益ハンター品質ゲート実装（低シグナルShow HN一括投入防止 v58）

**実施日**: 2026-09-08 (JST)
**提案**: critic_proposal_2026-09-08-v58
**担当**: kensho-revenue-worker

## 変更内容

### 1. `kensho-non-api-revenue-hunter.py` — 品質ゲート本体
- `MIN_HN_SCORE = 3`: score < 3 の低シグナル案件をスキップ（要件1）
- `MONETIZATION_PATTERNS` + `has_monetization_signal()`: 本文/タイトルに
  有料/データ販売/API化/サブスク/ストア販売等の収益シグナルが無ければスキップ（要件1）
- `MAX_KANBAN_PER_RUN = 3`: 1実行の新規ready投入を3件にキャップ（要件2）
- `quality_gate(item, created_count)`: 3ゲートを単一関数で評価、スキップ理由を
  gate_stats（score_low / no_monetization / cap_reached）にカウントしレポートへ
- `create_kanban_task(..., hn_id=...)`: HN item_id 主キー dedup を追加（要件3）。
  `hnid-skip` として done/archived 含む全ステータスと照合（t_58335360 の
  all-status dedup guard の hunter 拡張）
- レポートに「品質ゲート (t_2e20f1ef v58)」セクション + ゲート別スキップ内訳を追加

### 2. `scripts/kanban_norm.py` — HN item_id dedup 基盤
- `extract_hn_item_id()`: `news.ycombinator.com/item?id=<digits>` 抽出
- `fetch_existing_hn_ids()`: kanban DB tasks.body 全文から hn_id→task_id マップ
  （既定 ALL_STATUSES = done/archived 含む）
- `is_duplicate_hn_id()`: (bool, existing_task_id) 判定

### 3. `tests/test_non_api_revenue_hunter_gate.py` — 回帰テスト19件（新規）
要件1（score/monetizationゲート）、要件2（投入キャップ）、要件3（hn_id dedup、
一時DBでの done/archived 照合を含む）を網羅。

## 既存 running 案件への影響

なし（提案リスク欄のとおり hunter 生成ロジックのみ変更。16:02一括投入分の
17案件はワーカー側で処理済み）。

## 検証結果

- ゲート単体テスト: 19 passed
- 全テストスイート: 462 passed, 5 skipped
- mypy --strict scripts/kanban_norm.py: 0 error
- 実HNフィード・ドライラン（subprocess.run / OUT_DIR をインターセプトしBoard
  へ一切書き込まない状態で main() を実行）:
  - GATE STATS: `{'no_monetization': 22, 'score_low': 4, 'PASS': 6}` — 26候補中
    26件中22件が収益シグナル無し、4件がscore<3でブロック
  - 通過した6件も全てhnid/title dedupで既存案件と衝突し create 0 件
    （16:02〜17:00の稼働で既に同種案件がBoard済み＝期待どおりの重複排除）
  - CAP OK: create試行 0 <= 3
- Board検証コマンド（カード本文記載）: `hunter_ready: 0` / hunter_running: 0 —
  健全状態に回復済み

## 成功指標のフォローアップ（変更後48h）

- ready増分 ≤3/日、in_progress ≤5、score<3 のhunter案件 = 0件
- 検証コマンドを次回 qa ループで再実行すること

## verification_evidence

```
$ python -m pytest tests/test_non_api_revenue_hunter_gate.py -q
============================= 19 passed in 15.23s ==============================
```

```
$ python -m pytest -q -p no:cacheprovider
================== 462 passed, 5 skipped in 327.39s (0:05:27) ==================
```

```
$ python -m mypy --strict scripts/kanban_norm.py
Success: no issues found in 1 source file
```

```
$ timeout 280 python .../workspaces/t_2e20f1ef/dryrun_gate.py
=== DRY RUN (rc=0) ===
GATE STATS: {'no_monetization': 22, 'PASS': 6, 'score_low': 4}
would-be kanban creates: 0
CAP OK: 0 <= 3
```

```
$ python .../workspaces/t_2e20f1ef/check_board.py
hunter tasks total: 214
hunter_ready: 0
hunter_running(in_progress): 0
```

ドライランスクリプトはワークスペースに保存:
/home/atushi/.hermes/kanban/boards/kensho-ai-team/workspaces/t_2e20f1ef/dryrun_gate.py
