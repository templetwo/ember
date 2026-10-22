"""Synthetic protocol fixtures only. These are never Ember's training signal."""
import copy
import json
import contextlib
import importlib.util
import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from ember.baselines import fit_length, predict, run_baselines, score
from ember.cli import main
from ember.validation import (ROOT, InvalidCorpus, digest, json_loads, load_manifest,
                              read_bound_file, render_evidence, validate_decision,
                              validate_pair, validate_split)

CUT = "2026-10-01T00:00:00Z"


def pair(number, label, time="2026-09-01T00:00:00Z", text=None):
    claim = f"fixture-claim-{number}"
    return {
        "pair_id": f"fixture-pair-{number}", "source_kind": "temple_record",
        "source_claim_ids": [claim], "recorded_at": time, "shape": "catch", "holdout": "none",
        "situation": text or f"Synthetic protocol test situation {number}",
        "evidence": [{"claim_id": claim, "recorded_at": time, "text": "Synthetic protocol evidence, not a real Temple claim."}],
        "target": {"decision": label, "rationale": "Synthetic test target.", "cited_claim_ids": [claim], "factual": True},
        "review": {"reader": "test-fixture", "receipt": "fixture-only", "negations_checked": True, "unverified_claims_tagged": True},
    }


def splits():
    train = [pair(1, "OPEN", text="read"), pair(2, "PAUSE", text="delete pending artifact"), pair(3, "WITNESS", text="ask before change")]
    held = [pair(4, "OPEN", CUT, "inspect status"), pair(5, "PAUSE", CUT, "push without review")]
    return train, held


def fixture_manifest(base):
    train, held = splits()
    robot = pair(6, "WITNESS", text="Synthetic reserved robot event")
    robot["holdout"] = "robot_stop"
    held.append(robot)

    def put(name, data):
        raw = data if isinstance(data, bytes) else json.dumps(data).encode()
        (base / name).write_bytes(raw)
        return {"path": name, "sha256": digest(raw)}

    corpus = {"train": put("train.jsonl", "\n".join(json.dumps(p) for p in train).encode()),
              "heldout": put("heldout.jsonl", "\n".join(json.dumps(p) for p in held).encode())}
    policy = put("policy.json", {"fixture_only": True})
    exclusions_hash = digest((ROOT / "docs/corpus-exclusions.md").read_bytes())
    receipt = put("release.json", {"status": "passed", "reader": "fixture-reader", "corpus_sha256": {k: v["sha256"] for k, v in corpus.items()}, "policy_sha256": policy["sha256"], "exclusions_sha256": exclusions_hash})
    manifest = {"schema_version": "0.1", "purpose": "p0-baselines", "freeze_at": CUT,
                "robot_stop_claim_ids": ["fixture-claim-6"], "corpus": corpus,
                "release_review": {"status": "passed", "reader": "fixture-reader", "receipt": receipt,
                                   "policy": policy, "exclusions_sha256": exclusions_hash},
                "constraints": {"evidence_max_chars": 4000, "length_fit": "train-only", "statistic": "balanced_accuracy_open_vs_stop", "keyword_stop": ["rm", "push", "delete", "token", "child"]},
                "reader": {"name": "fixture-reader", "cadence": "during this unit test"}}
    path = base / "manifest.json"
    path.write_text(json.dumps(manifest))
    return path, manifest


