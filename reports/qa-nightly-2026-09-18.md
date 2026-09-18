# QA Nightly Report — 2026-09-18 16:14 (nightly-qa 033ff6065ef7)

## verification_evidence

### ループ健康度（script実測）
```bash
$ bash /mnt/d/Project2/kensho/scripts/loop_health.sh
score=100|ready=0|blocked=0|prio=normal|streak=0|esc=False|skip=False|dirty=Y|bulk=N
```
判定: **healthy**。score=100維持、streak=0で停滞なし。dirty=Yはt_f4698348 SOCKS5編集中（ active work ）。

### 前回QAからの変化
- t_06fdd792: running(53h) → **done** (protocol violation後user対応で回復)
- t_bfb4bd78: running(dirty) → **done** (SeleniumBase CDP完了)
- t_f4698348: **running** (SOCKS5プロキシローテーション実装中)
- t_3dd60265: **running** (JEPX MCP redeploy)
- t_cc979e26: done (非API収益)

### Worker実装検証（t_f4698348: SOCKS5プロキシローテーション）
```bash
$ python -m pytest tests/test_socks_rotation.py tests/test_collector.py -q
============================= 65 passed in 51.86s ==============================
```
```bash
$ git diff HEAD --stat
config.yaml | 7++++++
kensho/scraping/collector.py | 20+++++++++++++++++--
tests/test_socks_rotation.py | 1+
3 files changed, 26 insertions, 2 deletions
```
検証: 実装は最小限・インターフェース互応( common.fetch() と同じ戻り値)。3層選択ロジック(Scrapling>SOCKS5>直接)は正しい。コメントにt_f4698348代替案経緯が明記されている。

### 回帰ゲートテスト（重要発見）
```bash
$ python -m pytest tests/test_regression_gates.py::test_gate_result_column_empty_after_v151 -xvs
FAILED: done(empty result)=2/done(total)=60 since window start, offenders=['t_f91d2729', 't_9f37e5e3']
```
**発見**: v151導入後、2件のタスクがresult空のままdoneされた。
- t_f91d2729: QAタスク（kensho-qa担当）— result未設定
- t_9f37e5e3: workerタスク（kensho-worker担当）— result未設定
**分類**: プロセス問題（done_guardのresult記入忘れ）。コードバグではない。
**対応**: workerにkanban_complete前にresult必須を徹底。QAがresult空doneを検出するゲートは正しく機能。

### Apify API 実測
```bash
$ curl -sS -o /dev/null -w "HTTP=%{http_code}\n" -H "Authorization: Bearer $APIFY_TOKEN" "https://api.apify.com/v2/acts"
HTTP=200
```
Apify API 継続正常。token有効。

### Git状態（コードファイルのみ）
```bash
$ git status --porcelain -- '*.py' '*.yaml' '*.sh' '*.js'
 M config.yaml
 M kensho/scraping/collector.py
 M tests/test_socks_rotation.py
```
未コミットコード3ファイルはt_f4698348のSOCKS5作業中。data/・reports/・downloaded_files/は除外。

## 3軸評価
```json
{
  "evaluation": {
    "technical": {
      "score": 8,
      "assessment": "SOCKS5 rotation実装は正しくインターフェース互換。65テスト合格。回帰ゲートがresult空doneを検出（プロセス改善材料）。",
      "evidence": "pytest 65pass/1fail(回帰ゲート別)/Apify HTTP200/git diff最小"
    },
    "business_kpi": {
      "score": 7,
      "assessment": "SOCKS5回収改善はインフラ強化で間接的収益貢献。Apify API安定。ただしt_f4698348未完了で収集強化は未生效。",
      "evidence": "Apify 200 / loop_health score=100 / running 2件"
    },
    "cost_efficiency": {
      "score": 9,
      "assessment": "既存httpx+SOCKS5基盤の再利用（新規ライブラリなし）。Crawlee互換性問題を回避して低コスト代替案を実装済み。",
      "evidence": "新規依存なし/socks_rotation.py 190行/PROXY_POOL_DEFAULT既存6プロキシ再利用"
    }
  },
  "loop_health": {
    "score": 100,
    "stagnation_streak": 0,
    "verdict": "healthy"
  },
  "self_review_quality": {
    "valid": true,
    "notes": "QAは回帰ゲートのFAILを正しく検出し、プロセス問題とコードバグを区別して報告。SOCKS5実装の評価も具体的エビデンス付き。"
  },
  "verdict": "conditional_pass",
  "next_steps": [
    "t_f4698348: workerにkanban_complete前にresult記入を徹底（回帰ゲート指摘分）",
    "t_f91d2729/t_9f37e5e3: result空のdoneを修正（result追記 or 再完了）",
    "loop_health.shパス: ~/.hermes/profiles/kensho-sweeps/scripts/ではなく/mnt/d/Project2/kensho/scripts/を指定",
    "t_3dd60265: JEPX MCP redeployの完了確認"
  ]
}
```

## 重大な申し送り
1. **回帰ゲートtest_gate_result_column_empty_after_v151 FAIL**: doneでresult空が2件（t_f91d2729 QA / t_9f37e5e3 worker）。プロセス問題—完了時にresultを記入する規律を徹底。
2. **dirty=Y継続**: t_f4698348 SOCKS5コード未コミット。完了時にguard通過を確認。
3. **loop_health.shパス不一致**: skill記載パス(`~/.hermes/profiles/kensho-sweeps/scripts/`)と実際(`/mnt/d/Project2/kensho/scripts/`)が異なる。cronのPATHまたはシンボリックリンクを修正推奨。

## 教訓（notepad保存済）
- loop_health score=100維持。streak=0で停滞なし。dirty=Yはactive work（t_f4698348）
- t_06fdd792/t_bfb4bd78共にdone回復。protocol violationはuser対応で解消
- 回帰ゲートは機能正常—result空doneを正しく検出。ただし検知後の修正はworker責任
- SOCKS5代替案(Crawlee不可→httpx+SOCKS5回帰)は低コストで正しく実装
- Apify API 200継続。healthチェック有効
```