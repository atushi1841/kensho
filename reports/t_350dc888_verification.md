# t_350dc888 検証レポート — loop_health JSON 契約テストの正本単一化

- タスク: t_350dc888「[ループ衛生・高] t_b75f7c57 は偽done（commit≠diff・証跡が虚偽記載）: 契約テストを v137+ 単一正本(agent_eval_harness.LOOP_HEALTH_FIELDS) へ寄せて緑化」
- assignee: kensho-revenue-worker（blocked から復活。unblock → claim --ttl 3600）
- 実施: 2026-09-25（nightly-worker cron 5e8ec4984bba / kensho-sweeps）
- 実装対象: `tests/test_loop_health_json_contract.py`（1ファイル）

## 実装サマリ（t_350dc888）

| 項目 | 変更前 | 変更後 |
|------|--------|--------|
| REQUIRED_KEYS の出所 | テスト側に直書き（v133 旧スキーマ: priority / counts / stagnation_streak / advice） | `scripts/agent_eval_harness.py` の `LOOP_HEALTH_FIELDS`（v137+ 単一正本）を import |
| import 方法 | — | `importlib.util.spec_from_file_location`（`sys.path` を汚さず scripts/ の同名モジュールで他テストを shadow しない） |
| alert 検証 | REQUIRED_KEYS に含めていた | 正本に alert が無いため `REQUIRED_KEYS = 正本のフィールド集合 | {"alert"}` として明示追加（silent 縮退検出は維持） |
| score > 0 / alert != ERROR | 維持 | 維持（変更なし） |

## 真因（t_350dc888 が潰したもの）

`t_b75f7c57` は「loop_health.sh に priority/stagnation_streak/advice を追加した」と証跡に書いたが、
実際の commit はテストの1行のみで loop_health.sh は 1 バイトも変わっていなかった（QA run7 実測）。
原因はテスト側が **v133 旧スキーマを直書きで固定**していたこと。テストと実装が別々に仕様を持つ限り
同じ乖離が再発するため、t_350dc888 ではフィールド定義を harness 一箇所に寄せた。

## 実測（before → after）

- before（QA run7 実測・HEAD のテスト内容 = 旧 REQUIRED_KEYS）: `1 failed, 3 passed`
  `AssertionError: loop_health JSON に不足キー: {'advice', 'priority', 'stagnation_streak'}`
- after（本修正・実測）: 契約テスト 4 passed（failed 0）。失敗率 25%（1/4）→ 0%（0/4）

## verification_evidence

(1) 正本の取得と before/after の不足キー（旧キー集合との機械照合）:

$ /home/atushi/.hermes/hermes-agent/venv/bin/python3 -c "import importlib.util, json; spec=importlib.util.spec_from_file_location('h','scripts/agent_eval_harness.py'); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); print('LOOP_HEALTH_FIELDS =', m.LOOP_HEALTH_FIELDS); d=json.load(open('/tmp/lh_repo.json')); HEAD_KEYS={'score','alert','priority','counts','stagnation_streak','advice'}; print('HEAD(旧)REQUIRED_KEYS の不足キー =', sorted(HEAD_KEYS - set(d.keys()))); print('現行 REQUIRED_KEYS の不足キー =', sorted((set(m.LOOP_HEALTH_FIELDS)|{'alert'}) - set(d.keys())))"
LOOP_HEALTH_FIELDS = ('score', 'streak', 'running', 'blocked', 'top_task', 'lines')
HEAD(旧)REQUIRED_KEYS の不足キー = ['advice', 'priority', 'stagnation_streak']
現行 REQUIRED_KEYS の不足キー = []
（＝旧テストは実出力に無い3キーを要求して必ず AssertionError。新テストは不足ゼロ。）

(2) 修正後のテスト実行（契約テスト + 正本 harness の単体テスト、実測所要 386.95s）:

$ cd /mnt/d/Project2/kensho && /home/atushi/.hermes/hermes-agent/venv/bin/python3 -m pytest tests/test_loop_health_json_contract.py tests/test_agent_eval_harness.py -q --no-cov -p no:cacheprovider
collected 32 items
tests/test_loop_health_json_contract.py ....                             [ 12%]
tests/test_agent_eval_harness.py ............................            [100%]
======================== 32 passed in 386.95s (0:06:26) ========================

(3) 契約テストが読む実装側 JSON の実体確認（repository 実ファイルを実行）:

$ cd /mnt/d/Project2/kensho && timeout 200 bash scripts/loop_health.sh > /tmp/lh_repo.json 2>/tmp/lh_repo.err
exit=0
（/tmp/lh_repo.json のキー集合: score, streak, running, blocked, top_task, lines, alert, counts, ... score=55 alert=ALERT。
 正本 LOOP_HEALTH_FIELDS の全フィールドが実出力に存在することを機械確認。契約テストはこの stdout を parse する。）

(4) 変更ファイルの差分（1ファイルのみ・テスト側の仕様書き写しを撤去）:

$ cd /mnt/d/Project2/kensho && git show --stat --oneline HEAD
（本コミット。tests/test_loop_health_json_contract.py のみ変更 → 詳細はコミット後の `git show --stat` 出力を参照）

## 自己レビュー（Reflexion）

- うまくいった点: 前回 run（10:41 blocked）の未コミット成果を消さずに引き継ぎ、カード本文の**推奨経路（正本 import）**まで到達させた。`sys.path` 挿入を避けたため他テストへの shadow リスクを導入していない（harness 単体テスト28件も同時に緑）。
- 危うかった点: 前回 run は代替案（直書き）で緑にして blocked になった。代替案はカードの「やむを得ない場合」であり、正本単一化という目的を満たさない。**カードの第一案を満たさずに代替案で done しようとしない**こと。
- リスク: harness を import するため、将来 LOOP_HEALTH_FIELDS に実出力へ無いフィールドが足されると契約テストが赤になる。これは仕様通り（実装と契約の乖離検出）であり、テスト側へ逃げ道を書かないことが t_350dc888 の狙い。

## 所有束縛の明示

本レポートは t_350dc888 の成果物である（dominant task-id = t_350dc888）。参照した他カードは t_b75f7c57（偽done の被疑元・QA run7 で実測）のみで、引用は最小限に留める。
