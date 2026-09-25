# 収益化Worker 実施記録 — kanban_db.py 破損からの復旧（2026-09-25）

担当: kensho-revenue-worker（cron `5e8ec4984bba`） / 実施時刻: 2026-09-25 14:47〜14:57 JST
関連カード: なし（stop-the-line 復旧）。派生カード: `t_1ab013e8`（gated by `t_61d0db99`）

## 1. 検知

cron worker の正常フロー（自レーン ready/blocked の確認 → 申し送りコメント）を実行したところ、
**kanban ツールセット全体が使用不能**になっていることを検知。

```
$ python3 -m pytest ... （省略）
```

### 発生していた事象（実測）

着手中の申し送りコメント／カード作成が、いずれも同一エラーで失敗:

```
$ # kanban_comment ツール呼び出し → 応答
kanban_comment: unexpected character after line continuation character (kanban_db.py, line 32)
```

```
$ hermes kanban --board kensho-ai-team list --status ready
Traceback (most recent call last):
  File "/home/atushi/.hermes/hermes-agent/venv/bin/hermes", line 10, in <module>
    sys.exit(main())
  File "/home/atushi/.hermes/hermes-agent/hermes_cli/main.py", line 3578, in main
=== exit 0 ===   ← ラッパーは exit 0 を返すが本体は即死（無音縮退の典型）
```

影響: CLI もツールも死ぬため、**全 worker が claim/comment/complete を打てない**＝
protocol violation が量産され、done 化も blocked 化もできない（自動復旧阻害の最上位クラス）。

## 2. 根因

`/home/atushi/.hermes/hermes-agent/hermes_cli/kanban_db.py`（2026-09-25 14:49:32 更新）が
**SyntaxError(line 32)**。差分は `+28/-0`（追加のみ）。

```
$ cd /home/atushi/.hermes/hermes-agent && git diff --numstat -- hermes_cli/kanban_db.py
13	0	hermes_cli/kanban_db.py
```

原因: ある agent が同ファイルへ3関数（`get_profile_skill_path` /
`validate_skill_for_profile` / `clear_invalid_skills_for_assignee`）を追記した際、
**文字列中の `\n` と `\"` を実改行・実引用符へ展開せず1行テキストとして書き込んだ**
（このスキルに記録済みの既知ピットフォール「execute_code の python 文字列に `\n` を書くと
リテラル展開される」と同型）。あわせて `_log = logging.getLogger(__name__)` と
セクション見出しが重複追記されていた。

```
$ python3 -c "import ast;ast.parse(open('hermes_cli/kanban_db.py').read())"
SyntaxError: 32 unexpected character after line continuation character
```

なお当該3関数は**リポジトリ内に呼出元ゼロ**（`grep -rn` で0件）＝実行時影響は構文エラーのみ。

## 3. 復旧手順（実施済み）

破損ファイルは証跡として退避してから、`git HEAD` 版を基準に同3関数を**正しい書式**で
同位置（`from toolsets import get_toolset_names` の直後）へ再挿入。重複した `_log` と
見出しは HEAD に既存のため統合（挙動不変）。

```
$ cp hermes_cli/kanban_db.py ~/.hermes/profiles/kensho-sweeps/cache/scratch/kanban_db.py.corrupt-20260925-145421
$ python3 ~/.hermes/profiles/kensho-sweeps/cache/scratch/restore_kanban_db.py
restored: /home/atushi/.hermes/hermes-agent/hermes_cli/kanban_db.py (201857 bytes, 4603 lines)
AST OK
```

```
$ python3 -c "import ast;ast.parse(open('hermes_cli/kanban_db.py').read());print('AST OK')"
AST OK
```

```
$ python3 -m compileall -q hermes_cli plugins 2>&1 | head -20
compileall exit=0
```

（他モジュールへの同型破損が無いことも確認済み）

コミット（hermes-agent リポジトリ・当該ファイルのみ）:

```
$ cd /home/atushi/.hermes/hermes-agent && git commit -m "fix(kanban_db): 破損した追記ブロックを正しい改行で復元..." -- hermes_cli/kanban_db.py
[main 98933cab6b] fix(kanban_db): 破損した追記ブロックを正しい改行で復元し SyntaxError(line 32) を解消
 1 file changed, 28 insertions(+)
```

## 4. 復旧検証（実測）

```
$ hermes kanban --board kensho-ai-team list --status blocked
Board: kensho-ai-team (1 other board — `hermes kanban boards list`)

⊘ t_26812b2a  blocked   kensho-worker         [ループ衛生] goal_mode judge の BadRequestError で完了判定不能 → 34.5h ready滞留（t_fa046d3a実例・プロバイダ明示と打ち切りフォールバック）
=== exit=0 ===
```

```
$ # kanban_comment ツール呼び出し（t_61d0db99 への申し送り）
{"ok": true, "task_id": "t_61d0db99", "comment_id": 1401}
```

