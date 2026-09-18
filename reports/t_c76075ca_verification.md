# t_c76075ca 検証レポート — Apify健康度チェック追加で test_revenue_collect 3件FAIL → モック契約更新

## 対応内容
commit `45f9349`（Apify API 404回復力強化）で `fetch_apify_pricing()` 先頭に
`check_apify_health()`（requests.get 2本消費）が追加されたが、既存の
`tests/test_revenue_collect.py` は固定長 `side_effect` リストを渡すため、health が
先に2本消費 → 本命の actor 取得が StopIteration → 例外 → `result={}` で恒常FAIL。
本カード t_c76075ca は**テスト側のみ**修正し、本番コードは触らない。

### 修正内容（tests/test_revenue_collect.py）
1. `TestFetchApifyPricing._isolate_cache` と `TestV94FetchPartialResilience._isolate`
   （両者 autouse fixture）に `monkeypatch.setattr(krc, "check_apify_health", ...)` で
   status="ok" を固定 ← side_effect 長に依存しない robust な形。
2. 新クラス `TestApifyHealthGate` を追加（3本）:
   - `test_down_uses_cache` — health=down → requests.get を呼ばず 24h内キャッシュへ早期フォールバック
   - `test_down_without_cache_returns_empty` — down + キャッシュ無し → {} かつ requests 未呼
   - `test_degraded_continues_fetch` — degraded（補助エンドポイント不調）→ 本命 fetch 継続

## 本番コード無変更の確認
```
$ git diff --name-only
tests/test_revenue_collect.py
```
や `data/*.json`・`reports/*.md` のみ変更（runs/遭遇時のデータ・報告系。本番ソースは touch していない）。
scripts/kensho_revenue_collect.py は diff に出現しない。

## verification_evidence
（t_c76075ca 検証 / 本カード t_c76075ca の証跡。下記は実測レポート。残存 failure の帰属確認で別カードに言及する）

```
$ python3 -m pytest tests/test_revenue_collect.py -q --no-cov -k "ApifyPricing or PartialResilience or ApifyHealthGate"
tests/test_revenue_collect.py .........                                  [100%]
======================= 9 passed, 49 deselected in 1.07s =======================
```

```
$ python3 -m pytest tests/test_revenue_collect.py -q --no-cov
tests/test_revenue_collect.py .......................................... [ 72%]
................                                                         [100%]
============================== 58 passed in 1.87s ==============================
# 受入基準1「55 passed / 0 failed」を上回る 58 passed（3件新規含む）/ 0 failed
```

```
$ python3 -m pytest -q --no-cov   # 全体
3 failed, 763 passed, 6 skipped in 129.39s (0:02:09)
# FAILED tests/test_regression_gates.py::test_gate_result_column_empty_after_v151  ← 許容
# FAILED tests/test_regression_gates.py::test_gate_checkpoint_on_exhaustion        ← 許容
# FAILED tests/test_regression_gates.py::test_gate_protocol_violation_crash        ← 別カードで対応（t_455add05）
```

## 全 body 3件の解消確認（受入基準1が定める本件由来3件 / t_c76075ca）
QA 検出時（21:20）は以下が FAIL だったが、現在は全て PASS:
- `TestFetchApifyPricing::test_uses_last_entry_as_active_price` → PASS
- `TestV94FetchPartialResilience::test_one_timeout_keeps_other_results` → PASS
- `TestV94FetchPartialResilience::test_success_writes_cache` → PASS

## 残存 failure の帰属（全 suite）
- `test_gate_result_column_empty_after_v151` / `test_gate_checkpoint_on_exhaustion`
  → 受入基準2で「許容」の回収ゲート2件。
- `test_gate_protocol_violation_crash` は受入基準対象外の**新規**発生で、本カード変更に
  起因しない。証跡: gate detail = `{'t_455add05': 1}`。
  t_455add05（DeepSeek 401: OpenRouter :free切替, p1）は run 752(20:58)/753(21:01) の
  2回とも rc=0 silent exit（protocol violation, 未回収 crash）で status=ready のまま
  停滞。これは本カードのモック契約更新とは無関係の別カード事象であり、本カードの
  スコープ外（修正は本番 config.yaml の model 切替等が必要で、別カードで対応すべき）。
