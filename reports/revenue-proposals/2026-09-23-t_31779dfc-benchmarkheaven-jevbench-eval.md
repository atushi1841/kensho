# 評価レポート: Show HN: JevBench, a reproducible benchmark for typed decision models（Benchmark Heaven）

- Task: t_31779dfc
- 対象: https://benchmarkheaven.com/jev-models / HN: https://news.ycombinator.com/item?id=49800574
- 元記事URL: https://benchmarkheaven.com/jev-models
- カテゴリ: アプリ/ツール / 非API自動収益
- 判断: **却下（非収益・実装対象外）**
- 実装工数推定: 適用外（Kensho が付加価値を出せる収益商品が成立しない）

## 対象の実態（実測）
「JevBench」は、モデル比較サイト **Benchmark Heaven**（運営: Florian Standhartinger / productivity-boost.com Betriebs UG）が
**自前で走らせた Jev 系（型付き意思決定モデル）のベンチマーク**であり、HN の Show HN はそのリリース告知。

- サイトの性格（/about 実測）: 「Benchmark Heaven is **open source under the MIT licence and a hobby project**…
  free, open-source, **non-commercial hobby project**」。収益化は `Support this project` の**投げ銭のみ**（donate リンク）。
- データの出所は**ほぼ全て第三者**（/about 明記）: OpenRouter（モデルカタログ・endpoint 価格の live API）、
  Artificial Analysis v2 API（Intelligence/Coding index、**attribution 必須**）、Epoch AI（**CC BY**）、
  DesignArena（**ライセンス未公開＝ "documented risk decision" として掲載**）、AWS Bedrock / Azure AI Foundry /
  Google Vertex / Scaleway / OVHcloud / Nebius 等の**公開価格表**。
- **サイト自身の免責**: 「The licence covers this code only… **nothing collected here is relicensed by the MIT licence**」。
  = コードは MIT でも**データは第三者ライセンスのまま**で、再許諾・再販はできない。
- 規模（実測）: sitemap **737 URL**（`/models/*` 669本 + `/jev-models/*` 54本 + 固定ページ）、
  カタログ **863 モデル / 669 family / 2,976 offers / 94 providers / 95 boards**。
- **完全公開の機械可読 API**: `/api/dataset` = 「**the full dataset in one response** — the canonical machine-readable
  feed」、`/api/models` は **認証なし・CORS 全開**で 1.56 MB JSON を返す（API.md 406行、README 相当を GitHub で公開）。
  = スクレイピングして集約する余地が**最初から存在しない**（正規の一括ダウンロード経路が公式に用意されている）。
- JevBench 自体も **MIT ハーネス + 問題の一部公開 + frozen artifacts + GitHub 公開**（fstandhartinger/jevbench、534 decisions / 220 hard: 111 public・109 held out）。
- 可用性（実測）: 応答が**不安定**。root `/` と `/robots.txt` は初回 curl で 20〜45 秒のタイムアウト（http=000）を繰り返したが、
  同一 URL が数分後の再試行では 200 を返す（root は 3 回連続 200、sitemap は 88,409 B で 200）。
  **恒久的なボット遮断ではなく間欠的な遅延**であり、`/api/models` も 200（5.5 秒）と 000（60 秒）が混在した。
  robots.txt は `User-Agent: * / Allow: / / Disallow: /account`（実測 126 B）＝**収集自体は許可**だが、
  許可されたデータは上記のとおり公式 API で全部取れるため収集代行の余地は無い。

## 自動化キーワード判定
Hunter フラグ「自動化ワード含む: あり」= **誤検出**。本件の auto 系記述は
「auto-router job のラベル付きタスクから 146 問を import」「自動車/automatic」等、
**原作者が自分のベンチマークを走らせる内部ジョブの説明**であり、Kensho の「自動収集・自動配信」機能ではない。
スキルの誤検出除外パターン「開発ツール内部機能記述」に該当。

## 3点評価（Kensho 非API収益モデル）
### 1) プロトタイプ — 不成立
- Kensho の核（スクレイピング + 集約 + LLM要約）が刺さる**未取得データが存在しない**。
  対象データは `/api/dataset`（canonical feed）と `/api/models`（863モデル・無認証）で**全部・無料・JSON** で取れる。
  公式が「一括ダウンロード経路」を提供している時点で、収集代行の価値はゼロ。
- 独占性もゼロ: 元データは OpenRouter / Artificial Analysis / Epoch AI / DesignArena の**公開値**。
  誰でも同じものを同じ手順で再現できる（＝スキル定義の「コモディティ＝価値なし」に該当）。
