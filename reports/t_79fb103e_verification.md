# t_79fb103e — STAGGER_MOD空文字エラー処理 検証レポート

## 対応コミット
- `fbd9404` — fix(apply): STAGGER_MOD空文字/非数値で[-gt]エラー→既定10分フォールバック
- origin/main 反映済み（69542a4..fbd9404 pushed）

## 変更ファイル
- `kensho-auto-apply.sh`（1ファイル・+8行のみ。他作業ツリー変更には触れず）

## 根因（QA検出の再現確認）
`kensho-auto-apply.sh:102` の `[ "$STAGGER_MOD" -gt 0 ]` が、STAGGER_MOD が
空文字/非数値のとき bash で `integer expression expected` / `too many arguments`
エラーを吐き、スタガー判定が偽→スタガー実質0化（全垢が同時刻spawn→15分グリッド集中再発）。
再現実測（bash 5.x）:
```
$ STAGGER_MOD="" のとき → /tmp/stagger_test.sh: line 5: [: : integer expression expected
$ STAGGER_MOD="abc" → [: abc: integer expression expected
$ STAGGER_MOD="10"  → (エラーなし)
```

## 修正内容
STAGGER_MOD 読取直後に検証ガードを追加。空文字・非数値（空白含む）は既定10分へ
フォールバックし、0は明示的無効化として維持（数値のみ受理）:
```bash
STAGGER_MOD=${KENSO_STAGGER_MOD:-10}
case "$STAGGER_MOD" in
  ''|*[!0-9]*) STAGGER_MOD=10
               log "STAGGER_MOD='${KENSO_STAGGER_MOD:-<unset>}'が空/非数値 → 既定10分にフォールバック" ;;
esac
```
`${VAR:-default}` のため空文字でも既に既定値化されるが、非数値・空白・(防御的)空文字を
calcパターンで一括無効化する二段構え。config.yaml に default_stagger は存在しないため
スプリクト既定の10分を採用（代替案の趣旨=失敗時フォールバック）。

## 検証実測
### 構文
```
$ bash -n kensho-auto-apply.sh
SYNTAX OK
```
### ガード挙動（入力→最終STAGGER_MOD）
```
input=<>     -> 10   (空→既定)
input=<abc>  -> 10   (非数値→既定)
input=<5>    -> 5    (数値維持)
input=<10>   -> 10   (既定まま)
input=<0>    -> 0    (無効化0を維持)
input=< 12>  -> 10   (空白→既定)
```
- 空文字で `[ -gt 0 ]` エラーなし、既定10分で正常動作（成功指標充足）
- `0`（ロールバック値）は維持（既存無効化仕様を壊さない）

## 非適用
- タスク本文の `pytest tests/ -k stagger` は Python 側に stagger 実装・config の
  `default_stagger` が存在しないため不適用（この修正は bash スクリプト）→ bash 実測で検証済み。
