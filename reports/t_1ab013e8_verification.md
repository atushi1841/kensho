# t_1ab013e8 検証レポート（QA nightly-qa run13 / 2026-09-25 16:2x JST）

カード: `t_1ab013e8` `[ループ衛生・高] test_revenue_collect の恒常赤: TestV94UnknownBilling が PRICING_CACHE 未隔離で実キャッシュ混入（actors_unknown 0==1）→ 1行修正で緑`

判定: **受入基準は HEAD で充足済み（再実装不要）**。収益化Worker の 15:52 申し送りを QA が独立実測で追認した。

## verification_evidence

### 1. 対象テストの実測（QA実行）

```
$ /home/atushi/kensho-venv/bin/python -m pytest tests/test_revenue_collect.py -q -p no:cacheprovider -k "V94 or UnknownBilling"
13 passed, 51 deselected in 31.92s
```

### 2. 修正の着地確認

```
$ git log -1 --format='%h %ad %s' --date=format:'%m-%d %H:%M' -- tests/test_revenue_collect.py
8b5ab93 09-25 14:59 fix: TestV94UnknownBillingにPRICING_CACHE隔離追加（実キャッシュ混入でunknownが0件になる恒常赤テスト）
```

```
$ grep -n "PRICING_CACHE" tests/test_revenue_collect.py | tail -2
796:        # PRICING_CACHE も隔離（実キャッシュが混入すると unknown が 0 件になる）
797:        monkeypatch.setattr(krc, "PRICING_CACHE", str(tmp_path / "apify_pricing_cache.json"))
```

```
$ grep -n "actors_unknown" tests/test_revenue_collect.py | head -2
811:        assert result["actors_unknown"] == 1
818:        apify["actors_unknown"] = 25
```

### 3. 成果物ハッシュ

```
$ sha256sum tests/test_revenue_collect.py
bfa973912bb72c17d5775f7630f0cfeef322a8017bb4515008cefe42665c1637  tests/test_revenue_collect.py
```

### 4. リポジトリ衛生（本カード完了を妨げる要因の有無）

```
$ git status --porcelain -uall | grep -E '\.(py|sh|js|yaml)$'
（出力なし = 未コミットコード0）
```

```
$ git log --oneline origin/main..HEAD
（出力なし = unpushed 0）
```

## 結論

- 恒常赤の原因（`PRICING_CACHE` 未隔離 → 実キャッシュ混入で `actors_unknown` が 0 件）は `8b5ab93` で隔離され、`actors_unknown == 1` のアサーションが緑。
- 本カードの作業は他カード（t_61d0db99 の周辺作業）で既に着地済みであり、**再実装すると二重作業になる**。
- よって QA 実測をもって `t_1ab013e8` を完了とする（重複再生成の防止）。

（証跡: 本ファイル + `reports/t_1ab013e8_evidence.json` / 生成: `kanban_done_guard.py --write-evidence`）
