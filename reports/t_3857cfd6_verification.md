# t_3857cfd6 verification evidence

## verification_evidence

$ python3 scripts/check_dep_drift.py --selftest
→ SELFTEST OK: drift injection detected -> exit 1 (per card regression guard)

$ python3 scripts/check_dep_drift.py
→ {"ok": true, "drift": [], "pip_check": "No broken requirements found.", "venv_python": "/home/atushi/kensho-venv/bin/python", "pyproject": "/mnt/d/Project2/kensho/pyproject.toml", "checked": {"playwright": "1.61.0", ...}}

$ grep -c "playwright==1.61.0" requirements-lock.txt
→ 1

$ grep -A2 -B2 "name = \"playwright\"" uv.lock | grep "version =" | head -1 | cut -d'"' -f2
→ 1.61.0