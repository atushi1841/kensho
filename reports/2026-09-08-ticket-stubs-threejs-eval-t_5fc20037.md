# 評価レポート: Show HN: Browse 27 years of movie ticket stubs in ThreeJS（t_5fc20037）

- Task: t_5fc20037
- 対象: HN https://news.ycombinator.com/item?id=49604127（score 3、コメント 0、投稿者 zebomon）
- 対象サイト: https://gardnermcintyre.com/stubs/ / https://github.com/billybillymc/stubs
- カテゴリ（Hunter）: アプリ/ツール
- 実装工数推定: 適用外（実装すべき収益商品が存在しない）
- 判断: **却下（実装対象外）**

## 対象の実態（HN API・GitHub リポジトリ・data.js・ライブサイトを実測）

作者の個人的な映画チケット半券コレクション（27年分）を Three.js で閲覧する
MIT ライセンスの OSS「agent harness（自作UIキット）」で、収益モデル皆無の趣味プロジェクト。

- HN item 実測: score 3 / descendants 0、text 投稿（URL 無し）。本人が「reposted with the link」と
  記す通り、リンク付き再投稿 49604590 も score 1 / コメント 0 — 元投稿・再投稿とも観客ゼロ。
- GitHub billybillymc/stubs 実測: created 2026-09-07（投稿前日）、stars 0 / forks 0、
  license MIT、description "Agent harness to create your own over-engineered UI for
  browsing a movie ticket stub collection"。
- data.js 実測: 「Six invented tickets ship with the kit」— 同梱データは作者が描いた
  サンプル6件のみ。実コレクション（写真）はリポジトリに無く、転載・収集対象データ不在。
- README 実測: 「no build, no npm install」「Designed to work well with a coding agent」—
  Hunter の「自動化キーワード: あり」は "agent" 誤検出。サービスではなく DIY キット。
- ライブサイト gardnermcintyre.com/stubs/ は 200（静的 Three.js デモ）。API/RSS/pricing/
  販売導線なし。

## 3点評価

### 1) プロトタイプ
不成立。収益化の素材となり得るデータは作者の私物写真（非公開）だけで、公開されているのは
MIT コードとサンプル6件。模倣して「チケット半券ビューア」を作っても、ユーザー自身の
スキャンを自分で入力する手作業前提のツールで、Kensho の scraping+LLM 資産が活きる
収集対象（公開DS・API・RSS）が存在しない。コード自体が無料配布済み=コモディティ。

### 2) ローンチ手順
不成立。配置経路（データAPI / 自動化 / 自前FastAPI / Apify / RapidAPI）のいずれにも載らない。
「3Dビューア制作受託」は受動収益に非適合の労働集約事業。競合として Three.js 公式事例・
各種ギャラリーテンプレートが無料飽和。

### 3) 集客
不成立。HN score 3（元投稿）・1（再投稿）は却下閾値（score<20）を大きく下回り、GitHub
stars 0 — 観客規模が微小。対象側に集客アセット（メーリングリスト/CtoA/既存トラフィック）なし。

## 却下理由（スキル判定例と一致）
- 「大企業のOSS開発フレームワーク/OSSライブラリ（無料で配布、収集データ・有料化余地なし）」の
  個人版に該当 — MIT 無料配布キットで収益モデル皆無。
- 「自動化キーワード」は README の "coding agent 対応" 記述の誤検出（開発ツール内部機能記述パターン）。
- ネイティブの私物データ（作者の半券写真）は非公開で、公開ソース集約による再現すらできない=商品構成不能。
- 24h 以内のプロトタイプ/ローンチ/集客の3点で worker 実装へ切り出すべき商品ではない。

## verification_evidence

対象が収益導線ゼロの MIT OSS キットであること、同梱データがサンプル6件のみであること、
HN 注目度が閾値未満であることを実コマンド出力で検証した。

```sh
$ curl -s https://hacker-news.firebaseio.com/v0/item/49604127.json
{"by":"zebomon","descendants":0,"id":49604127,"score":3,"time":1788823953,
 "title":"Show HN: Browse 27 years of movie ticket stubs in ThreeJS",
 "type":"story","text":"edit - reposted with the link ... That part is here:
 https://github.com/billybillymc/stubs ..."}
（score=3, descendants=0, url フィールド無し → 却下閾値 score<20 未満。text 投稿のみ）
```

```sh
$ curl -s https://api.github.com/repos/billybillymc/stubs | grep -E '"(description|stargazers_count|forks_count|created_at|key)"'
  "description": "Agent harness to create your own over-engineered UI for browsing a movie ticket stub collection",
  "created_at": "2026-09-07T22:02:49Z",
  "stargazers_count": 0,
  "forks_count": 0,
    "key": "mit",
（MIT 無料配布・stars 0/forks 0・作成は投稿前日 → 収益導線・観客ゼロ）
```

```sh
$ curl -s https://raw.githubusercontent.com/billybillymc/stubs/main/data.js | head -8
/* THE COLLECTION.
   ... Six invented tickets ship with the kit so it runs the moment you
   open it. Replace this file with your own ... */
window.TICKETS = [
{ "id": 1, "title_raw": "JURASSIC PARK", ... "notes": "Sample stub — not a real ticket.",
（公開データは作者描画のサンプル6件のみ = 収集可能な実データ不在）
```

```sh
$ grep -iE "price|paid|sponsor|donat" README.md
（該当ゼロ — 販売・寄付・スポンサー導線なし）
$ curl -s -o /dev/null -w "%{http_code}" https://gardnermcintyre.com/stubs/
200
（ライブサイトは静的 Three.js デモのみ、API/RSS/pricing 無し）
```
