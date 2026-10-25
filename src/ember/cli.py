"""Offline CLI. Every invocation selftests before it reads a corpus."""
from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import platform
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import __version__
from .baselines import run_baselines, score
from .release import scan_candidate
from .validation import ROOT, InvalidCorpus, digest, load_manifest, validator

MAX_GIT_WARNINGS = 20
MAX_GIT_WARNING_CHARS = 512


def selftest() -> dict:
    if sys.version_info[:3] != (3, 10, 12):
        raise InvalidCorpus("evaluation interpreter must be Python 3.10.12 (see .python-version)")
    if importlib.metadata.version("jsonschema") != "4.25.0":
        raise InvalidCorpus("jsonschema version differs from evaluation pin")
    for name in ("decision", "pair", "manifest", "candidate", "source_index"):
        validator(name)
    if score(["OPEN", "PAUSE"], ["PAUSE", "PAUSE"])["balanced_accuracy"] != 0.5:
        raise InvalidCorpus("balanced-accuracy selftest failed")
    return {"status": "passed", "python": platform.python_version(), "executable": _redact(sys.executable),
            "jsonschema": importlib.metadata.version("jsonschema"), "scope": "offline evaluator; no MLX or model test"}


def _git(*args: str) -> subprocess.CompletedProcess:
    # stderr is captured, never discarded: a warning from git means the inspection was incomplete.
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True,
                          text=True, encoding="utf-8", errors="backslashreplace")


def _home() -> str | None:
    # Path.home() raises with no HOME and no passwd entry, and a root home would turn every slash into '~'.
    try:
        home = str(Path.home())
    except RuntimeError:
        return None
    return home if len(home) > 1 else None


def _redact(line: str) -> str:
    # Reports travel to a second seat: keep the reason, drop this machine's absolute paths.
    prefixes = [(str(ROOT), "<repo>")]
    home = _home()
    if home:
        prefixes.append((home, "~"))
    temp = os.environ.get("TMPDIR", "").rstrip("/")
    if temp.startswith("/"):
        prefixes.append((temp, "<tmp>"))
        # macOS tools may spell the same temporary directory with either prefix.
        if temp.startswith("/var/"):
            prefixes.append(("/private" + temp, "<tmp>"))
        elif temp.startswith("/private/var/"):
            prefixes.append((temp[len("/private"):], "<tmp>"))
    prefixes.extend([("/private/tmp", "<tmp>"), ("/tmp", "<tmp>"),
                     ("/opt/homebrew", "<homebrew>")])
    # Specific paths win over their parents; do not replace a sibling's shared prefix.
    for prefix, replacement in sorted(prefixes, key=lambda item: len(item[0]), reverse=True):
        line = re.sub(re.escape(prefix) + r"(?=/|$|[\s'\":])", lambda _: replacement, line)
    return re.sub(r"/Volumes/[^/\n'\"]+", "<volume>", line)


def _bounded_warnings(lines: list[str]) -> list[str]:
    """Bound report text after redaction, keeping the first occurrence in order."""
    result: list[str] = []
    for line in lines:
        if not line.strip():
            continue
        line = _redact(line)
        if len(line) > MAX_GIT_WARNING_CHARS:
            line = line[:MAX_GIT_WARNING_CHARS - len(" [truncated]")] + " [truncated]"
        if line in result:
            continue
        if len(result) == MAX_GIT_WARNINGS:
            result.append("additional git warnings omitted")
            break
        result.append(line)
    return result


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
        for name, completed in (("rev-parse", head), ("status", status)):
            warnings.extend(line for line in completed.stderr.splitlines() if line.strip())
            if completed.returncode != 0:
                warnings.append(f"git {name} exited {completed.returncode}")
        revision = head.stdout.strip() if head.returncode == 0 and head.stdout.strip() else "uncommitted"
        # Conservative: a tree git could not fully inspect is reported dirty, and the reason travels with the report.
        dirty = bool(status.stdout.strip()) or bool(warnings)
    packages = {name: importlib.metadata.version(name) for name in
                ("jsonschema", "attrs", "jsonschema-specifications", "referencing", "rpds-py")}
    return {"git_revision": revision, "working_tree_dirty": dirty, "git_warnings": _bounded_warnings(warnings), "code_sha256": hashes,
            "packages": packages, "platform": platform.platform(), "machine": platform.machine()}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("selftest", "validate", "baselines", "scan"))
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--candidate", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        check = selftest()
        if args.command == "selftest":
            print(json.dumps(check, indent=2))
            return 0
        if args.command == "scan":
            if args.candidate is None or args.output is None:
                parser.error("scan requires --candidate and --output")
            output = args.output.resolve()
            if not output.is_relative_to(ROOT.resolve() / "local"):
                raise InvalidCorpus("candidate scan reports must stay under local/")
            report = scan_candidate(args.candidate)
            report.update(selftest=check, provenance=runtime_provenance(),
                          started_at=datetime.now(timezone.utc).isoformat())
            with output.open("x", encoding="utf-8") as stream:
                json.dump(report, stream, indent=2, allow_nan=False)
                stream.write("\n")
            print(json.dumps({"status": report["status"], "report_sha256": digest(output.read_bytes()),
                              "release_review": "pending"}))
            return 0 if report["status"] == "clear" else 2
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
    except (InvalidCorpus, OSError, ValueError, KeyError, TypeError, RecursionError) as error:
        # No arbitrary exception string: JSON parse errors and paths can contain private data.
        message = str(error) if isinstance(error, InvalidCorpus) else type(error).__name__
        print(f"ember: refused: {message}", file=sys.stderr)
        return 2
