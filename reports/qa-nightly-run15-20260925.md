# nightly-qa run15 検証レポート（2026-09-25 18:05–18:35 JST / job 033ff6065ef7）

## 0. 結論（3行）
- **ループは healthy だが blocked が 2→6 に増加**（`score=100 / streak=0 / alert=OK / cap_mismatch=True / dirty=Y`）。増分は (a) default host config 401 の review 全死、(b) 証跡条件系の再blocked 3件＋新規1件。
- **P1回帰は run14 から2回連続で未修正**: `kanban_done_guard.py --selftest` = exit 2。親 ff2a357 は exit 0、e079f50（t_efe1736c）が原因と**実行比較で確定**（soft期間スタブが新経路に追随せず）。
- **ライブ計測は正常**: 実アクション175（全稼働垢が日次上限到達）・深夜0・リプライ0・ERROR 0・出口IP分離 3/3。

## 1. ループ健康度
```
$ bash ~/.hermes/profiles/kensho-sweeps/scripts/loop_health.sh | python3 -c "import json,sys;d=json.load(sys.stdin);print(d['score'],d['streak'],d['alert'],d['running'],d['blocked'],d['cap_profile'],d['cap_dispatcher'],d['cap_mismatch'])"
100 0 OK 1 6 4 8 True
$ python3 -c "sqlite集計"
ready 0 / blocked 6 / running 1 / triage 0 / done 685
```
- monitor 差分: `blocked=2→6`, `dirty=N→Y`（検知した変化はこの2点）
- `cap_mismatch=True` は前run同様（profile=4 / dispatcher=8）＝構造要因は未解消

## 2. blocked 6件の内訳（すべて実測）
| id | 状態 | 直近の理由（実測） |
|----|------|-------------------|
| t_5490697f | **要ユーザー・高** | default host config の deepseek 401 → kanban_decomposer/background_review 全死（後述 P2） |
| t_28e11c70 | blocked（実装は完了済） | guard exit 1、唯一の不足は (d) `uncommitted(code,OWNED): scripts/check_dep_drift.py` ＝ **兄弟カードの未コミットファイルをOWNED誤帰属** |
| t_ebbfe4a7 | blocked | run #1448（17:47:59→17:59:50）終了時に自分の実装を**未コミットのまま**残留（下記 §3） |
| t_fe629b9e | blocked（crashed ×4） | `error: no task-owned worker report found (cross-task evidence rejected)`（dominant-id 不一致） |
| t_a38b99bc | blocked | (g) `evidence file not committed: reports/t_a38b99bc_verification.md`（未追跡） |
| t_26812b2a | 要ユーザー維持 | goal judge の provider 明示（前runから変更なし） |

## 3. P1: guard `--selftest` 回帰（2回連続・未修正・修正カード無し）
```
$ bash ~/.hermes/profiles/kensho-sweeps/scripts/kanban_done_guard.py --selftest; echo REAL_EXIT=$?
SELFTEST FAILED: guard did not behave as designed (e_push_gap=True d_bleed=True d_prohibited=True d_nonowned=True g_durability=False h_result=False i_config_drift=True j_write=True k_outcome=True write_report=True)
REAL_EXIT=2

$ git show ff2a357:scripts/kanban_done_guard.py > /tmp/guard_ff2a357.py && bash /tmp/guard_ff2a357.py --selftest; echo FF2A357_EXIT=$?
SELFTEST OK: (e) unpushed/ghost-hash detection works; (d) task-scoped bleed fix works; ... (k) outcome-review before/after gate works
FF2A357_EXIT=0

$ bash /home/atushi/.hermes/profiles/kensho-sweeps/scripts/kanban_done_guard.py --selftest | grep soft_period
selftest g_durability: soft_period_pass_with_warning=False (g_soft=False g_status=skip)
selftest h_result:     soft_period_pass_with_warning=False (h_soft=True h_status=fail)
```
- 切り分け: 親 ff2a357 = exit 0 / e079f50（t_efe1736c「--write-report 実装」）= exit 2 → **同日・同環境での実行比較なので日付依存ではなくコード回帰**。
- 失敗2条件の共通点: **soft期間の期待値（pass-with-warning）に到達していない**。g は `g_status=skip`（g_soft=False）、h は `h_status=fail`。`_g_is_hard()` をスタブして両分岐を検証する設計が、e079f50 の evidence 経路変更でスタブの効かない経路に移った。
- 影響: **回帰ゲート自身が赤**＝以後の「証跡・durability」系の変更をゲートで守れない。t_efe1736c は「selftest全pass」を含む受入基準のまま done 済み（前run コメント1432）。

