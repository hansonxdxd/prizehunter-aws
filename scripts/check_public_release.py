"""Conservative public-file/history checks; findings never print matched secrets."""

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

PATTERNS = {
    "AWS access-key ID": rb"(?:AKIA|ASIA)[A-Z0-9]{16}",
    "GitHub token": rb"(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})",
    "private key": rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
    "credential assignment": rb"(?im)^\s*(?:aws_secret_access_key|aws_session_token|password|api_key)\s*[=:]\s*[^\s#]{12,}",
    "machine absolute path": ("/" + "Users/|/" + "home/[^/]+/").encode(),
    "private host email": rb"[A-Za-z0-9_.+-]+@[A-Za-z0-9_.+-]+\.local\b",
    "possible AWS account number": rb"(?<![A-Za-z0-9])\d{12}(?![A-Za-z0-9])",
}


def scan(name, data):
    return [f"{name}: {kind}" for kind, pattern in PATTERNS.items() if re.search(pattern, data)]


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--history", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    manifest = json.loads((root / "docs/PUBLICATION_CANDIDATES.json").read_text())
    allowed = set(manifest["paths"])
    findings = []
    checksums = {}
    for name in sorted(allowed):
        file = root / name
        if not file.is_file() or file.is_symlink():
            findings.append(f"{name}: missing file or symlink")
            continue
        data = file.read_bytes()
        checksums[name] = hashlib.sha256(data).hexdigest()
        findings.extend(scan(name, data))
    objects = 0
    if args.history:
        tracked = set(git(root, "ls-files", "-z").decode().rstrip("\0").split("\0"))
        if tracked != allowed:
            findings.append("Tracked files differ from reviewed allowlist")
        for row in git(root, "rev-list", "--objects", "--all").splitlines():
            oid = row.split(b" ", 1)[0].decode()
            kind = git(root, "cat-file", "-t", oid).strip()
            if kind in {b"blob", b"commit", b"tag"}:
                objects += 1
                findings.extend(scan(f"Git object {oid}", git(root, "cat-file", "-p", oid)))
    print(
        json.dumps(
            {
                "files_checked": len(checksums),
                "history_objects_checked": objects,
                "findings": findings,
                "status": "PASS" if not findings else "FAIL",
            },
            indent=2,
        )
    )
    # Dependency author/copyright contacts are legitimate notices and retained.
    # Human review of every allowlisted file supplements these recognizable patterns.
    raise SystemExit(1 if findings else 0)


if __name__ == "__main__":
    main()
