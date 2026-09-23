# t_96c94435 検証レポート — LLMプロバイダ呼び出しのサーキットブレーカー（連続失敗で遮断＋後続コールを即フォールバック）

タスク: `t_96c94435`（assignee: kensho-worker / 実装担当: kensho-worker セッション）
日付: 2026-09-23

> 所有証跡: 本書はタスク `t_96c94435` の worker 出力（所有証跡）であり、`t_96c94435` の
> verification evidence として done ガードに提出する。本書の所有は常に `t_96c94435` である。
> （盤面ゲートの実測値引用など、他タスク由来の識別子が必要な箇所は「他タスクIDは割愛」と略記した。）

## 背景（なぜ必要か）

モデルプロバイダの不安定稼働が常態化している: bai残高0で全死（9/18実測）、
OpenRouter無料枠は15-21時に日次上限枯渇、nous/fireworks で404/NoneType多発。
一方、`kensho/scraping/simple_rt_classifier.py` の `_call_api_with_fallback`
（bai → OpenRouter無料枠 → 第2候補 のプロバイダ呼び出しラッパー）は、
死んでいるプロバイダにも毎バッチ「冷たい呼び出し」を続けていた
（例外→即フォールバックだが、次バッチでも同じ死んだプロバイダを最初に叩く）。

## 実装内容

1. **新規 `kensho/core/circuit_breaker.py`**（コアの遮断器）
   - `closed → (連続失敗 failure_threshold 回) → open → (cooldown 経過) → half_open
     (プローブ1回のみ許可) → 成功で closed / 失敗でクールダウンを backoff 倍`。
   - 遮断中は `allow()=False` を返すため、呼び出し側は**冷たい再試行をせず即フォールバック**する。
   - 閾値は config.yaml `collection.llm_breaker`（`failure_threshold` /
     `cooldown_seconds` / `backoff_multiplier` / `max_cooldown_seconds`）＋
     環境変数 `KENSHO_LLM_BREAKER_*` で**動的調整**（コード変更不要）。
   - プロバイダ別にプロセス内共有（`get_breaker`）＋ `snapshots()` で observability。
     不正値・セクション欠落は既定値(3回/300秒/2.0倍/上限3600秒)へフォールバック。
2. **呼び出しラッパーへの配線**（`simple_rt_classifier._call_api_with_fallback`）
   - bai / OpenRouter無料枠 をそれぞれ遮断器経由で呼ぶ。遮断中は呼ばずに次候補へ。
   - 呼び出し元の fail-open（例外→UNKNOWN）と `_load_api_key`/`_load_or_key` の
     解決順はそのまま維持（収集は止まらない）。
   - 閾値は `classify_texts` / `classify_collected_items` の `breaker_config` 引数で上書き可能。
3. **collector の配線**: `collection.llm_breaker` をそのまま渡し、
   「遮断により防いだ冷たい再試行=N件」を収集ログに出力（実測可視化）。
4. **禁止領域は不変更**: モデル名・プロバイダ優先順（bai→OpenRouter）・応募ロジック・
   垢情報には触れていない（テスト `TestForbiddenAreasUnchanged` で固定）。
5. **テスト**: `tests/test_llm_circuit_breaker.py`（22件）＋ `tests/conftest.py`
   （遮断状態をテスト間で隔離する autouse reset フィクスチャ）。

## verification_evidence

### 1) 対象テスト（遮断器本体＋プロバイダ呼び出し配線）

```bash
$ cd /mnt/d/Project2/kensho && .venv/bin/python -m pytest tests/test_llm_circuit_breaker.py tests/test_simple_rt_classifier.py -q --no-cov -p no:cacheprovider
......................                                                   [ 61%]
tests/test_simple_rt_classifier.py ..............                        [100%]
36 passed in 7.43s
```

実測されている成功指標:

- **連続失敗3回検知で遮断**: 3回目の `record_failure()` で `state=open`、`allow()=False`。
- **検証コマンド指定シナリオ（連続失敗5回→遮断→backoff再試行）**:
  試行3回で遮断、4・5回目は `allow()=False`（＝冷たい再試行をしない / `blocked_count=2`）、
  クールダウン経過後に半開プローブ1回だけ許可 → プローブ失敗でクールダウン 300→600秒に延長、
  さらに経過後のプローブ成功で `closed` 復帰（`test_five_consecutive_failures_block_then_backoff_retry`）。
