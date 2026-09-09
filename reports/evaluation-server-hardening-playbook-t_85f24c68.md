# 評価レポート: Show HN: Server hardening playbook where every item is failure/fix/verify

- Task: t_85f24c68
- 対象: https://github.com/Sanexxxx777/server-hardening-playbook / HN: https://news.ycombinator.com/item?id=49593916 (score 3, コメント 0)
- カテゴリ: アプリ/ツール / 非API自動収益
- 判断: **却下（非収益・実装対象外。worker 実装タスクへ切り出さない）**
- 実装工数推定: 適用外（着手すべき収益商品なし）

## 対象の実態
**server-hardening-playbook** = production Linux サーバをロックダウンするための、Markdown で書かれた静的チェックリスト/ベストプラクティス集。各項目が「failure → fix → verify」の3段構成（問題点 → 修正コマンド → 検証コマンド）で、SSH / firewall / サービス binding / リモートデスクトップ / 秘密鍵 / DB認証 / 攻撃面監査 / インシデント対応 / 変更規律 / サプライチェーン等 12章 + 1ページ版 CHECKLIST.md。
- 実体: GitHub リポジトリ内の README.md + docs/*.md + CHECKLIST.md の**静的ドキュメントのみ**。サイト・API・管理画面・DB・バックエンド一切なし。
- 配布: MIT License 無料OSS（実測 LICENSE: Copyright 2026 Aleksandr Shulgin, "free of charge"）。著者は @Sanexxxx777 / Telegram @Aleksandr_NFA。
- 実測: GitHub stars **8**（aria-label="8 users starred"）、HN score **3**・コメント **0**件。注目度は極小。

## データの出所・収益要素（決定打）
- **収益要素ゼロ**：README 全文・LICENSE 実測で、価格・サブスク・有料版・寄付・商用レイヤの記載一切なし。完全無料の静的ドキュメント。
- **スクレイピング対象データが存在しない**：サイトではなく GitHub リポジトリ + Markdown 文書。裏に集約・再販できる独占データ（属性・リスト・DS・API）がない。
- **手法の内容が自由公開のセキュリティ常識**：SSH 無効化・firewall default-deny・サービス binding・秘密鍵管理・DB認証等は、CIS Benchmarks / Lynis / Mozilla ・Curlie 等の既存無料チェックリストと重なるコモディティ知識。今 README にある内容を集約+LLM要約しても誰でも再現可能で独占性ゼロ。
- **MIT で無料公開済み**：リポジトリごと再梱包して販売できる法的余地はあるが、既に著者が無料で公開済みのため再販価値ゼロ。

## 自動化キーワード判定
Hunter 検出「自動化キーワード含む: あり」は誤検出。タイトル/本文に自動化語は無く、「failure/fix/verify」は**ドキュメントの行ごとの構成（問題/修正/検証）**を指す記述であり、収集・配信・収益自動化の文脈ではない（スキル判定の「技術速報・開発ツール内部機能=除外」パターンに最も近い）。

## 3点評価（Kensho 非API収益モデル）
### 1) プロトタイプ — 不成立
スクレイピング対象データ・収集対象・独占データ資産が皆無。Kensho の Python スクレイピング+LLM要約資産を再利用して再現困難な価値を積む対象がゼロ。内容を「要約データ商品」にするのも、無料公開済み OSS ドキュメントの再要約で誰でも再現できコモディティ化する。

### 2) ローンチ手順 — 不成立
Kensho の配置経路（データAPI / 自動化 / 自前FastAPI / Apify/RapidAPI）のいずれにも乗らない。静的ドキュメントを自前ホストしても受動収益化の仕組みが無い（ペイウォールを掛ける独自性も無い）。

### 3) 集客 — 不成立
集客アセット（属性データ / CtoA / 既存トラフィック / 既存観客）ゼロ。GitHub star 8・HN score 3・コメント 0 = 観客規模が微小。サーバー管理のベストプラクティスを求める観客は Kensho の既存観客（国内懸賞/スクレイピング系）と重ならず、再配布先も無い。

## 結論
server-hardening-playbook は「アプリ/ツール」カテゴリの静的ドキュメントOSS（MIT 無料公開済み）で、①収集対象データ/API/DS 皆無 ②収益要素ゼロ・CIS Benchmarks/Lynis 等と重なるコモディティ知識 ③Kensho Python資産の再利用対象なし ④集客ゼロ（star 8 / HN score 3 / コメント 0）。Apify/RapidAPI 以外のどの手法でも Kensho の収益商品に構成できないため、worker 実装タスクへの切り出しは行わない。

## verification_evidence
対象タスク: t_85f24c68（実測コマンド出力の引用）

- GitHub リポジトリ取得（HTTP 0 = 成功、HTML 300,283 bytes）:
```
$ curl -sL -m 25 -A "Mozilla/5.0" https://github.com/Sanexxxx777/server-hardening-playbook -o repo.html
HTTP github: 0 → 300283 repo.html
```

- README 取得 + 収益キーワード走査（価格/有料/寄付/商用レイヤの記載なし、grep 該当行 0）:
```
$ curl -sL -m 25 -A "Mozilla/5.0" https://raw.githubusercontent.com/Sanexxxx777/server-hardening-playbook/main/README.md
readme: 0 → 6567 README.md
grep -inE "price|charge|subscription|premium|pro version|donate|sponsor|paid" README.md → exit 1 / 該当行なし
```

- LICENSE 実測（MIT, free of charge）:
```
$ curl -sL -m 20 -A "Mozilla/5.0" https://raw.githubusercontent.com/Sanexxxx777/server-hardening-playbook/main/LICENSE | head -5
MIT License
Copyright (c) 2026 Aleksandr Shulgin (@Aleksandr_NFA)
Permission is hereby granted, free of charge, to any person obtaining a copy
```

- HN スレッド実測（score 3 / コメント 0）:
```
$ curl -sL -m 30 -A "Mozilla/5.0" "https://news.ycombinator.com/item?id=49593916" -o hn.html
exit: 0 → 4402 hn.html
class="score" id="score_49593916">3  /  commtext 数 = 0
```

- GitHub star 数（実測 8）:
```
$ grep -oE 'aria-label="[0-9]+ users starred this repository"' repo.html
aria-label="8 users starred this repository"
```

## 検出パイプラインへの推奨除外ルール
- カテゴリ「アプリ/ツール」かつ対象が 静的ドキュメントOSS（Markdown/README/ガイドの GitHub リポジトリのみ、サイト・API・DB・サービスなし）で、収益要素・収集データを持たない場合、自動的に却下。
- さらに MIT/Apache/GPL 等で無料公開済み && GitHub stars < 10 && HN score < 20 && コメント 0 なら即却下。
- 既存セキュリティ/健全性チェックリスト（CIS Benchmarks / Lynis / Mozilla / LinuxCNC系）と同内容のコモディティ知識を集約するだけのドキュメントは即却下。
