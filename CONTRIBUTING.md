# Contributing to Disk Cleaner

Thanks for thinking about contributing. This project values **safety**,
**clarity**, and **conservative defaults** — please read
[DESIGN_PRINCIPLES.md](DESIGN_PRINCIPLES.md) before opening a PR.

## Development setup

```bash
sudo apt install python3-gi gir1.2-gtk-3.0 python3-cairo
git clone https://github.com/codechu/disk-cleaner.git
cd disk-cleaner
pip install -e ".[dev]"
pytest -q
ruff check disk_cleaner tests
```

## Workflow

- Branch names: `feature/<short>`, `fix/<short>`, `refactor/<short>`,
  `docs/<short>`.
- Commit messages: [Conventional Commits](https://www.conventionalcommits.org/)
  (`feat:`, `fix:`, `refactor:`, `docs:`, `test:`, `chore:`).
- Open a PR using the template; describe the *why* in the body.

## Tests

- `pytest -q` must pass.
- New feature → new test (pure logic preferred — keep UI tests minimal).
- Don't rely on the real `~/.config/disk_cleaner/`; use `tmp_path`.

## Adding a new Scanner

1. Create `disk_cleaner/scanners/<name>.py`.
2. Subclass `disk_cleaner.scanners.Scanner` and implement `list_tasks`.
3. Register it in `disk_cleaner/app.py` (`AppContext` scanners dict).
4. Update [docs/SCANNERS.md](docs/SCANNERS.md).
5. Add a smoke test under `tests/`.

## Adding a new Cleaner

1. Create `disk_cleaner/cleaners/<name>.py`, subclass `Cleaner`.
2. **Default to trash mode** (never permanent unless explicitly opted in).
3. Test on a `tmp_path` first; never against `~`.

## Adding a new Visualization

1. Create `disk_cleaner/viz/<name>.py`, subclass `VizStrategy`.
2. Implement `layout`, `draw`, `hit_test`.
3. Register the strategy in `AppContext.viz`.

## Style

- `ruff check` + `ruff format` clean.
- Type hints on public APIs (`from __future__ import annotations`).
- Use `logging.getLogger(__name__)`; avoid `print`.
- Keep PRs focused — one change, one PR.

## Security

If you find a security issue (e.g. a path-escape, an injection in a
cleaner command), **don't open a public issue** — email the maintainer
at the address in `pyproject.toml`.
