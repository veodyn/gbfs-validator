"""Copy JSON Schemas from the pinned upstream clone into package data."""

from __future__ import annotations

import json
import pathlib
import shutil
import subprocess

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "upstream/gbfs-validator/versions/gbfs-json-schema"
DST = ROOT / "src/gbfs_validator/data/schemas"


def _rev(repo: pathlib.Path) -> str:
    return subprocess.check_output(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        text=True,
    ).strip()


def main() -> None:
    if not SRC.is_dir():
        raise SystemExit("upstream clone missing: run tools/sync_upstream.sh first")
    if DST.exists():
        shutil.rmtree(DST)
    for vdir in sorted(SRC.glob("v*")):
        if not vdir.is_dir():
            continue
        out = DST / vdir.name
        out.mkdir(parents=True)
        for f in sorted(vdir.glob("*.json")):
            json.loads(f.read_text())
            shutil.copy(f, out / f.name)
    pins = [_rev(ROOT / "upstream"), _rev(SRC)]
    (DST.parent / "PIN").write_text("\n".join(pins) + "\n")


if __name__ == "__main__":
    main()
