#!/usr/bin/env python3
"""Read-only local artifact inventory. Does not fetch, load a model, or read record bodies."""
import argparse
import hashlib
import json
import platform
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def command(args):
    result = subprocess.run(args, capture_output=True, text=True, timeout=30)
    return {"returncode": result.returncode, "stdout": result.stdout.strip()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--reader", required=True)
    parser.add_argument("--cadence", required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(ROOT / "local"):
        parser.error("audit receipts must stay under the ignored repository local/ directory")
    home = Path.home()
    compass = home / "Desktop/💻 Code_Projects/phenomenological-compass"
    repos = {name: home / name for name in ("t2helix", "temple-harness", "conditioned-kernel", "PhaseGPT")}
    repos["phenomenological-compass"] = compass
    report = {"observed_at": datetime.now(timezone.utc).isoformat(), "host": platform.node(),
              "reader": {"name": args.reader, "cadence": args.cadence},
              "scope": "Local artifacts; no remote fetch, record bodies, model execution, or training", "repositories": {}, "files": {}}
    for name, repo in repos.items():
        if not repo.exists():
            report["repositories"][name] = {"status": "absent"}
            continue
        head = command(["git", "-C", str(repo), "rev-parse", "HEAD"])
        dirty = command(["git", "-C", str(repo), "status", "--porcelain", "--untracked-files=no"])
        report["repositories"][name] = {"path": str(repo), "head": head,
                                               "tracked_dirty_count": len(dirty["stdout"].splitlines()),
                                               "status_returncode": dirty["returncode"]}
    report["fix_7ee32ff_in_local_main"] = command(["git", "-C", str(repos["t2helix"]), "merge-base", "--is-ancestor", "7ee32ff", "main"])["returncode"] == 0
    sources = [repos["t2helix"] / "lib/chronicle.js", repos["temple-harness"] / "mcp-shim/bench/run_visitor.py",
               repos["temple-harness"] / "mcp-shim/temple_stack_mcp.py", repos["conditioned-kernel"] / "README.md",
               compass / "README.md", compass / "adapters_v1.0_qwen/adapter_config.json",
               compass / "adapters_v1.0_qwen/adapters.safetensors", repos["PhaseGPT"] / "adapters/phasegpt_v4.1_overfit/README.md"]
    sources.extend((repos["conditioned-kernel"] / "benchmarks/project_companion_v0/receipts").glob("*.json"))
    for path in sources:
        if path.is_file():
            data = path.read_bytes()
            report["files"][str(path)] = {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
    for name, executable in {
        "default": home / ".pyenv/versions/3.10.12/bin/python3",
        "scientific-index": home / "SCIENTIFIC_INDEX/15_IMPLEMENTATIONS/PhaseGPT/.venv/bin/python",
        "compass": compass / ".venv/bin/python",
    }.items():
        code = "import importlib.metadata as m,sys,json; d={};\nfor n in ('mlx','mlx-lm'):\n try: d[n]=m.version(n)\n except m.PackageNotFoundError: d[n]=None\nprint(json.dumps({'python':sys.version,'executable':sys.executable,'packages':d}))"
        report.setdefault("interpreter_metadata_only", {})[name] = command([str(executable), "-c", code]) if executable.exists() else {"status": "absent"}
    database = home / ".claude/plugins/data/t2helix-templetwo-t2helix/chronicle.db"
    if database.exists():
        with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as connection:
            connection.execute("PRAGMA query_only=ON")
            count, first, last = connection.execute("SELECT count(*),min(occurred_at),max(occurred_at) FROM compass_log").fetchone()
            columns = [row[1] for row in connection.execute("PRAGMA table_info(compass_log)")]
            at = int(datetime(2026, 8, 30, tzinfo=timezone.utc).timestamp() * 1000)
            report["local_compass_log"] = {
                "count": count, "first_utc": datetime.fromtimestamp(first / 1000, timezone.utc).isoformat() if first else None,
                "last_utc": datetime.fromtimestamp(last / 1000, timezone.utc).isoformat() if last else None,
                "aug30_utc_rows": connection.execute("SELECT count(*) FROM compass_log WHERE occurred_at>=? AND occurred_at<?", (at, at + 86400000)).fetchone()[0],
                "classes": dict(connection.execute("SELECT classification,count(*) FROM compass_log GROUP BY classification")),
                "columns": columns,
                "with_ruleset_hash": connection.execute("SELECT count(*) FROM compass_log WHERE ruleset_hash IS NOT NULL").fetchone()[0] if "ruleset_hash" in columns else None,
            }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")
    print("Local audit receipt recorded; no source bodies were copied.")


if __name__ == "__main__":
    main()
