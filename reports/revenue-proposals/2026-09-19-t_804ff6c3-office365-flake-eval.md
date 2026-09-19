# 評価レポート: Show HN: Microsoft Office running with Wine on Linux with no virtualization

- Task: t_804ff6c3
- 対象: https://github.com/Tombert/office365_flake / HN: https://news.ycombinator.com/item?id=49746401 (score 85, コメント 82)
- カテゴリ: アプリ/ツール / 非API自動収益
- 判断: **却下（OSS設定フレームワーク・無料公開の操作手順プロジェクト。worker 実装タスクへ切り出さない）**
- 実装工数推定: 適用外（着手すべき収益商品なし）

## 対象の実態
**office365_flake = Linux上（仮想化なし）で Microsoft 365 / Office を動かすための Nix flake + スクリプト集**。umu-launcher + GE-Proton（Valve/GloriousEggroll の Wine ビルド）経由で click-to-run Office を実行する設定レシピを作成者が公開したもの。

- **GitHub API 実測**: stargazers 31 / forks 0 / created 2026-09-16（新規repo）。LICENSE ファイル無し（GitHub license API 404）＝ OSS として無料公開、収益経路なし。
- README 明記: 「It packages nothing from Microsoft: the Office Deployment Tool and Office itself are downloaded at install time」「You need a Microsoft 365 licence to sign in」＝ 単なるインストール/設定スクリプトで、**Microsoft 製品をパッケージ化・再配布していない**。
- 収益モデルなし: 配布物は Nix flake 設定・シェルスクリプトのみ。販売するバイナリ・専有データ・API・課金経路ゼロ。
- HN コメント内容（82件）は「ODF/LibreOffice の普及」「OOXML 標準化批判」「LaTeX/Pandoc での代替」など**フォーマット論争**で、このプロジェクトそのものではなく MS Office エコシステムの議論。プロジェクト自体への関心は薄い。

## 自動化キーワード判定
タイトル・要旨には「自動化」ワードの直接的記述はほぼ無いが、ハンター検出の automation 判定は「実行/インストールの自動化を提供する設定ツール」のシグナル。これは**開発ツール/システム設定の内部機能記述**（Nix flake による依存解決・自動セットアップ）であり、Kensho が「自動収集・自動配信」する対象データは存在しない。skill の排除パターン「『自動化』のうち開発ツール内部機能記述は誤検出として除外」に該当。

## 3点評価（Kensho 非API収益モデル）
### 1) プロトタイプ — 不成立
Kensho 資産（Python scraping + LLM要約）で「作れるもの」がゼロ。スクレイピング対象データ・公開RSS/API・ダウンロード可能 DS が存在しない。配布物は Nix flake 設定とインストールスクリプトで、既に GitHub で無料公開され誰でも `nix run` できる。Kensho のスクレイパー・LLM資産で付加価値を出せる余地なし。
### 2) ローンチ手順 — 不成立
配置経路（データAPI / 自動化 / 自前FastAPI / Apify/RapidAPI）のいずれにも載せる「有料要素」が無い。OSS 設定プロジェクトを再配布して課金する余地はライセンス上・市場的に成立しない。競合も `nix run .#ms365` の1クリック手順が既に無料で成立。
### 3) 集客 — 不成立
集客アセット（属性データ / CtoA / 既存トラフィック / 既存観客）ゼロ。原サイトの HN score 85 は高いが、それは「MS Office を Wine で動かす」技術関心であり、Kensho の観客（国内懸賞/スクレイピング/非API収益）と重ならない。しかもコメントはこのプロジェクトへの収益/利用希望ではなくフォーマット論争に流れている。販売商品化経路なし。

## 結論
office365_flake は **Microsoft Office を Linux で動かす Nix flake 設定プロジェクト**（31⭐ / forks 0 / LICENSE 無し・無料公開、GitHub API・README 実測）。①収集対象の専有データなし（配布物は設定+スクリプトのみ、Microsoft 製品はパッケージ化していない） ②有料化余地なし（誰でも `nix run` で無料実行可能、競合は1クリック手順） ③Kensho スクレイパー/LLM 資産で付加できる価値なし ④集客アセットゼロ・観客層不一致（MS Office/Wine 技術関心 ≠ Kensho 観客、コメントはフォーマット論争に流布）。skill の既存却下パターン「OSS ライブラリ/開発フレームワーク（無料配布）: 収集データ・有料化余地なし → 却下」に該当。Apify/RapidAPI 以外のどの手法でも Kensho の収益商品に構成できないため、worker 実装タスクへの切り出しは行わない。

## Verification evidence
対象タスク: t_804ff6c3（実測コマンド出力の引用）

- GitHub API 実測（31 ⭐ / fork 0 / 新規repo created 2026-09-16 / description）:
```
$ curl -sL --max-time 40 "https://api.github.com/repos/Tombert/office365_flake" -H "User-Agent: kensho-eval" -o /tmp/office_repo.json
full_name: Tombert/office365_flake
description: A set of Nix Flakes and scripts to get Office 365 working on Linux without virtualization.
license: None
stargazers: 31
forks: 0
created_at: 2026-09-16T22:44:01Z
```

- LICENSE 存在確認（GitHub license API 404 = LICENSE ファイル無し、無料公開の設定プロジェクト）:
```
$ curl -sL --max-time 30 "https://api.github.com/repos/Tombert/office365_flake/license" -H "User-Agent: kensho-eval"
{"message":"Not Found","documentation_url":"https://docs.github.com/rest/licenses/licenses#get-the-license-for-a-repository","status":"404"}
```

- README 実測（「packages nothing from Microsoft / need a Microsoft 365 licence」 = 純正の設定+インストールレシピ、販売物なし）:
```
$ curl -sL --max-time 20 "https://raw.githubusercontent.com/Tombert/office365_flake/main/README.md"
It packages nothing from Microsoft: the Office Deployment Tool and Office itself are downloaded at install time by the `ms365` script. You need a Microsoft 365 licence to sign in.
Usage: nix run .#ms365 -- install   / nix run .#word   / nix profile install .#ms365
```

- HN スレッド実測（score 85 / コメント 82、内容は ODF/LibreOffice/OOXML のフォーマット論争で収益・データ商品に非該当）:
```
$ curl -sL --max-time 20 "https://news.ycombinator.com/item?id=49746401" -o hn.html
TITLE: Show HN: Microsoft Office running with Wine on Linux with no virtualization
POINTS: 85 | NUM_COMMTEXT: 82
（コメント例: 「universities and government offices should not expect a proprietary format」「use Overleaf with LaTeX」等、MS Office エコシステム批判）
```

## 検出パイプラインへの推奨除外ルール
- **「OS/ソフトウェアを特定環境で動かす設定レシピ・Nix flake・スクリプト集」**（ume+GE-Proton で Windows アプリを Linux 実行する類）は既定で却下対象。配布物が設定+スクリプトのみで、専有データ・有料バイナリ・API が存在しない。
- GitHub repo を持ち、**LICENSE 無し or MIT/Apache + 収益経路・専有データ・API がない OSS 設定プロジェクト**は実装タスクに切り出さない（GitHub license API + stargazers/forks で確認）。
- タイトルに「自動化」「no virtualization」等のワードがあっても、それがインストール/実行の自動セットアップ記述なら誤検出として除外。
