# t_eca89f41 検証レポート — AIチーム改善の事後効果測定（Outcome Review）

タスク: `t_eca89f41`（assignee: worker / 実装担当: kensho-sweeps セッション）
日付: 2026-09-23

## 背景（なぜ必要か）

Verifiability Constraint は「実装前の成功指標（数値）」を義務化しているが、
実装後に「その指標が実際に改善したか」を遡って確認・クローズする工程が無かった。
結果として「テスト通過＝done」で終わり、RT成功率・エラー率などの実KPIが動いたかは
不明のままだった（二重ループ学習の欠落）。

## 実装内容（実施項目3点の対応）

1. **done 時の before/after 指標フィールド**
   - 機械可読 `reports/<task_id>_evidence.json` の `outcome={metric,before,after}` を
     正式フィールドとして採用（ガード `kanban_done_guard.py` 条件(k) が検証）。
   - 新規 `scripts/outcome_review_check.py` が done 済みタスク横断で outcome を集計する。
2. **guard の after 数値必須チェック**
   - ガード条件(k) `outcome_review_state()` が、数値KPIのあるタスクに
     before/after 実測値（evidence.json の outcome、または検証セクションの `before→after` 数値）を要求。
   - 移行猶予 `K_HARD_AFTER=2026-10-01` 以降は欠落で exit 1（BLOCK）。
3. **critic 定期実行への「過去N日 done タスクの実測値再確認」ステップ追加**
   - 新規 `scripts/outcome_review_check.py` を実装（今回の新規成果物）。
   - nightly-critic のスクリプト `kensho-revenue-report.sh` に step 8 として配線し、
     毎時（cron `4baf143523e0`）critic のプロンプトに実測状況が注入されるようにした。
   - 判定規則はガード条件(k) と同一で、ドリフト検出テストで等価性を担保（下記）。

## verification_evidence

### 1) 事後効果測定の定期再確認スクリプト 実行（実データ・122件の done タスク走査）

```bash
$ python3 scripts/outcome_review_check.py --days 7 --reports-dir /mnt/d/Project2/kensho/reports --write-report
### 事後効果測定（Outcome Review / 過去7日 done）
- 対象: done=122件（2026-09-16以降）/ 数値KPIあり=10件
- 実測確認: あり=3件 / 未実測=7件 / KPI非該当=112件
- 実測確認率: 30.0%（目標>50%） → 未達
- 未実測タスク（before/after の数値を追記してクローズすること）:
  - `t_2dccb8b3` 全プロファイルのAPI鍵健全性を応募前に検知する監視を追加（kensho-revenue-worker）
  - `t_18ecf0a5` knshow 502 partial-degradation: port kenkaku v144 page retry（kensho-revenue-worker）
  - `t_9271d891` AIチーム検証の3層化: 構成要素・軌跡・疑似本番の自動ゲート（kensho-worker）
  - `t_f7b0d3bd` 非X応募導線(LINE/Instagram/アプリ/レシート/会員ID)の分類収集を実装し可視化（kensho-revenue-worker）
  - `t_515d0237` QA検証のSectioning化:観点別分割評価で単一パス見落とし防止（kensho-revenue-worker）
  - `t_8da22532` Apify Store SEO改善・未完了3項目（Custom icon/Categories複数選択/version更（kensho-revenue-worker）
  - `t_8bc5e2b4` 公開事業者リスト受託・初期提案セット作成(サンプル100件+3テンプレ)（kensho-revenue-worker）
- 実測済みタスク:
  - `t_2b64cf2c` 検証セクションに before→after 記載
  - `t_d2b1ba39` 検証セクションに before→after 記載
  - `t_9d494bc4` 検証セクションに before→after 記載
- レポート保存: /mnt/d/Project2/kensho/reports/outcome-review-2026-09-23.md
```

→ 実KPIの実測確認率 **30.0%（3/10）** が実測され、目標 >50% に対して未達であることが
自動で可視化された（この事実自体が「事後効果測定の仕組みが動いている」証跡）。

### 2) 自動テスト（11件・ガード規則とのドリフト検出を含む）

```bash
$ python3 -m pytest tests/test_outcome_review_check.py -q -p no:cacheprovider --no-cov
tests/test_outcome_review_check.py ...........                           [100%]
============================== 11 passed in 4.46s ==============================
```

