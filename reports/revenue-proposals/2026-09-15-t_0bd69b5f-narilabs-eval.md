# 検証記録: Nari Labs（Show HN: Nari Qwen3-TTS and Qwen3-ASR）非API収益評価（t_0bd69b5f）

- 対象: https://narilabs.com/blog/nari-labs-leads-coval-voice-ai-benchmarks/ / HN: https://news.ycombinator.com/item?id=49699267（score 79 / 11トップレベルコメント）
- 判断: 却下（実装対象外）— 中身は「オープンソースのQwen3-TTS/ASRモデルを自前推論エンジンで高速化して時間課金で貸す商用ホスティングAPI」で、売っているもの自体が推論サービング事業。独占データも独占配布物もなく（ASR推論エンジンは作者自身がスレッドで「the qwen3-asr inference repo is not OSSed as of now」と明言=売上の源泉を配布すらしていない）、Kensho の資産（Python scraping + LLM要約 + X運用）から音声推論インフラ事業への転用経路がゼロ。t_833a07b6（TokenDelivery）で確立した却下ロジックの音声版そのもの。
- 検出の「自動化キーワード: あり」は誤検出。本文の auto/realtime 系語彙は voice agent 向け低遅延推論（TTFA/TTFS）という製品内部特性の説明で、自動収集・自動配信サービスではない。

## 3点評価

### 1) プロトタイプ — 不可
- 商品 = Nari Qwen3-TTS 1.7B / Qwen3-ASR 1.7B のホストAPI（Public Beta、$0.12/hour STT、$10/1M chars TTS）。土台の Qwen3 系モデルは Alibaba が公開しているオープンウェイトで、サイトに「Optimized open-source models behind simple production APIs」と自己申告。価値の源泉は非公開推論エンジンだが、それは「GPU+論文レベル最適化資本」でありKenshoが持つものがない。
- 二次アイデア「音声AIベンチマーク（Coval等）の価格・遅廉・WER追跡データ商品」も検討: 元データの出所は Coval の第三者評価（30分ごとに変動と本文に明記）で、生データはNari独自ではなく公開競合（apimade.com/audio-compare.html のブラインド比較リーダーボード等がスレッド内で既に言及・公開済み）。公開ソースの集約+LLM要約=コモディティで独占性なし。
- Kensho のスクレイパー資産はこの事業の任何部分（推論、ホスティング、SLA、不正利用対策）に寄与しない。

### 2) ローンチ手順 — 不可
- Kensho 配置経路（データAPI / 自動化 / 自前FastAPI / Apify / RapidAPI / ニッチSaaS）のどれにも乗らない。音声推論ホスティングは原価率がGPUで決まる資本ゲームで、Apify/RapidAPI 以遠の「以遠」側。
- 市場性も作者界隈がスレッドで自認している: 「The STT/TTS market is quite saturated」（karimf）、「AssemblyAI の DevRel が次の月にもっと競合が来ると言う」（iharnoor）。価格競争の最下位にさらに下がる層への参入で、月1-3万円の受動収益スコープ外。

### 3) 集客 — 不可
- HN score 79 と注目度は高いが、これは開発者向けの技術話題性であり、観客は「自前GPUで推論を回す層」。Kensho の既存観客（懸賞/自動化系Xフォロワ）とは重ならない。
- 集客アセットの移管余地なし: Nari の集客装置は Coval ベンチマーク1位という権威と論文/テックレポート計画であり、販売物・属性データ・CtoAとして再利用できない。
- スレッドには品質クレームも見える（「switched voices half way」「too fast, like 1.25-1.5x」「independent evals needed」）— 商品自体の成熟度もプレ-beta。

## 結論
却下。worker 実装タスク（プロトタイプ/ローンチ/集客）は切り出さない。
検出側の教訓（hunterへ回付）: 「OSSモデル（Qwen/gemma/Llama等）の推論高速化ホスティング + ベンチマーク順位宣伝」系 Show HN は、t_833a07b6（TokenDelivery）以来の継続パターン。「open-source models」「inference engine」「benchmark/leaderboard + API pricing」語彙の組合せは wrapper_free / inference-hosting ゲートで自動除外候補（スコアが高くてもGPU資本ゲームは収益スコープ外）。

## verification_evidence

```
$ curl -sL -A "Mozilla/5.0" https://narilabs.com/blog/nari-labs-leads-coval-voice-ai-benchmarks/ -w "HTTP %{http_code} size %{size_download}"
HTTP 200 size 24288（本文 "Optimized open-source models behind simple production APIs" / "STT: #1 Latency... At $0.12 / hour" / "Coval's benchmarks can fluctuate every 30 minutes"）
$ curl -sL -m 20 https://narilabs.com/robots.txt
User-agent: *  Allow: /  Sitemap: https://narilabs.com/sitemap.xml（スクレイピング可否は無関係=対象データが自社の推論APIであり販売可能な公開データセットではない）
$ curl -sL https://hn.algolia.com/api/v1/items/49699267
title: "Show HN: Nari Qwen3-TTS and Qwen3-ASR – High accuracy, low latency and cost" points: 79 top-level comments: 11
$ python3 parse_hn.py（HNスレッド全文パース）
[toebee/Nari] "the qwen3-asr inference repo is not OSSed as of now." ／ [karimf] "The STT/TTS market is quite saturated" ／ [rahimnathwani] "it switched voices half way through a 33 second clip" ／ [apimade] "https://apimade.com/audio-compare.html Added it to my blind TTS model comparison leaderboard"（第三者の無料リーダーボードが既に公開済=追跡データの独自価値なし）
$ curl -sL https://narilabs.com/product/stt/ ; curl -sL https://narilabs.com/product/qwen3-tts/
stt HTTP 200 42458 / tts HTTP 200 53273、両ページ "Public Beta" ×11/×8（正式版ですらないホスティングAPIの宣伝が本HNの実態）
```

冒頭から証跡セクション末尾まで言及 task_id は t_0bd69b5f（本タスク）のみ。
