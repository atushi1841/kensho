# critic v61 提案 — cpmeikan deadline 全欠損のバックフィル恒久化（収集品質/BOT安全）

作成: 2026-09-08 20:4x JST / kensho-revenue-critic (4baf143523e0)
priority判定: health=95 / new_proposals / ready=0（供給不足）→ 1件提案可
ステータス: [open]

## エビデンス（実測）

`data/collected.json`（2026-09-08 20:13 スナップショット、1062件）を直接解析:

| source | 総件数 | 適用済 | 適用率 | deadline空 |
|--------|-------:|------:|------:|----------:|
| cpmeikan | 478 | 140 | 29.3% | **478（=全件空）** |
| knshow | 440 | 190 | 43.2% | 0 |
| kenshouclub | 85 | 45 | 52.9% | 0 |
| kema | 30 | 29 | 96.7% | 0 |
| ken-kaku | 10 | 10 | 100% | 0 |

- cpmeikan は**最大の収集源(478件)なのに deadline が全件空**、適用率が最低(29.3%)。
- 未適用 cpmeikan 338件を snowflake ID で tweet 年齢推定: **78件が30日超（=既に期限切れの懸賞）**、14日以内は59件のみ。
- 保存済み tweet_text を正規表現で舴めると 64件はローカルで deadline 抽出可能（例: 「締切：9/6」→既に過去）。

## 問題（なぜ高優先か）

`kensho/application/applier.py:906-916`:
```python
deadline_info = item.get("deadline", "") or "未設定"   # 空文字 → "未設定"に化ける
if deadline_info != "未設定":
    try:
        if strptime(deadline_info, "%Y-%m-%d").date() < now: [SKIP] 締切切れ
    except ValueError: pass
```
- cpmeikan の deadline は全件空 → `or "未設定"` により**締切切れチェックが構造的に一度も発火しない**（例外ですらなく、黙って素通り）。
- 結果、期限切れ懸賞（30日超が78件確認）にもいいね/RT/フォローが実行され得る。**当選確率ゼロのアクションで日次上限とBOT検出リスクを浪費する**経路が最大の収集源で常時開いている。
- 既に `backfill_deadlines.py`（173行・knshow詳細再取得＋fixupx本文抽出）が存在するのに、**どのcronにも配線されておらず**（grep結果: cron側参照0）、実行されず放置されている＝自動復旧が阻害された状態（優先度判定基準・高②に該当）。
- **【決定的実測】既に適用済みの cpmeikan 140件のうち 86件（61.4%）がツイート投稿から21日以上経過**（最古は160日前、90/89/85/85日前…）。締切が実質1週間前後のX懸賞で、これは期限切れ案件にアクションを消費している実績そのもの。日次上限（follow/rt/like）とBOT検出リスクの相当量を無駄に燃やしている。

## 提案（収集層・応募ロジックは変更しない）

`backfill_deadlines.py` を収集パイプラインの**後処理**として cpmeikan 空deadlineに適用し、抽出できた deadline を書き戻す。applier の既存の「deadline設定時は締切切れSKIP」が正しく効くようにするだけ（applier.py ロジック自体は触らない＝毎回確認境界を回避）。

1. collector 完了後に `backfill_deadlines` を cpmeikan の空deadline件に限定実行（fixupx本文抽出は既に tweet_text 保有分はローカルで可 → API不要の高速パス追加）。
2. 期限切れ（抽出 deadline < today）は collected.json 上で `expired=True` フラグ付与 or deadline を実値で埋め、applier の既存SKIPに渡す。
3. 回填率を計測・報告に記録。

## 成功指標（数値）
- cpmeikan の deadline 非空率: 0% → **70%以上**（次回収集後）。
- 30日超の未適用 cpmeikan への applied が**0件**（apply後 daily_counts 監査）。
- 収集1回あたりの「有効応募候補件数」が増加（無駄アクション減）。

## 検証コマンド（QA用1行）
```bash
python3 -c "import json;c=json.load(open('data/collected.json'))['collected'];cp=[x for x in c if x.get('source')=='cpmeikan'];print('non-empty deadline %=',round(100*sum(1 for x in cp if (x.get('deadline') or '').strip())/max(1,len(cp)),1))"
# → 70 以上なら PASS
```

## 失敗時の代替案
fixupx 本文取得がrate-limitで落ちる場合は、既に保存済みの `tweet_text` からのローカル正規表現抽出（64件/338件で可能）のみで回填し、残りは空のまま＝現状維持より改善。API呼び出しを増やせない場合は `expired` 推定を snowflake 年齢（30日超＝expired）で代替する。

## 影響範囲・ロールバック
- 変更ファイル: `kensho/scraping/collector.py`（後処理フック）＋ `backfill_deadlines.py`（cpmeikanローカル抽出パス）。applier.py は変更しない。
- ロールバック: git revert 当該コミット。collected.json は毎回収集で再生成されるためデータ被害なし。
- レビュー: 応募ロジック未変更のため「毎回確認境界」に該当しないが、収集順序変更は tests/test_collector.py で回帰確認。
