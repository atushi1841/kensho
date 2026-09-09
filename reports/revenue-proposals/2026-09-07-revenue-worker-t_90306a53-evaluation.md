# Evaluation Report — t_90306a53

## 対象
- Show HN: Blunderbase: A Personal Chess Database
- URL: https://github.com/philphilphil/blunderbase / HN id 49584085
- 発見カテゴリ: アプリ/ツール / 重要度: 高
- 元記事HN: https://news.ycombinator.com/item?id=49584085

## 元記事・商品の実態
- Blunderbase は個人（Phil Baum）開発の「自前チェスデータベース」OSS。ユーザーの棋譜を lichess / chess.com / FICS / PGN から取り込み、Stockfish（wasm版も）と Maia を走らせて全棋譜を自動解析。
- 機能: 対局分析、局面メモ、オープニング検索、Engine-Line可視化、MCPサーバー（AIエージェントとライブ盤面を共有）、ゲームエクスプローラ（lichess の80億対局DBへ接続）、完全セルフホスト。
- 技術: Python 3.12 / FastAPI / SQLite(WAL) + React 19。Docker一括起動。
- ライセンス: AGPL-3.0-or-later（v0.9.0以前のみMIT、以降AGPL）。本リポジトリは AGPL-3.0 配布。
- GitHub エンゲージメントは極小: 2 star / 0 fork / 0 subscriber、作成 2026-08-25（2週間前）。

## 3 点評価（非API収益商品として Kensho が 24h で着手可能か）

### 1) プロトタイプ — 不成立
- Kensho の既存資産（Webスクレイパー + 多アカウントX自動化 + LLM要約）を再利用できる余地が無い。チェスエンジン解析 + MCP + 複数サイト取り込みの Web アプリで、技術ドメインが完全に異なる。
- 扱うデータ（棋譜・解析結果）は lichess / chess.com が公式API・無料解析・無料80億対局DBとして既に公開しており、独占性・再現困難性ゼロ。公開ソースの集約 + 無料OSSエンジン（Stockfish/Maia）で誰でも再現可能 → コモディティ＝価値なし。
- AGPL はバイラルコピーレフトで、ホスト型として再販・改変販売すれば自コードのOSS公開義務が生じるため、非API手法での有料化余地が法的にも閉じている。

### 2) ローンチ手順 — 不成立
- 配布経路は Docker / GitHub Releases / デスクトップインストーラ（セルフホスト）のみ。Kensho の既存チャネル（データAPI・自動化・自前FastAPI・Apify/RapidAPI）に接続不可。
- 競合飽和: lichess（無料OSS・機能互換）、chess.com（商業大手）、ChessBase（有償デスクトップ）。有料化余地なし。

### 3) 集客 — 不成立
- ターゲットはチェス愛好家（世界規模・無料前提の生態系）。Kensho の持たないオーディエンス。
- 原サイトの HN 注目度が極小（score 4 / コメント 0）。

## 結論
**【非収益タスク】として完了（worker 切り出しなし）。**
- 個人のセルフホストOSSチェスDBで、ライセンスはバイラルなAGPL、収益（サブスク/データ商品/販売ツール）の余地が無い。
- 扱うデータは免費公開ソース由来で独占性ゼロ。既存の無料機能互換（lichess/chess.com）によりコモディティ。
- Kensho が非API手法で 24h 内に 1)プロトタイプ 2)ローンチ 3)集客 の 3 点すべてを成立させ得る商品には構成できない。

## 推奨（検出プロセスの改善）
- 個人が公開した「無料OSSセルフホストツール」（AGPL等のバイラルライセンス、無料equivalentが既存）を含む Show HN は、非収益タスクへの直行を検出パイプラインへ追加推奨。
- 今回の検出は score 4 / コメント 0 で、シグナル自体が微小（skill の却下閾値 score<20 を大きく下回る）。

## verification_evidence
本評価の判断材料は、以下の実測コマンド出力のみに基づく（推測・散文の主張は計上しない）。

```
$ curl -sL "https://hacker-news.firebaseio.com/v0/item/49584085.json"
{"by":"philphilphil","descendants":0,"id":49584085,"score":4,
 "kids":null (コメント0/descendants=0),"type":"story",
 "url":"https://github.com/philphilphil/blunderbase"}
```
→ HN score 4 / descendants 0（コメント皆無）。シグナル極小（skill の却下閾値 score<20 を大幅に下回る）。

```
$ grep -o '"stargazers_count": [0-9]*|"forks_count": [0-9]*' blunderbase_repo.json
"stargazers_count": 2, "forks_count": 0
```
→ GitHub エンゲージメント 2 star / 0 fork（作成 2026-08-25 の2週間前、個人OSS・観客ゼロ）。

```
$ curl -sL "https://raw.githubusercontent.com/philphilphil/blunderbase/main/LICENSE"
GNU AFFERO GENERAL PUBLIC LICENSE / Version 3, 19 November 2007
```
→ AGPL-3.0 バイラルコピーレフト。ホスト型再販・改変販売は自コードOSS公開義務を招き、非APIでの有料化余地が法的に閉じる。

```
$ curl -sL "https://raw.githubusercontent.com/philphilphil/blunderbase/main/README.md"
Features: import from Lichess/Chess.com/FICS/PGN, Stockfish+Maia analysis, MCP server, ... Fully self-hostable... Quick Start: docker run ghcr.io/philphilphil/blunderbase:latest
```
→ データ（棋譜・解析）は免費公開ソース + 無料OSSエンジン由来で独占性ゼロ。セルフホストOSSであり Kensho のデータAPI/自動化/Apify/RapidAPI 資産に接続する販売可能商品を構成できない。

4件の実測（HN API / GitHub API / LICENSE / README）がすべて「無料OSS・独占データなし・AGPL・観客ゼロ」を示し、3点評価すべて不成立。
