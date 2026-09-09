# 評価レポート: Show HN: Dsnitch – Real-time, zero-config Docker egress inspector via eBPF

- Task: t_77ccc2aa
- 対象: https://github.com/infomaniac777/dsnitch / HN: https://news.ycombinator.com/item?id=49586159 (score 5, コメント実質1スレッド)
- カテゴリ: アプリ/ツール / 非API自動収益
- 判断: **却下（非収益・実装対象外。worker 実装タスクへ切り出さない）**
- 実装工数推定: 適用外（着手すべき収益商品なし）

## 対象の実態
**dsnitch** = Linux 5.8+ 上で Docker コンテナの外部接続（TCP/UDP/ICMP/DNS）を eBPF の受動プローブで即時紐付けする、単一バイナリ・ゼロ設定・リアルタイム TUI のネットワーク/DNS エグレス監視ツール。
- Rust 実装 / Ratatui TUI / Hickory DNS による DNS レスポンス復号。cgroup v2 直結でサイドカー・コンテナ設定変更不要。
- 配布: リポジトリ + GitHub Releases のプリビルト済み Linux バイナリ（x86_64 / aarch64）。サイト・API・管理画面なし。
- ライセンス: **GPL v3.0**（無料OSS）。
- 実測: GitHub stars **4**（aria-label=4）、HN score 5・実コメントは coder-pm 1件と作者返信のみ。注目度は極小。

## データの出所・収益要素（決定打）
- **収益要素ゼロ**：README 全文・GitHub 実測で、価格・サブスク・有料プロ版・寄付・商用レイヤの記載一切なし。完全無料のローカルCLI/OBS。
- **スクレイピング対象データが存在しない**：サイトではなく GitHub リポジトリ+ローカルバイナリ。裏に集約・再販できる独占データ（属性・リスト・DS・API）がない。
- **技術スタックが根本乖離**：Rust + eBPF（カーネルトレースポイント・cgroup v2・BTF）。Kensho の Python スクレイピング+LLM要約資産を再利用する載せる物がゼロ。「新しいソフトウェア製品の開発」であり受動的データ収益化の対象ではない。
- 競合も飽和: bandwhich / ctop / iftop / nethogs / sysdig / docker stats 等の既存無料監視ツールと同領域のコモディティ。

## 自動化キーワード判定
Hunter 検出「自動化キーワード含む: あり」は誤検出。本文の "real-time" は「リアルタイムTUI監視」という**ツールの機能実装記述**であり、収集・配信・収益自動化の文脈ではない（スキル判定の開発ツール内部機能=除外パターンに該当）。headless streaming モードもあるが、これもローカル監視のパイプ用途であって検出自動化とは無関係。

## 3点評価（Kensho 非API収益モデル）
### 1) プロトタイプ — 不成立
スクレイピング対象データ・収集対象・独占データ資産が皆無。バックエンドもDBも Web 資産も無く、Kensho 資産を再利用して再現困難な価値を積む余地がゼロ。再現するなら eBPF エンジンの新規開発であり、受動収益とは別のソフトウェア事業。

### 2) ローンチ手順 — 不成立
Kensho の配置経路（データAPI / 自動化 / 自前FastAPI / Apify/RapidAPI）のいずれにも乗らない。無料 OSS・自前ホスト型（GPL v3）で有料化余地なし。リポジトリ丸ごと再配布は GPL 上可能だが、既に作者が無料で公開済み = 再梱包して売る余地ゼロ。

### 3) 集客 — 不成立
集客アセット（属性データ / CtoA / 既存トラフィック / 既存観客）ゼロ。GitHub star 4・HN score 5 = 観客規模が微小。ホームラボ/Docker 運用者という観客は Kensho の既存観客（国内懸賞/スクレイピング系）と重ならない。

## 結論
dsnitch は「アプリ/ツール」カテゴリのローカルOSS開発者・ホームラボ向けツールで、①収集対象データ/API/DS 皆無 ②GPL-3.0 完全無料・有料化余地なし、既存監視ツールと重なるコモディティ ③Kensho Python資産未利用・技術スタック乖離(Rust+eBPF) ④集客ゼロ（star4/HN score5）。Apify/RapidAPI 以外のどの手法でも Kensho の収益商品に構成できないため、worker 実装タスクへの切り出しは行わない。

## verification_evidence
対象タスク: t_77ccc2aa（実測コマンド出力の引用）

- GitHub リポジトリ取得（HTTP 0 = 成功、HTML 340,885 bytes）:
```
$ curl -sL -m 25 -A "Mozilla/5.0" https://github.com/infomaniac777/dsnitch -o dsnitch_github.html
HTTP github: 0 → 340885 dsnitch_github.html
```

- README 取得 + ライセンス・収益キーワード走査（価格/有料/寄付/商用レイヤの記載なし）:
```
$ curl -sL -m 25 -A "Mozilla/5.0" https://raw.githubusercontent.com/infomaniac777/dsnitch/main/README.md
readme: 0 → 9392 dsnitch_readme.md
grep -inE "license|pricing|pay|sponsor|donate|commercial" → 該当行は License セクションのみ
# License
GNU General Public License v3.0 (LICENSE)
```

- HN スレッド実測（score 5 / 実コメントは coder-pm 1件+作者返信のみ）:
```
$ curl -sL -m 30 -A "Mozilla/5.0" "https://news.ycombinator.com/item?id=49586159" -o hn_dsnitch.html
exit: 0 → 8198 hn_dsnitch.html
ユーザー coder-pm (49589978) + 作者返信 infomaniac777 (49592731)
```

- GitHub star 数（実測 4）:
```
$ grep -oE 'aria-label="[0-9.]+k?[^"]*starred[^"]*"' dsnitch_github.html
aria-label="4 users starred this repository"
```

## 検出パイプラインへの推奨除外ルール
- カテゴリ「アプリ/ツール」かつ対象が ローカル実行の無料OSS（CLI/TUI/デーモン、サイト・API・管理画面なし）で、収益要素・収集データを持たない場合、自動的に却下。
- さらに GPL/Apache/MIT 等で無料公開済み && GitHub stars < 10 && HN score < 20 なら即却下。
- "real-time / live / zero-config" 等の語が開発ツール/監視ツールの機能記述（TUI/ストリーミング/自動検出）の場合は誤検出として除外。
