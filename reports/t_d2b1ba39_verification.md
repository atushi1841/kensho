# t_d2b1ba39 検証記録 — ダッシュボード直近実行の成功率偽陽性修正

タスクID: t_d2b1ba39
変更: scripts/gen_status_data.py（recent_runs の status 判定を実エラー基準へ）
コミット: e606bbe

## 問題
scripts/gen_status_data.py L318-327 の status 判定が `⚠️|FAIL|ERROR|失敗` を
位置比較で warn 扱いしていた。benign 行
（`[WARN] プロフィール確認失敗（続行）` / `[i] RT API失敗 → UIフォールバック` /
`[DEFER] 失敗アクション` / `[CEILING] 連続失敗`）が多数あるため、
0エラーで完走した run まで warn になり、gen_status_html.py（status=="ok" のみ成功集計）
が成功率を偽の 0.0% と表示していた。

## 修正
真の失敗のみ fail 扱いに変更:
- `❌` / `FATAL` / `[NG] 完了` → status=error
- `[OK] 完了: N成功 / Mエラー` の M>0 → status=warn
- それ以外（M==0） → status=ok

## verification_evidence

修正対象の差分（11 insertions / 6 deletions）:
```
$ git -C /mnt/d/Project2/kensho diff --stat -- scripts/gen_status_data.py
 scripts/gen_status_data.py | 17 +++++++++++------
 1 file changed, 11 insertions(+), 6 deletions(-)
```

再生成後の recent_runs 判定（9/15 の実失敗 warn/3 のみ維持、他は ok へ）:
```
$ python3 scripts/gen_status_data.py >/dev/null 2>&1 && python3 -c "import json;d=json.load(open('/tmp/kensho_status_data.json'));print([(e['time'],e['status'],e['error']) for e in d['recent_runs'][-5:]])"
[('23:45', 'ok', 0), ('23:45', 'ok', 0), ('23:45', 'warn', 3), ('23:53', 'ok', 0), ('22:46', 'ok', 0)]
```

ダッシュボードの成功率（修正前 0.0% → 修正後 80.0%）:
```
$ python3 scripts/gen_status_html.py >/dev/null 2>&1; grep -oE "直近5回.*成功率 <strong>[0-9.]+%</strong>" kensho-status.html
直近5回: 成功 4 / 失敗 1 — 成功率 80.0%
```

構文・コンパイル確認:
```
$ python3 -m py_compile scripts/gen_status_data.py && echo compile OK
compile OK
```

修正前エビデンス（タスク起票時 2026-09-18 21:30 実測・タスク本文より）:
`直近5回: 成功 0 / 失敗 5 — 成功率 0.0%`

## 受け入れ条件チェック
- [x] 再生成後 /tmp/kensho_status_data.json で 0エラー完走 run の status が "ok"
- [x] ダッシュボード「直近5回」成功率 0.0% → 80.0%（9/13・9/14・9/17・9/18 が成功集計）
- [x] 真の失敗（9/15 のエラー3）は従来どおり warn を維持（M==0 以外は warn）

## 自己レビュー（Reflexion）
```json
{"self_review":{"what_was_done":"gen_status_data.py の recent_runs status 判定を benign 文字列マッチから実エラー基準（❌/FATAL/[NG]完了/エラー数>0）へ修正し、ダッシュボード成功率の偽0%を解消","what_went_well":["実ログ4日分（9/13/9/14/9/15/9/17）で ❌/FATAL/NG完了/⚠️ が全0件と実測し、benign『失敗』文字列だけが warn を起こしていた真因を確定","修正前後の数値（0.0%→80.0%、warn/3 維持）を実測で比較"],"what_could_improve":["gen_status_data.py がトップレベル副作用スクリプトのため import ベースの回帰テストが書けず、pytest 追加は見送った（将来 _classify_run_status を関数抽出してテスト化したい）"],"mistakes_or_risks":["応募ロジック・プロキシ・収集には非干渉（表示・集計のみ）"],"learned":"観測性の集計は『エラー数のような構造化シグナル』を主、文字列マッチを従にすべき。benign マーカーを無条件 fail 扱いすると偽警報で成功率が0になる","confidence":9,"verification_evidence":"git diff --stat 11+/6- / recent_runs=[ok,ok,warn/3,ok,ok] / 成功率80.0% / py_compile OK"}}
```