### 3) mypy strict（0 error）

```bash
$ python3 -m mypy scripts/outcome_review_check.py tests/test_outcome_review_check.py --strict
Success: no issues found in 2 source files
```

### 4) critic 定期実行への配線確認（構文＋呼出行）

```bash
$ bash -n /home/atushi/.hermes/profiles/kensho-sweeps/scripts/kensho-revenue-report.sh && echo 'bash syntax OK'
bash syntax OK
$ grep -n 'outcome_review_check' /home/atushi/.hermes/profiles/kensho-sweeps/scripts/kensho-revenue-report.sh
146:python3 "$KENSHO_REPO/scripts/outcome_review_check.py" \
148:  || echo "(outcome_review_check 実行失敗: scripts/outcome_review_check.py を確認)"
```

### 5) 既存ガード（条件(k)）の self-test — 途中で実バグを1件発見・修正

検証中に `--selftest` が FAIL していることを実測（条件(i) hard検証の偽陰性）:

```bash
$ python3 /home/atushi/.hermes/profiles/kensho-sweeps/scripts/kanban_done_guard.py --selftest; echo "EXIT=$?"
selftest i_config_drift: missing_checker_skip=True (i_status=skip)
selftest i_config_drift: drift_detected_fail=True (i_status=fail i_fails=1)
selftest i_config_drift: hard_drift_blocks=False (i_hard=True)
SELFTEST FAILED: guard did not behave as designed (e_push_gap=True d_bleed=True g_durability=True h_result=True i_config_drift=False j_write=True k_outcome=True)
EXIT=2
```

原因: 条件(i) selftest の step3（hard化検証）が、step2 の `finally` で実checkerへ戻した後に
`DRIFT_CHECK_PY` を fake へ再設置していなかったため、実checkerが drift=0 を返し
hard検証が常に偽陰性になっていた（selftest ハーネスのバグ。本体の(in)ゲート判定は正常）。

修正後（同一コマンド）:

```bash
$ python3 /home/atushi/.hermes/profiles/kensho-sweeps/scripts/kanban_done_guard.py --selftest; echo "EXIT=$?"
selftest i_config_drift: missing_checker_skip=True (i_status=skip)
selftest i_config_drift: drift_detected_fail=True (i_status=fail i_fails=1)
selftest i_config_drift: hard_drift_blocks=True (i_hard=True)
SELFTEST OK: (e) unpushed/ghost-hash detection works; (d) task-scoped bleed fix works; (g) evidence durability gate works; (h) result-column gate works; (i) cron-config-drift gate works; (j) evidence.json write+validate round-trip works; (k) outcome-review before/after gate works
EXIT=0
```

→ 条件(k)「outcome-review before/after gate works」を含め全項目 OK。

## Outcome Review（本タスク自身の事後効果測定）

- metric: critic 定期実行に組み込まれた事後効果測定ステップ数（before/after実測値比較の自動再確認）
- before: 0（再確認工程なし＝テスト通過のみで done）
- after: 1（`kensho-revenue-report.sh` step 8 で毎時自動実行・実測確認率を算出）
- 副次実測: 実測確認率 0%（計測不能）→ 30.0%（3/10件で before/after を実測確認・未実測7件を自動列挙）

## 成果物（artifacts）

- `/mnt/d/Project2/kensho/scripts/outcome_review_check.py`（新規・本体）
- `/mnt/d/Project2/kensho/tests/test_outcome_review_check.py`（新規・11テスト＋ドリフト検出）
- `/mnt/d/Project2/kensho/reports/outcome-review-2026-09-23.md`（実行生成レポート）
- `/home/atushi/.hermes/profiles/kensho-sweeps/scripts/kensho-revenue-report.sh`（step 8 配線）

## 申し送り（次アクション）

- 未実測7件のうち、実装系タスク（t_2dccb8b3 / t_18ecf0a5 / t_9271d891 / t_515d0237）は
  evidence.json に `outcome={metric,before,after}` を追記してクローズするのが望ましい。
- 2026-10-01 以降はガード条件(k) が hard 化され、数値KPIタスクで before/after 欠落は done 不可。
