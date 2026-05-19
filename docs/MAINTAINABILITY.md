# Maintainability — Disk Cleaner

Local commands for coverage, lint, and sanity checks.

## Test + coverage

```bash
pytest -q                                          # all tests
pytest --cov=disk_cleaner --cov-report=term-missing  # coverage report
ruff check disk_cleaner tests                      # lint
bandit -r disk_cleaner -ll                         # security scan
```

## CI threshold

CI minimum coverage: **35%** (baseline). Community goal: **60%**.
Per-module detail report via `--cov-report=html`.

## For new contributors

1. `pytest -q` — tests must pass
2. `ruff check disk_cleaner` — must be clean
3. New user-visible strings must be wrapped in `_()` (pre-commit hook catches this)
4. Commits: [Conventional Commits](https://www.conventionalcommits.org/)

PR template: [`.github/PULL_REQUEST_TEMPLATE.md`](../.github/PULL_REQUEST_TEMPLATE.md).
