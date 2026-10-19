#!/usr/bin/env python3
"""HQ-run Studio probe: installed versions and one disposable synthetic LoRA step.

Standalone stdlib entrypoint; MLX imports occur only inside the timed child.
No checkpoint, tokenizer, record, training dataset, or adapter output is used.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
import os
import platform
import site
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STEP_CHECKS = {
    "adapter_only_trainable", "finite_nonzero_gradients", "frozen_base_unchanged",
    "adapter_changed", "finite_parameters", "finite_losses", "loss_decreased", "exactly_one_step",
}
FIXTURE = {
    "name": "synthetic-linear-lora-v1", "seed": 0,
    "input_dims": 4, "output_dims": 3, "rank": 2, "scale": 1.0,
    "base_weight": "arange(12).reshape(3,4)/16", "lora_a": 0.125, "lora_b": 0.0,
    "inputs": [[1.0, 0.0, -1.0, 0.5], [0.0, 1.0, 0.5, -1.0]],
    "targets": [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]],
    "dtype": "float32", "optimizer": "SGD", "learning_rate": 0.01,
    "loss": "mean squared error", "optimizer_steps": 1,
}


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def package_metadata():
    result = {}
    for name in ("mlx", "mlx-lm"):
        try:
            dist = importlib.metadata.distribution(name)
            result[name] = {"version": dist.version, "distribution_root": str(dist.locate_file(""))}
        except importlib.metadata.PackageNotFoundError:
            result[name] = {"version": None, "status": "not-installed"}
    return result


def synthetic_step(device):
    """Actually evaluate forward, gradients and ONE update on 14 LoRA parameters."""
    import inspect
    import mlx.core as mx
    import mlx.nn as nn
    import mlx.optimizers as optim
    from mlx.utils import tree_flatten
    from mlx_lm.tuner.lora import LoRALinear

    if device == "gpu" and not mx.metal.is_available():
        raise RuntimeError("Metal is unavailable; the GPU probe cannot fall back to CPU")
    mx.set_default_device(mx.gpu if device == "gpu" else mx.cpu)
    mx.random.seed(FIXTURE["seed"])
    base = nn.Linear(4, 3, bias=False)
    base.weight = mx.arange(12, dtype=mx.float32).reshape(3, 4) / 16
    layer = LoRALinear.from_base(base, r=2, dropout=0.0, scale=1.0)
    layer.lora_a = mx.full((4, 2), 0.125, dtype=mx.float32)
    layer.lora_b = mx.zeros((2, 3), dtype=mx.float32)
    layer.linear.freeze()
    trainable = dict(tree_flatten(layer.trainable_parameters()))
    if set(trainable) != {"lora_a", "lora_b"}:
        raise RuntimeError("expected only LoRA parameters to be trainable")
    x = mx.array(FIXTURE["inputs"], dtype=mx.float32)
    y = mx.array(FIXTURE["targets"], dtype=mx.float32)
    mx.eval(layer.parameters(), x, y)
    frozen_before = layer.linear.weight.tolist()
    adapters_before = {name: value.tolist() for name, value in trainable.items()}

    def loss_fn(model):
        return mx.mean(mx.square(model(x) - y))

    loss, gradients = nn.value_and_grad(layer, loss_fn)(layer)
    mx.eval(loss, gradients)
    before = float(loss.item())
    flat_gradients = dict(tree_flatten(gradients))
    if set(flat_gradients) != {"lora_a", "lora_b"}:
        raise RuntimeError("gradient keys differ from the adapter-only parameter set")
    gradient_finite = all(bool(mx.all(mx.isfinite(g)).item()) for g in flat_gradients.values())
    gradient_nonzero = any(bool(mx.any(g != 0).item()) for g in flat_gradients.values())
    if not gradient_finite or not gradient_nonzero:
        raise RuntimeError("synthetic gradients must be finite and nonzero")
    optimizer = optim.SGD(learning_rate=FIXTURE["learning_rate"])
    optimizer.update(layer, gradients)
    mx.eval(layer.parameters(), optimizer.state)
    after = float(loss_fn(layer).item())
    adapters_after = dict(tree_flatten(layer.trainable_parameters()))
    checks = {
        "adapter_only_trainable": True,
        "finite_nonzero_gradients": gradient_finite and gradient_nonzero,
        "frozen_base_unchanged": layer.linear.weight.tolist() == frozen_before,
        "adapter_changed": any(value.tolist() != adapters_before[name] for name, value in adapters_after.items()),
        "finite_parameters": all(bool(mx.all(mx.isfinite(v)).item()) for _, v in tree_flatten(layer.parameters())),
        "finite_losses": math.isfinite(before) and math.isfinite(after),
        "loss_decreased": after < before,
        "exactly_one_step": int(optimizer.step.item()) == 1,
    }
    source = Path(inspect.getfile(LoRALinear))
    return {
        "status": "passed" if all(checks.values()) else "failed", "checks": checks,
        "device": str(mx.default_device()), "loss_before": before, "loss_after": after,
        "trainable_parameters": sum(v.size for v in trainable.values()),
        "frozen_parameters": base.weight.size, "optimizer_steps": int(optimizer.step.item()),
        "lora_source": str(source), "lora_source_sha256": sha256(source.read_bytes()),
        "mlx_core_origin": mx.__file__, "weights_saved": False,
    }


def run_step(executable, device, timeout):
    if not Path(executable).is_absolute():
        raise ValueError("the interpreter path must be absolute")
    env = dict(os.environ)
    env.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", HF_HUB_DISABLE_TELEMETRY="1", DO_NOT_TRACK="1")
    try:
        process = subprocess.run(
            [executable, "-B", str(Path(__file__).resolve()), "--worker", "--device", device],
            capture_output=True, text=True, timeout=timeout, env=env,
        )
    except subprocess.TimeoutExpired:
        return {"status": "failed", "reason": "worker-timeout", "timeout_seconds": timeout}
    except OSError as error:
        return {"status": "failed", "reason": "worker-launch", "error_type": type(error).__name__}
    try:
        result = json.loads(process.stdout)
        if not isinstance(result, dict) or result.get("status") not in {"passed", "failed"}:
            raise ValueError("invalid worker result")
        checks = result.get("checks")
        if result["status"] == "passed" and (not isinstance(checks, dict) or set(checks) != STEP_CHECKS
                or not all(v is True for v in checks.values())):
            raise ValueError("worker reported success without passing checks")
    except (ValueError, TypeError):
        result = {"status": "failed", "reason": "invalid-worker-result"}
    if process.returncode != 0:
        result["status"] = "failed"
        result.setdefault("reason", "worker-exit")
    result["worker_returncode"] = process.returncode
    result["stderr_sha256"] = sha256(process.stderr.encode())
    result["stderr_bytes"] = len(process.stderr.encode())
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--reader", default="HQ")
    parser.add_argument("--cadence", default="before P1 environment approval")
    parser.add_argument("--expect-mlx", default="0.32.2")
    parser.add_argument("--expect-mlx-lm", default="0.31.3")
    parser.add_argument("--device", choices=("gpu", "cpu"), default="gpu")
    parser.add_argument("--timeout", type=int, default=45)
    parser.add_argument("--metadata-only", action="store_true")
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.worker:
        try:
            result = synthetic_step(args.device)
        except Exception as error:
            result = {"status": "failed", "reason": "synthetic-step-error", "error_type": type(error).__name__, "detail": str(error)[:300]}
        print(json.dumps(result, allow_nan=False))
        return 0 if result["status"] == "passed" else 2
    if args.output is None:
        parser.error("--output is required")
    if not 1 <= args.timeout <= 120:
        parser.error("--timeout must be 1 to 120 seconds")
    if not args.reader.strip() or not args.cadence.strip():
        parser.error("reader and cadence must be named")
    output = args.output.resolve()
    if not output.is_relative_to(ROOT / "local"):
        parser.error("environment receipts must stay under this repo's ignored local/ directory")
    packages = package_metadata()
    expected = {"mlx": args.expect_mlx, "mlx-lm": args.expect_mlx_lm}
    pair_matches = all(packages[name]["version"] == version for name, version in expected.items())
    report = {
        "schema_version": "0.1", "probe": "studio-synthetic-lora", "status": "started",
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "reader": {"name": args.reader, "cadence": args.cadence},
        "interpreter": {"executable": sys.executable, "resolved_binary": str(Path(sys.executable).resolve()),
                        "version": sys.version, "prefix": sys.prefix, "base_prefix": sys.base_prefix,
                        "user_site_enabled": site.ENABLE_USER_SITE},
        "host": platform.node(), "platform": platform.platform(), "machine": platform.machine(),
        "packages": packages, "expected_pair": expected, "pair_matches": pair_matches,
        "script_sha256": sha256(Path(__file__).read_bytes()), "fixture": FIXTURE,
        "fixture_sha256": sha256(json.dumps(FIXTURE, sort_keys=True, separators=(",", ":")).encode()),
        "constraints": {"device_requested": args.device, "timeout_seconds": args.timeout,
                        "checkpoints_loaded": 0, "record_rows_read": 0, "adapter_files_written": 0},
        "review_status": "pending-HQ", "limits": [
            "This is an in-memory synthetic optimizer check, not an Ember training run.",
            "It does not validate a checkpoint, tokenizer, quantization, trainer CLI, or full-model memory budget.",
            "A passing alternate version pair does not verify the requested pair.",
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        stream = output.open("x", encoding="utf-8")
    except FileExistsError:
        print("environment probe refused: output already exists", file=sys.stderr)
        return 2
    with stream:
        # A native crash or interruption must not leave a success-looking receipt.
        json.dump(report, stream, indent=2)
        stream.flush()
        if args.metadata_only:
            step = {"status": "not-run", "reason": "metadata-only"}
            status = "metadata-only"
        elif any(packages[name]["version"] is None for name in expected):
            step = {"status": "not-run", "reason": "missing-package"}
            status = "failed"
        else:
            step = run_step(sys.executable, args.device, args.timeout)
            status = "passed" if pair_matches and step["status"] == "passed" else "failed"
        report.update(status=status, dry_lora_step=step, completed_at=datetime.now(timezone.utc).isoformat())
        stream.seek(0)
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write("\n")
        stream.truncate()
    print(json.dumps({"status": status, "pair_matches": pair_matches, "dry_lora_step": step["status"],
                      "report_sha256": sha256(output.read_bytes()), "review_status": "pending-HQ"}))
    return 0 if status in {"passed", "metadata-only"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
