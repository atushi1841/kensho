# QA v76 — 2026-09-09 19:10-19:35 JST (job 033ff6065ef7)

## 起動契機
monitor差分: score 75→85 / wip 3→2 / done 358→363 / streak=0 / skip=False / dirty=Y。
dirty=Yが本tickの主戦場となった（下記②が実害）。

## 検証対象（v75からの申し送り3件）

### ① dead-source 3タスクのworker処理追跡 → 3/3 done
| タスク | 判定 | QA実測 |
|--------|------|--------|
| t_27484abb knshow | 上流CF 502・ソース保持 | curl実測: 現在も502（全パス）。workerの「退役せずsentinel監視継続」判断を支持 |
| t_35da58ce twscrape | 修復（0.20.1+クッキー伝達） | **ライブ実測103件取得**（deadline/winners付き、tmp/test_twscrape_t35da58ce.py再実行）。248収集連続0件から完全復帰 |
| t_5ed34bc3 chance.com | 修復（&s=トークン廃止→正規表現任意匹配） | QA 19:17完了（本実行中）。commit 1f0485e、回帰テスト3件pass。ライブscrapeは110s timeout（サイト低速）→20:00収集で最終判定 |

### ② 【重要発見】worker doneタスクのコードが未コミット
t_35da58ceは18:47にdone済みだったが、実装差分（twscrape.py + pyproject.toml）が
ワーキングツリーに未コミットのまま残存（mtime 19:17まで更新なし=worker離脱後放置）。
done_guardを通過しているため「コミット済み」という保証が破られた事例。

**QA対処**: `git commit --only` で自前コミット（v70教訓準拠、ベアcommit回避）→ push。
- commit `a35c7df` fix(collect): revive twscrape... (t_35da58ce)
- push実測: origin/main..HEAD = 0件（1f0485e chance.com修正も同時におserializedされた）
- dirtyコードファイル = 0 を確認済み（monitorのdirty=Nへ遷移するはず）

**構造的指摘**: done_guardは「レポートにコミットハッシュ引用」を見るが、
「そのハッシュがHEADの子孫か」までは検証していない可能性。run#327のプロトコル違反
（complete呼ばずrc=0終了→reclaim）と同じ worker 側の終了手続きの穴。
→ critic v77 で「done前に git log origin/main..HEAD==0 検証をworker必須化」or
done_guardのハッシュ子孫チェック強化を提案化推奨。

### ③ t_e971e85a 最終指標（9/10 16:00 hunter投入≦3件）
workerがone-shot計測機構を登録済み（9764845、cron 50 16 10 9 *、
state/hunter_gate_measure.log は9/9 17:32 dry-run PASS記録あり）。
→ QA v77以降（9/10 17時以降）にクローズ。本tickでは機構の実在のみ確認。

## 事故観察: 19:00収集が Network unreachable で全滅
collect_20260909_190007.log は Step 1 で httpx.ConnectError（圏外）クラッシュ。
19:20時点のcurlは全正常（ken-kaku 301/chance 301）→ 一時的なWSLネットワーク断。
keepalive checkerが復帰を検知できなかった可能性は低いが、**20:00収集の成功を次tickで要確認**。
失敗継続なら【要ユーザー対応】エスカレーション。

## 1085 TankanNotes: 【要ユーザー対応】継続（再発3日目）
ss実測: :1085 LISTEN=0、socks5経由curl rc=7。アダプタTankan_HR01消失はSoftware復旧不能。
SAFETYバックオフ（圏外→10サイクルに1回再試行）で正常に自動停止、自宅IPフォールバックなし=ルール遵守。
→ **USB物理確認/再接続のみが解消手段。ユーザー対応until継続タグ維持。**

## 3軸評価
```json
{"evaluation":{"technical":{"score":8,"assessment":"dead-source3件の真因特定は全て実証的（CF502排除論/0.20.1 logged-out/トークン廃止）。QAライブ再測でtwscrape103件復帰を確認。減点: chance.comライブ未達(timeout)は20:00収集待ち。","evidence":"tmp再実行103件 / test_chancecom 3 passed / knshow 502 curl実測 / commits 1f0485e+a35c7df"},"business_kpi":{"score":7,"assessment":"twscrape（X直接検索）とchance.comの2ソース復帰は収集母数を直接増やす（twscrape単発103件=全ソース190件/tickに対し有意）。knshow上流死は収入影響を代替ソースが吸収中。","evidence":"18:00収集190件/tick維持、復帰2ソースで+αの見込み（20:00実測待ち）"},"cost_efficiency":{"score":6,"assessment":"t_35da58ceはrun327(1496s protocol violation)+run328(2156s)=計61分の二重走行。修正自体は正しくても終了手続きの欠陥がコストと未コミット事故を生んだ。","evidence":"Runs: #327 crashed / #328 2156s / 差分未コミットをQAが回収"}},"loop_health":{"score":85,"stagnation_streak":0,"verdict":"healthy"},"self_review_quality":{"valid":false,"notes":"worker自己レビューが『git commit/pushまで』をカバーせずdone。QA回収が有効に働いた事例だが、常態化すればdone_guardの信頼が崩れる。 critic v76(t_2aead8aa)は別問題(iteration budget)で進行中"},"verdict":"conditional_pass","next_steps":["20:00収集で chance.com>0 / twscrape>0 / 収集継続(19:00断の復帰)を最終実測","t_2aead8aa(iteration budget規則)の完了検証と効果測定(90/90枯渇回数の減少)","9/10 17時以降 hunter_gate_measure.log でt_e971e85a最終指標クローズ","done_guardにコミットハッシュ子孫チェック追加の提案化(critic v77へHANDOFF)","【要ユーザー対応】TankanNotes 1085 USB物理確認(再発3日目)"]}}
```

## 判定: **conditional_pass**
条件: ①20:00収集でのchance.com/twscrape正果確認、②done前push必須化の構造化。
本tickのQA能動修正: コミットa35c7df+push、コードツリークリーン化済み。
