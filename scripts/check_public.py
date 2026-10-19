#!/usr/bin/env python3
"""Inspect the exact Git index for accidental data/artifact/credential publication.

This is a narrow scaffold check, not the mirror's corpus release scanner.
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROOT_FILES = {"README.md", "AGENTS.md", ".gitignore", ".python-version", "pyproject.toml", "uv.lock"}
PATTERNS = {
    "scoped credential": re.compile(rb"\b(?:svs_|cbr_)[A-Za-z0-9_-]{12,}\b"),
    "GitHub credential": re.compile(rb"\b(?:gh[pousr]_|github_pat_)[A-Za-z0-9_]{20,}\b"),
    "API credential": re.compile(rb"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b"),
    "private key": re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "bare 43-character stem": re.compile(rb"(?<![A-Za-z0-9_-])[A-Za-z0-9_-]{43}(?![A-Za-z0-9_-])"),
    "absolute user-home path": re.compile(rb"/(?:Users|home)/[^\s/]+/"),
}


def allowed(path):
    p = Path(path)
    if path in ROOT_FILES or path == "scripts/ember" or path == "config/manifest.template.json":
        return True
    if path == ".github/workflows/ci.yml":
        return True
    if p.parts[0] == "docs":
        return p.suffix == ".md"
    if p.parts[0] in {"scripts", "tests"}:
        return p.suffix == ".py"
    if path.startswith("src/ember/"):
        return p.suffix == ".py" or (path.startswith("src/ember/schemas/") and path.endswith(".schema.json"))
    return False


def main():
    names = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode().split("\0")
    names = [name for name in names if name]
    if not names:
        print("public check refused: stage the intended files first", file=sys.stderr)
        return 1
    failures = []
    for name in names:
        if not allowed(name):
            failures.append((name, "outside scaffold publication paths"))
            continue
        data = subprocess.check_output(["git", "show", f":{name}"], cwd=ROOT)
        if b"\0" in data or len(data) > 1_000_000:
            failures.append((name, "binary or unexpectedly large file"))
            continue
        for label, pattern in PATTERNS.items():
            if pattern.search(data):
                failures.append((name, label))
    if failures:
        for name, label in failures:
            # Never print matched bytes.
            print(f"public check refused: {name}: {label}", file=sys.stderr)
        return 1
    print(f"Public index check passed: {len(names)} source/documentation files; no corpus or model artifacts.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
