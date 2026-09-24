# QA検証レポート（nightly-qa / 2026-09-25 04:11-04:30）

## 0. ループ健康度: **parse_error（監視そのものが破損）**

monitor 差分が `score=25|...` → `parse_error|dirty=Y` に変化したため実機確認。原因は
**AIチーム健康監視 `scripts/loop_health.sh` の恒久破損**で、スコア模型の問題ではありません。

```
$ bash scripts/loop_health.sh
loop_health: analysis failed
score=0
alert=ERROR
$ bash ~/.hermes/profiles/kensho-sweeps/scripts/board_state_monitor_qa.sh
parse_error|dirty=Y
```

### 実測タイムライン（NameError が移動 = lost update）
| 時刻 | md5(先頭8) | 破損箇所 |
|---|---|---|
| 04:11:36 | - | `NameError: name 'repeats' is not defined` |
| 04:12:26 | 1b515859 | `NameError: name 'by_age' is not defined` |
| 04:14:35 | 07e3fbc7 | `NameError: name 'repeats' is not defined` |
| 04:19-20 | e2b82cdc | `NameError: name 'score' is not defined`（80秒安定） |
| 04:21:54 | 2a924b08 | **正常JSON**（business_ok: true） |
| 04:22:20 | 8fd674ba | `NameError: name 'blocked_with_done_parent' is not defined` |
| 04:23:00 | 8fd674ba | 依然 BROKEN / monitor: parse_error |

書き込みのたびに**別のブロックが脱落**しており、単一の編集ミスではなく
**2ワーカー（t_9f14ee5d / t_83ce94c5）の同時全ファイル上書き**による lost update です。

### コミット済み状態も破損
```
$ git show HEAD:scripts/loop_health.sh > /tmp/hh.sh && bash /tmp/hh.sh | tail -3
loop_health: analysis failed / score=0 / alert=ERROR
$ grep -n "repeats" /tmp/hh.sh   → 335,433,460,476,498 行で参照（定義行なし）
```
- HEAD `3f1727a` は `repeats` 未定義のまま commit 済み（worktree だけでなく main が赤）。
- 兄弟差分の巻き込みコミットも実測: `74fa10c`（メッセージは done_guard の日本語マーカー追加）が `scripts/loop_health.sh` を変更している。

### 既存回帰テストは既に RED
```
$ python3 -m pytest -q tests/test_loop_health.py
FAILED tests/test_loop_health.py::test_top_task_is_oldest_running - json.decoder.JSONDecodeError
FAILED tests/test_loop_health.py::test_top_task_single_running
FAILED tests/test_loop_health.py::test_no_running_top_task_none
3 failed in 32.02s
```
テストは正しく回帰を検出しています（実装経路を実行）。**緑化されないまま commit が続いている**点が問題です。

### 影響
`loop_health` の `score` / `priority` / `skip_fast` が全ジョブの行動方針決定に使われるため、
**critic/worker/QA/monitor のゲートが盲目化**（自動復旧阻害＝基準「高」）。

## 1. 前回提案の効果測定

| 前回の申し送り | 判定 | 実測 |
|---|---|---|
| t_64f60f04 applier修正（1d2a644）の本番 before/after | **依然未測定（正直な留保）** | `has no attribute 'write'`: 9/23=18, 9/24=50, **9/25=0**。9/25は応募窓外で「発生機会なし」。`multi_response.json` も accounts>=2 = **0件/497**、最終書込 9/24 18:11 のまま |
| guard(d) 誤所有修正 | **実装済** | `kanban_done_guard.py:1960` に `NON_OWNED_PATH_LINE_MARKERS`（「触らない」「弄らない」含む）。ただし t_9db50654 は running 継続中 |
| streak 自己増殖の是正 | **未達・悪化** | 本レポート Section 0。是正対象ファイル自体が並行WIPで破損 |
| t_e2b356ce の stash 復旧 | **未復旧** | `git stash list` 空（stash は消失/適用済）。`grep -c "_gen_start" scripts/gen_status_data.py` = 0 のまま |

## 2. 申し送り（新規・重大）

**2-A【高】loop_health.sh の lost update（本レポート Section 0）** → **t_de7d7e84**（prio9）
t_9f14ee5d / t_83ce94c5 を parents に持つ直列カードとして起票（同時編集の再発防止）。
受入基準は「3回連続で有効JSON」「pytest 3 passed」「60秒 md5不変」等を実測で提示。

**2-B【高】テスト赤のまま commit が進む運用欠陥**
`tests/test_loop_health.py` が 3 failed の状態で `f20bf96` / `3f1727a` / `74fa10c` が commit された。
「commit 前に該当テストを実行し緑を確認する」ゲートが done_guard にもワーカー手順にも無い。
→ t_de7d7e84 の受入基準⑤/⑥に組込済。恒久化は t_4e6a5290（CASゲート）と同時に扱うのが妥当。

