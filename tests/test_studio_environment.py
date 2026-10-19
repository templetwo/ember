"""Probe control-flow tests. No test imports MLX or performs a numerical step."""
import contextlib
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("studio_probe", Path(__file__).resolve().parents[1] / "scripts/check_studio_environment.py")
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)


class StudioProbeTests(unittest.TestCase):
    def test_relative_interpreter_rejected(self):
        with self.assertRaises(ValueError):
            probe.run_step("python3", "gpu", 1)

    def test_native_crash_is_failure(self):
        process = subprocess.CompletedProcess([], -6, "", "native crash")
        with patch.object(probe.subprocess, "run", return_value=process):
            result = probe.run_step(sys.executable, "gpu", 1)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["worker_returncode"], -6)

    def test_timeout_is_failure(self):
        with patch.object(probe.subprocess, "run", side_effect=subprocess.TimeoutExpired("worker", 1)):
            result = probe.run_step(sys.executable, "gpu", 1)
        self.assertEqual(result["reason"], "worker-timeout")

    def test_incomplete_green_trace_rejected(self):
        for checks in ({"fiction": True}, list(probe.STEP_CHECKS), None):
            with self.subTest(checks=checks):
                process = subprocess.CompletedProcess([], 0, json.dumps({"status": "passed", "checks": checks}), "")
                with patch.object(probe.subprocess, "run", return_value=process):
                    self.assertEqual(probe.run_step(sys.executable, "gpu", 1)["status"], "failed")

    def test_worker_uses_same_python_and_offline_flags(self):
        payload = {"status": "passed", "checks": {key: True for key in probe.STEP_CHECKS}}
        process = subprocess.CompletedProcess([], 0, json.dumps(payload), "")
        with patch.object(probe.subprocess, "run", return_value=process) as run:
            result = probe.run_step(sys.executable, "gpu", 45)
        self.assertEqual(result["status"], "passed")
        args, kwargs = run.call_args
        self.assertEqual(args[0][0], sys.executable)
        self.assertEqual(kwargs["env"]["HF_HUB_OFFLINE"], "1")
        self.assertEqual(kwargs["timeout"], 45)

    def invoke(self, base, *extra, versions=("0.32.2", "0.31.3"), step=None):
        base = base.resolve()
        output = base / "local/result.json"
        metadata = {name: {"version": version} for name, version in zip(("mlx", "mlx-lm"), versions)}
        with patch.object(probe, "ROOT", base), patch.object(probe, "package_metadata", return_value=metadata), \
                patch.object(probe, "run_step", return_value=step or {"status": "passed"}) as run, \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            code = probe.main(["--output", str(output), *extra])
        return code, json.loads(output.read_text()), run

    def test_metadata_only_never_runs_step(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, report, run = self.invoke(Path(tmp), "--metadata-only")
        run.assert_not_called()
        self.assertEqual(code, 0)
        self.assertEqual(report["status"], "metadata-only")
        self.assertEqual(report["dry_lora_step"]["status"], "not-run")

    def test_wrong_pair_does_not_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, report, _ = self.invoke(Path(tmp), versions=("0.26.5", "0.26.2"))
        self.assertEqual(code, 2)
        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["dry_lora_step"]["status"], "passed")

    def test_missing_package_does_not_run_step(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, report, run = self.invoke(Path(tmp), versions=(None, None))
        run.assert_not_called()
        self.assertEqual(code, 2)
        self.assertEqual(report["dry_lora_step"]["reason"], "missing-package")

    def test_failed_step_cannot_pass_expected_pair(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, report, _ = self.invoke(Path(tmp), step={"status": "failed"})
        self.assertEqual(code, 2)
        self.assertTrue(report["pair_matches"])
        self.assertEqual(report["status"], "failed")

    def test_no_receipt_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            _, first, _ = self.invoke(base, "--metadata-only")
            code, second, run = self.invoke(base)
        self.assertEqual(code, 2)
        self.assertEqual(first, second)
        run.assert_not_called()

    def test_receipt_cannot_go_in_public_docs(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(probe, "ROOT", Path(tmp)), contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                probe.main(["--output", str(Path(tmp) / "docs/receipt.json"), "--metadata-only"])


if __name__ == "__main__":
    unittest.main()
