# Contributing

Thanks for wanting to improve this pipeline. Small, testable changes are welcome.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest -q
```

## Guidelines

- Keep the package useful without credentials. Demo mode must stay offline.
- Do not commit secrets, real job applications, resumes, or chat identifiers.
- New sources should implement `fetch(limit) -> list[Job]` and isolate their own failures.
- Prefer deterministic scoring and classification rules that a unit test can lock down.
- The optional LLM path must fall back to regex when the environment has no credential.
- English for code, comments, and docs.

## Pull requests

1. Add or update tests under `tests/`.
2. Run `python -m pytest -q`.
3. Keep the diff focused. Do not reformat unrelated files.

By participating you agree to the [Code of Conduct](CODE_OF_CONDUCT.md).
