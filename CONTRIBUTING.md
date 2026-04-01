# Contributing to OpenAgno

Thanks for contributing to OpenAgno.

## Development setup

```bash
git clone https://github.com/OpenAgno/OpenAgno.git
cd OpenAgno
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev,protocols]'
openagno validate
pytest -q
```

## Contribution guidelines

- Keep pull requests focused on one change.
- Add or update tests for behavior changes.
- Update docs for user-facing changes.
- Follow existing formatting and structure.
- Keep secrets out of version control and use `.env` for local credentials.

## Reporting issues

Use GitHub Issues and include:

- reproduction steps
- expected behavior
- actual behavior
- `openagno --version`
- Python version and operating system

## Pull requests

- Branch from `main`.
- Run tests before opening the PR.
- Describe the scope and impact clearly.
- Link the relevant issue or discussion when available.

By contributing, you agree that your contributions will be licensed under Apache 2.0.
