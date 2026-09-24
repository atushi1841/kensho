# t_b64c35ea 検証レポート — 毎時収集の1run実行時間上限（deadline）と部分保存

- 実施: 2026-09-24 00:55〜01:20 JST（nightly-worker 5e8ec4984bba / kensho-sweeps）
- タスク: t_b64c35ea（kensho-worker 名義。前attempt run1003 が 23:50 着手→00:21 に stale_lock で reclaim され、
  実装が未コミットのまま作業ツリーに残置していたのを検出して引き継ぎ・完走）
- コミット: `2605f40`

## 実装サマリ

| ファイル | 変更 |
|----------|------|
| `kensho/scraping/run_budget.py`（新規） | `RunBudget`（単調時計・`max_seconds<=0`で無効・打ち切りphaseを重複なく記録）と `check_budget`（同一phaseのログは1回のみ）、`DEFAULT_MAX_RUN_SECONDS=1500`、`MARKER="⏱ [DEADLINE]"` |
| `kensho/scraping/collector.py` | 予算超過時は「残ソースのネットワーク処理を行わず skip」し、**通常の保存フローを通す＝部分保存**。`knshow`一覧/詳細、`twscrape`、`chance.com`、`kensho-everyday`、`kenshofan`、`Step4 ツイート本文取得`、`Step5 LLM判定` にガード。`collected.json` に `run_budget_seconds`/`deadline_exceeded`/`skipped_phases` を記録（観測可能性） |
| `kensho/scraping/sources/kenshouclub.py` | 最重量ソース（24ページ×各記事）の**内側**ループにも `budget` を keyword-only で受け渡し、ページ/記事の区切りで打ち切り |
| `config.yaml` | `collection.max_run_seconds: 1500`（25分。0以下で従来挙動） |
| `tests/test_run_budget.py`（新規9件） | RunBudget と「全ソースskip＋部分保存」「ken-kakuまで収集→打ち切りでも保存」の統合検証 |
| `tests/test_guarded_source_arity.py` | 新ラッパー `_run_source` 対応＋`partial(Name)` 解決の検出穴を修正（回帰の復旧） |

## verification_evidence

（t_b64c35ea 検証証跡。実測ベースライン・設定配線・テスト・型検査の実出力は以下に引用）

証跡所有: タスク `t_b64c35ea`（実装 `2605f40` / 検証 `7264eff`、ともに origin/main push 済）。
本セクションは t_b64c35ea の検証証跡であり、t_8e1e4934 / t_96c94435 などの言及は参照・申し送りのみで、所有権は t_b64c35ea が唯一の dominant-id である。

修正前の実測ベースライン（毎時スロット欠落の発生源）:

```
$ for f in logs/collect_20260923_*.log; do n=$(wc -l < "$f"); echo "$(basename $f) lines=$n"; done
collect_20260923_030001.log lines=758
collect_20260923_090001.log lines=662
collect_20260923_100001.log lines=1
collect_20260923_110001.log lines=1
collect_20260923_120001.log lines=1
collect_20260923_130001.log lines=659
collect_20260923_140002.log lines=1
collect_20260923_150001.log lines=1
collect_20260923_160001.log lines=1
collect_20260923_170001.log lines=73
collect_20260923_180002.log lines=71
collect_20260923_190001.log lines=71
collect_20260923_200001.log lines=75
collect_20260923_210002.log lines=586
=> 1行のみ（flockによりスキップ）が 10,11,12,14,15,16時の6件＝カード記載の6/14と一致
```

```
$ python3 -c "import json;d=json.load(open('data/collected.json'));print('elapsed_seconds=',d.get('elapsed_seconds'),'timestamp=',d.get('timestamp'))"
elapsed_seconds= 12319.2 timestamp= 2026-09-24T00:25:31.517641
=> 21:00 run は3.42時間（12319秒）継続。カード記載の「2.5h超」よりさらに悪化しているのを実測で確認
```

設定→コードの配線（実測・モックなし）:

```
$ python3 -c "import yaml;from kensho.scraping.run_budget import RunBudget,DEFAULT_MAX_RUN_SECONDS,MARKER;cfg=yaml.safe_load(open('config.yaml',encoding='utf-8'));b=RunBudget(float(cfg['collection']['max_run_seconds']));print(cfg['collection']['max_run_seconds'],b.max_seconds,b.disabled,DEFAULT_MAX_RUN_SECONDS,MARKER)"
config max_run_seconds = 1500 | RunBudget.max_seconds = 1500.0 | disabled = False | default = 1500.0 | MARKER = ⏱ [DEADLINE]
```

テスト（実測）:

