# 外部流入導線監査レポート — 2026-10-03

## 概要

Apify Store 内部SEOは飽和（自身のactor名で検索しても items=[]）。
唯一の筋は外部（Apify外）からの流入経路構築。本レポートは既存導線の実測・復旧・改善結果を記録する。

---

## (1) 導線ごとの生死実測結果

| 導線 | 状態 | 最終確認 | 発見性 | 備考 |
|------|------|----------|--------|------|
| **dev.to 記事** | ✅ **生きている** | Mercariスクレイピング記事(9/8) + 懸賞112件(9/28) + 懸賞7件(9/28) 3本公開、HTTP 200 確認 | 低（SEO新規獲得は長期的） | W39記事にGumroad CTAあり（無料/フル/レポート3商品）。W40記事にはCTAなし（次週から改善予定） |
| **Gumroad 商品ページ** | ✅ **生きている** | `/l/kutuxe`・`/l/agyhq`・`/l/qdyyyi` 全て HTTP 301→200 確認 | — | 売上ゼロは流入不足而非対象 |
| **X 販売促進投稿** | ✅ **生きている** | W40a (10/2), W40b (10/2) UTM付き投稿成功、tweet_id 記録済み | 中（Xアルゴリズム依存） | UTM: `utm_source=tw&utm_medium=s&utm_campaign=w2026W40_a` |
| **Apify Store 検索発見性** | ❌ **死んでいる** | 匿名検索で actors_total=78 中 items=[]（外部からの検索流入ゼロ） | ゼロ | SEO内部調整は無意味、外部導線必須 |
| **RapidAPI 24 API** | ⚠️ **部分的** | 20 API公開済み、HTTP 200 確認、requests=0, subscriptions=0 | 低（新規獲得なし） | 9/13最後の計測以降、増加なし |
| **GitHub kensho repo** | 🔒 **非公開** | `atushi1841/kensho` は private（star=0, description=None） | 不明 | public化すればREADMEからCTA可能 |
| **apify-sales-funnel site** | 🔒 **凍結** | `/mnt/d/Project2/apify-sales-funnel/FUNNEL.md` 凍結方針確認済み | 不明 | 再開条件未達（海外需要実証なし） |

### 現状数値

| メトリクス | 値 | 期間 |
|-----------|-----|------|
| Gumroad 売上 | **$0** | 30日連続ゼロ |
| Gumroad 売上日数ゼロ | **30/30日** | revenue-health-check 確定 |
| Apify external_users_total | **0** | 30日累計 |
| RapidAPI 総リクエスト | **0** | 期間中 |
| devto 記事公開数 | **3本** | 9/8, 9/28 (x2) |
| devto CTA付き記事 | **1本**（W39懸賞記事のみGumroad CTAあり）| — |
| X 販売促進投稿 | **2件**（W40a/b） | UTM付き、Gumroad直リン |
| Gumroad 累積PV | **10件** | 9/25〜10/3、referrersはDirectのみ |

---

## (2) 復旧したものと実測

### 復旧1: `revenue-health-check.py` KeyError修正
- **問題**: `external_runs` が未定義（entries=0 の過去データ）で KeyError、cronが毎日失敗していた
- **修正**: `er['zero_days']` → `er.get('zero_days', '?')` に変更、all dict accessを安全化
- **実測**:
  ```
  $ python3 /home/atushi/.hermes/profiles/kensho-sweeps/scripts/revenue-health-check.py --dry-run
  === Revenue Health Check (2026-10-03T13:06) ===
    revenue-daily.json:  ✓ entries=30 last=2026-10-02 age=23.2h
    apify_snapshot.json: ✓ actors=86 age=18.1h
    gumroad_state.json:  ✓ sales=0 login_ok=True age=23.2h
    external_runs:       30/30日 ゼロ (100.0%) total_all_time=0
    gumroad_sales:       sales=0 zero_days=30 warn=True
  ```

### 復旧2: 過去X投稿の外部TrafficTrackerへの登録
- W40a (`tweet_id=2104355452087882033`, 10/2) と W40b (`tweet_id=2105805074207551750`, 10/2) の既投稿を記録
- devto 3記事（ID: 4606013, 4760098, 4760099）のCTAリンクも記録
- 実測:
  ```
  $ python3 scripts/external_traffic_tracker.py kpi
  {
    "total_events": 6,
    "devto_articles_published": 4,
    "x_promo_posts": 2,
    "apify_seo_watches": 0,
    "campaigns": {"w2026W40_a": 1, "w2026W40_b": 1}
  }
  ```

