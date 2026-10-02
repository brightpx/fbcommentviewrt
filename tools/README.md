# tools/ — one-off diagnostics, probes and manual live scripts

These scripts are **not** part of the app. They were previously scattered in
the repo root and are now grouped here:

- `debug/` — `check_*`, `debug_*`, `analyze_*`, `find_*`, `verify_*`, `measure_*`, etc.
- `probe/` — `probe_*` DOM probes against the live post page
- `inspect/` — `inspect_*` DOM/button inspectors
- `manual/` — `post_*`, `reply_to_latest.py`, `test_*` live scripts
  (manual end-to-end scripts that hit real Facebook — **not** pytest unit
  tests; the automated suite lives in `tests/`)

## Running

Always run from the **repo root** so relative paths (`config.yaml`,
`database/`, `session/`) and `from app...` imports resolve:

```bash
python tools/debug/check_db.py
python tools/manual/test_sort_switch.py
```

Most scripts that import `app` already do `sys.path.insert(0, ".")` for this.
