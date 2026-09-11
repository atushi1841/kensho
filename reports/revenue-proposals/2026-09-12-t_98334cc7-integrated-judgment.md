# 9/12 統合判定: PPE 7d A/B + Apify SEO 168h + Gumroad X 7d投稿

- タスク: t_98334cc7（実行: 2026-09-12、kensho-sweeps）
- 根拠データ: data/revenue-daily.json（9/2〜9/12、11日分）/ reports/apify-seo/apify-seo-effect.json / data/gumroad_state.json / data/gumroad_x_post_state.json / data/gumroad_x_analytics.json / t_47db49e9判定コメント

## 結論（先出し）

3施策いずれも**外部収益効果ゼロ**。原因は価格・SEOメタデータ・投稿文案ではなく**需要側の露出欠落**（全25アクター external_runs=0 継続、Gumroad conversion=0）。
→ 次の打ち手は**集客優先**（Store可視性回収 t_443551e0追跡 + dev.toバックリンク9/18レビュー）に一本化。価格・SEO系の追加調整は効果実証まで中止。

## 施策1: PPE値上げA/B（t_47db49e9、9/4適用）

| 項目 | 値 |
|---|---|
| 判定対象 | japan-offmall-market (Zh4kqcS4dYPWpFzBd) $0.002→$0.005 |
| 7d total runs | **39**（9/12 04:45 critic手動実行、APIFY_TOKEN_DEFAULT） |
| 閾値 | baseline 35 の70% = 24.5件未満で復帰 |
| 判定 | **39 ≥ 24.5 → $0.005維持**（復帰不要） |
| 外部run | 0（値上げ前後で不変） |

副次知見: 判定cron 83d7259ff043はenv不整合（APIFY_TOKEN≠APIFY_TOKEN_DEFAULT）+401非検出で7日間空出力→修復タスク投入済（t_6f3de363、9/12完了）。9/11付revenue-daily.jsonでoffmall=0.005計測を確認。

## 施策2: Apify SEOバッチ168h測定（v16-A、9/4適用）

測定cron（kensho-apify-seo-effect-sched.sh、08:10）は日付ガード対象日 9/7・9/11 に**発火せず**（logs/apify-seo-effect-*.log 存在せず、9/7ポイント欠測）。9/12に `apify_seo_effect.py --date 2026-09-11` で補充実行。

| ポイント | day_span | runs_delta合計 | u30d増アクター | 外部流入 |
|---|---|---|---|---|
| 9/4→9/5 (24h) | 1 | +40 | 0 | 0 |
| 9/3→9/11 (168h、補充) | 8 | +252 | 3（rent/camera-cn/camera-kr、各±1） | 0 |

- runs増は**全て自己スケジュール実行分**（revenue-daily.json 9/2: 1125→9/12: 1498、external_runs=全件0）。
- u30d 21→24も自己ユーザーのみ。データギャップ: 9/4・9/5エントリはapify集計null（revenue-daily）、baselineは9/3に縮退解決。
- 判定: **SEOメタデータ適用による外部流入増は観測されず（効果なし）**。

## 施策3: Gumroad X 7日連続投稿（v21-C、9/5〜9/11）

| 日付 | views | fav | conv |
|---|---|---|---|
| 9/5 | 46 | 0 | 0 |
| 9/6 | 47 | 0 | 0 |
| 9/7 | 61 | 0 | 0 |
| 9/8 | 29 | 0 | 0 |
| 9/9 | 43 | 0 | 0 |
| 9/10 | 29 | 0 | 0 |
| 9/11 | 4 | 0 | 0 |
| 合計 | 259 | 0 | 0 |

- 投稿7/7本完遂（dedupガードでウィンドウ終了、cron 45 8は継続登録のまま＝ガード側で中停止）。
- Gumroad 9/12収集: sales=0 / revenue=$0 / last_7_days_usd=$0 / login_ok=true。**セッション数変動なし**。
- 判定: **エンゲージメント0・ conversions 0。週1投稿文案の7日間連投では効果なし**。

## 収益サマリ（9/12時点）

| 経路 | 9/12実績 |
|---|---|
| Apify | $0（external runs 0 / external users 0） |
| Gumroad | $0（total_earnings_usd 0） |
| RapidAPI | 上限到達により無料枠停止中（過去レポート参照） |

## 次の打ち手（判定）

1. **集客優先を確定**: Apify Store可視性回収（t_443551e0）の進捗追跡を最優先。露出が復旧するまで価格・SEO系の再調整は行わない（施策1の0.005維持は露出と独立なので据置）。
2. **dev.toバックリンク**: 9/11種付けの weekly devto post cron（watchwords: mercari japan scraper / dev.to japan scraper、next_review_day 9/18）の自動発火を確認し、9/18にrank-history.json実数で効果測定。SEO効果測定の計測点はこの路線に引き継ぐ。
3. **X投稿は停止→再設計**: 7日連投・259views・エンゲージメント0。同一リンク連投の文案では刺さらないと実証されたため、ウィンドウ終了を以て停止。referral獲得できる文脈（Reddit等他コミュニティはreddit-posting-automationのG5=10/7最早投稿が別枠進行中）へ回す。
4. **QA v24申し送り**: 「収益0円脱却の次の打ち手」の判定根拠として本レポートを申し送りの主資料に指定。集客施策（1・2）の実測が出るまで新規収益施策の追加投入は保留。

## 教訓

- 効果測定cronは「日付ガード型ワンショット」に頼らず、期日超過時に補充実行できる設計（本次は9/7ポイント恒久欠測）。手動補充コマンド: `python3 scripts/apify_seo_effect.py --date <YYYY-MM-DD>`。
- 自己runを含むtotal runsは需要側の proxy に不適（external_runs=0 が真の実力値）。A/B判定・効果測定とも外部run基準で読むこと。