- 権利面で**再販不可**: 原作者が「データは MIT で再許諾していない」と明記。AA は attribution 必須、
  Epoch は CC BY、DesignArena は**ライセンス未公開**。Kensho 側で有料データ商品化すると権利侵害リスクを負う。
- Kensho の得意領域（日本語化・LLM要約）で足せるのは**翻訳・要約の薄いラッパー**のみで、
  原作が無料 API を持つ以上「有料化の導線」が発明できない（無料の完全上位互換が既にある状態）。

### 2) ローンチ手順 — 不成立
- Kensho の配置経路は「データAPI / 自動化 / 自前FastAPI / Apify / RapidAPI」。本件は Apify/RapidAPI 以外で評価するカードだが、
  自前 FastAPI で同種APIを出しても**価格の床が $0**（公式が無認証・CORS 全開で配布）。
  下位互換のクローンを有料で売る導線は成立しない。
- 原作者自身が **1人事業・非商用ホビー・投げ銭モデル**で運営している事実は、
  「このデータに支払意思がほぼ無い」ことの**実測に近い証拠**（1年以上運営して課金形態が存在しない）。
- JevBench 側を作る場合も、価値は「534問の凍結問題集 + 実行ハーネス」だが、**MIT で全公開**。
  加えて GPU・実測実行・109問の held-out 管理が必要で、Kensho の受動収益モデルとは別界隈の**手作業研究事業**。
  さらに作者は「held-out も被評価サービスに送っているので汚染防止ではない」と限界を明記しており、
  第三者による再走は**新規性が無く**、lab への売り込みは他の一発屋ベンチと同列（LMArena / AA が寡占）。

### 3) 集客 — 不成立
- Kensho 側の集客アセット（既存トラフィック / 観客 / 属性データ）はゼロ。
- HN 実測: **110 points / 28 comments**（13時間経過時点でカード記載の 95/24 から微増、伸びは鈍い）。
  コメント内容（実測）は ①Jev社の資金と「scam では？」論争 ②vibecoded なデザインへの批判
  ③ベンチマーク手法への質問（task distribution / held-out 汚染）④slop detector デモの精度崩壊の指摘
  （keysmash で 86% confident、無料 ChatGPT の作文が「100% slop」を通す）に終始。
  **「このデータに金を払う」需要言明は 1件も無い**（あるのは "add our model" の無償掲載依頼のみ）。
- 比較・ベンチマーク需要の受け皿は Artificial Analysis / OpenRouter / LMArena / Vellum / LLM Stats 等が
  **無料で寡占済み**。後発の集客は「ニュースレターをゼロから育てる」型の手動長期事業で、受動収益に非適合。

## 結論
本件は「MIT のホビーサイトが、第三者ライセンスの公開データを無認証 API 付きで無料配布し、
自前ベンチマークを投げ銭で維持している」構造。Kensho の非API収益の型
（**スクレイプ→集約→データ商品/販売ツール**、または**自動化ツールの販売**）に転換できる要素が一つも無い。
- 収集対象: 公式 canonical feed が既に存在 → 収集・集約の付加価値ゼロ
- 独占性: 出所は全て公開値 → コモディティ
- 権利: 「データは MIT で再許諾していない」明記 + AA attribution / Epoch CC BY / DesignArena ライセンス未公開 → 再販不可
- 価格: 公式 API が無認証・CORS 全開で $0 → 有料クローンの床が無い
- 需要: HN 110pt/28c は技術論とデザイン批判のみ、支払意思の言明ゼロ。運営自体が投げ銭

→ スキル判定パターン「ニュースアグリゲータ/キュレーション（生情報が公開ソース由来で独自価値なし）→ 却下」
および「大企業/個人のOSS・無料配布物（収集データ・有料化余地なし）→ 却下」の**複合**に一致。

- 成立条件を満たさないため、プロトタイプ / ローンチ手順 / 集客の3点はいずれも**着手しない**（24h 内タスクは no-op 完了）。

## 検出パイプラインへの推奨除外/優先ルール
- 「**正式な公開 API（/api/dataset 等）を提供している比較・ベンチマークサイト**」を対象にした Show HN は、
  収集代行の余地が構造的にゼロなので**即却下**でよい（HN スコアが高くても無関係）。
- 「OSS + 非商用ホビー + 投げ銭運営」の告知は、**そのデータの市場価格が $0 であることの実測シグナル**として扱う。
- 「自動化」ワードが**原作者の内部ジョブ/ハーネス説明**（auto-router, automatic rerun, auto-collect 等）である場合は誤検出として除外。
- 第三者ベンチマーク値の転載型商品化は、**attribution/CC BY/ライセンス未公開が混在**するため権利面で原則却下。

