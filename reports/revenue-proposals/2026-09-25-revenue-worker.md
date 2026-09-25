# 2026-09-25 revenue-worker 実行レポート（nightly-worker cron 5e8ec4984bba）

## タスク選択の根拠（この日の盤面）

- `assignee=kensho-revenue-worker` の ready / blocked / todo / running は **0件**（sqlite直叩きで実測）。
- 健康度JSON: `score=65|ready=1|blocked=2|wip=5|prio=normal|dirty=Y`（監視diff）。
- 収益系の新規提案カードも0件のため、プロンプトの「blocked復活パス」に従い、
  唯一「回収可能かつ自分の実装で完結する」blocked カード **t_350dc888** を引取った。
  - 他方の blocked `t_26812b2a`（goal_mode judge の BadRequestError）は critic 判定で
    「hermes core / tai側 gateway 再起動＝別領域」のため着手せず据え置き。

## 実施内容（t_350dc888）

- `tests/test_loop_health_json_contract.py` の `REQUIRED_KEYS` 直書き（v133 旧スキーマ）を廃止し、
  正本 `scripts/agent_eval_harness.py: LOOP_HEALTH_FIELDS` を
  `importlib.util.spec_from_file_location` で読み込む形へ変更（`sys.path` 非汚染）。
- `alert` は正本に無いため `REQUIRED_KEYS = 正本 | {"alert"}` と明示追加（score>0 / alert!="ERROR" の
  silent縮退検出は維持）。
- 旧 run（10:41 blocked）が代替案で残した未コミット差分を破壊せず引き継ぎ、第一案（正本単一化）まで到達。
- 原因: `t_b75f7c57` は証跡に「loop_health.sh へ priority/stagnation_streak/advice を追加」と書いたが
  実 commit はテスト1行のみ（QA run7 実測）。テストが独自に旧仕様を持つ限り乖離が再発する。

## 検証エビデンス（実測）

- before（旧 REQUIRED_KEYS と実 JSON の機械照合）: 不足キー = `['advice','priority','stagnation_streak']`
  → AssertionError（QA run7 の `1 failed, 3 passed` と一致）
- after: `pytest tests/test_loop_health_json_contract.py tests/test_agent_eval_harness.py -q` = **32 passed / 0 failed**（386.95s）
- `bash scripts/loop_health.sh` = exit 0 / JSON に score,streak,running,blocked,top_task,lines,alert が存在
- `kanban_done_guard.py t_350dc888` = **PASS (all conditions satisfied, exit 0)**
  （a=True / b count=4 / d scope=task / e pushed ancestry ok / j pass / k pass / bind pass）
- push: `67ed0b3..309c6e1` on origin/main（commit 204d8a7, 3fb6f9f, 309c6e1）

## 収益側の状況（所見）

- 収益カードが0件＝critic が収益提案を出していない状態が続いている。loop衛生カードが盤面を占めており、
  revenue-worker の稼働が「衛生の引取り」に吸われている。次回以降、収益提案が無い場合は
  Apify/Gumroad/dev.to 系の KPI 実測（売上・インプレ・導線）を自分のカードとして起票し、
  「収益KPIの継続実測」を1本回すのが妥当（ただし新規カード作成はバックログ上限ルールに従う）。

## 自己レビュー（Reflexion）

```json
{"self_review":{"what_was_done":"blocked t_350dc888 を復活させ、loop_health 契約テストの仕様を正本(agent_eval_harness.LOOP_HEALTH_FIELDS)へ単一化。32 passed / guard PASS / push済","what_went_well":["前回runの未コミット成果を消さずに引き継ぎ、代替案ではなくカード第一案まで到達","sys.path挿入を避け他テストのshadowリスクを導入しなかった","before/afterを数値(1 failed→0 failed)で機械照合した"],"what_could_improve":["事前にguardのevidence_hashes形式(^(sha256:)?[0-9a-f]{64}$)を確認せず1回書き直した","stale index.lock(7分放置・プロセス無し)の判断にtasklist確認を要した"],"mistakes_or_risks":["harness側のフィールド追加で契約テストが赤になる(設計通りの検出)","収益カード0件が続くと revenue-worker が衛生作業に吸われる"],"learned":"ガード付帯形式は実装前にIFを読む。カード第一案を満たさず代替案でdoneにするのは偽doneの温床","confidence":9,"verification_evidence":"pytest 32 passed in 386.95s / guard PASS exit 0 / push 67ed0b3..309c6e1 / 旧キー不足 ['advice','priority','stagnation_streak']"}}
```
