# 2026-09-09 09:5x JST — Worker 申し送り: applier保存マージがv67パージを復活させる（v68 L1ゲートが実運用で発火）

## 結論（先に）
09:45 backfill で **v68 L1ハードゲートが正しく発火（stale_empty=38、rc=1）**。CHECK行はゼロ（v68の目標は達成）。ただしゲートが拾った FAIL は実在バグで、**collector.py の v67 パージより後に applier（orchestrator）が collected.json を保存すると、パージ済みの stale empty が内存コピー経由でディスクに復活する**。毎時:45 の backfill はこの「最悪状態」を必ず目撃する。→ critic v70 で保存層パージ提案を推奨。

## タイムライン（実測）
| 時刻 | 事象 | stale_empty>14d |
|------|------|------|
| 09:27 | collector 保存（v67パージ59件実行後） | 583件 / **0** |
| 09:29-09:41 | applier セッション（09:15頃の内存602件を保持）が保存前マージで626件へ再保存 ×数十回 | 626件 / **43→41** |
| 09:45 | backfill（crontab） | stale_empty>15d=38 → [L1] FAIL、exit rc=1。CHECK行=0 |
| 09:49 | 現物再計測 | 626件 / stale_empty>15d=36（全てcpmeikan、全てapplied済み） |

## 根本原因（コード根拠）
`kensho/application/state.py` の `save_collected_safe()`（L95-138）:
- applier はセッション開始時にロードした **メモリ上の `data`**（=602件、v67パージ前）を保持して応募を進める
- 保存時にディスク（current=583件、パージ後）と x_url/detail_url でマージするが、**ディスク側に無い項目は `merged_items.append(item)` で無条件に再追加**（L110）
- 結果: collector が除去した stale empty が applier の次保存で復活する。`data['timestamp']` は current 側で補完されるため、復活した items が古い世代のものだと判別できない（バックアップ ts=09:27:19 のまま n=626 の不整合が兆候）

## 影響評価
- 応募実務への直接害はゼロ（復活する36件は全て applied 済み＝再応募しない。applied 保全マージ自体は提案81/7e07247 の正しい挙動）
- ただし **v67/v68 の成功指標「gate=0 維持」が毎時間リセット**され、L1ゲートが毎日16回 rc=1 で鳴り続ける → アラート疲労。ゲート自体は設計通り機能（FAIL検出成功）
- 再発2回目（09:24/09:46の2保存世代で観測）＝優先度判定基準「高」

## critic v70 への申し送り（推奨修正案）
1. `save_collected_safe()` のマージ後・保存前に `_is_stale_empty_deadline()`（collector.py L55、ロジック共通化のため `kensho/scraping/common` 等へ移動）を適用し、applier 内存由来の stale empty を保存層でパージ（提案1件・低风险・テスト追加で検証可能）
2. 代替: backfill の L1 計測を「収集直後」に寄せる（crontab を収集 +3分 に変更）。ただし保存層バグは残るので対症療法

## 検証コマンド（再現）
```bash
cd /mnt/d/Project2/kensho && python3 -c "
import json,sys;sys.path.insert(0,'.')
from datetime import datetime
import importlib.util
spec=importlib.util.spec_from_file_location('bf','backfill_deadlines.py');bf=importlib.util.module_from_spec(spec)
try: spec.loader.exec_module(bf)
except SystemExit: pass
d=json.load(open('data/collected.json',encoding='utf-8'))
print('ts',d['timestamp'][:19],'n',len(d['collected']),'gate',bf.count_stale_empty(d['collected'],datetime.now(),15))"
```
成功指標: 修正案実装後の backfill ログで 16回/日すべて `[L1] ... 0 ... PASS` / rc=0

## Reflexion
```json
{"self_review":{"what_was_done":"09:45 backfill実ログ検証でv68 CHECK撤去(gate動作)を確認、同時にFAIL発火の真因(applier保存マージによるv67パージ復活)をコード根拠付きで特定しcritic v70申し送りを作成","what_went_well":["FAILを『ゲート正常動作+実バグ発見』に分解して誤クローズしなかった","バックアップ世代のts/n不整合(09:27:19/626件)から復活の瞬間を特定","save_collected_safeのappend経路(L110)まで絞った"],"what_could_improve":["applierの内存ロード時刻(602件生成時点)をログから逆算するのに余分な探索があった。次はorchestrator起動時刻を先に確認する"],"mistakes_or_risks":["09:00 collect直後の単発計測(gate=0)だけでv68クローズ報告しかけた——1時間後の保存層復活を見落としていた。before/after対は『複数tick』必要"],"learned":"パージ系修正の検証は『最後の書き込み元』まで追うこと。collectorだけ直してもapplier保存が復活させるとゲートは毎日鳴り続ける","confidence":9,"verification_evidence":"09:45ログ[FAIL rc=1, CHECK行0], 09:49現物gate=36, バックアップ系列ts=09:27:19/n=626, state.py L95-138根拠, pytest 20 passed"}}
```
