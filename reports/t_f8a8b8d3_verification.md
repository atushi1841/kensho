# t_f8a8b8d3 検証レポート — done_guard 所有パス推定バグ（本文の「変更禁止」言及を owned 扱い → 永久BLOCK）

- 実施: 2026-09-24 02:45〜03:10 JST（nightly-worker 5e8ec4984bba / kensho-sweeps）
- タスク: `t_f8a8b8d3`「[ループ衛生] done_guard の所有パス推定バグ」
- 変更対象: `/home/atushi/.hermes/profiles/kensho-sweeps/scripts/kanban_done_guard.py`（repo外・全profileのhookが参照する単一ファイル）
- バックアップ: `/tmp/guard_old_t_f8a8b8d3.py`（md5 `b96eef7749f1a80e9cc0f28410a277bf`）

## 実装サマリ（t_f8a8b8d3）

| 対象 | 変更 |
|------|------|
| `body_path_tokens(text)`（新設・純関数） | title/body を**行単位**で走査し、`変更しない / 変更禁止 / 禁止 / 以外 / 対象外 / しないこと` を含む行のパストークンを owned 候補から除外。正規化（`kensho/` 前置除去・`~`/`/home/`/`.hermes` → bare 化）は旧実装と同一ロジックを移設 |
| `task_owned_paths()` | body 由来トークンの抽出ループを `body_path_tokens()` 呼び出しへ置換（`git log --grep=<task_id>` 由来の committed パスは従来どおり exact に加算、加算順序: commits → body） |
| `_selftest_d_prohibited_path()`（新設） | 一時 sqlite DB（title/body/result）+ 一時 git repo で ①禁止言及パスが owned に入らない ②マーカー無し行の変更対象は残る ③並行 workstream が当該ファイルを dirty でも cond(d)=pass（foreign 警告のみ）を検証 |
| `_selftest_all()` | 上記ケースを登録（`dp_ok`）。SUCCESS 文言に `(d2)` を追加 |

## verification_evidence

本節は t_f8a8b8d3 の実測証跡のみを記載する（推測なし。数値はすべて実行出力の転記）。

(1) t_f8a8b8d3 の同一入力 before/after 実測（旧実装コピーと新実装を同一の一時repo/DBで比較）:

```
$ python3 /tmp/t_f8a8b8d3_compare.py
before(旧): exact=['scripts/own_task.py'] bare=['config.yaml']
after(新): exact=['scripts/own_task.py'] bare=[]

期待: config.yaml が both から消え、scripts/own_task.py は残る
COMPARE RESULT: OK
exit=0
```

→ 旧実装は本文の「config.yaml の default/provider/model は変更しない」1行だけで config.yaml を owned(bare) に採っていた（=今回の事故の再現）。新実装では除外され、変更対象 `scripts/own_task.py` は保持される。

(2) t_f8a8b8d3 の回帰セルフテスト（追加ケース込み・全条件）:

```
$ python3 /home/atushi/.hermes/profiles/kensho-sweeps/scripts/kanban_done_guard.py --selftest
selftest d_prohibited: owned=['scripts/own_task.py'] bare=[] target_kept=True prohibited_excluded=True
selftest d_prohibited: foreign_dirty_config cond(d)_pass=True owned_dirty=[] foreign=['config.yaml']
SELFTEST OK (d_prohibited): prohibited-path mentions are excluded from ownership; foreign dirty config no longer blocks
SELFTEST OK: (e) unpushed/ghost-hash detection works; (d) task-scoped bleed fix works; (d2) prohibited-path mention excluded from ownership works; (g) evidence durability gate works; (h) result-column gate works; (i) cron-config-drift gate works; (j) evidence.json write+validate round-trip works; (k) outcome-review before/after gate works
selftest_exit=0
```

(3) カード指定の検証コマンド（再現カード t_8e1e4934）:

```
$ bash /home/atushi/.hermes/profiles/kensho-sweeps/scripts/kanban_done_guard.py t_8e1e4934 --task --json | python3 -c "import json,sys; d=json.load(sys.stdin); print('owned=',d['detail']['uncommitted_code_files'],'foreign=',len(d['detail']['foreign_uncommitted_code_files']))"
owned= [] foreign= 3
```

補足（正直な記載）: 現在 `config.yaml` はクリーンなため、この1コマンドの `owned=[]` は今回の条件下では自明でもある。**修正が効いている構造的証明は (1)(2)** で、旧実装では bare に `config.yaml` が入っていたことを同一入力で示している。

(4) t_f8a8b8d3 完了前チェック・実タスクへの影響確認（回帰なし）:

