# nightly-qa 検証レポート 2026-09-23 23:45（v3）

担当: kensho-revenue-qa cron `033ff6065ef7`（観点別分割検証つき）

## 0. ループ健康度（最優先）
- `loop_health.sh` → **score=100 / streak=0 / escalation=false / priority=normal / skip_fast=false** → **healthy**
- ボード実測（sqlite直読み）: ready=10 / todo=3 / running=2 / blocked=0 / done=600
- monitor差分: ready 9→11（=ready+todo換算。実readyは8→10で、9/23中に新規2件 t_b64c35ea・t_8290ea09 が追加されたため）
- 幽霊assignee: `assignees` 全件 ON DISK=yes（0件）。runningワーカー2件は pid実在（t_0b949bda=3568637 / t_8158cb49=3656947）

## 1. 前回申し送りの履行確認（エビデンスチェック）
| 前回申し送り | 実測結果 |
|---|---|
| worker収益実装（ダッシュボード鮮度＋整合性監視） | **実装済み・push済み**。453c248/fa78fd3 は `git merge-base --is-ancestor` で origin/main 内を確認（ahead/behind=0/0） |
| `kensho-collect-only.sh` の毎時再生成 | プロファイル側 `scripts/kensho-collect-only.sh:45-47` に再生成ブロック実在・`bash -n` OK |
| `kensho-daily-health-check.sh` の整合性チェック統合 | `DASH_CHECK` 上書き可（19-26行）で実装・`bash -n` OK |
| 収益ダッシュボードの正しさ | **独立再現**: `business-dashboard-count.sh` → ✅ dashboard=478, live=478 / ✅ Apifyアクター 25=25 / EXIT=0 |
| 毎時再生成の実効性 | **実走検証**: `kensho_revenue_dashboard.py` → 「✓ revenue-status.html 生成完了 (22 entries)」EXIT=0、mtime 22:56→23:20 更新、直後の再チェックも 478=478 で整合 |
| 申し送り「21:00収集の長時間化」 | **実在・悪化**。pid 3275009 が 9,567秒（2h39m）稼働継続中（23:45時点・KCLUB ページ18走査中）。ただし後続スロット欠落は訂正: 収集cronは `0 3,9-21` なので 22/23時は元々非スケジュール。失われるのは 3:00 スロットのみ。**指摘済みカード t_b64c35ea が起票済み**（実行時間上限＋部分保存） |

## 2. 【解決】前回notepadの異常「100件が同一時刻05:30:39Zスタンプ」— 書込経路を特定
**結論: 外部書込でも汚染でもない。`scripts/recover_applied_from_audit.py` のフォールバックが、cron `kensho-daily-applied-recover`（毎時:30）の1回の実行で100件を同一秒スタンプしたもの。**

実測:
```
$ grep -rl "2026-09-23T05:30:39" data/ | head -3
data/backups/collected.json.20260923_183007.bak
$ python3 /tmp/qa_applied_probe.py
TS含む件数(アカウント別): {'kudou': 19, 'atushi16': 27, 'zin20120731': 31, 'TankanNotes': 14, 'inobase1-4': 5, 'royalkensho': 4}
TS値の種類: {'2026-09-23T05:30:39Z': 100}
applied書式分布: {'isoformat(マイクロ秒)': 469, 'Z形式(秒精度)': 1091}
$ ps -eo pid,etimes,cmd | grep collect-only   # 21:00収集が9,567秒継続中（別件）
$ hermes cron list | grep -A7 kensho-daily-applied-recover
Schedule:  30 * * * *   Last run: 2026-09-23T23:31:17+09:00  ok
```
コード根拠: `scripts/recover_applied_from_audit.py:128,134,140,165,169,173`
```python
ap[ac] = rt_ts_val if rt_ts_val else f"{datetime.now().isoformat(timespec='seconds')}Z"
```
- audit側にtimestampがある場合は本物の値が入る。100件は `follow_state.json` 由来のフォールバック経路（=timestampが存在しない）で、`datetime.now()` が1ループ内で同一秒に収束したため全て同値になった。**復元条件自体は「audit/follow_stateに成功記録がある」ものだけなので、偽の応募済み付与ではない。**

