# critic v147: patchright 1.62.3→1.63 更新で X /status/ 403 再検証

日付: 2026-09-15 (JST) / 担当者: kensho-revenue-worker / カード: t_14784137

## 結論: **FAIL（前提不成立・pin更新見送り）**

**patchright 1.63.x は PyPI・GitHub どちらにも存在しない。**
本タスクの根拠となった research-20260915.md の「patchright本体は2026-09-03〜09-09に1.63.0系がリリースされたばかり（PyPI+GitHub一致）」は誤認。
1.63.0 は **microsoft/playwright（本家）** のリリース（named test locks 等テストランナー機能中心）であり、patchright-python のバージョン体系とは別物。両者の版本対応は約1ヶ月ずれている。

## 実測根拠（2026-09-15 取得）

| 項目 | 実測値 | 出典 |
|---|---|---|
| PyPI patchright latest | **1.62.3**（2026-09-02T22:12Z アップロード） | https://pypi.org/pypi/patchright/json |
| PyPI 1.63 系リリース有無 | **無し**（releases キーに "1.63" 一致ゼロ） | 同上 |
| GitHub patchright-python 最新リリース | v1.62.0（2026-08-17） | api.github.com/repos/Kaliiiiiiiiii-Vinyzu/patchright-python/releases |
| GitHub tags 最大 | v1.62.0 | 同上 /git/refs/tags |
| 現行 pin | requirements.txt 6行目 `patchright==1.62.3` ＝ **PyPI最新と同値** | /mnt/d/Project2/kensho/requirements.txt |
| インストール済み | pip show patchright = 1.62.3 | WSL venv 実測 |

## 実施／見送りの内訳

1. **pin更新 → 見送り**: 更新先バージョンが存在しないため `patchright==1.62.3` のまま（変更ゼロ＝git revert 不要）。
2. **read-only probe（2ケース×3回）→ 不実施**: 検証対象の「新ステルスパッチ」が存在しない以上、probe は 1.62.3 での再測定になる。9/5 実測（t_39eef5a3系）で 1.62.3 の chromium 路は X /status/ 403 を確認済みであり、同じバージョンでアカウントを実ブラウザ起動して再測する収益はないと判断（403解消の余地ゼロ）。
3. **pytest → 不変**: コード変更ゼロのため 568pass 状態維持（触れていない）。

## chromium stealth 路の扱い

**休止継続**（既定 Firefox 維持、`KENSHO_BROWSER=chromium` opt-in 停止）。research 提案C の nodriver（dev.to ベンチマーク 28 OK/0 blocked 首位、Windows CDP 直結）が最有力代替だが、導入はエンジン追加を伴うため別タスク起案判断（本カードは pin更新+検証限定の指示に従い起案しない。次回 critic ランで patchright 1.63 実リリース or nodriver 移行のどちらかを論点化）。

## 再検証トリガー

`curl -s https://pypi.org/pypi/patchright/json | grep -o '"1\.63[^"]*"' | head -1` が非空になったら（= patchright 1.63 が本当にPyPIへ出たら）本タスクを再実行する。それまで /status/ 403 の解消検証は保留。

## 検証コマンド結果

```
$ grep -i patchright /mnt/d/Project2/kensho/requirements.txt
patchright==1.62.3
$ test -f /mnt/d/Project2/kensho/reports/critic_v147_patchright163.md && echo OK
OK
```
