#!/usr/bin/env python3
"""t_e2b356ce 検証ヘルパー — status/<acct>.json が「同一 tick の PROXY-CHECK」を根拠にしているかを実測する。

使い方:
    python3 scripts/verify_status_proxy_same_tick.py            # 当日ログ全 tick の再現＋現在の status 突合
    python3 scripts/verify_status_proxy_same_tick.py --ticks 10 # 直近10 tick だけ

判定内容:
  1. 再現(replay): 各 tick について generate-status.sh の待ちループ（同一 tick の [PROXY-CHECK] 行が
     現れるまで最大 WAIT_TIMEOUT 秒ポーリング）を模して生成時刻を決め、その時点で存在したログ本文に
     gen_status_data.py の _filter_proxy_check_rows を適用する。採用行が「同一 tick の行」と一致すれば OK
     （前 tick の死骸を採用しないことの証明）。WAIT_TIMEOUT を超えた tick は「採用行なし＝前回値保持」
     が正解（古い行を採用したら NG）。WAIT_TIMEOUT は generate-status.sh から読む（ドリフト防止）。
  2. ライブ: data/status/<acct>.json の status が、ログ最終 tick の alive/dead リストと一致するか。
     /tmp/kensho_status_data.json の proxy.ts がログ最終 tick の開始時刻と一致するか（＝前 tick ではない）。

副作用なし: フィルタ関数は AST で関数定義だけを取り出して実行する（モジュール本体＝パイプラインは走らせない）。
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LOG_DIR = REPO / "logs"
STATUS_DIR = REPO / "data" / "status"
TS_RE = re.compile(r"^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]")
DUR_RE = re.compile(r"\((\d+(?:\.\d+)?)s\)")


def load_filter():
    """gen_status_data.py から _filter_proxy_check_rows だけを取り出して読み込む（副作用なし）。"""
    src = (REPO / "scripts" / "gen_status_data.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    fn = next(
        n for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name == "_filter_proxy_check_rows"
    )
    mod = ast.Module(
        body=[
            ast.ImportFrom(module="datetime", names=[ast.alias(name="datetime")], level=0),
            ast.Import(names=[ast.alias(name="re")]),
            fn,
        ],
        type_ignores=[],
    )
    ns: dict = {}
    exec(compile(ast.fix_missing_locations(mod), "<filter>", "exec"), ns)  # noqa: S102
    return ns["_filter_proxy_check_rows"]


def read_wait_timeout() -> int:
    """generate-status.sh の WAIT_TIMEOUT を読む（検証とスクリプトのドリフト防止）。"""
    src = (REPO / "scripts" / "generate-status.sh").read_text(encoding="utf-8")
    m = re.search(r"^WAIT_TIMEOUT=(\d+)", src, re.M)
    if not m:
        raise SystemExit("generate-status.sh に WAIT_TIMEOUT が見つからない")
    return int(m.group(1))


def parse_log(text: str) -> list[tuple[datetime, list[int], list[int], float]]:
    """(tick開始時刻, alive, dead, PROXY-CHECK所要秒) を出現順に返す。"""
    rows, cur = [], None
    for line in text.splitlines():
        m = TS_RE.match(line)
        if m:
            cur = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
            continue
        if "[PROXY-CHECK]" in line and cur is not None:
            a = re.search(r"alive=\[([0-9,\s]*)\]", line)
            d = re.search(r"dead=\[([0-9,\s]*)\]", line)
            du = DUR_RE.search(line)
            rows.append((
                cur,
                [int(x) for x in a.group(1).split(",") if x.strip()] if a else [],
                [int(x) for x in d.group(1).split(",") if x.strip()] if d else [],
                float(du.group(1)) if du else 0.0,
            ))
    return rows


def simulate_gen(ts: datetime, dur: float, timeout: int) -> datetime:
    """generate-status.sh の待ちループを模した生成時刻。

    tick 開始 ts と同時に起動し 5秒間隔でポーリング、[PROXY-CHECK] 行（完走時に書かれる）が
    現れた時点で生成へ進むため 生成時刻 ≒ 完走時刻＋(0〜5)s。timeout を超えたら打ち切る。
    """
    completion = ts + timedelta(seconds=dur)
    deadline = ts + timedelta(seconds=timeout)
    if completion <= deadline:
        return min(completion + timedelta(seconds=5), deadline)
    return deadline  # 打ち切り: 同一 tick の完走行はまだ存在しない


def text_at(full: str, gen: datetime) -> str:
    """生成時刻 gen 時点で存在したはずのログ本文（未来の行は見えない）。"""
    out, cur = [], None
    for line in full.splitlines():
        m = TS_RE.match(line)
        if m:
            cur = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
            if cur > gen:
                break
        if cur is None or cur > gen:
            continue
        if "[PROXY-CHECK]" in line:
            d = DUR_RE.search(line)
            if cur + timedelta(seconds=float(d.group(1)) if d else 0.0) > gen:
                continue  # まだ完走していない
        out.append(line)
    return "\n".join(out) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ticks", type=int, default=0, help="直近N tick のみ検証（0=全件）")
    args = ap.parse_args()

    log = LOG_DIR / f"auto_{datetime.now():%Y%m%d}.log"
    if not log.exists():
        print(f"ログが無い: {log}", file=sys.stderr)
        return 2
    full = log.read_text(encoding="utf-8", errors="replace")
    rows = parse_log(full)
    if not rows:
        print("PROXY-CHECK 行が見つからない", file=sys.stderr)
        return 2
    if args.ticks:
        rows = rows[-args.ticks:]

    timeout = read_wait_timeout()
    fn = load_filter()
    ng = []
    froze = 0
    for ts, alive, dead, dur in rows:
        # generate-status.sh の待ちループを模して生成時刻を決める（simulate_gen 参照）。
        completion = ts + timedelta(seconds=dur)
        deadline = ts + timedelta(seconds=timeout)
        gen = simulate_gen(ts, dur, timeout)
        got_ts, got_alive, got_dead, _restored, _best = fn(text_at(full, gen), gen - timedelta(minutes=2), None)
        if completion > deadline:
            # 打ち切りケースの正解は「採用行なし＝前回値保持」（偽 dead を書かない）。
            # ここで古い行（前 tick の死骸）を採用したら NG。
            froze += 1
            if got_ts is not None:
                ng.append((ts, got_ts, got_alive, got_dead, alive, dead))
        elif got_ts != ts or got_alive != alive or got_dead != dead:
            ng.append((ts, got_ts, got_alive, got_dead, alive, dead))

    print(
        f"1) 再現: {len(rows)} tick 中 {len(rows) - len(ng)} 一致 / {len(ng)} 不一致"
        f"（WAIT_TIMEOUT={timeout}s・打ち切り={froze} tick）"
    )
    for ts, got_ts, ga, gd, a, d in ng[:5]:
        print(f"   NG tick={ts:%H:%M:%S} 採用ts={got_ts} 採用alive/dead={ga}/{gd} 実測alive/dead={a}/{d}")

    latest = rows[-1]
    print(f"2) ログ最終 tick: {latest[0]:%Y-%m-%d %H:%M:%S} alive={latest[1]} dead={latest[2]}")
    panel_path = Path("/tmp/kensho_status_data.json")
    if panel_path.exists():
        panel = json.loads(panel_path.read_text(encoding="utf-8")).get("proxy", {})
        same_tick = panel.get("ts") == latest[0].strftime("%Y-%m-%d %H:%M:%S")
        print(f"   proxy.ts={panel.get('ts')} → 最終tickと{'一致' if same_tick else '不一致（前tickの可能性）'}")
    bad = 0
    for f in sorted(STATUS_DIR.glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        port, st, upd = d.get("port"), d.get("status"), d.get("updated", "")
        if port is None or not upd.startswith(datetime.now().strftime("%Y-%m-%d")):
            continue
        expect = "alive" if port in latest[1] else ("dead_proxy" if port in latest[2] else "unchecked")
        flag = "一致" if st == expect else f"不一致(期待={expect})"
        if st != expect:
            bad += 1
        print(f"   {f.stem:16s} port={port} status={st:11s} {flag}")

    ok = not ng and not bad
    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
