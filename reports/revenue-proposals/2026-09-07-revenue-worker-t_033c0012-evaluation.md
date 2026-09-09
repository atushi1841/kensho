# 評価レポート: Show HN: Byosynch – Continuous two-way file sync over SSH for Mac and Linux

- Task: t_033c0012
- 対象: https://byosynch.com/ / HN: https://news.ycombinator.com/item?id=49590729 (score 3, コメント 0)
- カテゴリ: アプリ/ツール / 非API自動収益
- 判断: **却下（非収益・実装対象外。worker 実装タスクへ切り出さない）**
- 実装工数推定: 適用外（着手すべき収益商品なし）

## 対象の実態
**byosynch** = Mac/Linux 向けの継続的双方向ファイル同期デーモン（CLI + バックグラウンド監視）。SSH（SFTP + リモートチェックサム）でユーザー自身が持つストレージ（rsync.net や自前サーバー）にファイルを直接同期する「Bring Your Own Storage」型の有料サービス。
- **有料プロダクト**: Personal プラン $49/年 または $4.99/月（30日無料トライアル、カード必須・自動更新）。Teams プランは「Coming soon」未実装。
- 特徴: ゼロナレッジ（プライベート鍵・ファイル内容は byosynch サーバーに届かない）、デバイスキーはローカル生成、同時編集時は両バージョンを保持、just a company（Accounts + Licensing のみ自社サーバー処理）。
- 技術スタック: **Go** 製ネイティブデスクトップクライアント（open-source ページは BurntSushi/toml・pkg/sftp・cobra 等のサードパーティ依存ライセンス帰属のみ。製品自体はプロプライエタリ）。
- 可用性: **現在 US のみ**。非 US は waitlist（`/api/waitlist`、Cloudflare Turnstile 人検証）でメール通知待ち。
- 実測: HN score **3**・コメント **0**（作者 hamiltonc、2026-09-06 公開）。sitemap は単なるマーケティング/docs ページ群。RSS/公開API/ダウンロード可能 DS なし。

## データの出所・収益要素（決定打）
- **データ資産ゼロ**: この商品は「ソフトウェア製品」であってデータ製品ではない。裏に集約・スクレイピング・再販できる独占属性/リスト/DS/API が一切存在しない（robots.txt はサイト許諾のみ、sitemap は docs ページのみ）。
- **Kensho 技術資産が再利用不能**: Kensho の Python スクレイピング+LLM要約資産が乗る載せる物がゼロ。byosynch の価値は SSH 経由のファイル同期エンジン（Go、fsnotify + sfpp + イベント/定期スキャン）というクライアント実装であり、「新しいソフトウェア製品の開発」であって受動的データ収益化の対象ではない。
- 競合が飽和: Dropbox（CLI が不満だった動機の筆頭）・Syncthing・rsync/rsync.net・Resilio Sync・Seafile・rclone 等、BYOストレージ型も含め既存無料/廉価ツールがひしめくコモディティ市場。
- 有料ではあるが、幾ら払うのは「ソフトウェア使用料」であり、Kensho がこれを再販・転売できる余地はない（プロプライエタリ + ライセンス認証サーバー管理 + US 限定）。

## 自動化キーワード判定
Hunter 検出「自動化キーワード含む: あり」は誤検出。「Continuous two-way file sync」「daemon watches the folder」「periodic scans」は**ファイル同期デーモンの機能実装記述**であり、収集・配信・収益自動化の文脈ではない（スキルの開発ツール内部機能=除外パターンに該当）。`byosynch setup` の「setup」も同期セットアップ導線であって自動応募・自動収集とは無関係。

## 3点評価（Kensho 非API収益モデル）
### 1) プロトタイプ — 不成立
スクレイピング対象データ・収集対象・独占データ資産が皆無。バックエンドも公開 API も Web データも無く、Kensho 資産を再利用して再現困難な価値を積む余地がゼロ。再現するなら SSH ファイル同期エンジンの新規開発（Go/iOS/macOS/Linux クライアント + ライセンス/課金サーバー）であり、24h プロトタイプや受動収益とは別格のソフトウェア事業。

