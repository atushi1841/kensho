# applier.py log.write型不一致 — root cause と最小パッチ案

- 日付: 2026-09-19
- 担当: kensho-revenue-worker
- 分野: 応募ロジック診断（**適用はユーザーGO待ち・禁止領域**）
- 関連カード: t_6532c324（提案） / t_d3a934d8（要因分類: log.write型不一致52件63%）

## エビデンス（ログ実測）
```
9/18: 52件 / 9/19(本0時〜): 22件・7logfileに再発
[NG] 'function' object has no attribute 'write' (url=https://x.com/...)
```
orchestrator.py L272 は正しく `LogWriter` を `apply_for_account(key, batch_max, cfg, log, ...)` へ渡す。
エラーは applier.py 内部で `log` が「関数オブジェクト」のまま使われる経路で発生する。

## 根本原因（root cause・特定済み・confidence: 高）

**applier.py:2257 が、LogWriter を要求する関数にローカル関数 `out` を渡している。**

```
applier.py:814  def out(msg: str) -> None:         # ローカル関数（Callable[[str], None]）
applier.py:2256  if tweet_id:
applier.py:2257      _multi_response_record(tweet_id, account_key, cfg, out)   # ← BUG
```

一方 `_multi_response_record` の契約は「`.write()` を持つオブジェクト」：

```
applier.py:446  def _multi_response_record(tweet_id, account_key, cfg, log: Any, state_path=None):
applier.py:507      if log is not None:
applier.py:508          log.write(msg)          # out は関数 → AttributeError
```

`out`（関数）は `.write` を持たないため、閾値に達した成功応募が `AttributeError: 'function' object has no attribute 'write'` を投げる。
これは apply_for_account 内の apply ループの例外ハンドラ (L2418 → L2425 `out(f"[NG] {err_msg} (url={cur_url})")`)
で捕捉され、`[NG] ... write (url=...)` として誤分類エラーになる。テスト（tests/test_applier.py:1274 等）は
`.write()` を持つ `_FakeLog` を渡しており、契約が `.write` オブジェクトであることを裏付ける。

この経路は **2026-09-18 追加の「複数同時刻応答検知（軽量版）」機能**で新設された呼び出しであり、
該当機能の追加時に `out` と `log` を誤って渡したのが発端。全 apply 成功件のうち tweet_id が存在する
応募成立分だけがこのコードを通る（tweet_id 無し＝フォロー限定案件は対象外）。

## 類縁経路（同一バグクラスの確認）
apply_for_account 内の他の LogWriter 受け取りは正しく渡っている（確認済み・要修正なし）：
- L988 / L997 `log=log`（create_account_context / create_browser）→ LogWriter 正しい
- L729 `verify_ip_separation(cfg, log=log)` → 正しい
- L924 / L2444 / L2453 / L2457 / L2262 / L2267 `save_collected_safe(data, account_key, log)` → 正しい
- L894 `_cross_account_proximity_defer(item, account_key, cfg, log)` → 正しい

**問題は applier.py:2257 の 1 箇所のみ。**

## 最小パッチ案（適用は GO 後・禁止領域規定に従い本報告では未適用）

applier.py:2257 の第4引数を `out` → `log` へ変更するだけ（1行）：

```diff
                 if tweet_id:
-                    _multi_response_record(tweet_id, account_key, cfg, out)
+                    _multi_response_record(tweet_id, account_key, cfg, log)
```

根拠:
- `log` は apply_for_account の引数（LogWriter または None）。`_multi_response_record` は L507 で
  `if log is not None` ガードするため None でも安全（`kensho_apply_single.py` 経由でもクラッシュしない）。
- 他経路の全てが `log`（LogWriter）を渡しており、型契約に一致。
- 同じバグクラス（関数 `out` を `.write` 想定先へ渡す）は applier.py 内に他に存在しない（grep 確認済）。

## 検証方針（適用後の確認）
- `_multi_response_record` 呼び出しが閾値到達成功でも AttributeError を投げず `same_campaign_multi` を
  ログ出力できること（既存テスト TestMultiResponse で契約確認済み）。
- 適用後は apply ループの `[NG] ... function object has no attribute write ...` が消失し、
  実応募成功分が誤って error 集計されなくなる。

## 禁止領域ステータス
- kensho/application/** への変更: **未実施（git status 空にて確認）**
- 適用可否の GO はユーザー判断待ち。
