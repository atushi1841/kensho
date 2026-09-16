# 検証記録: Pizza Bot（Show HN: An inbox for AI agents that work in the background）非API収益評価（t_e5fa3d3c）

- 対象: https://github.com/pizza-bot-app/pizza-bot / HN: https://news.ycombinator.com/item?id=49713894（score 47→48 / トップコメント15 / コメント31）
- 判断: 却下（実装対象外）— Amazon 製 Apache-2.0 のセルフホスト型デスクトップOSS（自前モデル持参・無登録・無テレメトリ）。収益フック（価格・API・データ・有償ホスティング）が構成のどこにも存在しない。スキル既定の却下パターン「大企業のOSS開発フレームワーク/OSSライブラリ（Apache/MIT等で無料配布）: 収集データ・有料化余地なし → 却下」の典型的該当。
- 検出側の「自動化キーワード: あり」は誤検出。本文の語彙（run AI agents in the background / cron or webhook triggers can start work / scheduled task）はアプリ自身の内部機能（バックグラウンド・エージェントランタイム）の説明で、Kenshoが自動化して売れる外部サービス・データフローではない。スキルの除外パターン「開発ツール内部機能記述は誤検出として除外」に直接該当。

## 3点評価

### 1) プロトタイプ — 不可
- 対象は Electron 製セルフホストデスクトップアプリ（TypeScript、LangGraph/DeepAgents ランタイム）で、無償ダウンロード・自前モデル（Anthropic/Bedrock/Gemini/OpenAI/OpenRouter/Ollama）持参・Apache-2.0=自由再配布可、という「誰でもタダで使える」ことが製品そのもの。売れるデータセット・スクレイピング対象・継続更新データが存在しない。
- Kensho資産（Python scraping + LLM要約 + X運用）を接続する隙間なし。ホスト型も商用版も無く、APIも機械可読データも無い（下記証跡）。
- 独占性・再現困難性はゼロ。むしろOSS普及が目的で、自社ホストSaaSに転換する余地（スキル・プロバイダ・シークレット管理は全部ローカル設定）を作者自ら否定している設計。

### 2) ローンチ手順 — 不可
- Kensho配置経路（データAPI / 自動化 / 自前FastAPI / Apify / RapidAPI / ニッチSaaS）のどれにも乗らない。他人のOSSデスクトップアプリの「ホスティング代行」は、継続運用コストの掛かる手動サービスであり、月1-3万円の受動自動収益のスコープ外。
- 収益モデルが作者から提示されていない（HN本文・READMEに価格・サブスク・ライセンスキー・スポンサー記述ゼロ、grep 全ヒット無し）。自前モデル持参=共有リソース課金も発生せず、収益化の持ち駒がない。

### 3) 集客 — 不可
- HN score 48・コメント31（作者が活発に返答する盛況なスレッド）だが、これは「人気OSS」の注目度であり、Kensho商品の観客ではない。観客を商品へ転換するアセット（属性データ・CtoA・既存トラフィック・売れるサービス）が移管不能。
- 対象は開発者向けエージェントランタイムで、Kenshoの観客（懸賞/自動化系Eコマース・ソーシャル）と重ならない。本物のpizzabot.appは無関係なSlack社交アプリで、Pizza Botのホスト版ではない。

## 結論
却下。worker実装タスク（プロトタイプ/ローンチ/集客）は切り出さない。
検出側の教訓（hunterへ回付）: 「Show HN: batch of an OSS desktop/tool (self-hosted, bring-your-own-model, 無登録無テレメトリ、Amazon等大手開発)」は、本文の「background / schedule / automated agent」等の自動化語彙がアプリ自身の機能記述である限り、スコアやコメントの盛況（本件48/31）とは無関係に自動除外してよい。既存除外パターン（AttaLambda=t_cf4993e8、OSS推論ホスティング=t_0bd69b5f、UiPath/coder_eval系）と同枠の「大手OSS無償配布ゲート」。収益フック（価格・API・データ・有償ホスティングの少なくとも1つ）が本文に見えなければ却下で確定。

## verification_evidence

```
$ curl -s -A "Mozilla/5.0" -I "https://github.com/pizza-bot-app/pizza-bot"
HTTP/2 200（リポジトリ実在。README: "Pizza Bot is an inbox for long-running AI work. ... bring your model provider ... Apache 2.0 license. Developed at Amazon"）
$ curl -s -A "Mozilla/5.0" "https://api.github.com/repos/pizza-bot-app/pizza-bot" (via script)
full_name=pizza-bot-app/pizza-bot, stars=231, forks=15, license=Apache-2.0, lang=TypeScript, created=2026-06-26（Amazon開発の無償OSSデスクトップアプリ）
$ grep -in -E "pricing|\$[0-9]+/mo|subscription|sign ?up|hosted|cloud|paid|license key" README.md
（全ヒット無し = 価格・サブスク・ホスト版・ライセンスキー一切なし）
$ for u in pizza-bot.app pizzabot.app; do curl -s -o /dev/null -w "%{http_code}" --max-time 12 -L https://$u; done
pizza-bot.app -> 000（ドメイン無し）、pizzabot.app -> 200（無関係な Slack 社交アプリ "PizzaBot invites 5 random people from your slack team out to eat Pizza"=ホスト版ではない）
$ curl -s -A "Mozilla/5.0" "https://hn.algolia.com/api/v1/items/49713894" (via script)
points=48, comment_count=15, url=https://github.com/pizza-bot-app/pizza-bot（人気OSSスレッド。作者が全質問に返答 = 製品普及モードのみ）
$ python3 parse_hn.py（HN HTML実測）
TITLE: Show HN: Pizza Bot – An inbox for AI agents that work in the background | 31 commtext（コメント内容=他OSS/GrokBot比較、llama.cpp設定の話題、AWS Open Source blog紹介など開発者会話のみ。価格・商用・データ・販売の言及ゼロ）
```

冒頭から証跡セクション末尾まで言及 task_id は t_e5fa3d3c（本タスク）のみ。