```
$ bash /home/atushi/.hermes/profiles/kensho-sweeps/scripts/kanban_done_guard.py t_f8a8b8d3 --task --json
{'a:verification_evidence_section': False, 'b:command_citations>=3': False, 'c:no_false_done_marker_in_summary': True, 'd:no_uncommitted_code': True, 'e:pushed_and_hashes_ancestor': True, 'f:no_dep_drift': True, 'g:evidence_durable': True, 'h:result_nonempty': True, 'i:cron_config_md5_matches': True, 'j:evidence_json_valid': True, 'k:outcome_review': True}
```

→ 未コミットの3ファイル（`scripts/diag_protocol_violation.py` 等 = 稼働中カード t_02a5afc4 所有）は repo-wide では残るが、本カードの owned には入らないため `d:no_uncommitted_code=True`（=修正の実地効果）。a/b が False なのは本レポート作成前の測定であり、作成後に再実行する。

(5) 他プロファイルへの配布要否:

```
$ ls -la /home/atushi/.hermes/profiles/*/scripts/kanban_done_guard.py
-rwxrwxr-x 1 atushi atushi 117870 ... /home/atushi/.hermes/profiles/kensho-sweeps/scripts/kanban_done_guard.py   # ← 唯一の実体
$ grep -rl "kanban_done_guard" /home/atushi/.hermes/profiles/*/config.yaml
kensho-critic / kensho-revenue-qa / kensho-revenue-worker / kensho-sweeps / kensho-worker の config.yaml
```

→ 実体は1ファイルのみ・5プロファイルがそこを参照しているため、追加配布作業は不要（1箇所の修正で全ワーカーに反映）。

## 残存リスク・申し送り

- 判定は**行単位**のため、「変更対象: scripts/x.py、config.yaml は変更しない」のように1行に混在させると `scripts/x.py` も除外され得る → **カード本文は1行1パス（変更対象行／禁止言行を分離）で書く**運用を critic 側の本文テンプレに反映するのが望ましい（本カードの代替案2に相当する運用側の補完）。
- 除外は **owned からのみ**。所有ゼロ時の repo-wide fail-safe と「自分の未コミットコード=BLOCK」維持（selftest d_bleed ケース2/3 が緑のまま）は不変。
- ロールバック: `cp /tmp/guard_old_t_f8a8b8d3.py /home/atushi/.hermes/profiles/kensho-sweeps/scripts/kanban_done_guard.py`（repo外変更のため `git revert` 不可）。
- hotspot: `kanban_done_guard.py` は t_02a5afc4（protocol violation 強制）と関心が近い。並行変更が入る場合は本修正（body_path_tokens）を壊さないこと。

## 自己レビュー（Reflexion）

```json
{"self_review":{"what_was_done":"done_guard 条件(d) の所有推定が、カード本文の『変更禁止』言及だけで並行編集ファイルを owned 扱いし永久BLOCKするバグを修正。body 由来トークン抽出を純関数 body_path_tokens() に分離し行単位で禁止・参照言及を除外、--selftest に再発防止ケースを追加。同一入力の before/after と全selftestで実測検証","what_went_well":["旧実装コピーを退避して同一入力で比較し、再現→解消を数値で示した（bare ['config.yaml'] → []）","selftest を実sqlite DB+一時git repo で回帰ガード化し、cond(d)=pass まで検証した","実体1ファイル・5プロファイル参照を実測して配布不要と確定（余計な作業を回避）"],"what_could_improve":["カード指定の検証コマンド（t_8e1e4934）は config.yaml がクリーンな現状では自明な [] になるため、最初から before/after 比較を主証跡に据えるべきだった","行単位判定の副作用（同一行に変更対象と禁止言及を混在させると対象も除外）を実装前に設計判断として明記できた"],"mistakes_or_risks":["行単位除外により、同一行に『対象: x.py と config.yaml は変更しない』形式のカードでは x.py が owned から漏れる（検出力が僅かに緩む方向）","repo外ファイルのためリポジトリ履歴に差分が残らず、/tmp 退避以外のロールバック手段が無い"],"learned":"所有推定はカード本文の自然言語に依存するため、『変更対象の列挙』と『禁止・参照の言及』を機械的に区別する必要がある。将来的には guard 側が本文の構造化ブロック（変更対象: 行）だけを読む方が頑健","confidence":8,"verification_evidence":"before/after: 旧 bare=['config.yaml'] → 新 bare=[] / 対象 scripts/own_task.py は両者で exact に保持 / --selftest exit=0（d_prohibited: prohibited_excluded=True, foreign_dirty_config cond(d)_pass=True）/ guard t_8e1e4934: owned=[] foreign=3"}}
```
