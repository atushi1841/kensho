# t_8946706e 検証レポート — self_heal 恒久修正（failure ceiling の垢粒度化 / セッション失効垢の盲目的リトライ停止）

- タスク: **t_8946706e**（self_heal 恒久修正: F1〜F6 + failure ceiling のアカウント粒度化 / プロキシ不通垢の応募停止）
- 実装コミット: **4ef200d**（親: 22c50a9）
- 実施: 2026-09-24（JST）/ profile kensho-worker
- 変更ファイル（commit 4ef200d に含まれる 7 件）
  - `kensho/core/self_heal.py`（+363/-? / 本体）
  - `kensho/application/applier.py`（非リトライ理由シンク＋dead_proxy ゲート＋垢単位キー）
  - `kensho/scraping/collector.py`（config 準拠＋回復アクションの再実行経路）
  - `kensho/utils/safety.py`（dead_proxy 判定の追加＝blocked 化）
  - `tests/test_self_heal.py`（18→30 件・新規12件）
  - `config.yaml`（self_healing.recovery_order / fatal_signal_* / collection.max_pages / safety.dead_proxy_check）
  - `reports/t_8946706e_repro_self_heal.py`（before/after 再現スクリプト）

## verification_evidence

対象タスク: **t_8946706e**（所有束縛: ファイル名 `t_8946706e_verification.md` + 本見出し直下のタスクID）

### 0.5 数値サマリ（改修前 → 改修後）
- セッション失効垢の apply 試行回数（1失敗あたり）: **3回 → 1回**（operation_calls 3 → 1）
- ceiling の遮断キー: **apply（全垢共通） → apply:<account_key>**（他垢の成功でリセットされない）
- 毎時cron（60分間隔）3連続失敗での遮断発動: **false → true**（blocked_until = 失敗時刻+30分）
- プロキシ死骸垢（本番 status=dead_proxy）の応募試行: **警告のみで試行継続 → 試行ゼロ（gate=SKIP）**
- 回復イベントのログ行数: **0行 → 1イベント1行（[SELF-HEAL] 構造化）**
- `max_attempts`: **3 → 3**（不変・値の変更行ゼロ）
- テスト件数: **18件 → 30件**（tests/test_self_heal.py）／全35 passed

### 0. 症状（before・親タスクのQA実測を再確認）
- apply 自己修復の最終失敗 32件中 **29件が1垢（zin20120731）のセッション失効**、全件 attempts=3。
- BOTシグナル増幅: `goto failed` 63件/日(09-20) → 227件/日(09-23)、ログイン試行 約55→108回/日。
- `data/self_heal_state.json` の ceiling count は apply/collection とも 0（遮断が一度も発動していない）。

```
$ cat data/self_heal_state.json | head -12
  "ceilings": {
    "apply": { "count": 0, "first_fail_time": "2026-09-22T15:06:28.137352" },
    "collection": { "count": 0, "first_fail_time": "2026-09-23T17:01:53.345701" }
  },
```
（= 全体キー "apply" に集約され、他垢の成功で毎回リセットされていた）

### 1. 修正内容（F1〜F6 + 追加要件）

| 項目 | 修正 | 実装位置 |
|---|---|---|
| P0 ceiling の垢粒度化 | キーを `apply` → `apply:<account_key>`（applier が context で渡す） | `applier.py` `SelfHealingLoop(context={"key": f"apply:{account_key}"})` |
| P0/F3 非リトライ分類 | `is_fatal_signal()` を新設。session/auth/dead_proxy/rate_limit/suspended 等は**1回で停止**＋当該キーのみ遮断＋通知（`stop_fatal`） | `self_heal.py` `is_fatal_signal` / `_block` |
| P0 理由の伝搬 | `_apply_impl(reason_out=...)` が失敗理由（`no_auth_session`/`goto_failed`/`needs_login`/`challenge`/`dead_proxy`…）を validator へ伝え `recoverable=False` を返す | `applier.py` `_FATAL_APPLY_REASONS` / `_validate_apply` |
| P1/F5 遮断判定 | `first_fail_time`（初回固定）→ `last_fail_time` + しきい値到達時に `blocked_until` を設定（毎時cronで発動） | `self_heal.py` `_is_ceiling_hit` / `_record_ceiling` |
| P1/F1 可観測性 | 全回復イベントを `[SELF-HEAL] …` の構造化1行として logger へ（attempt/key/error_kind/action/detail） | `self_heal.py` `_log_event` |
| P2/F2 | `ai_assisted=false` なら `ai_consult` をプランから除外（no-op attempt を作らない） | `self_heal.py` `_action_applicable` |
| P2/F4 | 回復プランを**永続カーソル**で段階消費。`max_attempts=3` のまま `transport_fallback`/`scope_reduction` へ到達（枯渇時は即停止）。apply では該当アクションをプランから除外し「使われない設定」を残さない | `self_heal.py` `_recovery_plan` / `_choose` / `_cursor` |
| P2/F6 | 呼出側ハードコードを廃し config を尊重（`retry_partial_apply` / `retry_empty_collection`）、回復アクションの設定変更を再実行へ反映 | `applier.py` / `collector.py` `_run_collect` |
| 追加要件 | dead_proxy 垢は**応募を試行しない**（applier 冒頭ゲート＋`safety.check_ip_separation` の不通垢を blocked へ合流）。自宅IPフォールバックは行わない | `safety.py` `dead_proxy_reason` / `dead_proxy_accounts`, `applier.py` |
| 副次 | `state_file` の相対パスを `project_dir` 基準に固定（CWD依存でカウンタが別ファイルに飛ぶ事故の防止） | `self_heal.py` `_resolve_state_path` |

