# t_fda64102 検証レポート: Apify pricing部分取得による誤free判定と24hキャッシュ縮小の修正

- タスク: t_fda64102（assignee: kensho-revenue-worker）
- 実施: 2026-09-25（JST）
- コミット: 108aba9（origin/main へ push 済み）
- 変更ファイル: `scripts/kensho_revenue_collect.py` / `tests/test_revenue_collect.py`
- ロールバック: `git revert 108aba9`（外部設定の変更なし）

## t_fda64102 での変更内容

1. `collect_apify()` の課金判定分岐を3段化（部分取得を free と断定しない）
   - API取得成功分 → 従来どおり ppe / free
   - API部分取得で欠落したアクター → 24h以内キャッシュに既知エントリがあれば第2ソースとして採用
   - それでも不明 → `unknown`（`pay_per_event.json` に載る場合のみ ppe として救済）
2. `_save_pricing_cache()` をマージ保存化
   - 24h以内の既存エントリを保持してマージし、`fetched` / `merged_from_cache` を記録
   - 部分取得（25件中1件のみ等）でキャッシュが縮み、誤判定が丸1日継続する事故を防止
3. `tests/test_revenue_collect.py` に t_fda64102 用テスト4件を追加
   - 部分取得→unknown / キャッシュ第2ソース / マージ保持 / 24h超はマージしない

## verification_evidence

実APIトークンありの実測（2026-09-25 02:51 JST）:

```
$ cd /mnt/d/Project2/kensho && python3 -m pytest tests/test_revenue_collect.py -q --no-cov
63 passed in 6.12s
$ python3 -c "import sys,json;sys.path.insert(0,'scripts');import kensho_revenue_collect as krc;r=krc.fetch_apify_pricing();print('fetched_api=',len([k for k in r if not k.startswith('_')]));d=json.load(open('data/apify_pricing_cache.json'));print('cache=',len(d['pricing']),'fetched=',d.get('fetched'),'merged_from_cache=',d.get('merged_from_cache'))"
fetched_api= 25
cache= 25 fetched= 25 merged_from_cache= 0
$ python3 -c "import sys;sys.path.insert(0,'scripts');import kensho_revenue_collect as krc;res=krc.collect_apify();print({k:res.get(k) for k in ('date','actors_total','actors_ppe','actors_free','actors_unknown','actors_public')})"
{'date': '2026-09-24', 'actors_total': 25, 'actors_ppe': 25, 'actors_free': 0, 'actors_unknown': 0, 'actors_public': 25}
$ git log --oneline -1
108aba9 fix(revenue): t_fda64102 Apify pricing部分取得でfree誤判定/キャッシュ縮小を修正
$ git status --porcelain | grep -E '\.(py|yaml|sh|js)$'
（出力なし = コード未コミットなし）
```

before/after（実測値の比較）:
- 劣化キャッシュ件数: before=1 → after=25（`saved_at 02:15:56` の旧コード部分保存を t_fda64102 の修正で復旧）
- actors_free（9/19の誤報告）: before=20 → after=0（本日API 25/25 成功を正しく反映）
- テスト件数: before=59 → after=63（t_fda64102 で4件追加）

## 検証上の注意（判定の限界）

- 「部分取得時に unknown になる」挙動は実APIでは再現不能（本日は25/25完全成功）のため、`tests/test_revenue_collect.py::TestTfda64102PartialPricing` の偽APIレスポンス注入で検証した（実測: 63 passed）。
- 実機で確認できたのは「完全成功時の free/unknown 増殖なし」＋「キャッシュが25件に復旧し fetched/merged_from_cache を記録」まで。

## 副次対応（衛生・同一キャッシュ汚染の遮断）

- プロファイル側の旧コピー `~/.hermes/profiles/kensho-sweeps/scripts/kensho_revenue_collect.py`（9/11版・56456B、同じ `data/apify_pricing_cache.json` を書く二重ソース）を退避し、リポジトリ実体への symlink に置換（`...py.bak-20260925-precsymlink` として保全）。cron参照は無し（日次ジョブは `PROJECT=/mnt/d/Project2/kensho` の実体を実行）。
- 他タスク（t_64f60f04 の "guard temp stash"）が 02:47:04 に `git stash` で作業ツリー全体を退避し、t_fda64102 の未コミット差分が消えていた（再発2回目）。t_fda64102 は冪等再適用ツールで復旧し、**検証前に commit+push を完了**させて巻き戻し耐性を確保した。stash 本体は他タスク所有のため pop していない（`git stash list` で `stash@{0}` として残存）。

## 自己レビュー（Reflexion）

- 学び: 共有リポジトリでは「パッチ→最小テスト→**即commit**→実機検証」の順でしか成果が残らない。検証を先に回すと他ワーカーの stash/checkout で消える。
- 残リスク: 同種の誤free判定は `fetch_apify_pricing()` の連続失敗打ち切り（`consecutive_failures>=3`）でも起こり得る。今回はキャッシュ第2ソースで緩和したが、キャッシュも空の場合の unknown 集計増のみで誤freeにはならない（t_fda64102 の修正で担保）。