## 4. dirty=Y の実体と帰属（churn源）
```
$ git status --porcelain | grep -E '\.(py|yaml|sh|js)$'
 M scripts/check_dep_drift.py
$ git diff --unified=0 -- scripts/check_dep_drift.py | head -4
-def check(venv_python: Path, pyproject: Path) -> dict[str, Any]:
+def check(venv_python: Path, pyproject: Path, skip_reverse_check: bool = False) -> dict[str, Any]:   # 逆方向検査の追加 = t_ebbfe4a7 の作業
$ python3 -m py_compile scripts/check_dep_drift.py && echo py_compile OK
py_compile OK
```
- 内容は **t_ebbfe4a7（依存4系統一致ゲート＝逆方向検査の追加）の正当な作業中コード**（+48/-8、17:59）。t_ebbfe4a7 は run #1448 終了時に commit せず blocked になった。
- その残留ファイルを guard が **t_28e11c70 の OWNED と誤帰属** → t_28e11c70 は「実装（07c8cfe・loop_health cap検出）完了＋証跡2種あり＋(a)(b)(e)(g)(j) pass」なのに (d) だけで exit 1。**復活しても同じ壁で再block**する構造。
- **本runでは commit していない**（兄弟カードの未完作業を「ついで直し」すると lost update を再生産するため。SKILL.md 9/25 規律②③）。

## 5. 【要ユーザー対応】(1) 既定host configの deepseek 401 → review/decomposer 全死
```
$ python3 -c "…errors.log 集計…"
total 524 / last 2026-09-25 17:59:37 / last30min 14 件（増加継続）
$ python3 -c "import yaml;d=yaml.safe_load(open('/home/atushi/.hermes/config.yaml'));print(d.get('fallback_providers'), d['auxiliary']['kanban_decomposer']['provider'])"
[] auto
```
- 実害（実測）: t_fe629b9e が review_requested 後 **crashed ×4**（`worker exited cleanly (rc=0) without kanban_complete/block/request_review` と review run の exit 1 が 17:20–18:00 に反復）。t_757b8b5d も #1447 で blocked。
- 推奨アクション: `~/.hermes/config.yaml` に `fallback_providers: [{provider: freellmapi, model: auto}]` を追加し、`auxiliary.kanban_decomposer.provider` / `auxiliary.background_review.provider` を `freellmapi` に明示 → gateway 再起動（t_5490697f の推奨と同一）。
- **おすすめですすすめます（GOで実行します）**。

## 6. 観点別分割検証（5観点・計測バッチ分離）
> 注: 本runは `delegate_task` 非搭載（tool_search で 0 件）。SKILL.md の失敗時代替案どおり**観点ごとの独立計測バッチ**で代替し、1コール一括評価はしていない。

1. **コード品質 6/10** — guard の回帰（§3）＋`scripts/*.bak|backup*` 3件残留。`py_compile OK`／`loop_health bash -n OK`。t_efe1736c の機械生成レポートは pytest 引用が `(exec failed: timed out after 60 seconds)` のまま (a)(b) を通過しており、**引用の実質性が弱い**。
2. **BOT検出リスク 9/10** — 最大セッション15成功（≤20）・深夜0-5時 **0件**・リプライ **0件（381行すべて「リプライ: 無効」）**・多重防止SKIP 2335・ERROR 0。
3. **設計一貫性 5/10** — cap 2系統割れ未解消（4 vs 8）＋OWNED誤帰属（§4）＋条件(j)「不在=skip」と SKILL.md hard 記述の乖離は未修正。
4. **テスト充足 6/10** — `pytest tests/test_loop_health.py tests/test_loop_health_json_contract.py -q` = **8 passed (77.52s)**、guard `write_report roundtrip_ok=True`。ただし **guard 自身の回帰テストが赤**＝ゲートが守れていない。done カードの証跡未追跡が2件（t_6f45dab0 / t_e07dab2a、`git ls-files`=0）。
5. **ライブ計測 9/10** — 出口IP **3/3 相異**（atushi16=219.104.132.236 自宅 / kudou=106.146.24.185 / TankanNotes=126.245.23.121）、zin/inobase1089/toushiwatch は不通＝稼働停止で整合。収集 **1029件**。wifi_watchdog「プロキシ1085生存」復旧0。
```
$ python3 kensho/utils/check_proxies.py
atushi16   1081 → 219.104.132.236 ✅ / kudou 1082 → 106.146.24.185 ✅ / TankanNotes 1085 → 126.245.23.121 ✅ / zin 1084・inobase1089・toushiwatch 1087 → 不通
```
- 16:49 以降の実アクション0は**正常**（`[LIMIT] atushi16: 日次総量上限到達 (75/75)` / kudou 50/50 / TankanNotes 50/50）。停止検知（120min閾値）には抵触しない。