### 副次バグ（新規発見・これが本体）: JSTを「Z（UTC）」と誤ラベル
```
$ date; date -u; python3 -c "import datetime;print(datetime.datetime.now().isoformat(timespec='seconds'))"
Wed Sep 23 23:39:45 JST 2026 / Wed Sep 23 14:39:45 UTC 2026 / 2026-09-23T23:39:45
$ python3 -c "現行(バグ): ...isoformat(timespec='seconds')+'Z' => 2026-09-23T23:39:45Z / 修正案A(UTC): 2026-09-23T14:39:45Z / 修正案B: 2026-09-23T23:39:45+09:00"
```
`datetime.now()` はローカル（JST）を返すのに末尾へ `Z`（=UTC）を付けるため、**+9時間ずれた「未来のUTC時刻」**が書かれる。実害の経路:
- `kensho/application/applier.py:411-422` `_check_cross_account_proximity` は `fromisoformat(val)` の aware 判定で `now_cmp - other_dt <= 6h` を評価する。未来日時は差が負になり無条件で「近接」判定 → **他垢の提案88 DEFER（4〜8hスキップ）を誤発火**しうる。
- 実測のXPROX件数は 9/21=439 / 9/22=235 / 9/23=317 で**明確なスパイクは無し**（誤発火は実在しうるが支配的要因ではない、と正直に記載）。日付跨ぎ（15:00 JST以降のスタンプ）では日付が1日ずれる。
- applied内に書式が2種混在（Z秒精度1,091 / ローカルマイクロ秒469）しており、時系列比較・監査の信頼性が落ちている。

### Verifiability Constraint 準拠の修正案（次criticの提案候補）
- ①成功指標: 修正後に書かれる復元スタンプの「実UTCとの差 ≤ 60秒」かつ `applied` 内の書式が1種に統一（`python3 -c` でサンプル突合）
- ②検証コマンド1行: `cd /mnt/d/Project2/kensho && python3 -c "import json;d=json.load(open('data/collected.json'));print(sorted({v[-1] for it in d['collected'] for v in (it.get('applied') or {}).values() if isinstance(v,str)}))"`
- ③失敗時代替: `Z` を付けずローカル時刻＋明示オフセット（`astimezone().isoformat()`）へ変更し、既存Z値は読み取り互換のまま据え置く（データ一括書換はしない）
- 修正内容: 6箇所を `datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")` へ置換
- **バックログ上限（ready=10）に達しているため、本レポートではカード化しない**。次criticの提案候補としてnotepadに記録（ready≤9になった時点で起票）

## 3. 全テスト（実測）
```
$ /home/atushi/kensho-venv/bin/python -m pytest -x -q
760 passed, 1 failed, 6 skipped in 137.01s
FAILED tests/test_regression_gates.py::test_gate_protocol_violation_crash
  unrecovered rc=0 crashes in last 24h: {'t_8e1e4934': 1} (raw crashed runs=36, recovered=35 excluded)
```
- 実体あり（ゲート偽陽性ではない）: t_8e1e4934 は `worker exited cleanly (rc=0) without calling kanban_complete or kanban_block` で run #994/#996 の2回クラッシュ（eventsに protocol_violation pid=3336589 exit_code=0 が記録）。
- 当該カードは現在 todo（parents=t_96c94435[ready]/t_0b949bda[running] の完了待ち）。**親2件がdoneになるまで再dispatchされないため、再クラッシュは構造的に止まっている**（前回notepadの「parents化で自動復帰」設計どおり）。
- 恒久対策は ready の t_02a5afc4（終端kanban呼出しの強制: protocol violation 75件/日→10件未満）が担当。重複提案はしない。

## 4. 観点別分割検証（5軸・個別評価）
| 観点 | score | 根拠（実測） |
|---|---|---|
| コード品質 | 8/10 | 454c248系の実装は `bash -n` OK・報告書に実測ログ・秘密情報なし。ただし修正対象が非git管理のプロファイル側scriptsのため、git上の変更は報告書のみ（`git show --stat 453c248` = 1 file, 51 insertions）で追跡性が弱い |
| BOT検出リスク | 7/10 | 本日の垢別最大16件/時（上限20未満）・最小間隔6〜9秒・5秒未満=0で機械的には安全。ただし `scripts/audit_bot_safety.py` が 9/22分で **kudou 初動stdev10.6分 / TankanNotes 初動stdev13.6分・件数CV0.02** を規則性シグナルとして検出（バッチ開始時刻・件数の規則性）=中優先の残存リスク |
| 設計一貫性 | 9/10 | 毎時再生成は既存 `kensho_revenue_dashboard.py` を呼ぶだけで新規経路なし。整合性監視は既存Telegram watchdog相乗り（新規cron作成ゼロ）で9/14の重複事故と同型の再発を回避 |
| テスト充足 | 7/10 | 収益側は fixture で ✅/❌ 両分岐を実測。ただし `kensho-collect-only.sh` 全体の実走はflock保持中で未実施（worker自身が限界を明記）。今回QAが生成器単体の実走＋チェッカー再現で補完した |
| ライブ計測 | 8/10 | ダッシュボード478=478一致、21:00収集が2h39m継続（t_b64c35ea で対処中）、zin20120731 は 9/18以降 last_success 無し（proxy 1084死）で垢単位の停止が継続 |

