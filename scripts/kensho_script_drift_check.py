#!/usr/bin/env python3
"""kensho_script_drift_check.py — cron実行スクリプトの repo↔profile ギャップ検出

背景 (critic_proposal_2026-09-09-v74 / task t_e971e85a):
  cron は jobs.json の `script` を **プロファイル scripts dir のコピー**から実行する。
  リポジトリ側 (/mnt/d/Project2/kensho) で改良してもプロファイルコピーへ同期しないと、
  cron は旧版を走り続ける = 「直したのに効かない」drift。
  実害例:
    - 9/6  ce22c907d66d の script drift（v30教訓、"次tickで検証"が未達のまま放置）
    - 9/9  kensho-non-api-revenue-hunter の profile copy が pre-v58 版（quality_gate /
           MAX_KANBAN_PER_RUN 欠落）→ 16:00 に ready 22件を無制限投入、score 95→65

判定:
  1. DRIFT   : jobs.json が参照する *.py / *.sh について、profile コピーと repo 版の
               md5 が不一致（= profile が古い／repo が古い。cron は profile を走る）
  2. MISSING : profile コピーが存在しない（scheduler が Block する／no_agent なら不発）
  3. UNTRACKED(参考): jobs.json 参照スクリプトに repo 版が無い = git管理外の単一ソース。
               drift は起き得ないが消失リスクがある（--all でのみ表示・FAIL化しない）

実行契約 (no_agent watchdog 規約、kensho-noagent-job-audit.sh と同じ):
  - FAIL（DRIFT / MISSING）0件なら stdout を空にしてサイレント配信抑制・exit 0
  - FAIL 1件以上で stdout にサマリ+FAIL行 → no_agent cron がそのまま配信
  - 検出自体は常に exit 0（自ジョブが exit 1 を返すと次回の自分が FAIL に見える循環を避ける）
  - 監査基盤の失敗（jobs.json unreadable 等）のみ exit 1

使い方:
  python3 kensho_script_drift_check.py                 # 既定プロファイル kensho-sweeps / FAILのみ
  python3 kensho_script_drift_check.py --all           # OK/UNTRACKED も含む全表（人手確認用）
  python3 kensho_script_drift_check.py --json          # 機械可読 JSON 1行
  python3 kensho_script_drift_check.py tai             # 複数プロファイル指定可
  環境変数でパス上書き（テスト用）:
    KENSHO_ROOT=/tmp/x PROFILE_HOME=/tmp/y DRIFT_JOBS=/tmp/jobs.json python3 ...
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

DEFAULT_HERMES_ROOT = Path("/home/atushi/.hermes")
DEFAULT_PROFILE = "kensho-sweeps"
DEFAULT_KENSHO_ROOT = Path("/mnt/d/Project2/kensho")
CHECK_SUFFIXES = (".py", ".sh", ".bash")


def md5sum(path: Path) -> str | None:
    try:
        return hashlib.md5(path.read_bytes()).hexdigest()
    except OSError:
        return None


def load_jobs(jobs_file: Path) -> list[dict]:
    data = json.loads(jobs_file.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data
    return data.get("jobs", []) or []


def repo_counterpart(name: str, kensho_root: Path) -> Path | None:
    """repo 側の対応ファイルを探す（直下 → scripts/ の順）。無ければ None。"""
    for cand in (kensho_root / name, kensho_root / "scripts" / name):
        if cand.is_file():
            return cand
    return None


def check_profile(profile: str, hermes_root: Path, kensho_root: Path) -> list[dict]:
    jobs_file = hermes_root / "profiles" / profile / "cron" / "jobs.json"
    scripts_dir = hermes_root / "profiles" / profile / "scripts"
    rows: list[dict] = []
    if not jobs_file.is_file():
        raise SystemExit(f"ERROR: jobs.json not found: {jobs_file}")

    seen: set[str] = set()
    for job in load_jobs(jobs_file):
        # v156 (t_20c9c446 / QA run508): monitor_script 配置も実行時に走るため
        # script と同様に走査対象化。同一名を複数ジョブが参照する場合は1回だけ検査。
        for key in ("script", "monitor_script"):
            script = job.get(key)
            if not script or not isinstance(script, str):
                continue
            name = Path(script).name
            if not name.endswith(CHECK_SUFFIXES) or name in seen:
                continue
            seen.add(name)
            enabled = bool(job.get("enabled", True))
            jid = str(job.get("id") or job.get("job_id") or "?")
            jname = str(job.get("name") or "?")
            prof_path = scripts_dir / name
            if not prof_path.is_file():
                rows.append({
                    "profile": profile,
                    "job_id": jid,
                    "job": jname,
                    "script": name,
                    "ref_kind": key,
                    "enabled": enabled,
                    "status": "MISSING" if enabled else "MISSING_DISABLED",
                    "repo": str(repo_counterpart(name, kensho_root) or ""),
                    "profile_md5": "",
                    "repo_md5": "",
                })
                continue
            repo_path = repo_counterpart(name, kensho_root)
            pm = md5sum(prof_path)
            if repo_path is None:
                rows.append({
                    "profile": profile,
                    "job_id": jid,
                    "job": jname,
                    "script": name,
                    "ref_kind": key,
                    "enabled": enabled,
                    "status": "UNTRACKED",
                    "repo": "",
                    "profile_md5": pm or "",
                    "repo_md5": "",
                })
                continue
            rm = md5sum(repo_path)
            rows.append({
                "profile": profile,
                "job_id": jid,
                "job": jname,
                "script": name,
                "ref_kind": key,
                "enabled": enabled,
                "status": "OK" if pm == rm else "DRIFT",
                "repo": str(repo_path),
                "profile_md5": pm or "",
                "repo_md5": rm or "",
            })
    return rows


FAIL_STATUSES = {"DRIFT", "MISSING"}

# ---- 意図的な差分の除外リスト ------------------------------------------------
# 「profile 版が敢えて違う」ケース（絶対パス依存回避など）を許可する。
# ファイル名（basename）で一致させたら DRIFT→ALLOWED（FAIL化しない）へ降格し、
# --all / --json では表示する（透明性を保つ）。
# 置き場所: profile scripts dir 直下 kensho_script_drift_allowlist.txt（1行1ファイル名、
#           `#` 以降はコメント）。環境変数 DRIFT_ALLOWLIST で上書き可。
ALLOWLIST_FILENAME = "kensho_script_drift_allowlist.txt"


def load_allowlist(profiles: list[str], hermes_root: Path) -> dict[str, str]:
    """{script_basename: 理由コメント} を返す（複数プロファイル分はマージ）。"""
    out: dict[str, str] = {}
    files: list[Path] = []
    envv = os.environ.get("DRIFT_ALLOWLIST")
    if envv:
        files.append(Path(envv))
    for p in profiles:
        files.append(hermes_root / "profiles" / p / "scripts" / ALLOWLIST_FILENAME)
    for f in files:
        if not f.is_file():
            continue
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            name, _, reason = line.partition("#")
            name = name.strip()
            if name:
                out.setdefault(name, reason.strip())
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="cron script repo↔profile drift check")
    ap.add_argument("profiles", nargs="*", default=None, help="対象プロファイル名（既定 kensho-sweeps）")
    ap.add_argument("--all", action="store_true", help="OK/UNTRACKED も表示（人手確認用）")
    ap.add_argument("--json", action="store_true", help="JSON 1行出力")
    args = ap.parse_args(argv)

    hermes_root = Path(os.environ.get("PROFILE_HOME") or DEFAULT_HERMES_ROOT)
    # PROFILE_HOME は ~/.hermes 相当を指す（下位に profiles/<name>/）
    if os.environ.get("PROFILE_SCRIPTS_ROOT"):
        hermes_root = Path(os.environ["PROFILE_SCRIPTS_ROOT"])
    kensho_root = Path(os.environ.get("KENSHO_ROOT") or DEFAULT_KENSHO_ROOT)
    jobs_override = os.environ.get("DRIFT_JOBS")

    profiles = args.profiles or [DEFAULT_PROFILE]
    all_rows: list[dict] = []

    if jobs_override:
        # テスト用: jobs.json を直接指定（profile scripts dir は <jobs親>/scripts とみなす）
        jf = Path(jobs_override)
        all_rows.extend(_rows_from_jobs(jf, jf.parent.parent / "scripts", kensho_root, profiles[0]))
    else:
        for p in profiles:
            all_rows.extend(check_profile(p, hermes_root, kensho_root))

    # 除外リスト適用: 意図的な profile 版差分は DRIFT → ALLOWED に降格（FAIL化しない）
    allow = load_allowlist(profiles, hermes_root)
    for r in all_rows:
        if r["status"] == "DRIFT" and r["script"] in allow:
            r["status"] = "ALLOWED"
            r["repo_md5"] = f"{r['repo_md5']} [allowlist: {allow[r['script']] or '理由未記載'}]"

    fails = [r for r in all_rows if r["status"] in FAIL_STATUSES and r["enabled"]]
    drift = [r for r in fails if r["status"] == "DRIFT"]
    missing = [r for r in fails if r["status"] == "MISSING"]
    untracked = [r for r in all_rows if r["status"] == "UNTRACKED"]
    allowed = [r for r in all_rows if r["status"] == "ALLOWED"]

    if args.json:
        print(
            json.dumps(
                {
                    "ok": not fails,
                    "checked": len(all_rows),
                    "drift": len(drift),
                    "missing": len(missing),
                    "untracked_git_outside": len(untracked),
                    "allowed_intentional": len(allowed),
                    "fails": fails,
                },
                ensure_ascii=False,
            )
        )
        return 0

    if not fails:
        if not args.all:
            return 0  # no_agent サイレント規約: 空stdout = 配信なし
        print(f"script-drift-check: OK（{len(all_rows)}件 checked / drift 0 / missing 0 / git外 {len(untracked)}件）")
        for r in all_rows:
            print(f"  [{r['status']:<12}] {r['script']} ({r['job']})")
        return 0

    print(f"⚠️ script-drift-check: FAIL {len(fails)}件（drift={len(drift)} / missing={len(missing)}）")
    print("  対策: cp <repo版> <profile scripts dir> で同期（md5一致を確認）→ 次回cronで反映")
    for r in fails:
        print(f"  [{r['status']}] {r['script']} job={r['job']} ({r['profile']}/{r['job_id']})")
        if r["status"] == "DRIFT":
            print(f"      profile_md5={r['profile_md5']} repo_md5={r['repo_md5']}")
            print(f"      repo={r['repo']}")
    return 0


def _rows_from_jobs(jobs_file: Path, scripts_dir: Path, kensho_root: Path, profile: str) -> list[dict]:
    """DRIFT_JOBS 上書き用（テストで jobs.json を任意位置から読む）。"""
    rows: list[dict] = []
    seen: set[str] = set()
    for job in load_jobs(jobs_file):
        name = ""
        for key in ("script", "monitor_script"):
            script = job.get(key)
            if script and str(script).endswith(CHECK_SUFFIXES):
                name = Path(str(script)).name
                break
        if not name or name in seen:
            continue
        seen.add(name)
        prof_path = scripts_dir / name
        repo_path = repo_counterpart(name, kensho_root)
        pm, rm = md5sum(prof_path), md5sum(repo_path) if repo_path else None
        if pm is None:
            status = "MISSING"
        elif rm is None:
            status = "UNTRACKED"
        else:
            status = "OK" if pm == rm else "DRIFT"
        rows.append({
            "profile": profile,
            "job_id": str(job.get("id") or "?"),
            "job": str(job.get("name") or "?"),
            "script": name,
            "enabled": bool(job.get("enabled", True)),
            "status": status,
            "repo": str(repo_path or ""),
            "profile_md5": pm or "",
            "repo_md5": rm or "",
        })
    return rows


if __name__ == "__main__":
    sys.exit(main())