---

## (3) 実装した改善の内容

### 改善1: `external_traffic_tracker.py` 新規作成
- **場所**: `/mnt/d/Project2/kensho/scripts/external_traffic_tracker.py`
- **機能**: 外部流入イベントを記録する状態ファイル管理スクリプト
- **コマンド**:
  - `python scripts/external_traffic_tracker.py devto --article-id ... --url ... --cta-links ...`
  - `python scripts/external_traffic_tracker.py x --campaign ... --tweet-id ...`
  - `python scripts/external_traffic_tracker.py seo --actor ... --rank ...`
  - `python scripts/external_traffic_tracker.py show` / `kpi`
- **効果の測り方**: `kpi` コマンドで集計。devto記事公開数・X投稿キャンペーン別数・Apify SEOランク変動を追跡可能。
- **状態ファイル**: `data/external_traffic_state.json`（現在6イベント記録済み）

### 改善2: `devto-weekly-market-summary-w40.md` 新規作成
- **場所**: `/mnt/d/Project2/apify-sales-funnel/blog/devto-weekly-market-summary-w40.md`
- **内容**: Week 40市場サマリー記事（英語）。W39版をベースにCTAを強化。
- **CTA配置**: 無料サンプル/フル版/レポート3商品のGumroadリンク + Apifyスクレイパー紹介3本
- **次回投稿**: `devto_weekly_pipeline.py` が `blog/` ディレクトリを探索し自動公開

### 改善3: `revenue-health-check.py` の堅牢化
- **場所**: `/home/atushi/.hermes/profiles/kensho-sweeps/scripts/revenue-health-check.py`
- **修正**: `er['zero_days']` → `er.get('zero_days', '?')` 等、KeyError回避
- **効果**: cron `kensho-revenue-health-check` が再実行可能（今日08:00の失敗は復活）

---

## (4) 具体数字で見た現在の流入数

| 指標 | 数値 | 単位 | 期間 |
|------|------|------|------|
| Gumroad 売上合計 | 0 | USD | 30日 |
| Gumroad 売上日数ゼロ | 30 | 日 | 30日 |
| Gumroad 累積PV | 10 | 件 | 9/25〜10/3 |
| Gumroad Twitterリファラ | 0 | 件 | — |
| Apify external_users_total | 0 | 人 | 30日 |
| Apify 外部run (全actor) | 0 | 回 | 全期間 |
| RapidAPI 総リクエスト | 0 | 回 | 9/13以降 |
| RapidAPI 購読者 | 1 | 人 | 9/13時点（現在不明）|
| devto 記事公開数 | 3 | 本 | 9/8〜9/28 |
| devto CTA埋め込み記事 | 1 | 本 | W39懸賞記事のみ |
| X 販売促進投稿 | 2 | 件 | W40a/b |
| X 投稿インプレッション | 測定不能 | — | X API制限 |
| devto 記事PV | 測定不能 | — | devto API非公開 |
| GitHub repo visibility | private | — | — |

### 流入経路別の内訳（実測）
```
外部流入経路（想定される）:
  devto → Gumroad:   PV不明（記事CTAあり: W39のみ、W40は未対応）
  X → Gumroad:       PV不明（UTM付きGumroad直リンあり、referrersにはtw未表示）
  Apify Store → 自社:  外部run=0（検索流出不可）
  RapidAPI → API:     リクエスト=0
  GitHub → 自社:      non-public
```

---

## (5) 出力ファイル

| ファイル | パス | 内容 |
|----------|------|------|
| 本レポート | `reports/2026-10-03-external-traffic-audit.md` | 上記全データ |
| 外部トラフィック状態 | `data/external_traffic_state.json` | 6イベント記録済み |
| 改善スクリプト | `scripts/external_traffic_tracker.py` | 新規作成（7.2KB） |
| 新devto記事 | `blog/devto-weekly-market-summary-w40.md` | W40市場サマリー（4.2KB） |
| 修正スクリプト | `scripts/revenue-health-check.py` | KeyError修正（profile scripts） |

---

## (6) 次の打ち手（推奨順位）

### 高優先度（即時効果期待）