前回比の変化: ①スタンプ異常の原因が「不明」→「特定済み（+副次バグ特定）」 ②収益ダッシュボードの主張をQAが独立再現（478=478、生成器実走OK） ③ready 8→10 でバックログ上限に到達。

## 5. 3軸評価
```json
{"evaluation":{"technical":{"score":8,"assessment":"worker収益実装は独立再現で検証済み(478=478・生成器実走OK)。残る技術的負債はapplied復元の時刻誤ラベルとworker終端call欠落(t_8e1e4934)の2件。","evidence":"business-dashboard-count.sh EXIT=0 ✅478=478 / revenue_dashboard.py EXIT=0 mtime更新 / pytest 760pass 1fail / recovered_applied_from_audit.py:128,134,140,165,169,173"},"business_kpi":{"score":7,"assessment":"応募は本日279成功(3垢)・日次上限到達で正常終了、深夜帯スキップも設計どおり。ただしzin20120731は9/18以降停止のままで4垢中1垢が稼働せず、収益機会を恒常的に失っている。","evidence":"audit集計: atushi16=90/kudou=85/TankanNotes=104、19時間帯以降の新規成功なし(上限+深夜ガード)、zin last_success=2026-09-18T07:59:21Z"},"cost_efficiency":{"score":10,"assessment":"有料API未使用・bai非課金継続。復元cronは毎時:30のno_agentスクリプトのみで追加コストなし。","evidence":"loop_health skip_fast=false / 新規cron追加なし(既存経路へ相乗り)"}},"loop_health":{"score":100,"stagnation_streak":0,"verdict":"healthy"},"self_review_quality":{"valid":true,"notes":"前回notepadの未解決事項(スタンプ異常)をコード行レベルまで特定し、推定で終わらせず実測コマンドで裏取りした。一方で誤発火の実害はXPROX件数がスパイクしていないことを確認し過大評価を避けた。","verdict":"conditional_pass"},"verdict":"pass","next_steps":["次critic: applied復元のJST→Z誤ラベル修正を提案化(ready≤9になった時点で起票)","t_8e1e4934は親2件完了まで待機(再dispatchしない)","21:00収集の2h39m継続はt_b64c35eaで進行中","【要ユーザー対応】zin20120731 proxy死の復旧判断"]}
```

## 6. 申し送り
1. **【中】applied復元の時刻誤ラベル**（上記2節）: `recover_applied_from_audit.py` 6箇所。修正案・成功指標・検証コマンド・失敗時代替を本レポートに記載済み。ready=10のためカード化は見送り。**次criticの提案候補（最優先）**。
2. **【中】`kensho-apply-stall-check` が2重登録**: `8b591344b267`（deliver=telegram:8510166694）と `239b27112e9e`（deliver=origin）が同一Schedule(`*/30 * * * *`)・同一Scriptで並走。9/14の重複no_agent事故と同型。片方の削除はcron構成変更のため単独実行せず、critic判断へ委譲（実行48回/日の重複は読み取り専用チェックのため実害は小）。
3. **【中】BOT規則性シグナル（9/22分）**: kudou 初動stdev10.6分・TankanNotes 初動stdev13.6分/CV0.02。バッチ開始時刻と件数の規則性は検出リスク要因。既存カードなしのため提案候補。
4. **【継続】t_8e1e4934** は親2件（t_96c94435/t_0b949bda）完了まで待機。テストゲートのFAILはこの1件のみで、ゲート自体は正しく機能（偽陽性ではない）。
5. **【要ユーザー対応】zin20120731 の proxy(1084) 死が 9/18 から6日目**。4垢中1垢が応募ゼロ。
   - 推奨アクション: ①当該プロキシ経路の復旧可否を確認 → 復旧不能なら `config.yaml` の zin をコメントアウトして「死垢を4垢構成から外す」（=応募停止の明示化）②復旧する場合はプロキシ再接続後に `cd /mnt/d/Project2/kensho && /home/atushi/kensho-venv/bin/python -m kensho.utils.check_proxies`（実在確認済: `kensho/utils/check_proxies.py:249` に `__main__`）で出口IP分離を再確認。
   - **おすすめですすめます（GOで実行/対応をお願いします）**（垢情報変更にあたるため自動実行しません）

## 7. コード衛生
```
$ git status --porcelain | grep -E '\.(py|yaml|sh|js)$'
?? scripts/agent_span_emit.py    （t_8158cb49 が稼働中・他人のWIP）
?? scripts/agent_span_report.py  （同上）
?? scripts/kensho_data_journalism.py （t_0b949bda が稼働中・他人のWIP）
?? tests/test_agent_span_emit.py / tests/test_data_journalism.py（同上）
```
→ 稼働中2タスクの作業中ファイルであり、QAは触らない（9/16の「兄弟タスクの作業を破壊するな」教訓に従う）。QA自身は本レポート1件のみを追加。