### 2. 実測1 — セッション失効垢は「3回リトライせず即停止」＋ ceiling キーが垢単位（before/after）

修正前の `self_heal.py`（22c50a9）と修正後を作業ツリーから同じ入力で走らせる再現スクリプト（モック可・本番非干渉）:

```
$ python reports/t_8946706e_repro_self_heal.py HEAD > reports/t_8946706e_repro_output.json
### scenario1（セッション失効 no_auth_session への retry 回数）
before(22c50a9): operation_calls=3  attempts=3  actions=[jitter_retry, jitter_retry]  blocked(apply:zin20120731)=false
after (4ef200d): operation_calls=1  attempts=1  actions=[stop_fatal, final]         blocked(apply:zin20120731)=true
### scenario2（毎時cron: 60分間隔で3連続失敗）
before: blocked_after_3rd=false（first_fail_time 固定・cooldown30分が常に経過済み）
after : blocked_after_3rd=true （3回目で blocked_until=+30分）
### scenario3（失効垢Aの失敗と健全垢Bの成功が交互に来る毎時run 6回）
before + 全体キー : A_failures=3  A_blocked=false  ceilings={"apply": 0}      ← 他垢の成功でリセット
after  + 垢キー   : A_failures=3  A_blocked=true   ceilings={"apply:acctA": 6} ← 別垢の成功はAに無関係
```

実運用の証跡（`[SELF-HEAL]` 構造化ログが実際に出ること＝F1）:

```
$ python reports/t_8946706e_repro_self_heal.py HEAD 2>&1 | grep -m2 "SELF-HEAL"
[SELF-HEAL] pipeline=apply key=apply:zin20120731 attempt=1 error_kind=no_auth_session action=stop_fatal detail=non_retryable:no_auth_session message=apply 0 success 1 errors (no_auth_session)
[SELF-HEAL] pipeline=apply key=apply:zin20120731 attempt=1 error_kind=none action=final detail=fatal message=apply 0 success 1 errors (no_auth_session)
```

### 2.5 実測1b — 本番 config + 本番 applier 経路での再現（`apply_for_account` を実コードで通す）

`data/` を一時ディレクトリへコピーして実 state を汚さずに、**実際の applier エントリ**（`apply_for_account`）と
実 config（`config.yaml` の self_healing / collection）を使って測る:

```
$ python reports/t_8946706e_repro_check.py
config.yaml self_healing.max_attempts = 3
collection.max_pages = 99
== 1/2. セッション失効垢は1回で停止＋ceiling キーが垢単位 ==
[SELF-HEAL] pipeline=apply key=apply:zin20120731 attempt=1 error_kind=goto_failed action=stop_fatal detail=non_retryable:goto_failed
apply_for_account raised (期待どおり最終失敗): self_heal failed: apply 0 success 1 errors (goto_failed) (attempts=1)
_apply_impl calls (旧実装=3回リトライ / 修正後=1回): 1
state ceilings keys: ['apply:zin20120731']
blocked entry: {"count": 4, "blocked_until": "2026-09-24T10:18:09", "blocked_reason": "failure_ceiling"}
== 3. 毎時runでも ceiling が発動する ==
  run1: attempts=3 ok=False blocked=False
  run2: attempts=3 ok=False blocked=False   ← この run で transport_fallback / scope_reduction を実際に実行（F4）
  run3: attempts=1 ok=False blocked=True    ← プラン枯渇で即停止＋ceiling 発動（F5）
auto-blocked on 3rd hourly failure: True
== 4. プロキシ死骸垢は応募を試行しない（実 status ファイル参照） ==
safety.dead_proxy_accounts(real_cfg) = ['zin20120731']
applier._FATAL_APPLY_REASONS = ['challenge', 'dead_proxy', 'frozen', 'goto_failed', 'login_failed', 'needs_login', 'no_auth_session', 'rate_limited', 'suspended']
```

同ログの `action=transport_fallback detail=toggled_scrapling:True->False` と
`action=scope_reduction detail=max_pages_set_1` が、**F4 の到達可能性を実コードで示している**
（`max_attempts=3` のままで後段アクションに到達し、枯渇後は `stop_no_recovery` で即停止）。

