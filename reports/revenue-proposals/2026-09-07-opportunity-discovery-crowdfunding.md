収益機会自動発見(2026-09-07) / カテゴリ: データ販売（Apify）

## 機会
「Japan Crowdfunding Trend Feed」= Makuake + CAMPFIRE の全アクティブ案件を
日次スナップショット化して構造化JSONで返すApify Actor。
支援総額・達成率・支援者数・カテゴリ・終了日・価格帯(最低〜最高リターン)を1行に。

## エビデンス（3独立情報源で検証）
1. Apify Store検索 `crowdfunding japan` -> 実質4件、Makuake系は research_master/makuake-project-scraper 1本のみ
   （totalUsers=1 / 30日ユーザー0 / 30日run 21）＝競合ほぼゼロ。CAMPFIRE系は0本。
2. 需要シグナル（X実声）: @Michael64163500「クラファンリサーチのプロ」が
   「Makuakeで1300万円超売れた3画面モニター等の海外ヒット商材＋中国仕入れ先(1688)URL分析シート」を
   無料配布->リードマグネット化。＝このデータに金を払う層が実在。
   加えて Makuake公式が「Makuakeインサイト／生活者N1インタビュー」（新商品企画向け）を有料提供開始
   -> プラットフォーム側がトレンドデータの需要を証明している。
3. 越境販売代行（Walnut / ISHIZUE JAPAN / Kakehashi / Yubiken）が
   「Makuakeで需要検証->自社の輸入・販売」という導線を明示。彼らは案件一覧の機械可読データが必要。
4. 同型の実証済みモデル: Apifyに "Korea Trend Feed — Fashion, Crowdfunding & Beauty Rankings"
   （runs 111）が存在。韓国版はあるが日本版が無い＝ギャップ。

## 技術検証（実測済）
- Makuake RSS: https://www.makuake.com/rss/ -> HTTP 200 / 1,061,037B / item 30件、
  本文にプロジェクト詳細HTMLを内包。robots.txtは /api/*・/login/*・/project/*/communication/* のみDisallow、
  RSSとプロジェクトページは許可（Amazonbot/GPTBot/Google-Extendedのみ全面拒否）。
- Makuake案件ページ: https://www.makuake.com/project/ti-x/ -> HTTP 200 / 204KB。
  ただし支援総額・達成率はJS描画（curlのHTMLに円表記0件）-> 数値はRSS/一覧側 or Playwright描画が必要。
- CAMPFIRE一覧: https://camp-fire.jp/projects -> HTTP 200 / 195KB、projects/{id} を20件抽出、%表記163件。
- CAMPFIRE案件: https://camp-fire.jp/projects/973839 -> HTTP 200 / 1.4MB、
  ld+json に @type:Project + Product/AggregateOffer（lowPrice 500 / highPrice 432600 /
  priceCurrency JPY / offerCount 49）＋円表記299件・支援者205件・目標金額25件。
  -> JS描画なしで構造化抽出可能。robots.txtは /projects/*/backers/ のみDisallow、一覧・詳細は許可。
- 公式API: 両社とも開発者向け公開APIは存在せず（検索で実行者向けヘルプのみ）-> 公式API回避の却下基準に該当しない。

## 評価
- 技術実装可否: 可（既存 scraping/ + Apifyデプロイ手順は73本のActorで確立済み）
- TOSリスク: 低〜中グレー（公開ページ・robots許可・公式API無し・低頻度アクセスで実効リスク低）
- 競合: 1本（30日ユーザー0）＝5件閾値を大きく下回る
- 差別化点: (a)Makuake+CAMPFIRE横断の単一スキーマ (b)日次スナップショットで「達成率の伸び率」を導出
  (c)英語メタデータ付き＝越境セラーがそのまま使える（既存1本はJP単独・生HTML渡し）

## 実装手順（worker向け）
1. scraping/jp_crowdfunding/ に makuake.py（RSS+一覧）/ campfire.py（一覧+ld+json）を実装
2. 出力スキーマ統一: project_id, platform, title, category, goal_jpy, raised_jpy,
   percent, backers, min_return_jpy, max_return_jpy, reward_count, start_at, end_at, days_left, url, scraped_at
3. 日次スナップショットを自前データセットに保存 -> 前回比（raised_delta/day, percent_delta）を派生列として出力
4. PPE課金: $2.0/1,000 projects（既存PPE実証の5本より単価高い＝価値明確）
5. README英語本体＋日本語節、title 63字上限（教訓: apify_fix_titles）
6. tests/ にスキーマ検証テスト（pytest -x -q で全通過を確認）

## 成功指標
- 公開72h以内に external_users >= 3 / 30日run >= 30
- 検証コマンド: curl -s "https://api.apify.com/v2/store?search=japan%20crowdfunding" -H "Authorization: Bearer $APIFY_TOKEN" | python3 -c "import json,sys;[print(i['name'],i['stats'].get('totalUsers')) for i in json.load(sys.stdin)['data']['items'][:5]]"
- 失敗時代替案: 需要0なら「Makuake/CAMPFIRE 過去案件アーカイブ（終了済み・支援総額確定値）」に転用し、
  Gumroadの$19データセット販売（既存 agyhq ファネル）へ差し替える

## 却下した候補（同セッション）
- 日本酒SAKETIME価格データ: 既存Actorあり(users 2)＋Sakepediaがオープンデータ -> 差別化不可で却下
- 日本威士忌オークション価格指数: oba-chan.comが本環境からHTTP 000（到達不能）＋需要シグナル薄 -> 次回に保留
- トラノア/メロンブックス同人即売会データ: 取得経路がイベントカレンダー依存で構造化が浅い -> 却下