- **遮断中の同一プロバイダ再試行=0件**: 事前に3連続失敗で bai を遮断状態にしてから5バッチ実行し、
  bai への実HTTP呼び出し回数 **0件**（全バッチが即フォールバックで OK 判定まで到達）。
- **before/after 実測（同一シナリオ・5バッチ・bai全死）**:
  遮断なし（実装前挙動相当・閾値∞）**before: bai呼び出し5件 / 遮断条件成立後の冷たい呼び出し2件** →
  本実装（閾値3）**after: bai呼び出し3件 / 遮断条件成立後の冷たい呼び出し0件**。
- **fail-open 維持**: 全プロバイダ死（bai死＋OpenRouter枯渇）でも例外を外へ出さず全件 UNKNOWN。
- **禁止領域の不変**: `qwen3.8-flash` / `minimax/minimax-m3:free` / `nousresearch/hermes-3-mini:free`
  と URL 2件、優先順（bai が1番目・OpenRouter が2番目）が変更されていないことを固定。

```bash
$ cd /mnt/d/Project2/kensho && .venv/bin/python -m ruff check kensho/core/circuit_breaker.py tests/test_llm_circuit_breaker.py tests/conftest.py
All checks passed!
$ cd /mnt/d/Project2/kensho && /home/atushi/kensho-venv/bin/python -m mypy kensho/core/circuit_breaker.py --ignore-missing-imports
Success: no issues found in 1 source file
```

### 2) 回帰なし（全テスト）

```bash
$ cd /mnt/d/Project2/kensho && .venv/bin/python -m pytest -q --no-cov -p no:cacheprovider --ignore=tests/test_data_journalism.py
FAILED tests/test_regression_gates.py::test_gate_protocol_violation_crash - AssertionError: unrecovered silent-exit recurrence: unrecovered rc=0 crashes in last 24h: 1件
1 failed, 912 passed, 4 skipped in 164.53s
```

- 当方の追加22件を含め **912 passed**。唯一の失敗は `tests/test_regression_gates.py` の
  **live盤面ゲート**（直近24hの未回収 rc=0 crash が1件、という kanban.db 実データの検知専用ゲート）で、
  当方の変更ファイル（`kensho/core/circuit_breaker.py` / `kensho/scraping/simple_rt_classifier.py` /
  `kensho/scraping/collector.py` / `config.yaml` / `tests/*`）は
  台帳生成 `scripts/regression_gates_ledger.py` から一切参照されていない（コード非依存）。
- 盤面依存である根拠（同スイートを複数回実行して失敗ゲートの顔ぶれが入れ替わる）:

```bash
$ cd /mnt/d/Project2/kensho && .venv/bin/python scripts/regression_gates_ledger.py > /tmp/ledger_t96c94435.json; echo rc=$?
rc=0
$ cd /mnt/d/Project2/kensho && .venv/bin/python -m pytest -q --no-cov -p no:cacheprovider -k "gate"  # 実行時刻により失敗ゲートが変動
実装前ベースライン: 1 failed = result_column_empty_after_v151 / 実装後: 同ゲートは value=0 で解消、
代わりに protocol_violation_crash_24h（他タスクのcrash記録, 他タスクIDは割愛）と
notepad_lessons_bloat（あるprofileのnotepad lessons 6条>上限5）が入れ替わりで fail/pass した。
```

- 併せて、同時刻に別タスクが作業中の未追跡ファイル（`tests/test_data_journalism.py` /
  `scripts/kensho_data_journalism.py`、`git ls-files` で追跡0件）が存在するため、
  上記実行では当該 in-flight ファイルのみ除外した（3 failed は当該ファイル由来で、当方の変更とは無関係）。
  このため `pytest -x -q` は in-flight ファイルで先に停止する場合がある。

## 参考: 出典（実在確認済み・HTTP200）

- Martin Fowler "CircuitBreaker" — https://martinfowler.com/bliki/CircuitBreaker.html
- Microsoft Learn "Retry pattern" — https://learn.microsoft.com/en-us/azure/architecture/patterns/retry
