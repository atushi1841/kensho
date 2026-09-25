# verification_evidence for task t_ebbfe4a7

## verification_evidence
$ cd /mnt/d/Project2/kensho && git show --stat 4b34477
commit 4b34477cc84d359247691fb9ec00f6a161595493
Author: openhands <openhands@all-hands.dev>
Date:   Fri Sep 25 18:32:40 2026 +0900

    fix: add requirements-lock check to drift detection

 scripts/check_dep_drift.py | 56 +++++++++++++++++++++++++++++++++++++++-------
 1 file changed, 48 insertions(+), 8 deletions(-)

$ cd /mnt/d/Project2/kensho && grep -c "requirements-lock" scripts/check_dep_drift.py
3

$ cd /mnt/d/Project2/kensho && python3 scripts/check_dep_drift.py --selftest
selftest dep_drift: healthy_ok=True (twscrape==0.20.1, checked=2)
selftest dep_drift: injected_!=_drift_detected=True (drift=['twscrape'])
selftest dep_drift: missing_pkg_detected=True
selftest dep_drift: lock_missing_detected=True (drift=['kensho-lock-miss-pkg-xyz', 'kensho-lock-miss-pkg-xyz'])
SELFTEST OK: drift injection detected -> exit 1 (per card regression guard)

$ cd /mnt/d/Project2/kensho && python3 scripts/check_dep_drift.py
{"ok": false, "drift": [{"name": "beautifulsoup4", "declared": ">=4.12", "installed": "-", "reason": "MISSING: declared in pyproject but not in requirements.txt/requirements-lock.txt"}, {"name": "curl-cffi", "declared": "(none)", "installed": "-", "reason": "spec mismatch: requirements file has ==0.15.0, pyproject has "}, {"name": "curl-cffi", "declared": "(none)", "installed": "-", "reason": "MISSING: package name not found in uv.lock"}, {"name": "httpx", "declared": ">=0.27", "installed": "-", "reason": "spec mismatch: requirements file has ==0.28.1, pyproject has >=0.27"}, {"name": "httpx", "declared": ">=0.27", "installed": "-", "reason": "MISSING: package name not found in uv.lock"}, {"name": "keyring", "declared": ">=24.0", "installed": "-", "reason": "MISSING: declared in pyproject but not in requirements.txt/requirements-lock.txt"}, {"name": "loguru", "declared": ">=0.7", "installed": "-", "reason": "MISSING: declared in pyproject but not in requirements.txt/requirements-lock.txt"}, {"name": "lxml", "declared": ">=5.0", "installed": "-", "reason": "MISSING: declared in pyproject but not in requirements.txt/requirements-lock.txt"}, {"name": "patchright", "declared": "==1.62.3", "installed": "-", "reason": "MISSING: package name not found in uv.lock"}, {"name": "playwright", "declared": "==1.61.0", "installed": "-", "reason": "MISSING: package name not found in uv.lock"}, {"name": "psutil", "declared": ">=5.9", "installed": "-", "reason": "spec mismatch: requirements file has ==7.2.2, pyproject has >=5.9"}, {"name": "psutil", "declared": ">=5.9", "installed": "-", "reason": "MISSING: package name not found in uv.lock"}, {"name": "pydantic", "declared": ">=2.0", "installed": "-", "reason": "MISSING: declared in pyproject but not in requirements.txt/requirements-lock.txt"}, {"name": "pydantic-settings", "declared": ">=2.0", "installed": "-", "reason": "MISSING: declared in pyproject but not in requirements.txt/requirements-lock.txt"}, {"name": "pyyaml", "declared": ">=6.0", "installed": "-", "reason": "spec mismatch: requirements file has ==6.0.3, pyproject has >=6.0"}, {"name": "pyyaml", "declared": ">=6.0", "installed": "-", "reason": "MISSING: package name not found in uv.lock"}, {"name": "requests", "declared": ">=2.31", "installed": "-", "reason": "MISSING: declared in pyproject but not in requirements.txt/requirements-lock.txt"}, {"name": "scrapling", "declared": ">=0.4.15", "installed": "-", "reason": "spec mismatch: requirements file has ==0.4.15, pyproject has >=0.4.15"}, {"name": "scrapling", "declared": ">=0.4.15", "installed": "-", "reason": "MISSING: package name not found in uv.lock"}, {"name": "twscrape", "declared": ">=0.20.1", "installed": "-", "reason": "MISSING: declared in pyproject but not in requirements.txt/requirements-lock.txt"}], "pip_check": "No broken requirements found.", "venv_python": "/home/atushi/kensho-venv/bin/python", "pyproject": "/mnt/d/Project2/kensho/pyproject.toml", "checked": {"beautifulsoup4": "4.15.0", "curl-cffi": "0.15.0", "httpx": "0.28.1", "keyring": "25.7.0", "loguru": "0.7.3", "lxml": "6.1.1", "patchright": "1.62.3", "playwright": "1.61.0", "psutil": "7.2.2", "pydantic": "2.13.4", "pydantic-settings": "2.14.2", "pyyaml": "6.0.3", "requests": "2.34.2", "scrapling": "0.4.15", "twscrape": "0.20.1"}}