class ValidationTests(unittest.TestCase):
    def test_valid_reviewed_pair(self):
        validate_pair(pair(1, "PAUSE"), 4000)

    def test_hold_label_bug_rejected(self):
        with self.assertRaises(InvalidCorpus):
            validate_pair(pair(1, "HOLD"), 4000)

    def test_invented_receipt_rejected(self):
        p = pair(1, "OPEN")
        p["target"]["cited_claim_ids"] = ["invented"]
        with self.assertRaises(InvalidCorpus):
            validate_pair(p, 4000)

    def test_factual_answer_requires_receipt(self):
        p = pair(1, "OPEN")
        p["target"]["cited_claim_ids"] = []
        with self.assertRaises(InvalidCorpus):
            validate_decision(p["target"], p["evidence"])

    def test_budget_counts_claim_headers_too(self):
        p = pair(1, "OPEN")
        cap = len(render_evidence(p["evidence"]))
        validate_pair(p, cap)
        with self.assertRaises(InvalidCorpus):
            validate_pair(p, cap - 1)

    def test_future_evidence_rejected(self):
        p = pair(1, "PAUSE")
        p["evidence"][0]["recorded_at"] = CUT
        with self.assertRaises(InvalidCorpus):
            validate_pair(p, 4000)

    def test_unreviewed_negation_rejected(self):
        p = pair(1, "PAUSE")
        p["review"]["negations_checked"] = False
        with self.assertRaises(InvalidCorpus):
            validate_pair(p, 4000)

    def test_synthetic_origin_cannot_enter_corpus(self):
        p = pair(1, "PAUSE")
        p["source_kind"] = "synthetic"
        with self.assertRaises(InvalidCorpus):
            validate_pair(p, 4000)

    def test_time_cut_is_strict(self):
        train, held = splits()
        validate_split(train, held, CUT, 4000)
        train[0]["recorded_at"] = CUT
        with self.assertRaises(InvalidCorpus):
            validate_split(train, held, CUT, 4000)

    def test_evidence_overlap_rejected(self):
        train, held = splits()
        held[0]["evidence"].append(copy.deepcopy(train[0]["evidence"][0]))
        with self.assertRaises(InvalidCorpus):
            validate_split(train, held, CUT, 4000)

    def test_normalized_duplicate_situation_rejected(self):
        train, held = splits()
        held[0]["situation"] = "  READ  "
        with self.assertRaises(InvalidCorpus):
            validate_split(train, held, CUT, 4000)

    def test_duplicate_pair_id_rejected(self):
        train, held = splits()
        held[0]["pair_id"] = train[0]["pair_id"]
        with self.assertRaises(InvalidCorpus):
            validate_split(train, held, CUT, 4000)

    def test_reserved_robot_event_cannot_be_training(self):
        train, held = splits()
        with self.assertRaises(InvalidCorpus):
            validate_split(train, held, CUT, 4000, ["fixture-claim-1"])

    def test_quarter_floor_applies_per_training_class(self):
        train, held = splits()
        train.extend([pair(7, "OPEN"), pair(8, "OPEN")])
        with self.assertRaises(InvalidCorpus):
            validate_split(train, held, CUT, 4000)

    def test_duplicate_json_keys_rejected(self):
        with self.assertRaises(InvalidCorpus):
            json_loads('{"decision":"OPEN","decision":"PAUSE"}')

    def test_nonfinite_json_rejected(self):
        with self.assertRaises(InvalidCorpus):
            json_loads('{"value":NaN}')