## 元データ
- https://benchmarkheaven.com/about（MIT / non-commercial hobby project / データは第三者ライセンス / 投げ銭 / 公開API 明記）
- https://benchmarkheaven.com/sitemap.xml（737 URL: /models 669, /jev-models 54）
- https://benchmarkheaven.com/api/models（無認証 200, 1,562,957 B, 863 モデル）
- https://raw.githubusercontent.com/fstandhartinger/model-market-comparison/main/API.md（406行, CORS 全開・read-only・/api/dataset = canonical feed）
- https://raw.githubusercontent.com/fstandhartinger/jevbench/main/README.md（33,035 B, MIT ハーネス, 534 decisions / 220 hard = 111 public + 109 held out）
- https://news.ycombinator.com/item?id=49800574（110 points / 28 comments 実測）
- https://benchmarkheaven.com/robots.txt（126 B: Allow / , Disallow /account）

## verification_evidence
検証コマンド（2026-09-23 実測, task t_31779dfc, 作業ディレクトリ /tmp/t_31779dfc_ev）:
$ curl -s -m 45 -o ev_sitemap.xml -w "%{http_code}" https://benchmarkheaven.com/sitemap.xml
200
$ grep -c "<loc>" ev_sitemap.xml
737
$ grep -o "<loc>[^<]*</loc>" ev_sitemap.xml | sed 's|<[^>]*>||g; s|https://benchmarkheaven.com||' | awk -F/ '{print "/"$2}' | sort | uniq -c | sort -rn | head -2
    669 /models
     54 /jev-models
$ curl -s -m 90 -o ev_api.json -w "api/models http=%{http_code} size=%{size_download} time=%{time_total}\n" https://benchmarkheaven.com/api/models
api/models http=200 size=1562957 time=5.496574
$ jq -r '"models=\(.count) generated_at=\(.generated_at) score=\(.score)"' ev_api.json
models=863 generated_at=2026-09-23T06:53:15.869Z score=aa_coding_index
$ curl -s -m 30 -o ev_about.html -w "about http=%{http_code} size=%{size_download}\n" https://benchmarkheaven.com/about
about http=200 size=207861
$ sed -e 's/<[^>]*>/ /g' ev_about.html | grep -o -m1 "free, open-source, non-commercial hobby project"
free, open-source, non-commercial hobby project
$ sed -e 's/<[^>]*>/ /g' ev_about.html | grep -o -m1 "nothing collected here is relicensed[^.]*"
nothing collected here is relicensed by the MIT licence
$ curl -s -m 30 -o ev_api_md.md -w "API.md http=%{http_code} size=%{size_download}\n" https://raw.githubusercontent.com/fstandhartinger/model-market-comparison/main/API.md
API.md http=200 size=38162
$ sed -n '69p' ev_api_md.md | cut -c1-180
The **full dataset** in one response — the canonical machine-readable feed: every model (with benchmarks, scores, all provider offers), the provider directory, source collection 
$ grep -niE "no api key|CORS-enabled" ev_api_md.md | head -2
16:All endpoints are **read-only**, return JSON, and are **CORS-enabled** (`Access-Control-Allow-Origin: *`), so they can be called from any site or tool — including directly from a browser.
$ curl -s -m 30 -o ev_robots.txt -w "robots http=%{http_code} size=%{size_download}\n" https://benchmarkheaven.com/robots.txt
robots http=200 size=126
$ head -3 ev_robots.txt
User-Agent: *
Allow: /
Disallow: /account
$ curl -s -m 30 -A "Mozilla/5.0" -o ev_hn.html -w "hn_item http=%{http_code} size=%{size_download}\n" "https://news.ycombinator.com/item?id=49800574"
hn_item http=200 size=47223
$ sed -e 's/<[^>]*>/ /g' ev_hn.html | grep -oE "[0-9]+ points| [0-9]+&nbsp;comments" | head -2
110 points
 28&nbsp;comments
$ curl -s -m 30 -o ev_jev_readme.md -w "jevbench README http=%{http_code} size=%{size_download}\n" https://raw.githubusercontent.com/fstandhartinger/jevbench/main/README.md
jevbench README http=200 size=33035
$ grep -c "534" ev_jev_readme.md
16
$ for i in 1 2 3; do curl -s -m 20 -o /dev/null -w "root attempt $i http=%{http_code}\n" https://benchmarkheaven.com/; done
root attempt 1 http=200
root attempt 2 http=200
root attempt 3 http=200
（初回の root / robots.txt 取得は 20〜45 秒でタイムアウト（http=000）したが、再試行で上記のとおり 200。間欠的な遅延であり恒久的な遮断ではない）
