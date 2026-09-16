# revenue-worker 2026-09-16 (t_8bf52d53) — critic v164 当選率源別自動分析

## 実施内容
- 新規 `scripts/kensho_winrate_analysis.py`: dm_wins.json（当選DM 15件）× collected.json系
  （現行878件+バックアップ3187件の履歴、応募レコード1796件）を突合し、源別当選率・
  カテゴリ別・応募遅延帯別・通知時刻帯別のMarkdownレポートを出力。
- 突合キーは設計上のcard前提（apply_logsテーブル）が実在しなかったため、失敗時代替案どおり
  ①tweet_id完全一致 ②(sender handle, account_key)一致 の2段フォールバックで実装。
- 新規 `tests/test_winrate_analysis.py` 8テスト（tmp_pathフェイクJSONでの突合・集計・CLI end-to-end）。
- 週次cron `kensho-winrate-weekly`（no_agent、`0 6 * * 1`、script=kensho-winrate-weekly.sh、
  deliver telegram:8510166694）登録。次回発火 2026-09-21 06:00 JST。
- ラッパー `~/.hermes/scripts/kensho-winrate-weekly.sh` は先週ISO週（`date -d '7 days ago' +%GW%V`）を計算して実行。

## 検証エビデンス（実測）
- `$ .venv/bin/python -m pytest tests/test_winrate_analysis.py -q` → **8 passed**
- `$ .venv/bin/python scripts/kensho_winrate_analysis.py --week 2026W38` →
  `winrate 2026W38: wins=15 matched=7 unmatched_rate=53.3% sources=8 → reports/winrate-2026W38.md`
- `$ bash ~/.hermes/scripts/kensho-winrate-weekly.sh` → rc=0、`reports/winrate-2026W37.md` 生成実測
- 成功指標確認: 源別当選率が**8源**数値出力（KNOW系knshow 801応募/5当選=0.62%、kenshouclub 367/0、
  twscrape 265/2=0.75%、kema 174/0、ken-kaku 128/0、kensho-everyday 24/0、chancecom 20/0、cpmeikan 17/0）
  ＝要求の4源以上を達成。突合7件>0、unmatched率53.3%明記。
- 全pytest: 646 passed / 3 failed — 失敗3件は test_regression_gates のみ。winrateファイルを
  git stash した状態でも同一3件失敗＝**本変更と無関係の既存failure**（t_c6b4e3ed教訓: 9/18窓rollで自然解消見込み、不干渉）。

## 分析所見（提案B『新しい順』キューへの示唆）
- 遅延帯: 突合7件のうち <1h=0、<7d=1、負値1、不明5。DM本文引用t.coのx.com展開は
  ReignStormJP 1件のみ（t.coは410/オフライン展開不可が大半）→ tweet_id一致0件はデータ上の制約。
- instant win仮説の検証には applied タイムスタンプとtweet投稿時刻の両方そろう突合件数が必要。
  現状 handle一致7件中2件のみ遅延算出可。**応募ロジック変更なし**のため critic へ申し送り。

## 自己レビュー（Reflexion）
```json
{"self_review":{"what_was_done":"dm_wins×collected突合の当選率源別分析スクリプト+テスト8件+週次no_agent cronを実装・実測・登録","what_well":[],"what_went_well":["card前提のapply_logs不在を実調で早期発見し失敗時代替案(tweet_url/handle照合)へ即切り替え","他ワーカーstaged(hunter guard等)をgit commit -- <path>で巻き込まない部分コミット遵守"],"what_could_improve":["t.co展開をオフラインで試み410/到達不可が多かった—オンライン展開はcron実行時にだけ有効と割り切るべき"],"mistakes_or_risks":["突合率が53.3%と低い—収集快照のローリングで過去の案件レコードが流失するため。恒久化には収集時にdata/campaign_history.jsonlへ追記する別タスクが必要(critic申し送り)"],"learned":"dm_winsは本文に当選キャンペーンの公式tweet URLを引用するがt.co短縮が大半でオフライン復元不能。handle+垢照合が主経路になる","confidence":8,"verification_evidence":"pytest 8 passed、--week 2026W38/--week W37ラッパー実行rc=0、レポート8源数値出力実測"}}
```
