# 評価レポート: Show HN: Build with Python – a beginner course where your code draws

- Task: t_9a358f9b
- 対象: scimigo.com (https://scimigo.com/en/learn/build-with-python/01-draw-with-python) / HN: https://news.ycombinator.com/item?id=49956771 (score 3, comments 16)
- カテゴリ: 教育コース / 非API自動収益
- 判断: **却下（非収益・実装対象外。worker 実装タスクへ切り出さない）**
- 実装工数推定: 適用外（着手すべき収益商品なし）

## 対象の実態
**SciMigo 「Build with Python」** = ブラウザ内PyodideでPythonを学ぶ13モジュールのインタラクティブコース。第1モジュール「Draw with Python」は無料、残りは$49 one-time。
- 配布: ブラウザアプリのみ（Pyodide/WASM）。モバイルアプリ・API・サーバーレイヤなし。
- ライセンス: サイト上で明記なし（有料教育コース）。
- 実測: HN score 3（1時間時点）、コメント16。スコア低い。
- 実測: robots.txt は `/en/learn/*/decks/` と `/en/learn/*/labs/` をDisallow。sitemap.xml に全モジュールURL掲載。RSS はNext.js静的HTML返却のみ（XML RSS無し）。
- API: 画面内JSに `/en/blog`, `/en/learn`, `/en/privacy`, `/en/terms` 以外のAPIエンドポイント検出なし。バックエンドAPIはクライアント側に隠蔽または外部プロキシ。

## データの出所・収益要素（決定打）
- **収益要素ゼロ**: コースはScimigo社の有料商品。Kenshoがスクレイピング/再販できる「データ」（属性・価格リスト・レビューDS・API）が存在しない。
- **スクレイピング対象データが存在しない**: サイトはNext.js SPA + Pyodide WASM。コンテンツはブラウザ内で動的描画（ロード時のHTMLに空ラベルのみ）。公開RSS/API/ダウンロードDSなし。robots.txt でlabs/decksはクロール禁止。
- **技術スタックが根本乖離**: Python教育コース。KenshoのPythonスクレイピング+LLM要約資産を再利用する載せる物がゼロ。
- 競合: freeCodeCamp,Codecademy,CS50等の既存無料教育コースと同領域。

## 自動化キーワード判定
Hunter検出は誤検出の可能性が高いが、本タスクはスコア低・収益要素皆無のため判定不要。

## 3点評価（Kensho非API収益モデル）
### 1) プロトタイプ — 不成立
スクレイピング対象データ・収集対象・独占データ資産皆無。バックエンドもDBもWeb資産も無く、Kensho資産を再利用して再現困難な価値を積む余地ゼロ。

### 2) ローンチ手順 — 不成立
Kenshoの配置経路（データAPI / 自動化 / 自前FastAPI / Apify/RapidAPI）のいずれにも乗らない。有料教育コースのスクレイピング/再販は商業的利益相反。

### 3) 集客 — 不成立
集客アセット（属性データ / CtoA / 既存トラフィック / 既存観客）ゼロ。HN score 3 = 観客規模微小。教育コース観客はKensho既存観客（国内懸賞/スクレイピング系）と重ならない。

## 結論
「Build with Python」(SciMigo) は教育コース商品で、①収集対象データ/API/DS皆無 ②有料コストを伴うスクレイピング対象（商業的利益相反）③Kensho Python資産未利用・技術スタック乖離 ④集客ゼロ（HN score 3）。Apify/RapidAPI以外のどの手法でもKenshoの収益商品に構成できないため、worker実装タスクへの切り出しは行わない。

## verification_evidence
対象タスク: t_9a358f9b（実測コマンド出力の引用）

- HNスレッド実測（score 3 / コメント16）:
```
$ curl -sL -m 30 -A "Mozilla/5.0" "https://news.ycombinator.com/item?id=49956771" -o hn_49956771.html
exit: 0
score 3 points by davidwshao
```

- SciMigo robots.txt 実測:
```
$ curl -sL -m 20 -A "Mozilla/5.0" https://scimigo.com/robots.txt
User-Agent: *
Allow: /
Disallow: /*/decks/
Disallow: /*/labs/
Sitemap: https://scimigo.com/sitemap.xml
```

- RSSパス確認（XML RSS無し、Next.js静的HTML返却）:
```
$ curl -sL -m 20 -A "Mozilla/5.0" https://scimigo.com/rss | head -c 200
<!DOCTYPE html><html>...（RSS XML 非応答、HTML返却）
```

- サイト内JSAPIエンドポイント探索（公開APIなし）:
```
$ grep -oE '"/[a-z]+/[a-z-]+"' scimigo_root.html | sort -u
"/en/blog" "/en/learn" "/en/privacy" "/en/terms"
```

## 検出パイプラインへの推奨除外ルール
- 「教育コース/ブラウザ学習アプリ」カテゴリはKensho対象外（収集データ・有料化余地・Kensho資産再利用いずれも無し）。
- HN score < 20 は即却下材料（観客規模微小）。
- robots.txt でlabs/decksがDisallowならばスクレイピング対象外。
