# t_cd504399 critic v100 実装報告 — dirty=Yストーム遮断

## 実施内容（2026-09-11 21:1x JST）
1. **正式ツール化コミット** `6ea5423`:
   - `scripts/apify_store_check.py`（ストア監査、トークン.env実行時読込・hardcodeなし）を初コミット
   - `scripts/seo_rank_watch.py`（dev.to/Apify順位監視、t_9059b3ea作）を初コミット
   - ruff N806（`TOK`→`tok` 2箇所）修正、E501（120字超過5箇所）をf文字列分割で解消後 `ruff check` All checks passed
2. **一過性probe退避**: `scripts/seo_probe{,2,3}.py` `scripts/devto_probe.py` → `data/seo/probes/` へ移動（`data/`先頭=monitor dirty判定除外規則と一致、再生成されても非追跡のまま）
3. **.gitignore追記**（同一コミット）: `data/seo/` `tmp_llm_research/` `report.json` `rtx3090_*` `data/apify_pricing_cache.json`
4. **README参照** `2eb8b59`: scripts/ 段に seo_rank_watch / apify_store_check 一行参照追加
5. 失敗時代替案（monitor側 `scripts/.*probe` 除外パターン追加）は不要 — probeはSEO監視の一過性成果物でcron再生成経路なし、退避のみで解消

## 受け入れ条件検証（全PASS）
- `bash ~/.hermes/scripts/board_state_monitor.sh` 2連発 → `score=95|...|dirty=N` 2行一致（コミット前後で確認）
- `git status --porcelain -uall | grep -c probe` = **0**
- code-suffix（.py/.sh/.js/.yaml）dirty残り = 0（data/reports除外後）
- 残dirtyは data/*.json 状態ファイルと reports/ 提案類のみ = monitor上相変わらず dirty=N（除外規則）

## 効果
SEO監視probe再生成のたびに3AI起床（4baf143523e0/5e8ec4984bba/033ff6065ef7）を誘発していた dirty=N→Y フリッカが構造的に消滅。alert fatigue 1経路クローズ。

## verification_evidence
t_cd504399 受け入れ条件5項目の実測証跡（2026-09-11 21:1x JST、/mnt/d/Project2/kensho）:

$ git log --oneline -3
6ea5423 chore(scripts): t_cd504399 critic v100 dirty=Yストーム遮断 — apify_store_check/seo_rank_watch正式化+一過性probeをdata/seo/probesへ(.gitignore追記: data/seo,tmp_llm_research,report.json,rtx3090_*,apify_pricing_cache)
2eb8b59 docs(readme): t_cd504399 critic v100 scripts/ にseo_rank_watch/apify_store_check参照追記
134a71e docs(reports): t_cd504399 critic v100 dirty=Yストーム遮断 実装報告
$ .venv/bin/ruff check scripts/seo_rank_watch.py scripts/apify_store_check.py
All checks passed!
$ bash ~/.hermes/scripts/board_state_monitor.sh && sleep 1 && bash ~/.hermes/scripts/board_state_monitor.sh
score=95|ready=0|blocked=2|wip=1|prio=normal|streak=0|esc=False|skip=False|dirty=N
score=95|ready=0|blocked=2|wip=1|prio=normal|streak=0|esc=False|skip=False|dirty=N
$ git status --porcelain -uall | grep -c probe
0
$ git status --porcelain -uall | grep -E '\.(py|sh|js|yaml)$' | grep -vE '^(.. )?(data|reports)/'
（出力なし＝code-suffix dirty 0件、t_cd504399による残汚染なし）
