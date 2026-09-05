# 2026-09-05 収益化Critic 提案: n8nテンプレ第2弾「一括相場リサーチ（メルカリ+駿河屋+価格com）」公開

## 実調査（GitHub live確認 2026-09-05 09:10 JST）
- テンプレ第1弾の公開先は **atushi1841/n8n-japan-price-monitor**（パブリック、HTTP 200）
  - 公開済みテンプレ: goobike-price-monitor.json + upgarage-price-monitor.json = ちょうど **2本**
  - README.html には Apify 6 actors + RapidAPI「Japan Price Stats」+ Gumroad agyhq への導線リンク設置済み
  - LICENSE(MIT)・Topics7件・BUNDLE-README.md まで整備済み（t_e0171885 done、push 0a39199）
- atushi1841/kensho は匿名アクセス404（private）。ローカル /mnt/d/Project2/kensho に templates/ ディレクトリは存在しない
- scraping/collector.py は 0 バイト（空）。既存資産の「collector」参照は実体なし

## 設計決定（オーケストレーター裁定 — この提案タスクで確定）
- **公開先は atushi1841/n8n-japan-price-monitor に統一**（kensho/templates/ ではない）
  - 理由: テンプレ1弾の導線READMEと2本が既にそこにあり、追加で 2本→3本 となり成功指標「公開7日後テンプレ総数2→3」を満たす。
  - kensho/templates/ に分離すると導線が2リポジトリに分裂し、QA検証コマンド `ls templates/*.json` の前提が崩れる。
- 新規テンプレファイル名: `price-research-workflow.json`（単一ファイルに3ソース+S集約を収める。bundle方式は既存と同様）
- n8nスキーマはテンプレ1弾と同一フォーマット（name/nodes/connections/settings/active/tags、typeVersion 1.2/4.2/2）→ n8n 1.0+ インポート互換

## テンプレ2弾スペック（worker実装t_f9c143ef向け）
構成（マニュアルトリガ or Schedule Trigger → 並列HTTP → JSONマージ → Slack通知）:
1. メルカリ相場: search.word 入力 → api.mercari.jp サーチ（要クッキー/セッション。テンプレでは「正常行動に必要な値」としてクッキー入力項目を用意。取得不可なら代替にeBay US APIへ同一コード骨格で切替）
2. 駿河屋: suruga-ya.jp 商品検索 → JSON/HTML抽出（新作・中古相場）
3. 価格com: kakaku.com 製品検索 → 最安価/製品名抽出
4. 集約: 3ソース結果を1つのSOFAJ {keyword, source, title, price, url, fetched_at} に正規化
5. Slack通知: 結果をMarkdown整形で1メッセージに投稿（Incoming Webhook URL を環境変数 SLACK_WEBHOOK_URL）

補足: メルカリのみ「クッキー必須」で他2本はキーレス。全ソース公開日本市場データ・robots.txt 確認・日次Low Volume をREADMEに明記（テンプレ1弾の「Run responsibly」方針を踏襲）。

## リスク評価
- メルカリスクレイピング: 【高】 login/anti-bot。失敗時 `eBay US API` に切替（同一JSON骨格、成功指標不変）
- kakaku/surugaya: 【低】 公開HTML/JSON想定。実装時の構造変更リスクのみ
- BOT検出リスク: 【無】 n8nはKenshoのX応募パイプラインとは完全分離の別サービス。Kensho絶対ルール（BOT対策）に非干渉

## worker/QA への引継ぎ（QA検証コマンド修正）
- QA検証は atushi1841/n8n-japan-price-monitor に対して実施:
  - JSON妥当性: `python3 -c 'import json; json.load(open("price-research-workflow.json"))'`（リポジトリルート）
  - 導線: README から Apify/RapidAPI/Gumroad へのリンクが2件以上（既存+維持）
  - テンプレ総数: リポジトリルートの .json = 2→3
- gh はWSL未認証 → push は cmd.exe（Windows Git認証）経由（t_e0171885 の実績どおり）

## 成功指標（この提案タスクの受け渡し）
- 親タスク t_01ea4efa 完了で t_f9c143ef(worker 実装) + t_a3bbd64d(QA) が自動ディスパッチ
- 公開後: atushi1841/n8n-japan-price-monitor のテンプレ総数 3本 / README導線2件以上維持
