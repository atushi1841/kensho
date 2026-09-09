# 評価レポート: Show HN: Lantunnel — a P2P-first private mesh for reaching your LANs

- Task: t_226bb0d8
- 対象: https://github.com/lantunnel/lantunnel / ホーム https://lantunnel.app / HN: https://news.ycombinator.com/item?id=49593653 (score 4, コメント 1)
- カテゴリ: アプリ/ツール（P2P メッシュ VPN） / 非API自動収益
- 判断: **却下（非収益・実装対象外）**
- 実装工数推定: 適用外（実装すべき収益商品なし）

## 対象の実態（実測）
**Lantunnel** = 自前 LAN をどこからでも到達可能にする「P2P ファースト」なプライベートメッシュ VPN ツール。Tailscale の競合。Rust 製、Apache-2.0 で OSS 公開、`lantunnel-client` がデスクトップ/ヘッドレスで動く。直接 P2P（QUIC + UDP ホールパンチング）を優先し、直結できないときは暗号化リレー（Gateway）にフォールバックする。
- 収益モデルは**彼らの**ホスト型 Gateway サービス (lantunnel.app): Free/Home/Plus の「USD per Tunnel per month」サブスク課金。OSS コアは無料配布。
- GitHub: 11 stars / Apache-2.0 / Rust。HN score 4 / コメント 1 — コメントは dsemakin の技術質問のみ（「オフライン provisioning vs Tailscale、盗難時の revocation はどうするか」）。観客バリデーション極小。
- `lantunnel.app` robots.txt / sitemap.xml は 200、/rss 404、/pricing 404。サイトに Kensho が掘るべき「データ」が存在しない。

## 自動化キーワード判定
Hunter の「自動化: あり」は誤検出。本件の「自動/mesh」はネットワーク配線・リレー自動フォールバックという**インフラ機能**の記述であり、Kensho 非API収益の核（データ収集・配信の自動化 → 販売可能なデータ商品/販売ツール）とは無関係。スクレイピング・集約対象となるデータが存在しない。

## 3点評価（Kensho 非API収益モデル）
### 1) プロトタイプ — 不成立
- Kensho の核（Python スクレイピング + LLM 要約 → データ商品/販売ツール）が活かせる対象が皆無。公開データ・RSS・API・ダウンロード可能 DS が無い。掘るべきデータソースがない。
- これは OSI 系インフラツールであって、Kensho が「データ商品」「販売ツール」を組み立てる材料が一つもない。LAN 到達性というインフラ価値は Kensho のスタックで再現・転売できるものではない。
### 2) ローンチ手順 — 不成立
- Kensho の配置経路（データAPI / 自動化 / 自前FastAPI / Apify/RapidAPI）は全て「データ商品 or 販売ツール」前提。売るものが無い。
- ホスト型 VPN/gateway を自前で立てても、常時稼働・認証・決済・帯域・セキュリティ/耐障害・サポートが必要な**ライブインフラ事業**であり、受動収益に非適合。Tailscale（成熟・飽和）と正面衝突で後発差別化ゼロ。
### 3) 集客 — 不成立
- Kensho の集客アセット（属性データ / CtoA / 既存トラフィック / 懸賞観客）はゼロ。バイヤーは「自分で VPN/mesh を運用する技術者」で Kensho の観客と重ならない。
- 原 HN score 4 / コメント 1 / GitHub 11 stars = 注目度ほぼゼロ。観客規模が微小。

## 結論（t_226bb0d8）
Lantunnel は、Apache-2.0 の OSS メッシュ VPN コア + ホスト型 Gateway サブスク（lantunnel.app）という図式のインフラツール。データ・API・スクレイピング対象・Kensho が接続できる収益経路を一切持たない。スキル判定パターン「OSS ツール（Apache/MIT 等で無料配布）+ ネイティブ/インフラ、データも転売対象も販売経路も無い → 却下」および「技術速報/汎用インフラ、集客観客ミスマッチ → 却下」に一致。前件（Aurict / AURA / AntiAgent 等の OSS・ツール・消費者 SaaS 系却下）と同じ型。

- 成立条件を満たさないため、プロトタイプ/ローンチ手順/集客の3点はいずれも着手しない（24h以内着手の対象外）。

## 検出パイプラインへの推奨除外ルール
- 「P2P mesh / VPN / トンネリング」系の OSS インフラツール（Tailscale 競合含む）は score の如何に関わらず即却下でよい。データ商品モデルに変換不能。
- キーワード「mesh / reach your LANs / peer-to-peer」は「ネットワーク機能」の記述であって自動化ワードではない → 実装タスクに遡上させる基準を厳格化（Tailscale/ZeroTier 系を除外辞書に追加）。
- 対象がホスト型インフラ SaaS + OSS コア（データ・API・DS なし）はスクレイピング・集約候補として不成立と即断。

## verification_evidence
HN スレッド / GitHub リポ / lantunnel.app の3点を実測したコマンドと出力。

$ curl -sL "https://news.ycombinator.com/item?id=49593653" (UA: Mozilla/5.0)
→ title "Show HN: Lantunnel – a P2P-first private mesh for reaching your LANs"; `4 points`; 唯一のコメント (dsemakin, 2h ago): "Nice concept, the offline provisioning is the part that stands out to me vs Tailscale. How does revocation work in that model? Didn't see it in the docs, if a laptop with a .peer profile gets stolen, what then?"

$ curl -sL "https://api.github.com/repos/lantunnel/lantunnel"
→ "full_name":"lantunnel/lantunnel","stargazers_count":11,"language":"Rust","license":{"key":"apache-2.0"},"fork":false,"homepage":"https://lantunnel.app"

$ curl -s -o /dev/null -w "%{http_code}" "https://lantunnel.app/{,robots.txt,sitemap.xml,rss}"
→ / =200, robots.txt=200, sitemap.xml=200, /rss=404

$ curl -sL "https://lantunnel.app/" | grep -oiE "per Tunnel per month|/tunnel/month|Free/Home/Plus"
→ "Prices are in USD per Tunnel per month, before tax. Free/Home/Plu..." (Free Tier offers price "0" USD)
