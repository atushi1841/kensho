# t_62e7242b 検証レポート — KPI方向性ルール（before/after 指標への 方向: up/down/equal 明記）

- タスク: t_62e7242b（board kensho-ai-team / assignee kensho-revenue-worker）
- 実装: `scripts/outcome_review_check.py`（`direction_label` / `format_outcome_entry` / `render_markdown` / `main`）
- テスト: `tests/test_outcome_review_check.py`
- 生成物: `reports/outcome-review-2026-09-24.md`
- コミット: `e515115`（t_62e7242b）
- push: 到達済み（`git rev-list --count origin/main..HEAD` = 0）

## 1. 課題（なぜ必要か）

`reports/outcome-review-2026-09-24.md` の after<before は「悪化」ではない。実測サンプル:

- 自己修復 attempts per failure 3→1（試行回数の down = 改善）
- exit_code 1→0（失敗コードの down = 改善）
- step1_elapsed_sec 345→47（所要秒数の down = 改善）

方向ラベルが無いと、レビュー側（critic / QA / 人間）が「after<before = 全件悪化疑い」と
誤読する。よって before/after を出すテンプレート側で **数値の上下を必ず明記**する。

## 2. 実装（t_62e7242b）

1. `direction_label(before, after)` — 数値のときだけ `方向: down|up|equal` を返す。
   良悪は判定しない（指標の意味に依存するため。例: 失敗回数の down は改善、未push残数の up は悪化）。
2. `format_outcome_entry()` — すべての before→after に方向ラベルを付与（= テンプレート強制）。
   数値でない before/after にはラベルを付けない（偽ラベルを作らない）。
3. `render_markdown()` — レポート本文の先頭に「KPI方向性ルール」1行を明文化
   （ラベルの読み方と、良悪が指標依存であることを本文に固定）。
4. `main()` — 生成レポート末尾に検証コマンド1行を埋め込む（critic v151 の「検証コマンド1行」要件と整合）。

なお run1049（同一カードの先行 attempt）は実装と再生成まで進めたが、完結呼出しなしで
protocol violation になった。run1055 が差分を検証し、明文化・検証コマンド行を追加して着地させた。

## 3. 成功指標（before → after 実測）

| 指標 | before | after | 備考 |
|---|---|---|---|
| outcome-review レポート内の `方向:` 行数 | 0（`ceccc50` 時点のレポート） | 33 | カード本文の成功指標は ≥5 |
| 方向ラベル付き KPI エントリ数 | 0 | 58（down 38 / up 15 / equal 5） | 全 before→after に付与 |
| `tests/test_outcome_review_check.py` passed | 12 | 13 | 明文化行の回帰テストを追加 |
| mypy（strict）エラー | 0 | 0 | 変更2ファイルで維持 |

## verification_evidence

### (1) t_62e7242b の受け入れ条件（カード本文の検証コマンド）

```
$ grep -c "方向:" reports/outcome-review-2026-09-24.md
33
```

### (2) 単体テスト（t_62e7242b の変更に対する回帰）

```
$ python -m pytest tests/test_outcome_review_check.py -q -p no:cacheprovider
13 passed, 1 skipped in 20.57s
```

### (3) 実レポート再生成（生成器が exit 0・再現）

```
$ python scripts/outcome_review_check.py --reports-dir reports --write-report
- `t_96c94435` bai全死シナリオ(5バッチ)での同一プロバイダ(bai)呼び出し総数 5→3 (方向: down)

- レポート保存: reports/outcome-review-2026-09-24.md
```

### (4) 型チェック（t_62e7242b の2ファイル）

```
$ python -m mypy scripts/outcome_review_check.py tests/test_outcome_review_check.py
Success: no issues found in 2 source files
```

### (5) 方向ラベルの内訳（t_62e7242b の生成物）

```
$ grep -o "方向: [a-z]*" reports/outcome-review-2026-09-24.md | sort | uniq -c
     38 方向: down
      5 方向: equal
     15 方向: up
```

### (6) 明文化行がレポート本文に存在

```
$ grep -n "KPI方向性ルール" reports/outcome-review-2026-09-24.md
6:- KPI方向性ルール: 各 before→after の末尾に `(方向: up/down/equal)` を明記する。 この語は数値の上下のみを表し、良悪は指標の意味に依存する（例: 失敗回数・試行回数・所要秒数の down は改善 / 未pushコミット残数の up は悪化）。
```

### (7) コミットと push（条件(e)）

```
$ git log --oneline -1 e515115
e515115 t_62e7242b: KPI方向性ルール(before/after に 方向: up/down/equal)をレポートテンプレートで強制＋明文化
$ git rev-list --count origin/main..HEAD
0
$ git merge-base --is-ancestor e515115 origin/main && echo "e515115 in origin/main: YES"
e515115 in origin/main: YES
```