class BaselineTests(unittest.TestCase):
    def test_always_stop_imbalance(self):
        result = score(["OPEN", "PAUSE", "WITNESS", "PAUSE"], ["PAUSE"] * 4)
        self.assertEqual(result["balanced_accuracy"], 0.5)
        self.assertEqual(result["confusion"], {"stop_as_stop": 3, "stop_as_open": 0, "open_as_open": 0, "open_as_stop": 1})

    def test_same_statistic_for_all_controls(self):
        train, held = splits()
        results = run_baselines(train, held)
        self.assertEqual(set(results["baselines"]), {"always-stop", "keyword-stop", "length-stop"})
        self.assertEqual({x["scores"]["denominator"] for x in results["baselines"].values()}, {2})

    def test_unknown_label_not_silently_collapsed(self):
        with self.assertRaises(InvalidCorpus):
            score(["OPEN", "HOLD"], ["OPEN", "PAUSE"])

    def test_perfect_and_reversed_predictions_have_expected_scores(self):
        labels = ["OPEN", "OPEN", "OPEN", "PAUSE", "WITNESS"]
        self.assertEqual(score(labels, labels)["balanced_accuracy"], 1.0)
        self.assertEqual(score(labels, ["PAUSE", "PAUSE", "PAUSE", "OPEN", "OPEN"])["balanced_accuracy"], 0.0)

    def test_missing_prediction_cannot_cherry_pick_denominator(self):
        with self.assertRaises(InvalidCorpus):
            score(["OPEN", "PAUSE"], ["OPEN"])

    def test_one_class_statistic_is_undefined(self):
        with self.assertRaises(InvalidCorpus):
            score(["PAUSE", "WITNESS"], ["PAUSE", "PAUSE"])

    def test_length_fit_has_no_heldout_label_dependency(self):
        train, held = splits()
        first = run_baselines(train, held)
        held[0]["target"]["decision"], held[1]["target"]["decision"] = "PAUSE", "OPEN"
        second = run_baselines(train, held)
        self.assertEqual(first["length_rule"], second["length_rule"])
        self.assertEqual([p["predicted"] for p in first["baselines"]["length-stop"]["predictions"]],
                         [p["predicted"] for p in second["baselines"]["length-stop"]["predictions"]])

    def test_keyword_matching_is_case_insensitive_whole_word(self):
        rows = [pair(1, "OPEN", text="PUSH now"), pair(2, "OPEN", text="tokenize text")]
        self.assertEqual(predict(rows, {"threshold_chars": 10, "stop_when": "ge"})["keyword-stop"], ["PAUSE", "OPEN"])


class ManifestTests(unittest.TestCase):
    def test_valid_manifest_and_cli_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            path, manifest = fixture_manifest(base)
            m, rows, sha = load_manifest(path)
            self.assertEqual(len(rows["heldout"]), 3)
            output = base / "report.json"
            stdout, stderr = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                rc = main(["baselines", "--manifest", str(path), "--output", str(output)])
            self.assertEqual(rc, 0, stdout.getvalue() + stderr.getvalue())
            self.assertEqual(stderr.getvalue(), "")
            self.assertEqual(stdout.getvalue().count("\n"), 1)
            self.assertTrue(stdout.getvalue().endswith("\n"))
            recorded = json.loads(stdout.getvalue())
            self.assertEqual(recorded, {"status": "recorded", "report_sha256": digest(output.read_bytes()),
                                        "second_seat_verification": "pending"})
            report = json.loads(output.read_text())
            self.assertEqual(report["manifest_sha256"], sha)
            self.assertEqual(report["second_seat_verification"], "pending")
            self.assertEqual(report["constraints"], manifest["constraints"])
            self.assertEqual(len(report["result"]["baselines"]["always-stop"]["predictions"]), 3)
            self.assertNotIn("Synthetic protocol evidence", output.read_text())
            stdout, stderr = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                rc = main(["baselines", "--manifest", str(path), "--output", str(output)])
            self.assertEqual(rc, 2, stdout.getvalue() + stderr.getvalue())
            self.assertEqual(stdout.getvalue(), "")
            self.assertEqual(stderr.getvalue(), "ember: refused: FileExistsError\n")
            self.assertNotIn(tmp, stderr.getvalue())
            self.assertEqual(digest(output.read_bytes()), recorded["report_sha256"])

    def test_modified_quote_invalidates_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            path, _ = fixture_manifest(base)
            file = base / "train.jsonl"
            file.write_text(file.read_text().replace("not a real", "a real"))
            with self.assertRaises(InvalidCorpus):
                load_manifest(path)

    def test_rehashing_cherry_picked_rows_still_breaks_release_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            path, m = fixture_manifest(base)
            data = (base / "heldout.jsonl").read_text().splitlines()[0].encode()
            (base / "heldout.jsonl").write_bytes(data)
            m["corpus"]["heldout"]["sha256"] = digest(data)
            path.write_text(json.dumps(m))
            with self.assertRaises(InvalidCorpus):
                load_manifest(path)

    def test_fake_execution_trace_is_not_an_accepted_schema_field(self):
        p = pair(1, "OPEN")
        p["target"]["execution_trace"] = "success"
        with self.assertRaises(InvalidCorpus):
            validate_pair(p, 4000)

    def test_release_receipt_must_match_current_policy(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            path, m = fixture_manifest(base)
            data = b'{"fixture_only":false}'
            (base / "policy.json").write_bytes(data)
            m["release_review"]["policy"]["sha256"] = digest(data)
            path.write_text(json.dumps(m))
            with self.assertRaises(InvalidCorpus):
                load_manifest(path)

    def test_path_escape_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name in ("../outside", "/etc/passwd"):
                with self.assertRaises(InvalidCorpus):
                    read_bound_file(Path(tmp), {"path": name, "sha256": "0" * 64})

    def test_symlink_escape_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "escape").symlink_to("/etc/passwd")
            with self.assertRaises(InvalidCorpus):
                read_bound_file(base, {"path": "escape", "sha256": "0" * 64})

    def test_template_cannot_be_mistaken_for_reviewed_corpus(self):
        with self.assertRaises(InvalidCorpus):
            load_manifest(ROOT / "config/manifest.template.json")


