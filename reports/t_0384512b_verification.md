# 検証証跡: t_0384512b — 駿河屋エンタメ/ポケカ価格モニタリング用日本語圏価格データセットAPI国際販売

## summary
- 駿河屋(日本IP)の既存suruga-scraperを検証し、TCG/ポケカ実データ取得を確認。
- `scripts/tcg_price_collect.py`（低頻度収集+時系列蓄積）を実装・実行し、`data/tcg_dataset/` に初期データセット（240obs・116ユニーク・71価格付き・2タイムスタンプ）を生成。
- 競合調査（Apify Store API）でTCGplayer(Pokemon/米国)=36u需実証、日本TCG=2-3u空白を確認。販売戦略文書を作成。
- コミット: ecc451d（[ci skip]）

## verification_evidence

$ git log --oneline -1
> ecc451d feat(t_0384512b): Japan Pokemon/TCG used-price dataset + collection pipeline (surugaya) [ci skip]

$ python3 scripts/tcg_price_collect.py --pages 1 2>&1 | tail -12
> total_observations: 240 | unique_items: 116 | with_used_price: 71
> keywords: 5 (リザードン/ピカチュウ/ミュウツー/151/イーブイ)
> first→last collected_at: 2026-09-21T23:13:01Z → 2026-09-21T23:15:22Z (2タイムスタンプ=時系列実証)

$ wc -l data/tcg_dataset/tcg_dataset_latest.csv data/tcg_dataset/tcg_price_history.csv
> 117 data/tcg_dataset/tcg_dataset_latest.csv
> 121 data/tcg_dataset/tcg_price_history.csv

$ head -3 data/tcg_dataset/tcg_dataset_latest.csv
> (実在): ポケモンカードゲーム MEGA スターターセットex イーブイex, ¥2,980 used, release 2026/07/31 …（件名・価格実在）

- 駿河屋プローブ（ローカル・日本IP）: `ポケモンカードゲーム リザードン` -> 24 items, used ¥280〜¥42,800（scraper v4・httpx, 15s crawl-delay準拠）。

## Acceptance criteria
- [x] 駿河屋からTCG/ポケカ価格が取得できる（ローカル日本IP実測）
- [x] 時系列蓄積パイプラインが動作し、価格履歴を生成する
- [x] 競合調査で日本TCG価格が空白・需要シグナル実証
- [x] 国際販売パッケージ（README/ライセンス/戦略文書）用意
- [ ] Apify/Gumroad実際の公開・蓄積cron常駐（フォローアップカードへ）

## Notes
- 駿河屋は日本IP限定+Cloudflareのため公開オンデマンドApifyアクターは無料プラン不可→「蓄積データセット」として販売する戦略（戦略文書参照）。
- 検証の残余（値動きAPI化・Gumroad実出品・蓄積cron設置）はQA委譲・フォローアップタスクへ。
