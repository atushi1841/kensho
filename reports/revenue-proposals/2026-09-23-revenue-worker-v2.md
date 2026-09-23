# revenue-worker 実施記録 v2（2026-09-23）— 収益ダッシュボード「本日収集実績」手書き値の自動集計化

担当: nightly-worker (cron 5e8ec4984bba) / assignee kensho-revenue-worker
実施時刻: 2026-09-23 21:45–22:15 JST
タスク種別: 未所有の収益計測基盤バグ修正（t_5e16a983 の申し送りの消化・カード未紐付けのため本記録を検証記録とする）

## 1. 症状（実測）

t_5e16a983（dashboard収集実績表示修正）は **HTMLとJSONへ手書きで値を入れただけ** で、
自動生成経路に乗っていなかった。そのため次の2つの虚偽リスクが残っていた。

1. `scripts/kensho_revenue_dashboard.py` を実行してダッシュボードを再生成すると、
   「本日収集実績」カードが **消える**（生成器にカードが存在しない）。同時に
   「RapidAPI API」カードが復活し、手書き編集と生成物が食い違う。
2. `data/revenue-daily.json` の `collectors.collected_today=222` は手書き値であり、
   翌日以降も 222 のまま固定化しうる（＝虚偽報告）。

## 2. 原因

- 集計元が存在せず、表示値の出所が「人の手」だけだった。
- 整合性チェッカー `business-dashboard-count.sh` は
  「手書きHTML vs 手書きJSON」の自己参照比較だったため、両方が同じ誤値に腐っても緑になる。

## 3. 実施内容

| ファイル | 変更 |
|----------|------|
| `kensho/core/collection_volume.py`（新規） | 収集ボリューム指標の **唯一の集計元**。`collected_today`=当日の収集ログ `logs/collect_<YYYYMMDD>_*.log` に出現したユニークX URL数（走査件数ではない・重複は1件）、`collected_total`=`data/collected.json` の累計。 |
| `tests/test_collection_volume.py`（新規） | 6テスト: 複数run重複の丸め／別日・非status URL除外／twitter.com表記／収集0件runは加算なし／collected.jsonのdict・list・欠落の3形態／キーと出典表記の固定／欠落ディレクトリで0。 |
| `scripts/kensho_revenue_collect.py` | `collectors.collected_today / collected_total / collected_today_source / collected_today_runs` を実データから自動計上（失敗時は warning のみ・収集は止めない）。テスト注入用に `build_revenue_summary(..., volume=None)` を追加。 |
| `scripts/kensho_revenue_dashboard.py` | 「収集ボリューム（実データ自動集計）」カードを追加し、値はライブ集計から描画（集計失敗時は revenue-daily.json の記録値へフォールバック）。 |
| `tests/test_revenue_collect.py` | collectors の完全一致assertを、健全性3フラグ＋ボリュームキー検証へ更新（新規 `test_collectors_include_volume_stats` 追加）。 |
| `revenue-status.html` | 再生成（手書き222 → 自動集計478/1191・RapidAPIカード復活）。 |
| `~/.hermes/profiles/kensho-sweeps/scripts/business-dashboard-count.sh`（リポジトリ外） | 自己参照比較をやめ、ライブ集計値との突き合わせに変更（不一致は exit 1 で再生成手順を提示）。 |

モデル切替・垢情報・応募ロジック・GALLERIA・物理操作には一切触れていない（禁止領域外の低リスク修正）。

## verification_evidence

```
$ python3 -m pytest tests/test_collection_volume.py tests/test_revenue_collect.py -q --no-cov => 65 passed in 5.05s
```

```
$ python3 -c "from kensho.core import collection_volume as cv; print(cv.volume_stats('/mnt/d/Project2/kensho'))" => {'collected_today': 478, 'collected_total': 1191, 'collected_today_date': '2026-09-23', 'collected_today_runs': 14, 'collected_today_source': 'logs/collect_20260923_*.log'}
```

