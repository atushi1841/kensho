# t_79fb103e — STAGGER_MOD空文字エラー処理 検証レポート

## 対応コミット
- `fbd9404` — fix(apply): STAGGER_MOD空文字/非数値で[-gt]エラー→既定10分フォールバック
- 証跡レポート: `ae4c489` — origin/main 反映済み（69542a4..ae4c489 pushed）

## 変更ファイル
- `kensho-auto-apply.sh`（1ファイル・+8行のみ。他作業ツリーの未コミット変更には触れず）

## 根因
`kensho-auto-apply.sh:102` の `[ "$STAGGER_MOD" -gt 0 ]` が、STAGGER_MOD が
空文字/非数値のとき bash で `integer expression expected` / `too many arguments`
エラーを吐き、スタガー判定が偽に落ちて実質0化（全垢が同時刻spawn→15分グリッド集中再発）。

## 修正内容
STAGGER_MOD 読取直後に検証ガードを追加。空文字・非数値（空白含む）は既定10分へ
フォールバックし、0は明示的無効化として維持（数値のみ受理）。(`${VAR:-default}` の
ため空文字は既に既定化されるが、非数値・空白・防御的空文字を一括無効化する二段構え。
config.yaml に `default_stagger` は存在しないため代替案の趣旨（失敗時フォールバック）
に従いスプリクト既定の10分を採用。）

## 実測

### 1. 構文チェック
```
$ cd /mnt/d/Project2/kensho && bash -n kensho-auto-apply.sh
SYNTAX OK
```

### 2. 根因の再現（修正前の line102 相当）
```
$ bash /tmp/stagger_test.sh ""   # STAGGER_MOD 空文字
/tmp/stagger_test.sh: line 5: [: : integer expression expected
$ bash /tmp/stagger_test.sh "abc" # 非数値
/tmp/stagger_test.sh: line 5: [: abc: integer expression expected
$ bash /tmp/stagger_test.sh "10"  # 数値 → エラーなし
gt ok
```

### 3. ガード挙動（入力→最終 STAGGER_MOD、guard_test.sh 実測）
```
$ bash /tmp/guard_test.sh
input=<>     -> 10   (空→既定10分)
input=<abc>  -> 10   (非数値→既定10分)
input=<5>    -> 5    (数値維持)
input=<10>   -> 10   (既定維持)
input=<0>    -> 0    (無効化0を維持)
input=< 12>  -> 10   (空白→既定10分)
```

### 結果（成功指標）
- STAGGER_MOD空文字で `[ -gt 0 ]` エラーなし、既定10分フォールバックで正常動作 ✗→✓
- ロールバック値 `0` は維持（既存無効化仕様を壊さない）✓
- `bash -n` 構文合格 ✓

## 非適用（タスク本文との差分）
`pytest tests/ -k stagger` は Python 側に stagger 実装・config の `default_stagger` が
存在しないため不適用。本例は bash スクリプト修正のため bash 実測で検証した。
