# Scrapling A/B 比較 — 収集TLS指紋偽装 use_scrapling 有効化準備（critic v142 / t_cafe0cdd）

日時: 2026-09-13 14:38–14:43 JST / 実行: kensho-revenue-worker (WSL /mnt/d/Project2/kensho .venv)
スクリプト: workspace scrapling_ab.py / ja4_check.py（読み取り専用、config.yaml 未変更）

## 目的
research-20260913.md 提案A（現行httpxのJA4=t13d1712h1…は非ブラウザ丸腰 → curl_cffi
chrome136でt13d1516h2…へ）の受け入れ条件検証。GO待ちの事前A/B。

## 1. 解析件数A/B（現行fetch=httpx vs scrapling_fetch、各1ページ、同一時間帯）

| 収集源 | URL | A httpx (status/件数/長) | B scrapling (status/件数/長) | 差分 |
|---|---|---|---|---|
| knshow | https://www.knshow.com/ | 502 / n/a / 6400B | 502 / n/a / 6400B | 同一（後述） |
| ken-kaku | present.cgi?id=104510000 | 200 / 4 / 36654B | 200 / 4 / 36654B | +0.0% |
| kenshou.club | /archives/tag/twitterで応募 | 200 / 25 / 491871B | 200 / 25 / 491871B | +0.0% |
| cp.meikan | /xcp/ | 200 / 10 / 69083B | 200 / 10 / 69083B | +0.0% |

- パース正規表現は各ソース実装（knshow.py:13 / kenkaku.py:47 / kenshouclub.py:40 /
  cpmeikan.py:36-39）と同一パターン。
- 3源はバイト一致・解析件数一致（±10%基準をクリア、実差0%）。

### knshow 502 について
両経路交互3回+追加1回すべて HTTP 502、応答本文は Cloudflare 502 Bad gateway
エラーページ（"www.knshow.com Host: Error — The web server reported a bad gateway
error"、Cloudflare/TokyoはWorking表示）。= **オリジン側の障害**であり指紋差異ではない
（httpxでもscraplingでも同一応答）。この日のknshow比較はn/aだが、両経路同一＝回帰リスクなし
の傍証となる。回復後に再度 `https://www.knshow.com/twitter` で再確認推奨。

## 2. JA4実測（tls.peet.ws/api/all）

| クライアント | JA4 | 判定 |
|---|---|---|
| 現行 httpx | `t13d1712h1_ab0a1bf427ad_8e6e362c5eac` | 非ブラウザ（GREASE無し・h1・拡張総数17=Python系） |
| scrapling(curl_cffi) | `t13d1516h2_8daaf6152771_d8a2da3f94cd` | **Chrome一致（t13d1516h2系、GREASE・h2・延長16）** ✓ |

受け入れ条件「JA4実測値がt13d1516h2…系に切り替わる」を**充足**。research 9/13の
自己実測と再現一致。

## 3. ★重要発見: use_scrapling:true の実効範囲はknshow経路のみ

collector.py:214-215で `_do_fetch/_do_fetch_retry` を切り替えるが、使用箇所は
- collector.py:254（knshow一覧 /twitter/page:N）
- collector.py:302（knshow詳細 /detail/*.html）
の2箇所のみ。一方
- **kenkaku.py:37** は `httpx.Client` 直叩き
- **kenshouclub.py / cpmeikan.py** は `sources.common.fetch`（httpx）をモジュール内import直接呼び
- **knshow.py:31 resolve_redirect** は `httpx.Client` 直叩き（一覧→詳細は切替対象でもリダイレクト解決はhttpx）

→ 設定をtrueにしても**ken-kaku/kenshou.club/cp.meikan/knshowリダイレクトはhttpx指紋のまま**。
「4源保護強化」として完成させるには scrape_* 関数への `_do_fetch` 引き回し（または共通fetchの
config参照化）のパイプライン改修が必要＝.hermes.md禁止領域のため別途GO+criticカード相当。

## 4. 次要事項
- scrapling 0.4.15 が `Fetcher()` 生成時に "deprecated… Use `Fetcher.configure()` instead"
  WARNING（scrapling_fetch.py:38）。動作には支障なし、将来のメジャーで削除予定。
- タイムアウト: scrapling経路はCloudflare突破待合で体感1〜5秒/リクエスト、現行httpxと同等以下。

## 5. 判定と次アクション
- 成功指標: 解析件数±10%以内 = **PASS**（3源0%差、knshowはオリジン502で両経路同一n/a）
  / JA4 Chrome一致 = **PASS**
- config切替（use_scrapling: true）は**未実施**（.hermes.mdゲート: カードコメントにGOなし）。
- GO後の手順: config.yaml:184 true → 収集1run → collected.json件数100以上・HTTPエラー率
  前回比 → 失敗時同一行false戻すのみ。
- GOと同時に上記 §3 の実効範囲の狭さを承知おくこと（true化のみではken-kaku等3源は無効）。
