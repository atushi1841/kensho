# 検証記録: TokenDelivery.ai（Show HN: Deterministic LLM inference for lowest price Gemma 4）非API収益評価（t_833a07b6）

- 対象: https://www.tokendelivery.ai/ / API: https://api.tokendelivery.ai/v1 / HN: https://news.ycombinator.com/item?id=49674280（score 6 / 1コメント）
- 判断: 却下（実装対象外）— 中身は「Googleのオープンウェイト（gemma-4-26b-a4b-it）をint8でホストし直した OpenAI互換推論エンドポイント」で、独占データも独占技術もゼロのコモディティ再販。しかもプレビュー期間中は本人たちが無料配布中（="Free while we're in preview. no card"）。スキルの却下濃厚パターン「OSS/無料ラッパー（有料化余地なし）」「誰でも再現可能な集約物」にそのまま該当し、Kensho の資産（Python scraping + LLM要約 + X運用）から推論サービング事業への転用経路が存在しない。
- 検出は「自動化キーワード: なし」の判定どおり、製品機能も「決定論的推論」（内部実装特性）であり、自動収集・自動配信サービスではない。収益モデルはトークン従量課金だが、親市場は OpenRouter が同一モデルを $0.09/$0.30 ＋ :free 枠 $0 で即日出荷済み（実測 below）で、価格競争の最低値にさらに一段下がる GPU 資本ゲーム。月1-3万円の受動収益スコープ外。

## 3点評価

### 1) プロトタイプ — 不可
- 商品は「同一リクエスト→同一バイト列を返す決定論的 Gemma ホスティング」。ホスト対象は Google 公開のオープンウェイト（hugging_face_id: google/gemma-4-26b-a4b-it をサイト自身が公称）で、データにもモデルにも独占性がない。誰でも vLLM/SGLang + int8 で再現可能な層を販売している。
- Kensho の再利用資産（スクレイパ、LLM要約パイプライン、Xアカウント運用）は推論インフラ事業に一切寄与しない。逆にこの種の事業に必要なのは GPU クラスタ運用・容量SLA・不正利用対策で、Kensho が持つものがない。
- 副次アイデア「無料プレビュー中に TDN を自前パイプの LLM バックエンドとして無料利用する」も、無名のプレビュー API 依存は事業でなく機会費用。既存の無料枠（OpenRouter :free 等）で十分置換可能。

### 2) ローンチ手順 — 不可
- Kensho 配置経路（データAPI / 自動化 / 自前FastAPI / Apify / RapidAPI / ニッチSaaS）のどれにも乗らない。推論ホスティングは GPU 原価率が商品価値を決める事業で、Apify/RapidAPI 以遠の「以遠」側。
- 価格構造が決定的: TDN 公称 list $0.042/$0.22（1M token）は OpenRouter 同一モデル実測 $0.09/$0.30 より安いが、OpenRouter には $0 の :free tier が併存し、TDN 自身も現在 $0。市場の平衡価格は事実ゼロで、"lowest price" 差別化が収益にならない（クローンが翌日出る）。
- 提供面も未成熟: robots.txt は 404、/api・/pricing・/docs は 308 リダイレクト経由でも最終 404（Next.js の _not-found を返すだけ）、llms.txt なし。API 表面は /v1/models が開いているだけの屋台状態。

### 3) 集客 — 不可
- HN 実測: score 6 / descendants 1（"Very clever. If I'm going to use LLM's might as well XP-theme it." のみ。批評・需要・課金シグナルゼロ）。スキルの score<20 却下基準を大きく下回る観客規模。
- 作者 carsonpoole の集客アセット（既存トラフィック・属性データ・CtoA）を Kensho に移管する余地なし。XPデスクトップ演出は話題性デザインであり収益資産ではない。

## 結論
却下。worker 実装タスク（プロトタイプ/ローンチ/集客）は切り出さない。
検出側の教訓（hunterへ回付）: 「オープンウェイトLLMの安価ホスティング/決定論推論/推理API」系 Show HN は、有料化以前に先行者自身が無料配布中のコモディティ・ラッパーであり、critic v138 の wrapper_free ゲート系の拡張としてスコア<10 × "free while/in preview" × open-weight 語彙で自動除外候補。

## verification_evidence

```
$ curl -s 'https://hn.algolia.com/api/v1/items/49674280'
{"author":"carsonpoole","points":6,"title":"Show HN: Determinstic LLM inference for lowest price Gemma 4, with Windows XP","url":"https://www.tokendelivery.ai/","children":[{"author":"initramfs","text":"Very clever. If I'm going to use LLM's might as well XP-theme it."}]}
$ curl -sS -o /dev/null -D - https://www.tokendelivery.ai/
HTTP/2 200  server: Vercel  x-vercel-cache: HIT  content-length: 32816（robots.txt=404、/api /pricing /docs /status=308→Next _not-found HTML、llms.txt=404）
$ grep -o 'Open-weight models[^<]*' /tmp/td_root.html
Open-weight models, fully deterministic. The same answer every time, byte for byte, at the floor price. ＋本文 "Free while we're in preview: no card" / "List input $0.042 List output $0.22" / "Base URL: https://api.tokendelivery.ai/v1"（自己申告の無料プレビュー＋オープンウェイト再ホスティング）
$ curl -s https://api.tokendelivery.ai/v1/models
{"data":[{"id":"google/gemma-4-26b-a4b-it","owned_by":"tokendelivery","hugging_face_id":"google/gemma-4-26b-a4b-it","quantization":"int8","description":"...served fully deterministically: every kernel is integer..."}]}（キー無しで読める単一モデルカタログ、認証・課金面の成熟度なし）
$ curl -s https://hacker-news.firebaseio.com/v0/item/49674280.json
{"by":"carsonpoole","descendants":1,"score":6,"time":1789231514,"title":"Show HN: Determinstic LLM inference for lowest price Gemma 4, with Windows XP","type":"story"}
$ grep -o '"id":"google/gemma-4-26b-a4b-it.\{0,900\}' /tmp/or_models.json
OpenRouter 同一モデル実測: "pricing":{"prompt":"0.00000009","completion":"0.0000003"} ＋ 別エントリ "id":"google/gemma-4-26b-a4b-it:free" "pricing":{"prompt":"0","completion":"0"}（コモディティ市場に $0 平衡価格が既に併存）
```

冒頭から証跡セクション末尾まで言及 task_id は t_833a07b6（本タスク）のみ。
