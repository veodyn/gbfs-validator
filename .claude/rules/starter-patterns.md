# Starter patterns: apply on touch

Apply these when already editing the relevant code. Never as a bulk refactor.

- Editing a file over 300 lines -> split per the file-size hook's suggestions
  (types / constants / validation / utils).
- Touching a `raise` site -> route it through the error registry
  (`src/gbfs_validator/constants/error_ids.py`).
- Touching an env read -> there are none, and there should be none. This
  package reads no environment variables at runtime.
- Adding a dependency -> stop. `dependencies = []` is the product, not a
  detail. Dev-only tooling goes in `[project.optional-dependencies].dev`.

## Project-specific: parity work

- Changing anything under `src/gbfs_validator/schema/` -> rerun
  `python -m pytest tests/test_ajv_goldens.py tests/test_formats.py` before
  committing; those goldens come from upstream's own AJV stack.
- Changing `feed.py`, `partials.py`, or `versions.py` -> rerun
  `python tools/differential.py` (needs `bash tools/sync_upstream.sh` first).
- Regenerating any golden -> regenerate `tests/fixtures/META.json` in the same
  commit so provenance (node version, pins, lockfile hash) stays accurate.
- Found upstream behaviour that looks wrong -> match it and record it in the
  spec's mirrored-behaviour list, described neutrally. Do not silently correct
  it.
