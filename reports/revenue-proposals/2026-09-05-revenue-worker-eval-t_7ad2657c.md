# revenue-worker 評価記録: 非収益・実装対象外判定 (2026-09-05)

## タスク
- Kanban: `t_7ad2657c` [非API自動収益] アプリ/ツール: Show HN: Sirenfall
- 発見元: kensho-non-api-revenue-hunter（HN 自動検出）
- 元記事: "Show HN: Sirenfall, a civil defense siren synthesized in Web Audio" (https://news.ycombinator.com/item?id=49556678)
- URL: https://sirenfall.live/ ／ 実装: beeswaxpat (GitHub: sirenfall, 単一HTML・MIT)
- 指示: 「Apify/RapidAPI 以外で実装できるか」評価。実装可能なら 1) プロトタイプ 2) ローンチ手順 3) 集客の3点を 24h 以内に着手。

## 判定: 実装対象外（収益機会なし）

## 根拠（HN API 実測 + 本文）
| 項目 | 値 |
|------|-----|
| 著者 | beeswaxpat |
| 種別 | Show HN（Web Audio による防災サイレンの生成アート） |
| score | 5（公開時点） |
| descendants | 1 |
| 唯一のコメント | 49561907（atmanactive）= 音の現実感への技術的フィードバックのみ。収益・採用・購入の言及なし |
| CtoA | 無し（「No cookies, no personal data… anonymous page-count pixel」= 無料公開前提） |
| 内容 | ディストピア都市の雨のシェルター窓シーン。引き開けてサイレン塔が回転。515/618Hz 5:6 二重音を Web Audio で合成（360°回転・ドップラー等は角連動）。単一HTML・MIT OSS。収益要素ゼロ |

### 非API収益として成立しない理由
1. **収益化の起点そのものが記事に無い** — 作者自身が「無料・クッキーなし・広告なし・ページカウントピクセルのみ」と明言。OSS 単一 HTML で、販売物・登録導線・サブスク・寄付・待機リストが全て不在。
2. **Kensho の非API資産（スクレイパー/自動化/Gumroad/RapidAPI）が一切適用できない** — スクレイピング対象データなし・課金ゲートなし・ツール連携なし・マーケット出品要素なし。Web Audio のアート体験で、データ商品にも業務自動化にもならない。
3. **需要も支払い意欲もゼロ** — score 5 ・コメント1件は技術フィードバックのみで市場反応無し。購入者セグメントが存在しない（「siren community」は趣味が高じた無料愛好層）。
4. **競合/代替が全て無料** — 同種の心象風景ブラウザアート（itch.io の無料作品群、shader 系 ambient scene）は無料供給が文化であり、切り出して有料化する余地が著しく薄い。

### 強引に組み立てた場合の反証（却下理由）
- 「アンビエント睡眠/集中用ベースミュージックに転換」→ 既に大規模な無料市場（brown noise系 は無料）、Sirenfall の差別化（サイレン警報）はむしろ安眠用途と逆特性。E/A 逆転。
- 「テンプレート/コース教材化」→ 単一 HTML の増減・単発アートで複製可能な手順知見が薄く教材価値が成立しない。Web Audio 合成ノウハウは Qiita/OSS に無料氾濫。
- 「有料壁紙/GIF販売」→ アニメーション保存(Sキー)が無料内蔵で回収不能。

## 結論と申し送り
- 本タスクは**評価完了 = 実装対象外**。プロトタイプ/ローンチ/集客の着手は行わない（着手すべき現実的機会を検出できないため）。作業切り出しは行わず `kanban_complete` で終了。
- hunter へのフィードバック: **「単一HTML・MIT・CtoAなし・無料公開を明言する Web アート/生成体験」は非API収益カテゴリから除外** するルールを推奨。判定条件の目安: ①ライセンスが OSS/MIT かつ ②無料公開明言（広告なし・カウントピクセルのみ）かつ ③販売・課金・登録導線が本文に見当たらない 場合は「アプリ/ツール」カテゴリでもスコア下限(5未満)で落とす/即時除外。
- 次候補: 同 worker の過去申し送り t_c4343276（Apify PPE 値上げ A/B）など、収益即時発生の実装タスク。

## 検証エビデンス
- HN Firebase API `/v0/item/49556678.json` → by=beeswaxpat, score=5, descendants=1, text に OSS/MIT・無料公開明言を確認
- `/v0/item/49561907.json` → 唯一コメントは技術的フィードバックのみ（収益/採用言及なし）
