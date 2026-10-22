"""Offline CLI. Every invocation selftests before it reads a corpus."""
from __future__ import annotations

import argparse
import importlib.metadata
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import __version__
from .baselines import run_baselines, score
from .validation import ROOT, InvalidCorpus, digest, load_manifest, validator


def selftest() -> dict:
    if sys.version_info[:3] != (3, 10, 12):
        raise InvalidCorpus("evaluation interpreter must be Python 3.10.12 (see .python-version)")
    if importlib.metadata.version("jsonschema") != "4.25.0":
        raise InvalidCorpus("jsonschema version differs from evaluation pin")
    for name in ("decision", "pair", "manifest"):
        validator(name)
    if score(["OPEN", "PAUSE"], ["PAUSE", "PAUSE"])["balanced_accuracy"] != 0.5:
        raise InvalidCorpus("balanced-accuracy selftest failed")
    return {"status": "passed", "python": platform.python_version(), "executable": sys.executable,
            "jsonschema": importlib.metadata.version("jsonschema"), "scope": "offline evaluator; no MLX or model test"}


def _git(*args: str) -> subprocess.CompletedProcess:
    # stderr is captured, never discarded: a warning from git means the inspection was incomplete.
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True)


def runtime_provenance() -> dict:
    files = sorted((ROOT / "src/ember").rglob("*.py")) + sorted((ROOT / "src/ember/schemas").glob("*.json"))
    files += [ROOT / name for name in ("pyproject.toml", "uv.lock", ".python-version", "scripts/ember.py", "scripts/ember", "docs/corpus-exclusions.md")]
    hashes = {str(p.relative_to(ROOT)): digest(p.read_bytes()) for p in files}
    warnings: list[str] = []
    try:
        head = _git("rev-parse", "HEAD")
        status = _git("status", "--porcelain", "--untracked-files=normal")
    except OSError as exc:
        revision, dirty = "uncommitted", True
        warnings.append(f"git unavailable: {exc}")
    else:
        for completed in (head, status):
            warnings.extend(line for line in completed.stderr.splitlines() if line.strip())
            if completed.returncode != 0:
                warnings.append(f"git {completed.args[3]} exited {completed.returncode}")
        revision = head.stdout.strip() if head.returncode == 0 and head.stdout.strip() else "uncommitted"
        # Conservative: a tree git could not fully inspect is reported dirty, and the reason travels with the report.
        dirty = bool(status.stdout.strip()) or bool(warnings)
    packages = {name: importlib.metadata.version(name) for name in
                ("jsonschema", "attrs", "jsonschema-specifications", "referencing", "rpds-py")}
    return {"git_revision": revision, "working_tree_dirty": dirty, "git_warnings": warnings, "code_sha256": hashes,
            "packages": packages, "platform": platform.platform(), "machine": platform.machine()}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("selftest", "validate", "baselines"))
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        check = selftest()
        if args.command == "selftest":
            print(json.dumps(check, indent=2))
            return 0
        if args.manifest is None:
            parser.error("--manifest is required")
        if args.command == "baselines" and args.output is None:
            parser.error("--output is required; every run needs a reader and a record")
        manifest, rows, manifest_hash = load_manifest(args.manifest)
        if args.command == "validate":
            print(json.dumps({"status": "passed", "train_pairs": len(rows["train"]), "heldout_pairs": len(rows["heldout"]), "manifest_sha256": manifest_hash}))
            return 0
        report = {
            "schema_version": "0.1", "instrument_version": __version__,
            "run_kind": "p0-baselines", "started_at": datetime.now(timezone.utc).isoformat(),
            "selftest": check, "provenance": runtime_provenance(), "manifest_sha256": manifest_hash,
            "freeze_at": manifest["freeze_at"], "corpus": manifest["corpus"],
            "constraints": manifest["constraints"], "release_review": manifest["release_review"],
            "reader": manifest["reader"], "train_pairs": len(rows["train"]), "heldout_pairs": len(rows["heldout"]),
            "result": run_baselines(rows["train"], rows["heldout"]),
            "second_seat_verification": "pending",
            "limitations": ["No adapter exists or is scored by this command.",
                            "Release-review receipt is an attestation, not an automatic privacy proof.",
                            "Cited-and-present is structural; a person must check semantic support and negations.",
                            "No deployment or Tier 2 claim follows from this run alone."],
        }
        # Exclusive creation preserves prior runs. No raw situation/evidence text is emitted.
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, indent=2, allow_nan=False)
            stream.write("\n")
        print(json.dumps({"status": "recorded", "report_sha256": digest(args.output.read_bytes()), "second_seat_verification": "pending"}))
        return 0
    except (InvalidCorpus, OSError, ValueError, KeyError, TypeError) as error:
        # No arbitrary exception string: JSON parse errors and paths can contain private data.
        message = str(error) if isinstance(error, InvalidCorpus) else type(error).__name__
        print(f"ember: refused: {message}", file=sys.stderr)
        return 2
