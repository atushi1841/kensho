import hashlib, subprocess, json, sys

g = subprocess.run([sys.executable,"/home/atushi/.hermes/profiles/kensho-sweeps/scripts/kanban_done_guard.py","--selftest"], capture_output=True, text=True).stdout
b = subprocess.run([sys.executable,"/mnt/d/Project2/kensho/scripts/done_guard_evidence_binding.py","--selftest"], capture_output=True, text=True).stdout
p = subprocess.run([sys.executable,"/mnt/d/Project2/kensho/scripts/push_guard.py","--selftest"], capture_output=True, text=True).stdout
t = subprocess.run([sys.executable,"-m","pytest","tests/test_done_guard_evidence_binding.py","tests/test_hunter_guard_v162.py","tests/test_gumroad_cookies_guard.py","tests/test_crash_guard.py","tests/test_guarded_source_arity.py","tests/test_url_guard.py","-q"], capture_output=True, text=True).stdout

payload = {
    "task_id": "t_7060bd39",
    "success_indicators": [
        "pre-commit done-guard hook added (.pre-commit-config.yaml)",
        "worker completion-before-guard rule added (SOUL.md)",
        "CI guard selftest step added (.github/workflows/ci.yml)",
    ],
    "verification_commands": [
        "python3 /home/atushi/.hermes/profiles/kensho-sweeps/scripts/kanban_done_guard.py --selftest",
        "python3 /mnt/d/Project2/kensho/scripts/done_guard_evidence_binding.py --selftest",
        "python3 /mnt/d/Project2/kensho/scripts/push_guard.py --selftest",
        "python3 -m pytest tests/test_done_guard_evidence_binding.py tests/test_hunter_guard_v162.py tests/test_gumroad_cookies_guard.py tests/test_crash_guard.py tests/test_guarded_source_arity.py tests/test_url_guard.py",
    ],
    "artifact_paths": [
        "/mnt/d/Project2/kensho/.pre-commit-config.yaml",
        "/mnt/d/Project2/kensho/.github/workflows/ci.yml",
        "/mnt/d/Project2/kensho/Makefile",
        "/home/atushi/.hermes/profiles/kensho-revenue-worker/SOUL.md",
        "/mnt/d/Project2/kensho/reports/t_7060bd39_verification.md",
    ],
    "evidence_hashes": [
        "sha256:" + hashlib.sha256(g.encode()).hexdigest(),
        "sha256:" + hashlib.sha256(b.encode()).hexdigest(),
        "sha256:" + hashlib.sha256(p.encode()).hexdigest(),
        "sha256:" + hashlib.sha256(t.encode()).hexdigest(),
    ],
}
print(json.dumps(payload, ensure_ascii=False))