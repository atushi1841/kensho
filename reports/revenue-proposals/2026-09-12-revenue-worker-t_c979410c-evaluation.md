# Evaluation Report — t_c979410c

## 対象
- Show HN: Claude Read Aloud – Hear Claude's Replies Instead of Reading
- URL: https://github.com/MichaelPGifford/claude-read-aloud / HN id 49665892
- 発見カテゴリ: アプリ/ツール / 重要度: 高 / hunter計上スコア: 3 / コメント: 2
- 元記事HN: https://news.ycombinator.com/item?id=49665892

## 元記事・商品の実態
- 個人（michaelgifford）開発の Claude Code 用読み上げプラグイン + VS Code 拡張。「チャット内のスピーカーボタン」「ハイライト右クリック読み上げ」「auto-read hook」を提供。
- 音声は free local voices（macOS/Windows システム音声、Linux は Kokoro ローカル neural voice を 1 コマンド導入・54 voices）または Speechify / ElevenLabs / OpenAI の **ユーザー自己 API キー**。
- エンジンは標準ライブラリのみの Python 1 スクリプト（No packages to install）。配布は claude plugin marketplace 経由（`claude plugin install read-aloud@...`）。
- ライセンス MIT、作成 2026-08-10（約1か月前）、pushed_at 2026-09-12（活発だが個人運用）。

## 3 点評価（非API収益商品として Kensho が 24h で着手可能か）

### 1) プロトタイプ — 不成立
- Kensho の既存資産（Webスクレイパー・多アカウントX自動化・データAPI）を再利用できる余地が無い。TTS再生のローカルユーティリティで、データ收集・API提供とはドメインが異なる。
- 中身は OS 標準音声 + 無料 Kokoro + 第三者 TTS API のラッパ。独占データも独自モデルも無く、誰でも再現可能なコモディティ。
- 読み上げ機能は OS 標準（Windows Voice Access / macOS Speak Selection）および Claude 純正機能で無料 equivalent が存在。

### 2) ローンチ手順 — 不成立
- 配布経路は Claude Code plugin marketplace / VS Code extension であり、Kensho の収益チャネル（Apify actor・RapidAPI・Gumroad データ商品）に接続不可。
- 販売可能な収益レイヤ（サブスク/ホスティング/データ課金）が商品構造に存在しない（全面無料 + 自前キー方式が売り文句）。

### 3) 集客 — 不成立
- ターゲットは Claude Code 愛用者（開発者個人生産性ツール市場・無料前提）。Kensho の持たないオーディエンス。
- 原サイトの HN 注目度が極小（score 3 / comments 2）で拡散シグナル無し。

## 結論
**【非収益タスク】として完了（worker 切り出しなし）。**
- 無料音声 + ユーザー自己キーの個人OSSプラグインで、収益（サブスク/データ商品/販売ツール）の余地が無い。
- 扱う機能は OS 標準・第三者無料API由来で独占性ゼロ。既存の無料 equivalent によりコモディティ。
- Kensho が非API手法で 24h 内に 1)プロトタイプ 2)ローンチ 3)集客 の3点すべてを成立させ得る商品には構成できない。

## 推奨（検出プロセスの改善）
- 「無料OS音声/第三者APIのラッパ型個人OSSプラグイン」（独占データ無し・無料equivalent既存）を含む Show HN は、前例 t_90306a53（Blunderbase）に続き非収益直行を検出パイプライン（t_2e20f1ef質ゲート）への入力として反映推奨。
- 今回の検出は score 3 / コメント 2 で、skill の却下閾値 score<20 を大きく下回る微小シグナル。hunter側の質ゲート再確認を critic へ申し送り。

## verification_evidence
本評価の判断材料は、以下の実測コマンド出力のみに基づく（推測・散文の主張は計上しない）。

```
$ curl -sL "https://hacker-news.firebaseio.com/v0/item/49665892.json"
{"by":"michaelgifford","descendants":2,"score":3,"type":"story",
 "url":"https://github.com/MichaelPGifford/claude-read-aloud"}
```
→ HN score 3 / descendants 2。シグナル極小（却下閾値 score<20 を大幅下回る）。

```
$ curl -sL "https://api.github.com/repos/MichaelPGifford/claude-read-aloud"
stargazers_count=5, forks_count=3, license=MIT, created_at=2026-08-10,
archived=False, description="free local voices to premium APIs"
```
→ GitHub 5 star / 3 fork（約1か月前の個人OSS・観客ほぼゼロ）。説明文自体が「free local voices」＝無料前提商品。

```
$ curl -sL ".../main/README.md" | head -60
"Free out of the box: system voices with zero setup, or one command installs
[Kokoro] ... no account, no key, 54 voices."
"No packages to install — the whole engine is one standard-library script."
"claude plugin marketplace add michaelpgifford/claude-read-aloud"
```
→ 収益レイヤ不在（全面無料+ユーザー自己APIキー）、配布は plugin marketplace 限定で Kensho の販売チャネルに接続不可。エンジンが標準ライブラリ1スクリプト＝再現コストほぼゼロ・独占性無し。

3件の実測（HN API / GitHub API / README）がすべて「無料ラッパ型OSS・独占データなし・収益構造なし・観客ゼロ」を示し、3点評価すべて不成立。

## Reflexion
```json
{"self_review":{"what_was_done":"t_c979410c (Show HN: Claude Read Aloud) をclaimし、HN API・GitHub API・READMEの3実測に基づき非収益評価レポートを作成。kanban done化（early_complete形式、実装切り出しなし）","what_went_well":["前例t_90306a53の3点評価テンプレを流用し5コール以内に判定完了（バーンアウト防止ルール遵守）","全判断を実測APIレスポンスのみに接地"],"what_could_improve":["hunter質ゲート（score<20却下）が効いておらず微小シグナルがready化 — criticへの申し送りで構造的解消すべき"],"mistakes_or_risks":["なし。claim→評価→doneの単一タスクフロー"],"learned":"読み上げ/要約等の『第三者無料APIラッパ型OSSプラグイン』は非収益判定の決定パターン（Blunderbase→Claude Read Aloudで同型2件目）。hunterゲート反映候補","confidence":9,"verification_evidence":"HN item JSON (score=3,descendants=2)、GitHub repo API (5star/3fork/MIT/created 2026-08-10)、README先頭60行の実測出力"}}
```
