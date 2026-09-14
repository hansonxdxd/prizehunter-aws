"""Verify the pinned source dependency without accessing NEXT or Google."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
manifest = json.loads((ROOT / "SOURCE_MANIFEST.json").read_text())
for item in manifest["files"]:
    path = ROOT / item["export_path"]
    if hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
        raise SystemExit(f"Pinned source changed: {item['export_path']}")
print(f"Verified {len(manifest['files'])} pinned files at {manifest['source_commit']}")
