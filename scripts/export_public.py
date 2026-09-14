"""Copy only reviewed allowlisted files to a NEW public staging directory."""

import argparse
import json
import shutil
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("destination", help="New directory; must not exist")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    destination = Path(args.destination).resolve()
    if destination.exists():
        raise SystemExit("Destination already exists; no overwrite or history rewrite performed")
    manifest = json.loads((root / "docs/PUBLICATION_CANDIDATES.json").read_text())
    paths = manifest["paths"]
    for name in paths:
        source = root / name
        if source.is_symlink() or not source.is_file() or root not in source.resolve().parents:
            raise SystemExit(f"Invalid candidate file: {name}")
    destination.mkdir(parents=True)
    for name in paths:
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / name, target)
    print(f"Exported {len(paths)} reviewed files; private Git history excluded.")


if __name__ == "__main__":
    main()