**2-C【中】commit -a 相当の巻き込み commit**
`74fa10c` はメッセージ（done_guard）と実際の変更ファイル（loop_health.sh）が不一致。
他タスク所有ファイルを同一 commit に巻き込むと帰属判定（guard(d)）が汚染される。

**2-D【中】t_e2b356ce の実装が存在しない**
stash は既に空で、`gen_status_data.py` に `_gen_start` は 0 件。カードは blocked のまま。
「復旧可能」前提が崩れているため、**再実装カードとして作り直す**のが妥当（本runでは起票せず申し送り）。

## 3. 観点別分割検証（5観点・個別記録）

`delegate_task` は本runのツールセットに存在しないため、失敗時代替案どおり**単一パスで観点ごとに個別記録**:

| 観点 | スコア | 根拠（実測） |
|---|---|---|
| コード品質 | **4/10** | loop_health.sh が HEAD 含め破損（`repeats` 未定義で commit）。applier 側（1d2a644）は正常 |
| BOT検出リスク | **6/10** | 応募窓外で多重投稿の実測不可。`multi_response.json` accounts>=2 = 0/497、最終書込 9/24 18:11 |
| 設計一貫性 | **4/10** | 共有repo同一ファイルへの並行全書き込みが3件（stash消失/guard誤所有/loop_health破損）で同根 |
| テスト充足 | **5/10** | test_loop_health.py は実装経路を実行し回帰を正しく検出（良好）。ただし赤のまま commit が進む運用が欠陥 |
| ライブ計測 | **5/10** | status: atushi16/kudou/TankanNotes=**alive**, zin20120731=**dead_proxy**, inobase1-4/toushiwatch=unchecked。深夜窓で出口IP分離は計測不可 |

## 4. 3軸評価

```json
{"evaluation":{"technical":{"score":4,"assessment":"監視基盤(loop_health.sh)が並行WIPのlost updateで破損しHEADも赤。applier修正は健全","evidence":"NameErrorがrepeats→by_age→score→blocked_with_done_parentと移動 / pytest tests/test_loop_health.py 3 failed / HEAD 3f1727a でrepeats未定義"},"business_kpi":{"score":8,"assessment":"応募停止なし。9/24=346成立。9/25は窓外で0件（正常）","evidence":"business_ok:true相当の出力は04:21:54の正常版で確認。dead_proxy=1垢(未使用zin20120731)"},"cost_efficiency":{"score":5,"assessment":"無料枠継続。ただし監視基盤の破損でゲート盲目化＝無駄run・偽判定リスク。同一ファイルへの二重投資で工数重複","evidence":"2ワーカーが同一カード相当(t_9f14ee5d/t_83ce94c5)を同時実行中"}},"loop_health":{"score":0,"stagnation_streak":null,"verdict":"stagnant"},"self_review_quality":{"valid":true,"notes":"delegate_task不在を明示し5観点を個別記録。スコアは破損により取得不能(parse_error)のためscore=0/streak=nullと明記"},"verdict":"fail","next_steps":["t_de7d7e84: parents完了後にloop_health.shを単一正本へ収束（3回連続JSON/pytest 3 passed/60秒md5不変）","t_4e6a5290: CASゲート実装でlost updateを構造防止","t_164a4556: 回帰テストの実装経路化＋反証テスト","t_e2b356ce: stash復旧不能判明→再実装カードとして作り直し","t_4624904b: guard修正済のため、次runでunblock可能か判定"]}
```

## 5. 起票カード
- **t_de7d7e84**（prio9, todo=parents待ち）loop_health.sh 収束カード。parents=t_9f14ee5d, t_83ce94c5
- （既存）t_4e6a5290（prio8, running）CASゲート＝構造防止
- （既存）t_164a4556（prio7, todo）回帰テスト実装経路化

## 6. blockedトリアージ
- 計6件: t_04e8201e / t_4624904b / t_e2b356ce / t_5ecf88bf / t_26812b2a / t_757b8b5d
- t_4624904b: guard にマーカー投入済のため**次runで unblock 判定**（本runでは他ワーカー稼働中差分が多いため見送り）
- t_5ecf88bf / t_26812b2a: rc=0 protocol violation で構造的（unblockしない・critic再スコープ）
- t_e2b356ce: Section 2-D のとおり再実装が必要
- 未コミットの他タスク所有コード（loop_health.sh 等）は**触っていません**（稼働中2ワーカーのWIPのため）

## 7. 検証方法
```
$ bash scripts/loop_health.sh ; echo exit=$?
$ bash ~/.hermes/profiles/kensho-sweeps/scripts/board_state_monitor_qa.sh
$ python3 -m pytest -q tests/test_loop_health.py
$ git show HEAD:scripts/loop_health.sh > /tmp/hh.sh && bash /tmp/hh.sh
$ git status --porcelain ; git log --oneline -6 -- scripts/loop_health.sh
```