### 2) ローンチ手順 — 不成立
Kensho の配置経路（データAPI / 自動化 / 自前FastAPI のデータ商品 / Apify/RapidAPI）のいずれにも乗らない。プロプライエタリ有料クライアントを 24h で複製・再販できる訳がなく、Kensho のデータ商品構成ロードマップとは無関係。

### 3) 集客 — 不成立
集客アセット（属性データ / CtoA / 既存トラフィック / 既存観客）ゼロ。HN score 3・コメント 0 = 観客規模が事実上無し。加えて対象は **US 限定**で Kensho 運用者の所在地（日本）では waitlist + Turnstile 人検証により日本からの参入すら不可。Kensho の既存観客（国内懸賞/スクレイピング系）とも重ならない。

## 結論
byosynch は「アプリ/ツール」カテゴリの有料ネイティブ同期クライアントで、①収集対象データ/公開API/DS 皆無（データ製品でない）②Go 製プロプライエタリ+ライセンス認証サーバーで Kensho Python 資産を再利用できる余地なし、既存同期ツールと重なるコモディティ ③集客ゼロ（HN score 3 / コメント 0）かつ US 限定で日本から参入不可。Apify/RapidAPI 以外のどの手法でも Kensho の収益商品に構成できないため、worker 実装タスクへの切り出しは行わない。

## verification_evidence
対象タスク: t_033c0012（実測コマンド出力の引用）

- ランディングページ取得（有料プラン $49/年・$4.99/月・BYOストレージ・ゼロナレッジを確認）:
```
$ curl -sL -m 20 -A "Mozilla/5.0" -o byosynch_root.html -w "HTTP %{http_code} %{size_download}B\n" https://byosynch.com/
root HTTP 200 29326B
Personal: $49 USD / year | $4.99 USD / month | 30-day free trial
```

- robots.txt / sitemap（公開API・DB 無し、マーケティングページのみ）:
```
$ curl -sL -m 20 -A "Mozilla/5.0" -o byosynch_robots.txt https://byosynch.com/robots.txt
robots HTTP 200 524B
$ curl -sL -m 20 -A "Mozilla/5.0" -o byosynch_sitemap-index.xml https://byosynch.com/sitemap-index.xml
sitemap-index HTTP 200 183B
$ curl -sL -m 20 -A "Mozilla/5.0" -o byosynch_sitemap-0.xml https://byosynch.com/sitemap-0.xml
sitemap0 HTTP 200 1251B
(urls: /about /contact /docs/* /open-source /privacy /security /terms — データエンドポイントなし)
```

- HN スレッド実測（Algolia API。score 3 / コメント 0、作者 hamiltonc、2026-09-06）:
```
$ curl -sL -m 20 -A "Mozilla/5.0" "https://hn.algolia.com/api/v1/items/49590729" -o hn_api.json
algolia HTTP 200 893B
"points":3, "children":[], "author":"hamiltonc"
```

- 製品が Go ネイティブクライアント（open-source ページはサードパーティ依存の帰属のみ）:
```
$ curl -sL -m 20 -A "Mozilla/5.0" -o byosynch_open_source.html https://byosynch.com/open-source
open-source HTTP 200 225318B
同梱: BurntSushi/toml(MIT)・pkg/sftp(BSD-2)・cobra/pflag(Apache-2.0)・fsnotify(BSD-3) — 製品自体はクローズド
```

## 検出パイプラインへの推奨除外ルール
- カテゴリ「アプリ/ツール」で対象が 「Bring Your Own Storage 型の有料ネイティブクライアント/同期ツール」等、データ資産（公開API/DS/リスト）を持たないソフトウェア製品の場合、収益が有料サブスクでも却下（データ製品でなくソフトウェア事業）。
- "continuous sync / daemon watches folder / periodic scan / setup" 等は同期デーモン・セットアップ導線の機能記述であって収集・配信・収益自動化ではない → 誤検出除外。
- 加えて US 限定（非 US は waitlist + Turnstile）で日本語環境から参入不可、HN score < 20 かつコメント 0 は観客ゼロとして即却下。
