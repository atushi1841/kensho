#!/usr/bin/env python3
"""critic v169 (t_83759a2e): 静的検査 — kensho-auto-apply.sh 内の `pgrep -f` が
`flock -c "..."` の内側で自己マッチするパターンでないか検出する回帰ゲート。

バックグラウンド
----------------
`flock -n LOCK -c "CMD"` は引数 -c に渡された CMD 文字列を flock プロセス自身の
argv に保持する。CMD 内の `pgrep -f 'PATTERN'` は「全プロセスの full command line
に PATTERN(ERE) が部分一致するか」を見るため、PATTERN の concrete 形（文字クラス
`[x]` を実マッチ文字へ展開した形）が CMD 文字列中に存在すれば、flock プロセス自身
がマッチしてしまう → 常に1件以上ヒット → 「二重実行防止」が自分のせいで誤発火し、
orchestrator が一度も spawn されない（応募完全停止の直接原因、9/16 05:34 〜 実測）。

対処（呼び出し側 kensho-auto-apply.sh）は `[k]ensho/...` 形式の文字クラス逃避。
PATTERN=`[k]ensho` の concrete 形は `kensho` だが、CMD 中に並ぶのはリテラル
`[k]ensho`（=k の直後が ]）で、`kensho` の連続部分文字列は存在しない → 自己マッチせず
安全。本検査はこの concrete 部分文字列検査を pgrep 全てに適用する。

退出コード
----------
- 0 : 自己マッチしうる pgrep：検出されず（安全）
- 1 : flock -c 内の pgrep で自己マッチしうる行を検出（回帰 → ゲート遮断）
"""

import re
import sys

DEFAULT_TARGET = "/home/atushi/.hermes/profiles/kensho-sweeps/scripts/kensho-auto-apply.sh"


def concretize(pattern: str) -> str:
    """ERE 文字クラス `[abc]` をその先頭実文字へ還元した「おおまかな実マッチ文字列」。
    `[k]ensho` -> `kensho`。`([^'])` 等の高度なクラスは素朴に構文維持するが、
    本検査が対象にするのは文字クラス逃避(`[k]`/`[p]`)の有無だけなので十分。
    """
    out = []
    i = 0
    n = len(pattern)
    while i < n:
        ch = pattern[i]
        if ch == "\\" and i + 1 < n:
            out.append(pattern[i + 1])
            i += 2
            continue
        if ch == "[":
            # クラス末尾を探し、実文字として直後の1文字を採用（`[k]` -> `k`）
            j = pattern.find("]", i + 1)
            if j != -1 and j - i > 1:
                out.append(pattern[i + 1])
                i = j + 1
                continue
            out.append(ch)
            i += 1
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def find_pgrep_patterns(text: str):
    """全 `pgrep ... -f '<pat>'` / `-f "<pat>"` の (開始文字位置, パターン, 行番号) を返す。
    `-cf` 等の結合ショートフラグ(`pgrep -cf 'pat'`)にも対応するため、`-f` の前に任意の
    アルファベット集合を許す。
    """
    results = []
    flag_re = re.compile(r"pgrep\b[^\"']*?-(?:[a-z]*)f\b\s*([\"'])([^\"']+?)\1")
    for m in flag_re.finditer(text):
        results.append((m.start(), m.group(2), text.count("\n", 0, m.start()) + 1))
    return results


def flock_c_dquote_spans(text: str):
    """`flock ... -c "` のダブルクォート文字列領域 (start, end) を返す（未閉は drop）。"""
    spans = []
    i = 0
    n = len(text)
    while True:
        k = text.find("flock", i)
        if k == -1:
            break
        if not re.match(r"flock\b", text[k : k + 6]):
            i = k + 5
            continue
        # -c の後のクォートを探す（同トークン行内 id 優先）
        seg = text[k : k + 8000]
        cm = re.search(r"-c\s*([\"'])", seg)
        if not cm:
            i = k + 5
            continue
        q = cm.group(1)
        qpos = k + cm.start(1)
        if q != '"':
            # シングルクォート内の pgrep も対象だが、現行ファイルはダブルクォート利用。
            # 汎用性のため 両対応する。
            pass
        # 閉じクォート走査（バックスラッシュの直後は飛ばす）
        j = qpos + 1
        closed = False
        while j < n:
            if text[j] == "\\":
                j += 2
                continue
            if text[j] == q:
                spans.append((qpos, j))
                closed = True
                break
            j += 1
        i = k + 5 if not closed else j + 1
    return spans


def main() -> int:
    target = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_TARGET
    try:
        with open(target, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    except OSError as exc:
        print(f"ERROR: {target} を読めません: {exc}", file=sys.stderr)
        return 2

    spans = flock_c_dquote_spans(text)
    violations = []
    for pos, pat, lineno in find_pgrep_patterns(text):
        in_flock = any(start <= pos <= end for start, end in spans)
        if not in_flock:
            continue  # メイン本文の pgrep（bash argv=script名）は自己マッチせず安全
        concrete = concretize(pat)
        in_block = any(concrete in text[start:end] for start, end in spans)
        if in_block:
            violations.append((lineno, pat, concrete))

    if violations:
        print(f"FAIL: spawn スクリプトに flock -c 内で自己マッチしうる pgrep を検出（{len(violations)}件）")
        for lineno, pat, concrete in violations:
            print(f"  {target}:{lineno}  pattern={pat!r}  concrete={concrete!r}")
        print("対処: パターンを `[k]ensho` 等の文字クラス逃避形（concrete が flock ブロック文字列に")
        print("      連続部分文字列として現れない形）へ書き換えること。")
        return 1

    print(f"OK: {target} の flock -c 領域に自己マッチする pgrep は検出されません")
    return 0


if __name__ == "__main__":
    sys.exit(main())
