# t_cf8168c1 実装報告 — critic v100 follow-up: scripts/ 既存lint残骸17件一掃

日付: 2026-09-11 / 作業者: kensho-revenue-worker / 親: t_cd504399 (critic v100)

## 実施内容

対象3スクリプトの ruff 残存エラー17件を解消。コミット `3b64cdd`（pre-commitフック通過済み）。

1. `ruff check scripts/ --fix` による自動修復4件:
   - scripts/update_worker_prompt.py: E401（複数import1行）/ I001（import順）/ F401×2（`json`, `sys` 未使用削除 — 本文で未使用であることを grep で確認済み）/ W292（最終行改行付与）
2. 残存 E501 12件の手動解消（ロジック変更なし）:
   - scripts/apify_seo_apply.py:695 — f文字列内の `','.join(r.fields_changed) or '-'` を変数 `changed` に抽出して分割（プレースホルダ内複雑式を展開、表示結果は同一）
   - scripts/apify_seo_full_apply.py — docstring/READMEテンプレの長文英文を空白位置で改行（markdown ソフトラップ=レンダリング同一、6ea5423 と同じ方針）
   - scripts/update_worker_prompt.py — NEW_PROMPT 内 markdown 箇条書きを空白位置で改行（同上）
3. pre-commit の ruff-format フック整合のため `ruff format` を対象3ファイルに適用（apify_seo_apply.py の print 1行化、update_worker_prompt.py の subprocess.run 引数集約 — いずれもスタイルのみ）

## 受け入れ条件検証

- `ruff check scripts/` All checks passed!（HEADコミットベース／作業ツリーのseo_rank_watch.py v2書き換えは本カード範囲外の他セッション未コミット分のため対象外）
- pytest: 545 passed, 5 skipped（既存テスト失敗なし）
- py_compile: 対象3スクリプト OK（import側確認）

## verification_evidence

$ git log --oneline -1
3b64cdd chore(scripts): lint残骸一掃 — apify_seo_apply/apify_seo_full_apply/update_worker_prompt 計17件解消 (t_cf8168c1)
$ git show HEAD:scripts/apify_seo_apply.py | ruff check --stdin-filename scripts/apify_seo_apply.py -  (他2ファイル+既存2ファイルも同様)
seo_rank_watch.py: PASS / apify_store_check.py: PASS / apify_seo_apply.py: PASS / apify_seo_full_apply.py: PASS / update_worker_prompt.py: PASS
$ git show HEAD:scripts/seo_rank_watch.py | ruff check --stdin-filename scripts/seo_rank_watch.py - --output-format concise
All checks passed!
$ .venv/bin/python -m pytest -q (tail)
================== 545 passed, 5 skipped in 85.69s (0:01:25) ===================
$ git pre-commit hooks (commit 3b64cdd時)
ruff check...Passed / ruff format...Passed / trim trailing whitespace...Passed / fix end of files...Passed / check added large files...Passed
$ /mnt/c/Program Files/Git/cmd/git.exe -C D:\Project2\kensho push origin main
   1cc0bff..3b64cdd  main -> main

## 所見（範囲外・要注视）

作業ツリーの scripts/seo_rank_watch.py が commit 6ea5423 の後（21:08 JST）に別セッション由来と見られる v2 全面書き換えで未コミット dirty になっている（656行差分、UP009/F401×2/N806×2/F541 の lint 6件含む）。本カードの3スクリプトとは無関係のため触れていない。monitor の dirty 判定に再影響する可能性があるので、保有セッションか次回 critic での正式化/退避判断が必要。
