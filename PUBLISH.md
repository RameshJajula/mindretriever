# Publishing mindretriever to PyPI

This guide is the release checklist for publishing `mindretriever`.

## Prerequisites

- Python 3.10+
- A PyPI account: https://pypi.org/account/register/
- A PyPI API token: https://pypi.org/manage/account/token/

## 1) Prepare Environment

```bash
pip install --upgrade build twine setuptools wheel
```

Optional on Windows PowerShell (clean old artifacts):

```powershell
Remove-Item build, dist, *.egg-info -Recurse -ErrorAction SilentlyContinue
```

## 2) Update Version

Keep versions in sync:

- `pyproject.toml` -> `[project].version`
- `graphmind/__init__.py` -> `__version__`
- `setup.py` -> `version` (compatibility metadata)

Example release progression: `0.1.3` -> `0.1.4`

## 3) Run Quality Gates

```bash
python -m pytest tests -q
```

Ensure all tests pass before building.

## 4) Build Distributions

```bash
python -m build
```

Expected outputs:

- `dist/mindretriever-<version>-py3-none-any.whl`
- `dist/mindretriever-<version>.tar.gz`

## 5) Validate Package Metadata

```bash
twine check dist/*
```

Both files should report `PASSED`.

## 6) Upload to TestPyPI (Recommended)

```bash
twine upload --repository testpypi dist/* --username __token__ --password <TESTPYPI_TOKEN>
```

Install test package:

```bash
pip install --index-url https://test.pypi.org/simple/ mindretriever
```

## 7) Upload to PyPI

```bash
twine upload dist/* --username __token__ --password <PYPI_TOKEN>
```

Then verify:

- https://pypi.org/project/mindretriever/

## 8) Post-release Smoke Test

```bash
pip install --upgrade mindretriever
python -m mindretriever --help
python -m uvicorn mindretriever.api:app --host 127.0.0.1 --port 8000
```

Health check:

```bash
curl http://127.0.0.1:8000/health
```

## Notes

- Upload endpoint accepts multipart field `files` (preferred) and `file` (compatibility alias).
- Supported upload formats remain: `.md`, `.docx`, `.sql`.
- On some Windows terminals, the `mindretriever` / `mindretriever-api` commands may not resolve unless Scripts is on `PATH`. Use `python -m mindretriever` and `python -m uvicorn mindretriever.api:app ...` as reliable fallbacks.