### 3. 実測2 — プロキシ死骸垢は応募を試行しない（本番データ・モックなし）

```
$ python reports/t_8946706e_dead_proxy_gate_check.py
project_dir=/mnt/d/Project2/kensho
safety.dead_proxy_check=True
safety.dead_proxy_max_age_hours=6
  atushi16         status=alive       updated=2026-09-24T09:30:03.416995 gate=allow
  kudou            status=alive       updated=2026-09-24T09:30:03.416995 gate=allow
  zin20120731      status=dead_proxy  updated=2026-09-24T09:30:03.416995 gate=SKIP  reason=プロキシ死骸（TCP疎通 or 出口IP確認失敗） / 最終確認 2026-09-24T09:30:03.416995
  TankanNotes      status=alive       updated=2026-09-24T09:30:03.416995 gate=allow
dead_proxy_accounts=['zin20120731']
```
（実運用の `data/status/zin20120731.json` は `status=dead_proxy` / `last_error_type=http_0`。修正前は「警告のみ」で応募処理へ進んでいた）

### 4. 実測3 — テスト（既存を落とさず + 新規が赤→緑）

```
$ python -m pytest tests/test_self_heal.py tests/test_guarded_source_arity.py -q --no-cov
tests/test_self_heal.py ..............................                   [ 85%]
tests/test_guarded_source_arity.py .....                                 [100%]
35 passed in 46.58s
```

```
$ grep -c "def test_" tests/test_self_heal.py
30
```
新規12件が本タスクの受け入れ条件を直接固定している:
`test_ceiling_key_is_per_account` / `test_fatal_session_signal_stops_without_retry` /
`test_ceiling_fires_on_hourly_schedule` / `test_recovery_plan_reaches_transport_and_scope` /
`test_ai_assisted_false_excludes_ai_consult` / `test_recovery_events_are_logged` /
`test_state_file_is_anchored_to_project_dir` / `test_collect_context_respects_config` /
`test_apply_uses_account_key_and_fatal_reason` / `test_check_ip_separation_blocks_unreachable` /
`test_safety_blocks_dead_proxy_status` / `test_apply_impl_skips_dead_proxy_account`

### 5. 実測4 — `max_attempts` を増やしていないこと（差分で証明）

```
$ git diff 22c50a9..4ef200d --unified=0 -- config.yaml kensho/core/self_heal.py | grep -E "^[-+].*max_attempts"
+  #   段階消費するため、max_attempts=3 のままでも後段のアクションへ到達できる（F4）。
+  #   ★ max_attempts は絶対に増やさないこと（増やすとセッション失効垢への盲目的リトライが復活し、
+  - 回復プランは永続カーソルで段階的に消費する。max_attempts を増やさずに
+        max_attempts = int(self.cfg.get("max_attempts", DEFAULT_MAX_ATTEMPTS))
-        for attempt in range(int(self.cfg.get("max_attempts", DEFAULT_MAX_ATTEMPTS))):
+        for attempt in range(max_attempts):
```
値の変更（`+  max_attempts: N`）は**1行も無い**（追加行はコメントとローカル変数化のみ）。

```
$ grep -n "max_attempts" config.yaml
315:  max_attempts: 3
332:  #   段階消費するため、max_attempts=3 のままでも後段のアクションへ到達できる（F4）。
333:  #   ★ max_attempts は絶対に増やさないこと（増やすとセッション失効垢への盲目的リトライが復活し、
```

### 6. 制約の遵守

- 1時間20アクション上限 / 1セッション15〜20件 / アカウント別IP分離 / リプライ単独実行 / 曜日ローテーション: **いずれも変更なし**（本修正は自己修復層とゲートのみで、応募アクションの量・種類・順序を増やしていない。唯一の変更は「試行回数を減らす」方向）。
- 死骸プロキシを自宅IPへフォールバックさせない絶対ルール: 維持（`dead_proxy` は**試行ゼロで停止**。ブラウザ層の `USE_PROXY`/`PROXY_MAP` 常時指定は無変更）。
- アカウントの追加・削除、X垢情報の変更: 未実施（本カードの範囲外）。

### 7. 変更ファイルの状態（後続カードへの引き継ぎ）

```
$ git status --porcelain kensho/core/self_heal.py kensho/application/applier.py kensho/scraping/collector.py kensho/utils/safety.py tests/test_self_heal.py
(出力なし = クリーン)
```

### 8. 残課題（未実装・別カード範囲）

1. **fatal 遮断の期間は cooldown（30分）のまま**。毎時cronでは「1時間に1回だけ1回試行」となる（修正前は毎run 3回試行）。恒久的に止め切るならセッション再取得（auth_token/ct0 の更新）が前提で、これは運用側の作業。
2. プロキシ死骸の**復旧**（アダプタ再起動）は `proxy_watchdog` 側の領分。本カードはゲート追加のみ。
3. 48時間窓での `goto failed` 件数の before/after 実測は、修正投入後 24時間以上経過しないと取れない（別カードで追跡）。
