#!/usr/bin/env python3
"""check_dep_drift.py — declared pyproject deps vs actual venv drift gate (t_7b040302 / v65).

背景 (2026-09-09, 1日2連続インシデント):
  twscrape: venv 0.19.1 残置 vs pyproject 宣言更新 → cookies kwarg 未対応で
    TypeError が「XClientTxId generation failed」として誤報告。
  patchright: venv 1.61.1 vs 宣言 1.62.3。
  QA v77 handoff: 「done_guard add check: declared deps vs real venv versions must match」

採用パターン: configuration-drift gate / declarative env sync。
  望ましい状態 (pyproject.toml [project].dependencies) と実際の状態
  (kensho cron が使う venv にインストール済みの distribution metadata) を
  定期 diff し、drift を fail-fast する。incident-time fix の繰り返しを止める。

実際の venv の決定順 (kensho cron worker が実際に使うもの):
  1. --venv-python 引数
  2. KENSHO_VENV_PYTHON 環境変数
  3. config.yaml general.python (現行: /home/atushi/kensho-venv/bin/python)
  4. /home/atushi/kensho-venv/bin/python (既定フォールバック)

stdlib のみ使用 (yaml 非依存: config.yaml の python: 行は正規表現で抽出)。

使い方:
  python3 scripts/check_dep_drift.py                 # 正常時 {"ok": true, ...} rc=0
  python3 scripts/check_dep_drift.py --quiet         # drift 0件時は stdout を空に
                                                     # (no_agent cron 静音配信規約)
出力: JSON 1行 {"ok": bool, "drift": [...], "pip_check": "..."}
終了コード: 0 = drift 無し, 1 = drift 検出 or 監査基盤エラー (2 は未使用)

自己テスト (回帰ガード、実venvを読み取り専用で使用・一切インストールしない):
  python3 scripts/check_dep_drift.py --selftest
  一時 pyproject で (1) 一致宣言=ok (2) twscrape!=実インストール版 → drift 検出
  (3) 存在しないパッケージ → MISSING 検出 を検証。
  検出成功時 exit 1 (drift 検出 = 正常系)。 "SELFTEST OK" / "SELFTEST FAILED" を出力。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.yaml"
DEFAULT_VENV_PY = Path("/home/atushi/kensho-venv/bin/python")

# "twscrape>=0.20.1" / "patchright==1.62.3" 等の requirement 行を分解する。
_REQUIREMENT_RE = re.compile(
    r"""^\s*
    (?P<name>[A-Za-z0-9][A-Za-z0-9._-]*)                                 # package name
    (?:\[[^\]]*\])?                                                      # extras (無視)
    \s*
    (?P<spec>(?:===|==|>=|<=|~=|!=|>|<)\s*[0-9*][^,;\s]*   # 例: >=0.20.1 / ==1.62.3
           (?:\s*,\s*(?:===|==|>=|<=|~=|!=|>|<)\s*[0-9*][^,;\s]*)*)?  # 連結: >=1.52,<1.53
    \s*(?:;.*)?$                                                         # environment marker
    """,
    re.VERBOSE,
)

_CONFIG_PYTHON_RE = re.compile(r'^\s*python:\s*"([^"]+)"', re.MULTILINE)


def _canon(name: str) -> str:
    """PEP 503 正規化: -/_/. を同一視し小文字化 (PyYAML → pyyaml)。"""
    return re.sub(r"[-_.]+", "-", name).lower()

# ---- 宣言側 (pyproject.toml) -------------------------------------------------


def parse_pyproject_deps(path: Path) -> dict[str, str]:
    """[project].dependencies を {canonical_name: spec_str} で返す。spec 無しは ""。"""
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as e:
        raise RuntimeError(f"pyproject unreadable: {e}") from e
    declared: dict[str, str] = {}
    for raw in data.get("project", {}).get("dependencies", []):
        m = _REQUIREMENT_RE.match(str(raw))
        if not m:
            continue
        declared[_canon(m.group("name"))] = (m.group("spec") or "").replace(" ", "")
    return declared

# ---- 実際の venv ---------------------------------------------------------------


def resolve_venv_python(cli_arg: str | None = None) -> Path:
    """kensho cron が実際に使う venv python を決定する (docstring の決定順)。"""
    if cli_arg:
        return Path(cli_arg)
    env = os.environ.get("KENSHO_VENV_PYTHON")
    if env:
        return Path(env)
    try:
        m = _CONFIG_PYTHON_RE.search(CONFIG_PATH.read_text(encoding="utf-8", errors="ignore"))
        if m:
            return Path(m.group(1))
    except OSError:
        pass
    return DEFAULT_VENV_PY


def installed_versions(venv_python: Path) -> dict[str, str]:
    """venv の `pip list --format=freeze` を {canonical_name: version} で返す。

    pip 不在/実行失敗時は RuntimeError (呼び出し元が監査基盤エラーとして扱う)。
    """
    try:
        r = subprocess.run(
            [str(venv_python), "-m", "pip", "list", "--format=freeze", "--disable-pip-version-check"],
            capture_output=True,
            text=True,
            timeout=180,
        )
    except (OSError, subprocess.SubprocessError) as e:
        raise RuntimeError(f"pip list failed: {e}") from e
    if r.returncode != 0:
        raise RuntimeError(f"pip list rc={r.returncode}: {(r.stderr or r.stdout or '').strip()[:200]}")
    out: dict[str, str] = {}
    for line in (r.stdout or "").splitlines():
        line = line.strip()
        if "==" not in line:
            continue  # warning 行などを無視
        name, _, ver = line.partition("==")
        if name and ver:
            out[_canon(name)] = ver.strip()
    if not out:
        raise RuntimeError("pip list returned no packages (empty venv?)")
    return out


def load_req_files(req_paths):
    """Return dict of canonical_name -> spec_str (with spaces removed) for each requirement in the given files."""
    result = {}
    for req_path in req_paths:
        if not req_path.is_file():
            continue
        for line in req_path.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            m = _REQUIREMENT_RE.match(line)
            if m:
                name = _canon(m.group('name'))
                spec = (m.group('spec') or "").replace(" ", "")
                result[name] = spec
            else:
                # fallback: split by first separator
                found = False
                for sep in ('==', '>=', '<=', '>', '<', '~=', '!=', '@'):
                    if sep in line:
                        name, spec = line.split(sep, 1)
                        name = _canon(name.strip())
                        spec = sep + spec.strip()
                        spec = spec.replace(" ", "")
                        result[name] = spec
                        found = True
                        break
                if not found:
                    # just a package name
                    name = _canon(line)
                    result[name] = ""
    return result

def run_pip_check(venv_python: Path) -> tuple[int, str]:
    """venv の `pip check` を実行し (rc, 出力) を返す。pip 不在も rc!=0 として扱う。"""
    try:
        r = subprocess.run(
            [str(venv_python), "-m", "pip", "check", "--disable-pip-version-check"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        return r.returncode, (r.stdout or r.stderr or "").strip()
    except (OSError, subprocess.SubprocessError) as e:
        return 127, f"pip check exec failed: {e}"

# ---- バージョン比較 (PEP 440 の実用サブセット) ----------------------------------


def _version_key(v: str) -> tuple[int, ...] | None:
    """先頭の数値コンポーネントを最大4つ取り出す。数値無しは None ("1.62.3.post1"→(1,62,3))。"""
    parts = re.findall(r"\d+", v)
    if not parts:
        return None
    return tuple(int(p) for p in parts[:4])


def _spec_satisfied(spec: str, installed: str) -> bool | None:
    """installed が spec を満たすか。判定不能 (数値無しバージョン等) は None。"""
    for clause in [c for c in spec.split(",") if c]:
        m = re.match(r"^(===|==|>=|<=|~=|!=|>|<)\s*(.+)$", clause)  # ===は==より先に順序付け
        if not m:
            return None
        op, want = m.group(1), m.group(2).strip()
        if want.endswith(".*"):  # 例: ==1.52.*
            want = want[:-2]
            if not installed.startswith(want):
                return False
            continue
        if op == "===":
            if installed != want:
                return False
            continue
        if op == "==":
            if installed != want:
                return False
            continue
        if op == "!=":
            if installed == want:
                return False
            continue
        wk, ik = _version_key(want), _version_key(installed)
        if wk is None or ik is None:
            return None  # 数値比較不能
        if op == ">=" and not ik >= wk:
            return False
        if op == ">" and not ik > wk:
            return False
        if op == "<=" and not ik <= wk:
            return False
        if op == "<" and not ik < wk:
            return False
        if op == "~=":  # ~=X.Y == >=X.Y, ==X.*
            if not (ik >= wk and installed.split(".")[0] == want.split(".")[0]):
                return False
    return True

# ---- メインの検査 ----------------------------------------------------------------


def check(venv_python: Path, pyproject: Path, skip_reverse_check: bool = False) -> dict[str, Any]:
    """drift 検査本体。{"ok", "drift", "pip_check", ...} を返す (exit 判定は main)。"""
    result: dict[str, Any] = {
        "ok": False,
        "drift": [],
        "pip_check": "",
        "venv_python": str(venv_python),
        "pyproject": str(pyproject),
        "checked": {},
    }
    try:
        declared = parse_pyproject_deps(pyproject)
    except RuntimeError as e:
        result["error"] = str(e)
        return result
    if not declared:
        result["error"] = "no dependencies parsed from pyproject [project.dependencies]"
        return result
    try:
        installed = installed_versions(venv_python)
    except RuntimeError as e:
        result["error"] = str(e)
        return result

    if not skip_reverse_check:
        # Load requirements files and uv.lock for additional checks.
        # requirements.txt is the canonical declaration mirror; requirements-lock.txt
        # is a partial lock snapshot (subset of deps). A package is "missing" only when
        # absent from BOTH files. uv.lock existence is checked separately (name only).
        req_pkgs = load_req_files([ROOT / "requirements.txt", ROOT / "requirements-lock.txt"])
        req_pkgs_set = set(req_pkgs.keys())
        uv_lock_pkgs = set(load_req_files([ROOT / "uv.lock"]).keys())

        for name in sorted(declared):
            # pyproject にあるが requirements 系に両方無い → drift
            if name not in req_pkgs_set:
                result["drift"].append({
                    "name": name,
                    "declared": declared[name] or "(none)",
                    "installed": "-",
                    "reason": "MISSING: declared in pyproject but not in requirements.txt/requirements-lock.txt",
                })
                continue
            # spec 整合性確認: requirements.txt の spec と pyproject の spec が異なる
            req_spec = req_pkgs.get(name)
            if req_spec is not None and req_spec != (declared[name] or ""):
                result["drift"].append({
                    "name": name,
                    "declared": declared[name] or "(none)",
                    "installed": "-",
                    "reason": f"spec mismatch: requirements file has {req_spec}, pyproject has {declared[name]}",
                })
            # uv.lock に存在するか確認（name のみ）
            if name not in uv_lock_pkgs:
                result["drift"].append({
                    "name": name,
                    "declared": declared[name] or "(none)",
                    "installed": "-",
                    "reason": "MISSING: package name not found in uv.lock",
                })

    for name in sorted(declared):
        spec = declared[name]
        inst = installed.get(name)
        result["checked"][name] = inst or "(missing)"
        if inst is None:
            result["drift"].append({
                "name": name,
                "declared": spec or "(none)",
                "installed": None,
                "reason": "MISSING: declared in pyproject but not installed in venv",
            })
            continue
        if not spec:
            continue  # 宣言にバージョン指定が無い = drift 定義上の比較対象外
        sat = _spec_satisfied(spec, inst)
        if sat is False:
            result["drift"].append({
                "name": name,
                "declared": spec,
                "installed": inst,
                "reason": "version mismatch: installed does not satisfy declared specifier",
            })
        # sat is None (数値比較不能) は誤検知防止のため drift にしない

    rc, pip_out = run_pip_check(venv_python)
    result["pip_check"] = pip_out or "(no output)"
    if rc != 0:
        result["drift"].append({
            "name": "(pip check)",
            "declared": "-",
            "installed": "-",
            "reason": f"pip check rc={rc}: {pip_out[:300]}",
        })
    result["ok"] = not result["drift"]
    return result

# ---- 自己テスト ------------------------------------------------------------------


def selftest(venv_python: Path, pyproject: Path) -> int:
    """回帰ガード: 一時 pyproject で pass/detect/MISSING を検証。検出成功時 exit 1。

    実 venv は読み取り専用 (pip list/check のみ)。一切インストール・変更しない。
    """
    import tempfile

    try:
        installed = installed_versions(venv_python)
    except RuntimeError as e:
        print(f"SELFTEST FAILED: cannot read venv: {e}")
        return 3
    tws = installed.get("twscrape")
    if not tws:
        print("SELFTEST FAILED: twscrape not installed in venv — cannot build test cases")
        return 3

    with tempfile.TemporaryDirectory(prefix="dep_drift_selftest_") as td:
        tmp = Path(td)

        # (1) 一致宣言 → ok=True (正常系)
        ok_proj = tmp / "ok.toml"
        ok_proj.write_text(
            f'[project]\nname = "t"\nversion = "0"\ndependencies = ["twscrape=={tws}", "httpx>=0.27"]\n',
            encoding="utf-8",
        )
        r1 = check(venv_python, ok_proj, skip_reverse_check=True)

        # (2) カード本文の回帰ガード: twscrape != 実インストール版 → drift 検出
        bad_proj = tmp / "bad.toml"
        bad_proj.write_text(
            f'[project]\nname = "t"\nversion = "0"\ndependencies = ["twscrape!={tws}"]\n',
            encoding="utf-8",
        )
        r2 = check(venv_python, bad_proj, skip_reverse_check=True)

        # (3) 存在しないパッケージ → MISSING 検出
        miss_proj = tmp / "miss.toml"
        miss_proj.write_text(
            '[project]\nname = "t"\nversion = "0"\ndependencies = ["kensho-no-such-pkg-9x7q>=1.0"]\n',
            encoding="utf-8",
        )
        r3 = check(venv_python, miss_proj, skip_reverse_check=True)

        # (4) lock欠落を注入 → drift 検出 (reverse checking)
        lock_miss_proj = tmp / "lockmiss.toml"
        lock_miss_proj.write_text(
            '[project]\nname = "t"\nversion = "0"\ndependencies = ["kensho-lock-miss-pkg-xyz>=1.0"]\n',
            encoding="utf-8",
        )
        r4 = check(venv_python, lock_miss_proj, skip_reverse_check=False)
    ok_path = r1["ok"] and not r1["drift"]
    detect = (not r2["ok"]) and any(d.get("name") == "twscrape" for d in r2["drift"])
    missing = (not r3["ok"]) and any("MISSING" in str(d.get("reason", "")) for d in r3["drift"])
    lock_missing = (not r4["ok"]) and any("MISSING" in str(d.get("reason", "")) and ("requirements.txt" in str(d.get("reason", "")) or "uv.lock" in str(d.get("reason", ""))) for d in r4["drift"])

    print(f"selftest dep_drift: healthy_ok={ok_path} (twscrape=={tws}, checked={len(r1.get('checked', {}))})")
    print(f"selftest dep_drift: injected_!=_drift_detected={detect} (drift={[d['name'] for d in r2['drift']]})")
    print(f"selftest dep_drift: missing_pkg_detected={missing}")
    print(f"selftest dep_drift: lock_missing_detected={lock_missing} (drift={[d['name'] for d in r4['drift']]})")
    if ok_path and detect and missing and lock_missing:
        print("SELFTEST OK: drift injection detected -> exit 1 (per card regression guard)")
        return 1
    print("SELFTEST FAILED: check_dep_drift did not behave as designed")
    return 2


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="declared vs installed dependency drift gate")
    ap.add_argument(
        "--venv-python", type=str, default=None, help="検査対象 venv の python パス (既定: config.yaml general.python)"
    )
    ap.add_argument("--pyproject", type=str, default=None, help="宣言側 pyproject.toml (既定: リポジトリルート)")
    ap.add_argument("--json", action="store_true", help="JSON 1行出力 (既定で JSON)")
    ap.add_argument("--quiet", action="store_true", help="drift 0件時は stdout を空にする (no_agent cron 静音規約)")
    ap.add_argument("--selftest", action="store_true", help="回帰ガード: 一時 pyproject で pass/detect/MISSING を検証")
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest(
            resolve_venv_python(args.venv_python), Path(args.pyproject) if args.pyproject else ROOT / "pyproject.toml"
        )

    venv_py = resolve_venv_python(args.venv_python)
    pyproject = Path(args.pyproject) if args.pyproject else ROOT / "pyproject.toml"
    try:
        res = check(venv_py, pyproject)
    except Exception as e:  # 監査基盤の想定外エラーも fail-loud (ok=false, exit 1)
        res = {"ok": False, "drift": [], "pip_check": "", "error": f"{type(e).__name__}: {e}"}

    if args.quiet and res.get("ok"):
        return 0
    print(json.dumps(res, ensure_ascii=False))
    return 0 if res.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())