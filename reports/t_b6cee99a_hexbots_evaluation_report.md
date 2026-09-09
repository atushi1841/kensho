# 評価レポート: Show HN: HexBOTs – a cellular automaton with robotic lawnmowers

- Task: t_b6cee99a
- 対象: https://hexbot-genesis.netlify.app/ / HN: https://news.ycombinator.com/item?id=49590247 (score 3, コメント 0)
- カテゴリ: アプリ/ツール / 非API自動収益
- 判断: **却下（非収益・実装対象外。worker 実装タスクへ切り出さない）**
- 実装工数推定: 適用外（着手すべき収益商品なし）

## 対象の実態
**HexBOTs** = 6角グリッド上の「ロボット芝刈り機」が決定論的ルールで動き回るセルオートマトンの可視化デモ。クリック/キー操作で実験を開始・再開するだけの**純クライアントサイド canvas 玩具**。
- Netlify 静的サイト。ホーム画面は canvas 2枚 + `index.js` の HTML のみ（ファイル実測 419 bytes）。
- `index.js` 114,332 bytes を実測走査: `fetch` / `api` / `http` / `WebSocket` / `localStorage` の出現 **0 件**。ネットワーク通信・永続化・外部連携は一切なし。
- アカウント・バックエンド・DB・管理画面・価格表示・収益要素なし（タイトル/説明文に課金・プロ版・献金の記載ゼロ）。
- HN score **3**・コメント **0**。観客規模は極小。
- robots.txt / sitemap.xml 実測 **404**。

## データの出所・収益要素（決定打）
- **収益要素ゼロ**：canvas 可視化デモであり、価格・サブスク・有料版・商用レイヤが構造的に存在しない。
- **スクレイピング対象データが存在しない**：サーバーデータ・公開RSS・API・ダウンロード可能DS が皆無。ブラウザ内でロボットが動くだけ。
- **技術スタックが根本乖離**：フロントのみの JS セルオートマトン。Kensho の Python スクレイピング+LLM要約資産を再利用して載せる物がゼロ。再現するなら同種の canvas 可視化を作る新規開発であり、受動的データ収益化の対象外。

## 自動化キーワード判定
Hunter 検出「自動化キーワード含む: あり」は誤検出。説明中の "naturally deterministic / reacting according to their rules" は**セルオートマトンの挙動記述**（ロボットが自律移動する）であり、収集・配信・収益の自動化文脈ではない。スキル判定の「開発ツール/作品内部機能の自動化記述 = 誤検出として除外」に該当。

## 3点評価（Kensho 非API収益モデル）
### 1) プロトタイプ — 不成立
スクレイピング対象データ・収集対象・独占データ資産が皆無。サーバーも DB も Web 資産も無く、Kensho 資産で再現困難な価値を積む余地がゼロ。

### 2) ローンチ手順 — 不成立
Kensho の配置経路（データAPI / 自動化 / 自前FastAPI / Apify/RapidAPI）のいずれにも乗らない。有料化余地・データ商品化余地なし。

### 3) 集客 — 不成立
集客アセット（属性データ / CtoA / 既存トラフィック / 既存観客）ゼロ。HN score 3・コメント 0 = 観客規模が微小。対象観客（セルオートマトン愛好家）は Kensho の既存観客（国内懸賞/スクレイピング系）と重ならない。

## 結論
HexBOTs は「アプリ/ツール」カテゴリの純クライアントサイド JS 可視化デモで、①サーバー/データ/API/DS 皆無 ②収益要素ゼロ ③Kensho Python資産未利用が明確 ④集客ゼロ（score 3/コメント0）。Apify/RapidAPI 以外のどの手法でも Kensho の収益商品に構成できないため、worker 実装タスクへの切り出しは行わない。

## Verification evidence
対象タスク: t_b6cee99a（実測コマンド出力の引用）

- 対象サイト取得（HTTP 200、HTML 419 bytes = canvas のみの静的最小ページ）:
```
$ curl -sL -A "Mozilla/5.0" -o hexbot.html -w "HTTP %{http_code}\n" https://hexbot-genesis.netlify.app/
HTTP 200
W: 419 hexbot.html (canvas 2枚 + index.js のみ、サーバー/API要素なし)
```

- index.js 取得 + ネットワーク/永続化シンボル走査（fetch/api/http/WebSocket/localStorage 全て 0 件）:
```
$ curl -sL -A "Mozilla/5.0" -o hexbot.js -w "js HTTP %{http_code} %{size_download}B\n" https://hexbot-genesis.netlify.app/index.js
js HTTP 200 114332B
$ grep -c "fetch\|api\|http\|WebSocket\|localStorage" hexbot.js
0
```

- robots.txt / sitemap.xml 実測（いずれも 404 = 構造化データ出口なし）:
```
$ curl -s -A "Mozilla/5.0" -o /dev/null -w "robots HTTP %{http_code} %{size_download}B\n" https://hexbot-genesis.netlify.app/robots.txt
robots HTTP 404 3449B
$ curl -s -A "Mozilla/5.0" -o /dev/null -w "sitemap HTTP %{http_code} %{size_download}B\n" https://hexbot-genesis.netlify.app/sitemap.xml
sitemap HTTP 404 3449B
```

- 元 HN スレッド取得で score 3 / コメント 0 を確認（title/score/コメント欄）:
```
$ curl -sL -A "Mozilla/5.0" https://news.ycombinator.com/item?id=49590247 -o hn_hexbots.html
hn_hexbots.html: 5453 bytes — score "3 points" by unitX、comment-tree 空要素（コメント 0）
```
