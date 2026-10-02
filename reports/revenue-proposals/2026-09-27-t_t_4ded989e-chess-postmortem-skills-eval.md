# 評価レポート: Show HN: A Claude Code skill to analyze your chess games (task t_4ded989e)

- Task: t_4ded989e
- 対象: https://news.ycombinator.com/item?id=49857528 (task t_4ded989e)
- 元記事URL: https://news.ycombinator.com/item?id=49857528
- GitHub: https://github.com/brumar/chess-postmortem-skills
- カテゴリ: アプリ/ツール / 非API自動収益
- 判断: **却下（非収益・実装対象外）** (task t_4ded989e)
- 実装工数推定: 適用外（Claude Code用OSSスキルリポジトリであり、販売可能なデータ商品・SaaS・有料APIモデルが存在しない）

## 対象の実態（実測）
本件は Bruno Martin 氏が公開した MIT ライセンスのオープンソース Claude Code スキル群（`chess-analysis`, `chess-video`, `chess-play`）である。

- **技術内容**: Python + Stockfish 16 + piper-tts + ffmpeg + whisper.cpp を組み合わせ、チェスの PGN 棋譜と音声対局メモから、Stockfish 評価値と連携した人間的な解説（Annotated PGN / HTML ビューア / ナレーション解説動画）を自動生成するローカル実行スキル。
- **コスト・実行特性**: 1 局の解析・動画生成に約 1 時間と $15 相当の LLM トークン（Claude API コスト）を消費する極めて高コストなローカル処理。
- **HN 反響実測**: **73 points / 53 comments**（Firebase API / Algolia API にて実測確認）。
- **コメント分析**: LLM 単体のハルシネーション問題への懸念、既存分析ツール（Lichess, chess.com, Elogram, Babelfish 等）との比較論議が中心であり、商用データやクラウドサービスとしての有料化需要ではなく、個人学習・実験ツールとしての評価が支配的。

## 自動化キーワード判定
Hunter フラグ「自動化キーワード含有: あり」= **機能誤検出**。
本文・リポジトリ内の「analyze / Stockfish sweep / automatic analysis / piper TTS / ffmpeg」等のキーワードは、**Claude Code 内部でローカル CLI やエンジンを自動連携呼び出しする記述**であり、Kensho が自動スクレイピング・集約・販売できるデータ商品や自動化パイプラインの記述ではない。
スキルの誤検出除外パターン「開発ツール内部機能記述（エージェント/スキルの自動検証等）/ 大企業のOSS開発フレームワーク・OSSライブラリ（MIT等で無料配布）」に該当。

## 3点評価（Kensho 非API収益モデル）
### 1) プロトタイプ — 不成立
- 収集・集約して高付加価値化できる独自の公開データセットやデータソースが存在しない。
- 1局 $15 の API トークンと 1 時間のレンダリングを要するため、Kensho の「Python scraping + LLM要約による自動データ商品/API販売」構造と完全に相反する。
- ソースコード自体が MIT ライセンスで完全公開されており、データ・機能ともに独占性・再現困難性がない。

### 2) ローンチ手順 — 不成立
- Kensho の配置経路（データAPI / 自前FastAPI / Apify / RapidAPI / Gumroad デジタルコンテンツ）に適合しない。
- Lichess / chess.com 等の無料高機能分析エンジンが既に普及しており、トークンコスト高の一般向けクラウドサービス化は不採算（1回 $15 以上の原価が発生）。

### 3) 集客 — 不成立
- HN 73 pt と反響はあるものの、ターゲットは Claude Code を自前で運用する極一部の開発者・チェス愛好家に限定。
- Kensho 側の集客アセット（X アカウント等）でチェス解析動画やツールを販売・集客する導線が存在しない。

## 結論
本件は「MIT ライセンスで公開された Claude Code 用ローカルチェス解析スキル（OSS）」であり、Kensho の非API自動収益商品（データ販売・スクレイピング代行・マイクロ SaaS）へ転換可能なデータ資産・収益モデルが存在しない。

- 成立条件を満たさないため、プロトタイプ / ローンチ手順 / 集客の 3 点はいずれも**着手しない**（24h 内タスクは no-op 完了）。

## verification_evidence
検証コマンド（2026-09-27 実測, task t_4ded989e）:
$ curl -s "https://hacker-news.firebaseio.com/v0/item/49857528.json"
{
  "by": "brumar",
  "descendants": 53,
  "id": 49857528,
  "kids": [
    49858841,
    49858757,
    49859681,
    49858031,
    49858178,
    49859465,
    49858035,
    49859054,
    49858824,
    49859487,
    49858329,
    49862469,
    49857830,
    49858551,
    49857866,
    49857848,
    49858492,
    49859100,
    49858722,
    49858019,
    49858057
  ],
  "score": 73,
  "time": 1790496296,
  "title": "Show HN: A Claude Code skill to analyze your chess games",
  "type": "story",
  "url": "https://github.com/brumar/chess-postmortem-skills"
}
$ curl -s "https://hn.algolia.com/api/v1/search?query=Show%20HN%3A%20A%20Claude%20Code%20skill%20to%20analyze%20your%20chess%20games&tags=story"
{
  "hits": [
    {
      "author": "brumar",
      "num_comments": 53,
      "objectID": "49857528",
      "points": 73,
      "title": "Show HN: A Claude Code skill to analyze your chess games",
      "url": "https://github.com/brumar/chess-postmortem-skills"
    }
  ]
}