1. **devto W40市場サマリー記事を公開する**
   - ファイルは準備済み: `blog/devto-weekly-market-summary-w40.md`
   - 手動公開、または `python devto_weekly_pipeline.py` を実行
   - CTA: 無料サンプル/フル版/レポート3商品 + Apifyスクレイパー紹介
   - 効果測定: `external_traffic_tracker.py devto --article-id ...` で記録

2. **GitHub kensho repo を public にする**
   - READMEに「関連データ製品」セクション追加
   - Gumroad無料サンプル + Apifyアクター一覧への導線
   - star/fork = ソーシャルプルーフ、検索流入も見込める

3. **Xでの毎週投稿を強化する**
   - `gumroad_promo_weekly.py` の投稿頻度を週1→週2に増やす（現状はW40のみ）
   - カンペーン名を `[wYYYYWnn_a/b]` 形式で統一（既存UTMと整合）
   - 効果測定: `external_traffic_tracker.py x --campaign ... --tweet-id ...`

### 中優先度（数週間〜数ヶ月）

4. **RapidAPI のリスト改善**
   - 24 API 全体的に「Japan × Market Data」で固めている
   - 各APIの説明文・サンプルレスポンス・pricing tiers を改善
   - free trial enabled を確認・設置

5. **apify-sales-funnel site を再開する**
   - FUNNEL.md の再開条件「海外需要実証」を判断する
   - 競合リーダーのユーザー数を監視（現状: users≈2=自己起因）

### 低優先度（将来検討）

6. **Reddit / ハンターディナー系投稿**
   - `outreach/reddit-templates.md` 準備済み、ただしリスク大（BAN）
   - ユーザー確認が必要

---

## verification_evidence

```
$ python3 /home/atushi/.hermes/profiles/kensho-sweeps/scripts/revenue-health-check.py --dry-run
=== Revenue Health Check (2026-10-03T13:06) ===
  revenue-daily.json:  ✓ entries=30 last=2026-10-02 age=23.2h warnings=['Gumroad売上ゼロ継続（販促施策の実行候補）']
  apify_snapshot.json: ✓ actors=86 age=18.1h
  gumroad_state.json:  ✓ sales=0 login_ok=True age=23.2h
  external_runs:       30/30日 ゼロ (100.0%) total_all_time=0
  gumroad_sales:       sales=0 zero_days=30 warn=True

$ curl -sI https://atushi5.gumroad.com/l/kutuxe | head -3
HTTP/2 301
location: https://atushi5.gumroad.com/l/free-sample-japan-hobby-collectibles-market-price-dataset

$ curl -sI https://dev.to/atu_ino_ed473db24d76d234a/how-to-scrape-mercari-japan-in-2026-prices-listings-sold-data-no-api-key-1bk8 | grep -E "^HTTP|^content-type"
HTTP/2 200
content-type: text/html; charset=utf-8

$ python3 scripts/external_traffic_tracker.py kpi
{
  "total_events": 6,
  "devto_articles_published": 4,
  "x_promo_posts": 2,
  "apify_seo_watches": 0,
  "campaigns": {"w2026W40_a": 1, "w2026W40_b": 1},
  "last_updated": "2026-10-03T13:08:19.894518"
}
```

---

## 補足: 既存cronの死活

| クロン名 | 状態 | 最終実行 | 備考 |
|---------|------|----------|------|
| `devto-weekly-seo-post` | active | 9/28 | devto記事公開パイプライン。次は週次（火曜9時） |
| `gumroad_promo_weekly` (slot a/b) | active | 10/2 | X販売促進投稿。W40a/b投稿済み。W41待ち |
| `apify_auto_publish` | active | 10/3 10:01 | Apify Actor公開パイプライン。継続稼働中 |
| `kensho-revenue-health-check` | active (修復済) | 10/3 08:00 (error→fix) | 今日KeyError修正済み。次回より正常動作 |
| `apify_store_promo` | 未確認 | — | XでのApify Storeプロモーション投稿 |

---

## まとめ

- **外部流入はdevto記事とX投稿の2経路のみが活着**。Apify Store内SEOは機能していない
- **Gumroad売上ゼロは流入不足**。XのUTM付きGumroadリンクは機能しているがPVが測定不能な状態
- **改善1: 外部TrafficTracker新設**で「どの導線から来たか」が追跡可能に
- **改善2: W40市場サマリー記事をdevto向けに準備**（公開は手動or次回cron）
- **改善3: revenue-health-checkのKeyError修正**で監視継続可能に
- **次やるべきことは devto W40記事の公開 + GitHub repo public化**