```
$ bash /home/atushi/.hermes/profiles/kensho-sweeps/scripts/business-dashboard-count.sh（再生成前） => ❌ 不一致: dashboard=222 vs live=478 / exit=1
```

```
$ python3 scripts/kensho_revenue_dashboard.py => ✓ revenue-status.html 生成完了 (22 entries)
```

```
$ bash /home/atushi/.hermes/profiles/kensho-sweeps/scripts/business-dashboard-count.sh（再生成後） => ✅ 一致: dashboard=478, live=478 ✅ 一致: Apifyアクター dashboard=25, json=25 / exit=0
```

```
$ grep -A2 '収集ボリューム' /mnt/d/Project2/kensho/revenue-status.html => <div class="card-title">収集ボリューム（実データ自動集計）</div> … <div class="stat-val" style="color:#3fb950">478</div><div class="stat-label">本日収集実績</div> / <div class="stat-val" style="color:#58a6ff">1191</div><div class="stat-label">収集済み総数</div>
```

```
$ python3 -m mypy kensho/core/collection_volume.py => Success: no issues found in 1 source file
$ .venv/bin/ruff check kensho/core/collection_volume.py tests/test_collection_volume.py scripts/kensho_revenue_collect.py scripts/kensho_revenue_dashboard.py => All checks passed!
```

```
$ python3 -m pytest -q --no-cov -p no:randomly（全体・修正後） => 1 failed, 908 passed, 6 skipped in 152.72s（失敗1件は tests/test_regression_gates.py::test_gate_protocol_violation_crash = ライブkanban.db依存の既存gate。t_8e1e4934 が rc=0 無打刻で ready に戻っている実データ起因で、本変更とは無関係。修正前は collectors 完全一致assertの1件も赤だった＝本変更を検知→テスト更新で解消）
```

## 4. ロールバック

本コミットを `git revert` するだけ（データファイルの削除なし・DB変更なし）。

## 5. 自己レビュー（Reflexion）

```json
{"self_review":{"what_was_done":"収益ダッシュボードの「本日収集実績」手書き値を、収集ログ/collected.json からの自動集計へ置換し、再生成で消える・値が固定化する虚偽リスクを除去","what_went_well":["集計元を単一モジュール化し収集スクリプト/ダッシュボード/チェッカーで共有","チェッカーが誤値222を再生成前に❌検知→修正後✅で出口を実測","既存テスト破壊を検知して同ターン内で更新・全関連テスト緑化"],"what_could_improve":["収集ログ集計はrun内の収集URL行のみを数える方式のため、収集停止runは0として扱われる（可用性の指標としては別途run数が必要）","revenue-daily.json の値は記録時点スナップショットであり日中はライブ値とズレる（仕様として明記したがUIでの注記は今後）"],"mistakes_or_risks":["別タスク(t_96c94435)の未コミット collector.py/simple_rt_classifier.py と同じ作業ツリーで作業しており、コミット対象を明示パスで限定しないと混入する（限定して対応済み）"],"learned":"自動生成されるダッシュボードに手書きでカードを足しても次の再生成で消える。修正は必ず生成器側（＋集計元）に入れる","confidence":9,"verification_evidence":"pytest 65 passed(関連)/908 passed(全体・残1件は既存ライブgate)、mypy/ruff緑、チェッカー exit0、実測値 478/1191"}}
```

## 6. 申し送り

- 収集runの可用性（当日のrun数）は `collected_today_runs`（本日=14本）としてダッシュボードに併記した。
  当日10:00–12:00・14:00–20:00帯のrunは収集0件（`guarded_source` 引数不整合で Step2c 以降停止＝290c480で修復済み）。
  同種の「収集0件run」を critic が検知できるよう、`collected_today` と `collected_today_runs` の比を監視指標に使える。
- `tests/test_regression_gates.py::test_gate_protocol_violation_crash` は t_8e1e4934 の未回収 rc=0 終了が原因で赤。
  恒久対策カード t_02a5afc4（ready/kensho-worker）の消化で解消見込み。
