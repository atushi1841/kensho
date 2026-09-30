# t_c1889d30 検証レポート — easy_win_score（当選易度スコア）導入

- 日時: 2026-09-30 15:00 JST 前後
- ブランチ作業ツリー: `/mnt/d/Project2/kensho`（HEAD = 未コミットの WIP が多数混在。下記 baseline 比較で分離）
- 検証用 baseline worktree: `/tmp/kensho-baseline`（`git worktree add --detach /tmp/kensho-baseline HEAD`）

## 1. 実装内容（差分は本タスクのみ）

| ファイル | 変更 |
|---|---|
| `kensho/scraping/scorer.py` | `EASY_WIN_SCORE_KEY="easy_win_score"` / `compute_easy_win_score()`（winner_count と prize_score.priority の [0,1] 正規化を等ウェイト平均し 0-100）/ `attach_easy_win_scores()`（collector と backfill の共通付与ヘルパー） |
| `kensho/scraping/collector.py` | スナップショット枝（`_collect_impl` 内、save 直前）で `attach_easy_win_scores` を実行し全件に付与。**応募バッチ配分・応募ロジックには一切食い込まない表示専用のフィールド** |
| `kensho/scraping/pathway_classifier.py` | `build_non_x_report_md` に「当選易度 TOP50」セクション（表: 順位 / easy_win_score / 当選者数 / 賞品優先度 / 締切 / 導線 / X投稿URL + 計算不能件数）。`EASY_WIN_TOP_N=50` |
| `scripts/backfill_easy_win_score.py`（新規） | 既存スナップショットへのバックフィル + 非Xレポート再生成（`--dry-run` 対応） |
| `tests/test_easy_win_score.py`（新規） | 17 テスト（スコア計算・計算不能・TOP50・データ整合・付与ヘルパー冪等性） |

`git diff --stat`（本タスク分のみ）:

```
 kensho/scraping/collector.py          | 12 ++++-
 kensho/scraping/pathway_classifier.py | 85 ++++++++++++++++++++++++++++++-
 kensho/scraping/scorer.py             | 77 +++++++++++++++++++++++++++++
 3 files changed, 172 insertions(+), 2 deletions(-)
```

## verification_evidence

### (a) collected_today.json の各レコードに easy_win_score がある

```
$ cd /mnt/d/Project2/kensho
$ grep -o '"easy_win_score"' data/collected_today.json | wc -l
940
$ grep -c '"x_url"' data/collected_today.json
940
```

→ 940/940 レコードに付与。検証スクリプト `verify_data.py`（作業ツリー）の結果:

```
easy_win_score付き: 940 / 940 件
スコア付与前: keyなし 0 件, 残存 0 件
レコード数: 940 (付与前後で不変)
URL集合: 変化なし
TOP50セクション行数: 50 行, 実行可能 743 件, 計算不能 197 件
```

### (b) スコアが実際に計算されている（TOP50 が表示される）

バックフィル出力（2回実行 = 冪等性も確認）:

```
$ .venv/bin/python scripts/backfill_easy_win_score.py
--- collected_today.json バックフィル ---
対象件数: 940 / 付与済み: 0 件 → 置換後: 940 件
計算可能: 743 件, 計算不能: 197 件
TOP5: 71.6 (wc=110 ...) https://x.com/Muvluv_GG/status/2094737045457662099
...
--- レポート再生成 ---
reports/non_x_manual_20260930.md (8843 chars)
```

レポート抜粋（`reports/non_x_manual_20260930.md`）:

```
## 当選易度 TOP50（display・応募ロジックには不使用）

計算可能 743 件中、当選しやすい順 TOP50（当選者数 × 賞品優先度の等ウェイト正規化平均、0-100）。
計算不能 197 件（winner_count 欠落・0）はこの表から除外。

| 順位 | easy_win_score | 当選者数 | 賞品優先度 | 締切 | 導線 | X投稿URL |
|---|---|---|---|---|---|---|
| 1 | 71.6 | 110 | 2.5 | 2026-10-31 | X | https://x.com/Muvluv_GG/status/2094737045457662099 |
| 2 | 62.4 | 30 | 2.5 | 2026-09-30 | X | https://x.com/tochigimilk/status/2083357052366397744 |
| 3 | 61.4 | 26 | 2.5 | 2026-11-30 | X | https://x.com/niftyonsen/status/2094636302973256126 |
| 4 | 59.5 | 20 | 2.5 | 2026-11-04 | X | https://x.com/mysurance_cp/status/2085166464261132755 |
```

計算不能は別枠: `### 計算不能（winner_count 不明・0）197 件`。

### (c) バックフィルで件数・データ整合性が変わらない

`verify_data.py` の付与前/付与後比較: レコード数 940→940、URL 集合 identical、
付与されるのは `easy_win_score` キーのみ（他キーの増減 0）。

### (d) 収集が壊れていない（collector の差分が安全）

- 差分はスナップショット枝の 12 行のみ（save 直前に `attach_easy_win_scores` 1 呼び出し）。
- 本タスクの変更は collector の既存 WIP と別領域（hotspot コメント 1722 をタスクに記録）。
- 収集 cron: `0 3,9..21 * * *` → 15:00 実行後にデータの再検証（§4）。

### (e)(f) ruff / mypy / pytest の baseline 比較

**pytest**（全suite、`-q --no-cov -p no:randomly`）:

| ツリー | 結果 |
|---|---|
| 本タスク変更後 | `12 failed, 1267 passed` |
| baseline (`/tmp/kensho-baseline`, HEAD) | `18 failed, 1244 passed` |

本タスク領域のテストのみ:

```
$ .venv/bin/python -m pytest tests/test_easy_win_score.py tests/test_pathway_classifier.py tests/test_scorer_weights.py -q --no-cov -p no:randomly
49 passed in 3.47s
```

12 件の failed の帰属（本タスク非関連）:

- 10 件は clean HEAD baseline でも同様に失敗（既存失敗）:
  `test_anime*` (5), `test_devto_publish_guards.py::test_already_published`, `test_loop_health*` (2),
  `test_regression_gates.py::test_preexisting_skill_ratchet[skill-loop-health-skills-software-development-loop-engineering-skills-loop-health-sh]`, `test_zombie_watchdog.py::test_loop_health_triggers_after_persisted_streak`
- 2 件は **他タスクの未コミット WIP** が原因: `tests/test_simple_rt_classifier.py` (assert 2 失敗)。
  証拠: baseline worktree に作業ツリー側 `kensho/scraping/simple_rt_classifier.py` をコピーすると
  同じ 2 件が失敗し、`git checkout --` で HEAD 版に戻すと再び通過（本タスクは同ファイルに未着手）。
- baseline 側にのみ出る 8 件（`test_run_budget.py`×2, `test_twscrape*`×4, `test_kanban_crash_breaker.py`,
  `test_devto_live_profile_copy.py`）は worktree 環境の未追跡データ欠如によるもので、本タスク変更後ツリーには発生しない。

**ruff**（`ruff check --output-format=concise`、本タスクの5ファイル）:

```
kensho/scraping/pathway_classifier.py:190:35: UP034 Avoid extraneous parentheses  ← HEAD baseline に同一の既存違反
Found 1 error.
```

`scorer.py` / `backfill_easy_win_score.py` / `test_easy_win_score.py` は 0 エラー。
collector の 9 エラーは HEAD と同一セット（既存）。→ 新規違反 0。

**mypy**（`.venv` に mypy 未導入のため既存の `python3 -m mypy` (1.13.0) を使用、`--ignore-missing-imports`）:

```
current  : Found 51 errors in 9 files (checked 5 source files)
baseline : Found 51 errors in 9 files (checked 3 source files)
```

ファイル別内訳が両者で完全一致（collector 11 / scorer 2 / sources 38）。
`backfill_easy_win_score.py` と `test_easy_win_score.py` のエラーは 0 件。
→ mypy も新規エラー 0。

## 3. テスト追加

`tests/test_easy_win_score.py`（17 ケース）:

- スコア計算: 範囲 [0,100]、等ウェイト性（priority 固定で wc 単調増加 / wc 固定で priority 単調増加）、
  最小・最大、計算不能（欠落・0・非数値・負・NaN）→ 0.0
- データ: `collected_today.json` の全レコードに 0-100 のスコア、付与後もレコード数・URL 不変
- TOP50: 順位降順・50 行上限・計算不能の分離・見出しと列ヘッダ・付与前レコードの分離
- 付与ヘルパー: 全件インプレース付与・件数返却・冪等（再実行で値不変）
- `scripts/backfill_easy_win_score.py --dry-run`: 件数不変・スコア付与・TOP50 生成を実 subprocess で検証

## 5. 15:00 定時収集での実地確認（t_c1889d30）

cron `0 3,9..21 * * * kensho-collect-only.sh` の 15:00 実行（本タスクの collector 差分を経由）:

```
$ grep -c '"x_url"' data/collected_today.json
940
$ grep -o '"easy_win_score"' data/collected_today.json | wc -l
940
$ grep -c "## 当選易度 TOP50" reports/non_x_manual_20260930.md
1
```

収集ログ `logs/collect_20260930_150001.log`:

```
$ grep -inE "error|traceback|exception" logs/collect_20260930_150001.log | head -5
```

（上記 grep は 0 件 = エラー/トレースバックなし。ログ末尾）

```
完了: 75.0秒
  成功: 0件
  エラー: 0件
[導線] 非X手動レポート: /mnt/d/Project2/kensho/reports/non_x_manual_20260930.md
収集完了: 0成功/0エラー/29合計
```

- 収集成功・エラー 0、新規 29 URL は全て既存（重複）のためレコード数 940 のまま。
- 収集と同時に data/collected_today.json と reports/non_x_manual_20260930.md が
  15:01:20 に更新され、スナップショット全 940 件に easy_win_score が付与されたまま、
  レポートにも TOP50 セクション（`計算可能 743件 / 計算不能 197件`）が出力されている。
- ログ出力 `成功: 0件` は重複除外後の新規件数であり、収集処理自体は正常完了。

`## verification_evidence` の実測サマリー（t_c1889d30）:

- 受け入れ(a): 940/940 レコードに `easy_win_score`
- 受け入れ(b): TOP50 セクションが `reports/non_x_manual_20260930.md` に表示
- 受け入れ(c): レコード数・URL集合は付与前後で不変（verify_data.py）
- 受け入れ(d): 15:00 実収集でエラー 0、データ・レポート両方更新
- 受け入れ(e): ruff 新規違反 0（既存 1 件 UP034 のみ）、mypy 新規違反 0（51→51 同一）
- 受け入れ(f): 本タスク領域 49 passed / 全体失敗 12 件は全て既存・他タスク WIP 由来
