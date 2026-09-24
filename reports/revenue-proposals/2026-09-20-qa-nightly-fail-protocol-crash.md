# QA 検証レポート — 2026-09-20(15時) nightly-qa

- 日付: 2026-09-20 07:13 JST
- ジョブ: nightly-qa (033ff6065ef7)
- タスク種別: 収益化QA検証
- 結果: **conditional_pass**（重大なprotocol violation crash検出）

## 1. ループ健康度

```
score=100 | ready=3 | blocked=0 | running=1 | streak=0 | priority=normal
```

前回(06:29)からのDIFF: `ready 1→3`, `blocked 1→0`。ブロック解消・健康継続。停滞なし。

**ready 3件**: t_515d0237(QA-Sectioning化・worker待ち) / t_8da22532(Apify SEO 3項目) / t_0b0d1647(中古カメラ差益アラート)
**running 1件**: t_8bc5e2b4(公開事業者リスト 初期提案セット) — evidence.json & hash一致を独立検証済み、正常進行。

## 2. pytest失敗の検出（最重要）

```
1 failed, 610 passed, 5 skipped
FAILED tests/test_regression_gates.py::test_gate_protocol_violation_crash
```

**gate: protocol_violation_crash_24h = value 1 (limit 0) FAIL**

- 対象: **t_8da22532**（Apify Store SEO改善・Custom icon/Categories/version、現ready）
- 過去24h に crashed run 20件、うち回収済み19件・**未回収1件（run 808、06:55終了=18分前）**
- error: `worker exited cleanly (rc=0) without calling kanban_complete or kanban_block — protocol violation`
- run metadata: `{exit_code:0, protocol_violation:true, retry_status:"ready"}`

### 異常パターン
同一タスクが計5回クエリされた範囲（run804-808）でもすべて crashed。workerが**毎回終端のkanban呼出を省略して静かに終了** → タスクがreadyへ戻り、dispatcherが再spawn → またcrash。**クラッシュループ**が続いている可能性が高い。

## 3. 3軸評価

```json
{
  "evaluation": {
    "technical": {
      "score": 6,
      "assessment": "他タスクの成果物は実測検証済みで質が高い（t_8bc5e2b4 evidence hash一致・再現完全一致）。ただしt_8da22532でprotocol violation crashが24h内20回おき、worker終端処理が壊れている。テストは1件だけ失敗し回帰ゲートが正しく作動。",
      "evidence": "pytest 610 passed/1 failed; ledger protocol_violation_crash_24h=1; run804-808全てcrashed(rc=0)"
    },
    "business_kpi": {
      "score": 5,
      "assessment": "SEO改善3項目（icon/categories/version）が未反映のためクリック率2.3倍・露出+40%の効果が未獲得。公開事業者リストは受託提案素材として現金化可能性を残す。",
      "evidence": "t_8da22532 ready(未完了); t_8bc5e2b4 ランサーズ受託素材100件+テンプレ3種完備"
    },
    "cost_efficiency": {
      "score": 4,
      "assessment": "t_8da22532の繰り返しspawnはworkerコストを浪費。20回の無駄なクラッシュ→再spawnは処理費の無駄。plugin経由のrate制限は未検証。",
      "evidence": "crashed run 20件(同タスク); 同一エラー2回超=高優先基準に一致"
    }
  },
  "loop_health": {
    "score": 100,
    "stagnation_streak": 0,
    "verdict": "healthy"
  },
  "self_review_quality": {
    "valid": true,
    "notes": "t_8bc5e2b4 のverification.md は$コマンド引用4件・evidence.json sha256一致・自己レビューJSON完備で高品質。アーティファクト6件全実在。"
  },
  "verdict": "conditional_pass",
  "next_steps": [
    "criticにt_8da22532のprotocol violation crash根本調査を高優先で提案させる（同一エラー20回=自動復旧阻害に近い）",
    "worker起動時の終端ガード強化: モデルAPI失敗時もkanban_block/completeを絶対呼ぶ省力化",
    "t_8da22532が元々の作業を実装済みなら、回収runが検証してcompleteへ",
    "t_8bc5e2b4 はworker完了後にQA独立検証済みのため、そのまま成立"
  ]
}
```

## 4. 申し送り

- 【要ユーザー対応】t_8da22532 の protocol violation crash はソフトウェア回帰ゲートで検出済みだが、workerの終端処理欠落が原因らしく、criticの根本調査＋worker起動テンプレ修正が先決。ランサーズ受託の実提出（next手）はユーザー判断待ち。
- おすすめですすめます（GOで実行/対応をお願いします）: t_8da22532 の crash ループ調査を critic → worker で進め、完了タスクを回収してください。

## 5. git状態（コードファイル）

未コミットのコード: `?? scripts/apify_remaining_audit.py / audit2.py / summary.py`（t_8da22532 検証用ワークスニペット、worker作業中）＋ `?? utils/x_link_reader.py`（既知・done対象外）。application/ は未変更（禁止領域のGO待ち22件は手付かずのまま正しい）。