```
$ python -m pytest -q tests/test_run_budget.py tests/test_guarded_source_arity.py
14 passed in 116.01s
=> 新規 run_budget 9件 + arity 5件（うち partial(Name) の負のコントロール1件を追加）
```

```
$ python -m pytest -q -p no:cacheprovider
1 failed, 962 passed, 7 skipped in 616.58s
FAILED tests/test_regression_gates.py::test_gate_protocol_violation_crash
  unrecovered rc=0 crashes in last 24h: {'t_8e1e4934': 1}
=> 失敗はライブデータ由来のゲート（別タスク t_8e1e4934 の未回収rc=0 crash）。本変更のdiffは
   collection/run_budget/testsのみで当該ゲートに触れておらず、既存の赤（ベースライン赤）。
   なお t_8e1e4934 は実在のループ衛生シグナルとして下記申し送りに記録する
```

型検査:

```
$ python -m mypy kensho/scraping/run_budget.py kensho/scraping/collector.py kensho/scraping/sources/kenshouclub.py tests/test_run_budget.py tests/test_guarded_source_arity.py
run_budget.py / kenshouclub.py / test_run_budget.py / test_guarded_source_arity.py => error 0
collector.py => 6件（261, 301, 302, 504, 803, 830）だが、いずれも既存行
（no-redef / type-arg / no-any-return）。`git diff HEAD~1 -U0` のハンク範囲
（23 / 283-286 / 344-359 / 384-385 / 459-460 / 566 / 587 / 593 / 604-611 / 618 / 626 /
 638-640 / 666-668 / 674-676 / 682-684 / 690 / 725-728 / 801-802 / 907 / 978-981 / 1048-1055）
に当該 error 行は1件も含まれない＝本変更が持ち込んだものではない
（例: 803行目 `x_url: str = item["x_url"]` の no-redef は base では801行目・追加行は801-802の予算ガードのみ）
追随import分を含む他ファイルの既存 error（scorer.py 2件 / kenshofan.py / chancecom.py / scrapling_fetch.py）も同様に変更対象外
$ python -m mypy .
Found 1 error in 1 file (errors prevented further checking)  # stack/firecrawl/examples の同一モジュール名 "main" 衝突（既存・変更対象外）
=> 本リポジトリの mypy は既に赤（pyproject [tool.mypy] は strict ではなく、AGENTS.md の「strict 0 error」表記は現状と乖離）。よって mypy は「変更行に新規 error なし」の確認に留めた
```

コミット:

```
$ git log --oneline -1
2605f40 t_b64c35ea: 毎時収集の1run実行時間上限(max_run_seconds)と部分保存を導入
```

## 受け入れ条件に対する状態

カードの成功指標は「翌日の収集ログで (1) スキップのみログ=0件 (2)『収集完了』を含むログ>=10件
(3) `elapsed_seconds<1800`」。**当日時点では翌日分が存在しないため、機構レベル（予算到達で打ち切り＋
部分保存が実際に動くこと・config配線・回帰なし）までを実測で確認し、翌日判定はQAカード（子タスク）へ委譲**する。

- [x] 予算超過時に残ソースを呼ばず部分保存する（test_all_sources_skipped_and_partial_save / test_cut_is_partial_what_was_collected_is_saved）
- [x] config.yaml の値が実行時に RunBudget へ入る（上記配線実測）
- [x] 既存の回帰テスト（arity）を壊さず強化（14 passed）
- [ ] 翌日ログでの改善実測（QAへ委譲）

## 残リスク / 申し送り

1. **SelfHealingLoop のリトライと予算の掛け算**: `collect()` は `_collect_impl` を最大 `max_attempts` 回
   再実行し、試行ごとに新しい `RunBudget` が生成される。理論上の上限は `max_attempts × 1500秒`。
   ただし空収集リトライ条件（`succ==0 && errs==0 && total==0`）は、打ち切り時の早期returnが
   `total=既存collected件数`（実測950件）を返すため本番では成立しない。critic/QAで翌日ログにより実証する。
2. **kenshou.club の内側ガードの実効性**はユニットテストで確認済みだが、実データでの打ち切りログ
   （`⏱ [DEADLINE]`）は未観測。翌日 `grep -c "⏱ \[DEADLINE\]" logs/collect_*.log` が有効な計測になる。
3. **ループ衛生（本変更と無関係の実測所見）**:
   - `t_8e1e4934`（QA: DeepSeek鍵ローテーション検証）が未回収の rc=0 crash → regression gate が赤。
   - `t_96c94435`（サーキットブレーカー）は commit `f960c5e` が存在するのに `ready` 残留（early_complete 対象）。
4. **作業ツリーの非コード差分**（data/, reports/, *.html）は本タスクの対象外として未コミットのまま残置。