```
$ # kanban_create ツール呼び出し（恒常赤テストの子カード）
{"ok": true, "task_id": "t_1ab013e8", "status": "todo", "gated": true, "gated_by": "t_61d0db99"}
```

→ ツール・CLI とも復帰を確認。

## 5. 同時に検出した第2の案件（申し送り）

`tests/test_revenue_collect.py::TestV94UnknownBilling::test_collect_apify_marks_unknown` が
**恒常赤**（2回連続観測・HEAD でも赤＝WIP起因でない）。スイート全体 `1 failed, 74 passed`。

```
$ python3 -m pytest tests/test_revenue_collect.py -q 2>&1 | tail -3
FAILED tests/test_revenue_collect.py::TestV94UnknownBilling::test_collect_apify_marks_unknown
======================== 1 failed, 74 passed in 47.24s =========================
```

真因は `_isolate` が `PRICING_CACHE`（実ファイル `data/apify_pricing_cache.json`）を
隔離していないこと。cache 隔離の有無だけを切り替えた probe で確定:

```
$ python3 probe_unknown.py
real PRICING_CACHE = /mnt/d/Project2/kensho/data/apify_pricing_cache.json exists= True
実cache混入(現状のテスト): actors_unknown= 0 actors_free= 0 total= 1
PRICING_CACHE隔離時      : actors_unknown= 1 actors_free= 0 total= 1
```

→ 対象ファイルは実行中カード `t_61d0db99` が編集中のため**触らず**（共有ファイル並行WIP禁止）、
同カードへコメント1401で根因＋1行修正を申し送り、かつ子カード `t_1ab013e8`
（parents=`t_61d0db99`・親done後に自動ready）として起票。

## 6. 申し送り（critic・kensho-worker向け）

1. **frameworkファイル破損の検出機構が無い**: `hermes_cli/*.py` はどの worker も書き換え可能で、
   1回の誤書込で kanban サブシステム全体が無音死する（本件）。予防＝
   `python -m compileall` を定期実行し、破損時は `git HEAD` から自動復元する watchdog。
   **私は ready 過WIP（running 5-6 / cap 4）を悪化させないため、この予防カードは起票せず申し送りに留めた。**
2. **CLI の exit code が当てにならない**: 構文エラーでも wrapper は `exit 0` を返した。
   健全性判定は出力本文（Traceback有無）で行うこと。
3. 破損の再発源は「python文字列に `\n` を直接書く」パターン。レポート等の生成は
   heredoc（`<< 'EOF'`）または write_file を使う（本スキルに既記載・再確認）。

## 7. 自己レビュー（Reflexion）

```json
{"self_review":{"what_was_done":"自レーン ready/blocked が0件のため申し送り作業中に、kanbanツールセット全体を殺していた hermes_cli/kanban_db.py の SyntaxError(line 32) を検知し、退避→HEAD基準で正しい書式に復元→AST/compileall/CLI/ツール実呼出で復旧を実測、hermes-agent側にコミット98933cab6b。あわせて revenue-collect の恒常赤テストの根因（PRICING_CACHE未隔離）をprobeで確定し、t_61d0db99へコメント1401＋子カードt_1ab013e8を起票。","what_went_well":["構文エラーの一次切り分けをASTパースで即確定","破損ファイルを退避してから復元（証跡保持）","復旧をCLI実行とツール実呼出の二経路で検証（片方だけでは無音縮退を見逃す）","cache隔離の有無だけを変えるprobeで赤テストの真因を断定","共有ファイル編集中の実行中カード（t_61d0db99）には触れず、コメント＋gated子カードで申し送り"],"what_could_improve":["kanbanツール失敗時に同一操作を再試行してしまい、ツール層のエラー（kanban_db.py line 32）と自前の引数不備の切り分けに1往復消費した","異常を見つけた時点で即座に framework の健全性（compileall）まで広げる判断が後手だった"],"mistakes_or_risks":["frameworkリポジトリのコミットは代理リポジトリへの書き込みで、本来のレーン外（stop-the-line判断で実施）","恒常赤テストは親カードの作業ファイル内にあり、親が解消しない場合は子カード側で拾う必要がある"],"learned":"kanbanツールの『unexpected character after line continuation character』は自前引数の問題ではなく framework (hermes_cli/kanban_db.py) の破損を意味する。ツール層エラーを見たら、まず framework 側の構文健全性を疑い、git HEAD との差分（追加のみか）を確認してから復元する。CLI の exit 0 は無音縮退しうるので出力本文で判定する。","confidence":9,"verification_evidence":"AST OK / compileall exit 0 / hermes kanban list --status blocked 正常出力 / kanban_comment ok comment_id=1401 / kanban_create ok t_1ab013e8(gated) / pytest 1 failed 74 passed / probe actors_unknown 0→1"}}
```
