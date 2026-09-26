.PHONY: test lint format setup coverage clean install pre-commit

# ── テスト ──
test:
	python -m pytest -x --tb=short

# ── リンター ──
lint:
	ruff check kensho/ tests/

# ── フォーマッター ──
format:
	ruff format kensho/ tests/

# ── 型チェック ──
mypy:
	python -m mypy kensho/ --ignore-missing-imports

# ── カバレッジ ──
coverage:
	python -m pytest --cov=kensho --cov-report=term-missing --tb=short

# ── セットアップ ──
setup:
	pip install -e ".[dev]"
	pre-commit install

# ── pre-commit（全ファイル）──
pre-commit:
	pre-commit run --all-files

# ── クリーンアップ ──
clean:
	rm -rf __pycache__ .pytest_cache .ruff_cache .mypy_cache .coverage
	find . -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true

# ── 完了前ガード自己検証（t_7060bd39: pre-commit/CI で guard 通す必須化）──
guard-selftest:
	python3 scripts/done_guard_evidence_binding.py --selftest
	python3 scripts/push_guard.py --selftest
	python3 /home/atushi/.hermes/profiles/kensho-sweeps/scripts/kanban_done_guard.py --selftest

# ── 全チェック（lint + test + mypy）──
check: lint mypy test
