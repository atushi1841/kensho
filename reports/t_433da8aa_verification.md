# t_433da8aa 検証証跡 — done guard hook 恒久配線（kensho-worker / kensho-critic / kensho-revenue-qa）

実施: 2026-09-16 02:45–02:55 JST / nightly-worker (5e8ec4984bba) / 起票元: QA run492（reports/qa_run492_2026-09-16_0240.md）

## verification_evidence

### 1. 事前状態実測（3プロファイル未配線=0 refs、既存2件は配線済）

```
$ grep -c kanban_done_guard /home/atushi/.hermes/profiles/kensho-worker/config.yaml /home/atushi/.hermes/profiles/kensho-critic/config.yaml /home/atushi/.hermes/profiles/kensho-revenue-qa/config.yaml
→ 0 / 0 / 0（hooksセクション自体が不在。652行 hooks_auto_accept: false のみ）
$ grep -n -B4 -A10 kanban_done_guard /home/atushi/.hermes/profiles/kensho-sweeps/config.yaml
→ 751-755: pre_tool_call / matcher: terminal|execute_code|kanban_complete / command: /home/atushi/.hermes/agent-hooks/kanban_done_guard_hook.sh / timeout: 30 / fail_closed: true
（kensho-revenue-worker は 830-835 に同形配線済を確認）
```

### 2. 変更内容（3ファイル同一形・他設定ゼロ変更）

各 config.yaml の `hooks_auto_accept: false` 直前に既存配線と同一のセクションを追記:

```yaml
hooks:
  pre_tool_call:
    - matcher: terminal|execute_code|kanban_complete
      command: /home/atushi/.hermes/agent-hooks/kanban_done_guard_hook.sh
      timeout: 30
      fail_closed: true
```

編集前バックアップ: 各 `config.yaml.bak-t433da8aa`（失敗時代替案=即リストア）。

### 3. 編集後実測（受け入れ条件grep≥1 / YAML通過 / diff追加6行のみ）

```
$ cd /home/atushi/.hermes/profiles && for p in kensho-worker kensho-critic kensho-revenue-qa; do python3 -c "import yaml; yaml.safe_load(open('$p/config.yaml')); print('YAML_OK')"; diff $p/config.yaml.bak-t433da8aa $p/config.yaml | grep -c '^>'; grep -c kanban_done_guard $p/config.yaml; done
→ 3ファイルとも YAML_OK / 追加行=6 / refs=1
```

model/default/provider 等の他設定キーは diff 追加行=6（hooksセクション）に一致、非変更を実測。絶対禁止領域（モデル切替等）に接触なし。

### 4. hook動作スモークテスト（dispatcher spawnのdoneが素通しされなくなったことの確認）

```
$ printf '{"hook_event_name":"pre_tool_call","tool_name":"kanban_complete","tool_input":{"task_id":"t_nonexistent_test"},"extra":{}}' | HOME=/home/atushi bash /home/atushi/.hermes/agent-hooks/kanban_done_guard_hook.sh; echo EXIT=$?
→ {"decision":"block","reason":"kanban_done_guard BLOCKED done for task t_nonexistent_test. ..."} EXIT=2
```

exit 2 + block JSON = pre_tool_callワイヤプロトコルどおりの拒否動作。hook本体は3プロファイル共通の同一スクリプト（/home/atushi/.hermes/agent-hooks/kanban_done_guard_hook.sh、6202B、実行権限済）を参照するのみ。

### 5. 回帰ゲート（基本方針=offender t_4e710909はbackfillせず窓roll待ち）

```
$ cd /mnt/d/Project2/kensho && HOME=/home/atushi python3 -m pytest tests/test_regression_gates.py -q -p no:cacheprovider --no-cov
→ 1 failed, 9 passed （failed=test_gate_result_column_empty_after_v151、offenders=['t_4e710909'] のみ）
```

カード本文基本方針（backfill行わず・window内offenderがt_4e710909のみで48h窓Roll後=9/18に自然解消）を実測で確認。新規空result増分0（t_433da8aa自身のdoneは --result 付きで発行）。

### 6. qa-v151-7day-measure 無影響確認

```
$ python3 -c "(jobs.json走査) → 67493a6c7468 qa-v151-7day-measure enabled=True once@2026-09-22T09:00+09:00 (profile=kensho-revenue-qa)"
```

本変更は kensho-revenue-qa の hooks セクション追加のみで同ジョブの schedule/prompt/model 無変更。7日計測（window内空result増分0）には配線完了がむしろ成功条件側。

## 自己レビュー（Reflexion）

```json
{"self_review":{"what_was_done":"kensho-worker/kensho-critic/kensho-revenue-qa の3 config.yamlへkanban_done_guard hook pre_tool_call配線を恒久化。バックアップ→編集→YAML/diff/hookスモーク/回帰ゲート/7day-measure無影響の5点実測","what_went_well":["既存2プロファイルと同形の6行追記に限定し他設定非変更をdiff行数で証明","hookのexit2 blockをペイロード模擬で実測（配線=ファイル存在ではなく動作確認まで）"],"what_could_improve":["config.yaml直編集は台帳なし。次回以降プロファイル設定変更もgit追跡領域へ移す提案はcritic行き","pytest結果のtail pipeはexit codeを隠すためパイプなし再実行を習慣化"],"mistakes_or_risks":["fail_closed=trueのためguardスクリプト自体が壊れると3プロファイルのterminal/kanban_completeが全停止する（hookは既にkensho-sweeps/revenue-workerで稼働実績あり、リスクは受容範囲）"],"learned":"dispatcher spawn経路の病理はプロンプト必須化では塞げない。pre_tool_call hook配線がkernel級防衛の最小実装","confidence":9,"verification_evidence":"§1-§6の実測出力のみ"}}
```
