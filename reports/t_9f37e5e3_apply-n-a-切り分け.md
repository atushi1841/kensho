# t_9f37e5e3 — apply成功率 n/a の切り分け調査（2026-09-17 02:10 実測）

## 結論（切り分け結果）
**応募停止（applyが本当に止まった）が主因。測定源欠落は副次**。

- 9/16(JST) の実applyは audit.jsonl 換算で**3アクション**（atushi16　20:10のみ）、daily_counts 換算で**4アクション**。9/15 は正常稼働（完了行・数百件）。
- 9/16 の dispatcher ログには **`[OK] 完了: N成功/Mエラー` が全tickを通して0件**。応募ワーカーは全て「処理待ちのバッチなし」で何もapplyせず。
- 一方で dispatcher は正常spawn・proxy全部alive → **インフラ障害ではない**。ワーカーが起動したが、applyバッチを1つも解決できなかった。
- 「n/a（成功0/エラー0）」の数値自体は **actions.db が0バイトの幽霊DB** 由来で、本来は計測不能な欠陥。ただし応募が実質止まっているため n/a が結果的に実態を反映しているだけ。欠落修復（計測源変更）は必要だが、それを直しても隠れていたapplyは出てこない。

## 証拠（全て実測）

| 項目 | 9/15（正常） | 9/16（異常） |
|---|---|---|
| `logs/auto_*.log` の `OK 完了` 行 | 17件（223/3, 98.7%） | **0件** |
| `data/audit.jsonl` のJST当日成功アクション | 数十〜数百（UTC日毎 80/229/196） | **3件**（atushi16 20:10のみ） |
| `data/daily_counts.json` 当日アクション | 数百件級 | **4件**（follow1/rt2/like1） |
| dispatcher spawn / proxy alive | — | 全tick spawn・proxy=[1081,1082,1084,1085]全てalive |

- audit.jsonl は追記専用の不変履歴（ハッシュチェーン付き）。全508行=UTC 9/13:80 / 9/14:229 / 9/15:196 / 9/16:3。9/16(UTC=JST 9/16 09:00〜)は僅か3行。
- audit.jsonl 最後の実applyバッチは `2026-09-15T13:46:40Z`（=JST 9/16 01:46）以降、次の記録は `2026-09-16T11:10:48Z`（=JST 9/16 20:10）の atushi16 follow/rt/like。**約18時間apply記録が無い**。

## 該当ログ・記録パス

- **記録先**: `logs/auto_20260916.log` — dispatcher(`kensho-auto-apply.sh`)が垢別ワーカー出力を追記する日次ログ。
  全96tickで「今回 spawn」後に各垢が **`処理待ちのバッチなし`** を出力（0成功/0エラーで最後まで）。
- **判定ロジック**: `kensho/orchestrator.py` の `get_pending_batches()`（L110-229）が各垢の予定バッチを解決。9/16は全垢0件を返したため `_apply_account`(L244-) に到達せず apply 未実行。
- **バッチ定義**: `config.yaml` `accounts.<key>.schedule.batches` — atushi16=12バッチ(k) / kudou=10 / zin20120731=8 / TankanNotes=10。8:02〜22:28に分散しており、9/16の大半の時刻で「時刻超過＆当日未処理」のバッチが理論上存在する。
- **状態ファイル**: `data/orchestrator_state.json`（mtime 9/16 20:07）→ `last_processed` は atushi16=`2026-09-16:08:02`、kudou/zin20120731/TankanNotes=`2026-06-29`（当日未処理のまま）。
  - 8:02 に atushi16 のバッチが一度「処理済み」状態になったが daily_counts/audit に朝のアクションは**0件（0成功0エラーではlast_processed更新しない設計なので、8:02は何か発生報告あり）**。
  - kudou/zin/TankanNotes は6/29のまま＝当日バッチ未消化 → にも関わらずログは終日「なし」＝**当日実行時点の state が「対象バッチを全て処理済み」扱いだった**ことを強く示唆（状態ファイルが20:07時点の縮小後スナップショットであり、実行中の中身は追跡不能）。

## n/a 数値の正体（測定欠落は副次）

- `data/actions.db` は **0バイト・mtime 9/16 12:47** の幽霊DB。**生成コードが存在しない**。
  - `.py` 全文検索で `actions.db` / `apply_logs` を読み書きする実装は0件。唯一の参照は `scripts/kensho_winrate_analysis.py` L381 の docstring（`apply_logs不在→collected applied使用` で既にフォールバック実装済み）。
  - critic-observe-2026-09-17.md の「成功0/エラー0」は critic 自身が actions.db を直接読んで出したもので、**本番のライブ指標ではない**。
- 本番のapply成功率サロゲート = `scripts/gen_status_html.py` が `recent_runs`（`gen_status_data.py` が auto_*.log の `OK 完了` 行から算出）を成功率表示。9/16は完了行ゼロ→実測0。
- 正しい集計元（audit.jsonl / daily_counts / auto log 完了行）で9/16の実績を再集計しても**約0件（応募停止）**。測定欠落を修復しても実成功率は向上しない。

## 提案（次アクション）
1. [最優先] **get_pending_batches が9/16全tickで空を返した真因のライブ調査**。9/17 08:00以降の auto_20260917.log を確認し、朝バッチが解決されるか観測。解決されなければ orchestrator_state.json の last_processed が当日高刻印で固定されバッチを全skipしている可能性 → 対策は state の日付リセット / save_state の論理修正。
2. [副次・欠陥修復の準備] actions.db は幽霊なので「行動履歴DB」として実装するか、apply成功率の計測源を auto log の `OK 完了` 集計（gen_status_data.py 使用済み）へ一本化。実装は本カードのスコープ外（要別タスク）。
3. 20:10 atushi16 の3件のみ = バッチ自体は少数ながら発火したため、apply実行は完全停止ではなく「ほぼ停止＋ごく稀に微実行」。9/17 08:00以降の挙動で継続事象か一過性かを確定。

## 検証コマンド（再実行用・単純なシェル）
```
ls -la data/actions.db                       # 0バイト・mtime 9/16 12:47
cat data/daily_counts.json                   # 9/16 = 4アクション
grep -oE '"timestamp": "2026-09-[0-9]{2}' data/audit.jsonl | sed 's/.*: "//' | sort | uniq -c
grep -c "OK 完了" logs/auto_20260916.log      # 0（9/16）
grep -c "OK 完了" logs/auto_20260915.log      # 17（9/15）
grep -n "処理待ちのバッチなし" logs/auto_20260916.log | head   # 全tick
cat data/orchestrator_state.json
```
（`sqlite3` / `python3 -c` は単一クエリモード等で承認制になるため生シェルで代替可。）