## 7. done カードの事後検査（成果物実在）
```
$ for t in t_efe1736c t_0e402d67 t_6f45dab0 t_e07dab2a; do echo "$t $(git ls-files reports/${t}_verification.md | wc -l)"; done
t_efe1736c 1 / t_0e402d67 1 / t_6f45dab0 0 / t_e07dab2a 0
```
- t_6f45dab0・t_e07dab2a は **done なのに証跡レポートが未追跡**（durability ギャップ、前run申し送りが未解消）。
- t_efe1736c は受入基準「selftest全pass」未達のまま done（§3）。

## 8. 3軸評価
```json
{"evaluation":{"technical":{"score":6,"assessment":"loop_health.sh は有効JSON(score=100)だが、guard --selftest が親ff2a357=exit0/e079f50=exit2 の実行比較でコード回帰と確定し2run連続未修正。t_28e11c70は兄弟ファイルのOWNED誤帰属で(d)のみFAIL、t_a38b99bcは証跡未コミット、t_fe629b9eはcross-task evidence rejected","evidence":"REAL_EXIT=2 vs FF2A357_EXIT=0 / g_soft=False g_status=skip / h_soft=True h_status=fail / 8 passed(77.52s)"},"business_kpi":{"score":9,"assessment":"応募は健全。実アクション175が全稼働垢の日次上限到達による正常終了で、深夜0・リプライ0・ERROR0・出口IP分離3/3を維持","evidence":"follow60/RT58/like57 / 上限 75/50/50到達 / deep-night 0 / SKIP 2335 / 収集1029件"},"cost_efficiency":{"score":5,"assessment":"blocked 2→6 で復活→再block の churn が進行。t_fe629b9e は crashed×4 で iteration を浪費（review死のため終端不能）。running=1 で WIP 余力はあるが、恒久修正（guard回帰・401）が入るまで同型浪費が残る","evidence":"crashed 4/件・blocked 6/running 1/ready 0/done 685・errors.log 524件"},"loop_health":{"score":100,"stagnation_streak":0,"verdict":"healthy"},"self_review_quality":{"valid":true,"notes":"全判定をコマンド+実出力で提示。回帰は親コミット版との実行比較で切り分け、兄弟カードの未コミットファイルには非介入(checkout/commitせず)。修正カード1件のみ起票し、他は申し送りに切替"},"verdict":"conditional_pass","next_steps":["次run: guard --selftest が exit 0 に戻ったか（修正カード t_aa4ee345 の進捗）を確認","default host config 401（要ユーザー）が解消し review run の crashed が 0 になるか","t_28e11c70 の OWNED 誤帰属が解消したか（check_dep_drift.py の commit/帰属修正）","t_6f45dab0・t_e07dab2a の証跡未追跡 2件が commit されたか"]}
```

## 9. 申し送り（critic / worker へ）
1. **guard OWNED 誤帰属**: カード本文にパス文字列があるだけで兄弟の未コミットファイルが OWNED 扱いになる（t_28e11c70 が実例）。判定を「自カードの run が実際に書いたか（mtime × run 期間）」へ寄せるべき。
2. **未コミット残留の常態化**: t_ebbfe4a7 の +48/-8 が working tree に残り、他カードを巻き込んで block を再生産。worker は**終端前に必ず commit**（iteration 残量が少ないと commit 前に落ちる）。
3. **review 全死**: 401 が解消するまで `kanban_request_review` を呼ぶカードは crashed ループに入る → critic は review 依存カードの復活を保留すべき。
4. **プロファイルrepo側の `(l)deliverable_token_exists` 追記が未コミット**（t_a38b99bc のWIPと推定・1行）＝同カードの証跡 commit と同時に終端すること。
5. done カードの証跡未追跡 2件（t_6f45dab0 / t_e07dab2a）の commit（前run申し送りの継続）。

証跡: 本ファイル（QA run15）／修正カード・各コメント／notepad 033ff6065ef7。
