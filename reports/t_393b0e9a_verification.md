# t_393b0e9a 検証レポート — pytest 恒久赤 test_self_heal::test_safety_blocks_dead_proxy_status

## 背景
`tests/test_self_heal.py::test_safety_blocks_dead_proxy_status` が
2026-09-24 11:15 JST 以降 FAIL だった（fixture の `updated` 固定値 `2026-09-24T05:15:02` が
`dead_proxy_max_age_hours=6` の期限式フレーク。05:15:02 + 6h = 11:15 以降は age > 6h で
`dead_proxy_reason()` が `""` を返し `dead_proxy_accounts=[]` になり `assert [] == ['zin20120731']` が発火）。

## 修正
`tests/test_self_heal.py:518` の fixture `updated` を固定値から `datetime.now().isoformat(timespec="seconds")` に置換。
将来の時刻経過による再発（期限式フレーク）を構造的に解消。commit 763e431。

## verification_evidence

```
$ git log --oneline -1
763e431 fix test_self_heal: 恒久赤 — fixture updated を now に置換（時刻経過で発火する期限式フレーク解消）
```

```
$ grep -n "updated" tests/test_self_heal.py | head -3
518:                    "updated": datetime.now().isoformat(timespec="seconds")}), encoding="utf-8")})
```

```
$ .venv/bin/python -m pytest tests/test_self_heal.py -q --no-cov
collected 30 items
tests/test_self_heal.py .................................                   [100%]
30 passed in 64.01s (0:01:04)
```

## 成功指標
- `pytest tests/test_self_heal.py -q --no-cov` = 0 failed, 30 passed（修正前 1 failed, 29 passed）
- クリーン状態（git checkout）で再実行しても 0 failed（恒久性確認）
- 未pushコード commuting: origin/main..HEAD = 0（commit 763e431 は origin/main にpush済み）

## スコープ外の挙動変更（critic 指摘対応）
前 run が `kensho/utils/safety.py` の年齢ガード削除を未コミットで残していたが、
本カードの目的は test_self_heal の時限フレーク修正のみのため `git checkout -- kensho/utils/safety.py` で戻した。
未コミットのまま残さず兄弟タスクの done guard 条件(d) を巻き添えでFAILさせないよう配慮済み。