class PublicCheckTests(unittest.TestCase):
    def test_public_paths_and_tokens(self):
        spec = importlib.util.spec_from_file_location("check_public", ROOT / "scripts/check_public.py")
        check = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(check)
        self.assertTrue(check.allowed("src/ember/schemas/pair.schema.json"))
        self.assertFalse(check.allowed("local/audit/private.json"))
        self.assertFalse(check.allowed("corpus/train.jsonl"))
        self.assertFalse(check.allowed("models/adapter.safetensors"))
        self.assertFalse(check.allowed("config/train.json"))
        self.assertTrue(check.PATTERNS["scoped credential"].search(b"svs_" + b"x" * 30))
        self.assertTrue(check.PATTERNS["bare 43-character stem"].search(b"x" * 43))
        self.assertFalse(check.PATTERNS["bare 43-character stem"].search(b"x" * 64))
        self.assertTrue(check.PATTERNS["Homebrew interpreter path"].search(b"/opt/home" + b"brew/bin/python3.14"))
        self.assertFalse(check.PATTERNS["Homebrew interpreter path"].search(b"Homebrew Python 3.14 user-site"))

    def test_scanner_reads_staged_bytes_even_if_worktree_is_cleaned(self):
        spec = importlib.util.spec_from_file_location("check_public", ROOT / "scripts/check_public.py")
        check = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(check)
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            subprocess.run(["git", "init", "-q", str(base)], check=True)
            path = base / "README.md"
            path.write_bytes(b"svs_" + b"x" * 30)
            subprocess.run(["git", "-C", str(base), "add", "README.md"], check=True)
            path.write_text("safe worktree text")
            check.ROOT = base
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(check.main(), 1)


class ProvenanceTests(unittest.TestCase):
    def test_git_calls_never_write_to_the_console(self):
        import ember.cli as cli
        calls = []

        def fake_check_output(argv, **kwargs):
            calls.append((argv, kwargs))
            return "abc123\n" if argv[-2:] == ["rev-parse", "HEAD"] else ""

        with patch.object(cli.subprocess, "check_output", side_effect=fake_check_output):
            provenance = cli.runtime_provenance()
        self.assertEqual(provenance["git_revision"], "abc123")
        self.assertFalse(provenance["working_tree_dirty"])
        git_calls = [kwargs for argv, kwargs in calls if argv[0] == "git"]
        self.assertEqual(len(git_calls), 2)
        for kwargs in git_calls:
            self.assertEqual(kwargs.get("stderr"), subprocess.DEVNULL)

    def test_provenance_falls_back_when_git_is_unavailable(self):
        import ember.cli as cli
        with patch.object(cli.subprocess, "check_output", side_effect=OSError("no git")):
            provenance = cli.runtime_provenance()
        self.assertEqual(provenance["git_revision"], "uncommitted")
        self.assertTrue(provenance["working_tree_dirty"])


if __name__ == "__main__":
    unittest.main()
