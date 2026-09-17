# 検証記録: Swift-Qwen3.8-27B（Show HN: -58.3% thinking, x1.95 speed, accuracy of xhigh）非API収益評価（t_fa7a9710）

- 対象: https://huggingface.co/ukisai/Swift-Qwen3.8-27b / HN: https://news.ycombinator.com/item?id=49727511（score 28 / コメント11=descendants 12 / kids 6）
- 判断: 却下（実装対象外）— オープンソースの推論省力 LoRA アダプタ＋重みダンプ（Apache-2.0+other、HF 無償・ungated 公開、権利作者自ら無償の研究用 API（OpenAI 互換 5RPM）と GGUF（Q1-Q8）＋コミュニティ量子化を提供）。収益フック（価格・有償ホスティング・独占データ・販売可能なサービス）がどこにも存在しない。スキル既定の却下パターン「大企業のOSS開発フレームワーク/OSSライブラリ（Apache/MIT等で無料配布）: 収集データ・有料化余地なし → 却下」および同枠の先行却下（Pizza Bot=t_e5fa3d3c、OSS推論ホスティング=t_0bd69b5f、UiPath/coder_eval系）に直接該当。
- 検出側の「自動化キーワード: あり」は誤検出。本文の語彙（efficient / 自動 thinking 削減 / auto 相当のトークン効率化 / 無料 Research API）はモデル自身の技術特性か作者提供の無料 API の説明で、Kensho が自動化して売れる外部データフロー・サービスではない。スキルの除外パターン「開発ツール内部機能記述は誤検出として除外」に準じる。

## 3点評価

### 1) プロトタイプ — 不可
- 対象は Qwen 3.8 27B を過思考トークン抑制（トークン係数ペナルティ＋LoRA SFT＋On-Policy Distillation）で省力化した OSS モデル。重みは safetensors（model-00001〜18）・GGUF（Q1-Q8）として HF に無償・ungated 公開で、誰でもタダで落とせる。売れるデータセット・スクレイピング対象・継続更新データが存在しない。
- 作者自身が HN コメント（kid 49727566）に完全再現手順を開示: 根拠は Meta 論文（arxiv 2606.00206）、共通分母トークン特定→推論時ペナルタイザ→社内トレースで LoRA SFT→On-Policy Distillation で誤差復元、8xH100 で再現可能。独占性・再現困難性ゼロ、純コモディティ。
- Kensho 資産（Python scraping + LLM要約 + Apify/RapidAPI 販売）を接続する隙間なし。GPU 推論を 27B でホスティングするインフラも持ち駒なし。

### 2) ローンチ手順 — 不可
- Kensho 配置経路（データAPI / 自動化 / 自前FastAPI / Apify / RapidAPI / ニッチSaaS）のどれにも乗らない。他人の OSS モデル重みの再配布・無償 API の再ホストは、無料配布品を扱うだけで月1-3万円の受動自動収益に転換不能。
- 収益モデルが提示されていない: HF card に価格・サブスク・ライセンスキー無し（license:other + LICENSE-APACHE-2.0 = 無償配布）。推論 API は作者が無料（5RPM、Nvidia GPU 提供）で先出し済み、市場は OpenCode Zen 等の飽和した有償/無償ホストで一杯（コメント実測）。

### 3) 集客 — 不可
- HN score 28・コメント6実測は「人気OSSモデルリリース」の物珍しさであり、Kensho 商品の観客ではない。ダウンロード数（HF: 2753 / 作者主張: 3日で80k）は作者 ukisai のブランド成果で、再販者への移管不能。
- 観客を商品へ転換するアセット（属性データ・CtoA・既存トラフィック・売れるサービス）がゼロ。開発者向けモデルで Kensho の観客（懸賞/自動化系）と非重複。

## 結論
却下（t_fa7a9710）。worker実装タスク（プロトタイプ/ローンチ/集客）は切り出さない。
検出側の教訓（hunterへ回付）: 「Show HN: an open-source LLM model/adapter release (weights free on HF, license:other/Apache, author offers free API + GGUF quants)」は、本文の「efficient / auto / free API / x% speedup」等の語彙がモデル自身の技術特性・無料提供の説明である限り、スコア・ダウンロード・コメントの盛況（本件28 / 80k claims）とは無関係に自動除外してよい。既存除外パターン（Pizza Bot=t_e5fa3d3c、OSS推論ホスティング=t_0bd69b5f、UiPath/coder_eval系）と同枠の「無償OSSモデルリリースゲート」。収益フック（価格・API利用料・独占データ・有償ホスティングの少なくとも1つ）が本文/カードに見えなければ却下で確定。

## verification_evidence

```
$ curl -s -A "Mozilla/5.0" "https://hacker-news.firebaseio.com/v0/item/49727511.json"
{"by":"kisjovan","descendants":12,"kids":[49737335,49727625,49727669,49730090,49733372,49727566],"score":28 }（title=Show HN: Swift-Qwen3.8-27B, -58.3% thinking, x1.95 speed, accuracy of xhigh）
$ curl -s -L --max-time 30 "https://huggingface.co/api/models/ukisai/Swift-Qwen3.8-27b"
HTTP 200 / id=ukisai/Swift-Qwen3.8-27b / downloads=2753 / likes=346 / private=False, gated=False / license:other + LICENSE-APACHE-2.0 / pipeline=image-text-to-text / siblings=35
$ python3 parse.py（kid 本文6件実測）
全コメント=技術Q&Aのみ（Q4量子化/ハード性能/ループ/ベンチマーク、作者が完全再現手順を開示）。価格・サブスク・商用・データ販売の言及ゼロ。
$ bash fetch2.sh
kid各HTTP取得 / HF page HTTP 200（作者提供の無料研究用API (OpenAI互換 5RPM, ukisai.com) と GGUF (Q1-Q8) を明記）
```

冒頭から証跡セクション末尾まで言及 task_id は t_fa7a9710（本タスク）のみ。
