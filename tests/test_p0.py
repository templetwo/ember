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


def pair(number, label, time="2026-09-01T13:00:00Z", text=None):
    claim = f"fixture-claim-{number}"
    return {
        "pair_id": f"fixture-pair-{number}", "source_kind": "temple_record",
        "source_claim_ids": [claim], "recorded_at": time, "shape": "catch", "holdout": "none",
        "pair_class": "observed-decision",
        "recorded_at_precision": "clock",
        "situation": text or f"Synthetic protocol test situation {number}",
        "evidence": [{"claim_id": claim, "source_row_id": f"fixture-row-{number}", "recorded_at": time, "text": "Synthetic protocol evidence, not a real Temple claim."}],
        "target": {"decision": label, "rationale": "Synthetic test target.", "cited_claim_ids": [claim], "factual": True},
        "review": {"reader": "test-fixture", "receipt": "fixture-only", "label_source_claim_id": f"fixture-label-{number}",
                   "label_source_row_id": f"fixture-label-row-{number}", "decision_claim_id": claim,
                   "observed_act": "proceed" if label == "OPEN" else "stop",
                   "negations_checked": True, "unverified_claims_tagged": True},
    }


def splits():
    train = [pair(1, "OPEN", text="read"), pair(2, "PAUSE", text="delete pending artifact"), pair(3, "WITNESS", text="ask before change")]
    held = [pair(4, "OPEN", "2026-10-01T00:00:01Z", "inspect status"), pair(5, "PAUSE", "2026-10-01T00:00:01Z", "push without review")]
    return train, held


def fixture_source_index(rows):
    items = {}
    for p in rows:
        sources = [(e["source_row_id"], e["claim_id"], e["recorded_at"]) for e in p["evidence"]]
        sources.append((p["review"]["label_source_row_id"], p["review"]["label_source_claim_id"], p["recorded_at"]))
        for rid, cid, stamp in sources:
            items[rid] = {"source_row_id": rid, "claim_id": cid, "source_utc": stamp,
                          "record_sha256": "0" * 64, "timestamp_basis": "explicit-source-offset",
                          "seed_backfill": False, "review_holds": [],
                          "name_screen": {"status": "no-person-named", "reader": "test-fixture",
                                          "receipt": "fixture-only", "public_record_refs": []}}
    return {"schema_version": "0.1", "rows": list(items.values())}


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
    source_index = put("source-index.json", fixture_source_index(train + held))
    receipt = put("release.json", {"status": "passed", "reader": "fixture-reader", "source_index_sha256": source_index["sha256"], "corpus_sha256": {k: v["sha256"] for k, v in corpus.items()}, "policy_sha256": policy["sha256"], "exclusions_sha256": exclusions_hash})
    manifest = {"schema_version": "0.1", "purpose": "p0-baselines", "freeze_at": CUT,
                "source_index": source_index,
                "robot_stop_claim_ids": ["fixture-claim-6"], "corpus": corpus,
                "release_review": {"status": "passed", "reader": "fixture-reader", "receipt": receipt,
                                   "policy": policy, "exclusions_sha256": exclusions_hash},
                "constraints": {"pair_classes": ["observed-decision"], "evidence_max_chars": 4000, "length_fit": "train-only", "statistic": "balanced_accuracy_open_vs_stop", "keyword_stop": ["rm", "push", "delete", "token", "child"]},
                "reader": {"name": "fixture-reader", "cadence": "during this unit test"}}
    path = base / "manifest.json"
    path.write_text(json.dumps(manifest))
    return path, manifest


class ValidationTests(unittest.TestCase):
    def test_first_cut_manifest_class_constraint_cannot_be_omitted_or_widened(self):
        with tempfile.TemporaryDirectory() as temporary:
            path, manifest = fixture_manifest(Path(temporary))
            for kinds in (None, [], ["observed-decision", "over-stop"]):
                changed = copy.deepcopy(manifest)
                if kinds is None:
                    del changed["constraints"]["pair_classes"]
                else:
                    changed["constraints"]["pair_classes"] = kinds
                path.write_text(json.dumps(changed))
                with self.subTest(kinds=kinds), self.assertRaises(InvalidCorpus):
                    load_manifest(path)

    def test_label_source_stays_outside_evidence_and_target(self):
        p = pair(1, "PAUSE")
        validate_pair(p, 4000)
        p["review"]["label_source_claim_id"] = p["evidence"][0]["claim_id"]
        with self.assertRaisesRegex(InvalidCorpus, "label source"):
            validate_pair(p, 4000)
        p = pair(1, "PAUSE")
        p["target"]["cited_claim_ids"] = [p["review"]["label_source_claim_id"]]
        with self.assertRaises(InvalidCorpus):
            validate_pair(p, 4000)

    def test_pair_class_and_label_source_are_required_without_defaults(self):
        for field in ("pair_class", "label_source_claim_id"):
            p = pair(1, "OPEN")
            del (p if field == "pair_class" else p["review"])[field]
            with self.assertRaises(InvalidCorpus):
                validate_pair(p, 4000)

    def test_other_classes_can_be_described_but_never_enter_first_cut(self):
        for kind in ("retrospective-rule",):
            p = pair(1, "PAUSE"); p["pair_class"] = kind
            validate_pair(p, 4000)
            for split in (0, 1):
                train, held = splits()
                (train, held)[split][0]["pair_class"] = kind
                with self.subTest(kind=kind, split=split), self.assertRaisesRegex(InvalidCorpus, "first cut"):
                    validate_split(train, held, CUT, 4000)

    def test_label_source_cannot_cross_splits_even_with_different_evidence(self):
        train, held = splits()
        held[0]["review"]["label_source_claim_id"] = train[0]["review"]["label_source_claim_id"]
        with self.assertRaisesRegex(InvalidCorpus, "overlap"):
            validate_split(train, held, CUT, 4000)

    def test_label_source_overlapping_other_split_evidence_is_also_refused(self):
        train, held = splits()
        held[0]["review"]["label_source_claim_id"] = train[0]["evidence"][0]["claim_id"]
        with self.assertRaisesRegex(InvalidCorpus, "overlap"):
            validate_split(train, held, CUT, 4000)

    def test_reserved_label_source_is_held_out(self):
        train, held = splits()
        held[0]["holdout"] = "robot_stop"
        reserved = [held[0]["review"]["label_source_claim_id"]]
        validate_split(train, held, CUT, 4000, reserved)
        held[0]["holdout"] = "none"
        with self.assertRaises(InvalidCorpus):
            validate_split(train, held, CUT, 4000, reserved)

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
        train[0]["recorded_at"] = "2026-10-01T13:00:00Z"
        with self.assertRaisesRegex(InvalidCorpus, "held-out event"):
            validate_split(train, held, "2026-10-01T13:00:00Z", 4000)

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
    """Provenance must stay quiet on the console and honest in the report.

    The doubles below patch ``subprocess.run`` on the shared module, so they pass every
    non-git command through to the real function: ``platform`` probes its own uname via
    ``subprocess`` and caches the answer process-wide, and a blanket fake was found to
    leave ``platform.processor()`` empty for the rest of the interpreter.
    """

    @staticmethod
    def _completed(argv, stdout="", stderr="", returncode=0):
        return subprocess.CompletedProcess(argv, returncode, stdout=stdout, stderr=stderr)

    def _git_double(self, status_stdout="", status_stderr="", status_rc=0, head_stdout="abc123\n", head_rc=0, calls=None):
        real_run = subprocess.run

        def fake_run(argv, **kwargs):
            if argv[0] != "git":
                return real_run(argv, **kwargs)
            if calls is not None:
                calls.append((argv, kwargs))
            if argv[-2:] == ["rev-parse", "HEAD"]:
                return self._completed(argv, stdout=head_stdout, returncode=head_rc)
            return self._completed(argv, stdout=status_stdout, stderr=status_stderr, returncode=status_rc)

        return fake_run

    def _provenance(self, **double_kwargs):
        """Run runtime_provenance() against the git double and assert the console stayed quiet."""
        import ember.cli as cli
        out, err = io.StringIO(), io.StringIO()
        with patch.object(cli.subprocess, "run", side_effect=self._git_double(**double_kwargs)), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            provenance = cli.runtime_provenance()
        self.assertEqual((out.getvalue(), err.getvalue()), ("", ""))
        return provenance

    def test_git_calls_capture_stderr_and_never_write_to_the_console(self):
        calls = []
        provenance = self._provenance(calls=calls)
        self.assertEqual(provenance["git_revision"], "abc123")
        self.assertFalse(provenance["working_tree_dirty"])
        self.assertEqual(provenance["git_warnings"], [])
        git_calls = [kwargs for argv, kwargs in calls if argv[0] == "git"]
        self.assertEqual(len(git_calls), 2)
        for kwargs in git_calls:
            self.assertTrue(kwargs.get("capture_output"), "stderr must be captured, not discarded")
            self.assertNotEqual(kwargs.get("stderr"), subprocess.DEVNULL)

    def test_git_warnings_mark_the_tree_dirty_without_console_output(self):
        warning = "warning: could not open directory 'locked/': Permission denied"
        provenance = self._provenance(status_stderr=warning + "\n")
        self.assertEqual(provenance["git_revision"], "abc123")
        self.assertTrue(provenance["working_tree_dirty"], "an incomplete inspection must not read as clean")
        self.assertEqual(provenance["git_warnings"], [warning])

    def test_modified_tree_reads_dirty_without_warnings(self):
        provenance = self._provenance(status_stdout="?? scratch.txt\n")
        self.assertTrue(provenance["working_tree_dirty"])
        self.assertEqual(provenance["git_warnings"], [])
        self.assertEqual(provenance["git_revision"], "abc123")

    def test_status_exit_code_is_recorded_and_marks_the_tree_dirty(self):
        provenance = self._provenance(status_rc=128)
        self.assertEqual(provenance["git_warnings"], ["git status exited 128"])
        self.assertTrue(provenance["working_tree_dirty"])
        self.assertEqual(provenance["git_revision"], "abc123")

    def test_rev_parse_failure_yields_uncommitted(self):
        provenance = self._provenance(head_stdout="HEAD\n", head_rc=128)
        self.assertEqual(provenance["git_revision"], "uncommitted")
        self.assertTrue(provenance["working_tree_dirty"])
        self.assertEqual(provenance["git_warnings"], ["git rev-parse exited 128"])

    def test_exit_warnings_never_name_the_repository_root(self):
        import ember.cli as cli
        provenance = self._provenance(status_rc=1, head_rc=1)
        self.assertEqual(len(provenance["git_warnings"]), 2)
        for warning in provenance["git_warnings"]:
            self.assertNotIn(str(cli.ROOT), warning)

    def test_provenance_falls_back_when_git_is_unavailable(self):
        import ember.cli as cli
        real_run = subprocess.run

        def no_git(argv, **kwargs):
            if argv[0] == "git":
                raise OSError("no git")
            return real_run(argv, **kwargs)

        with patch.object(cli.subprocess, "run", side_effect=no_git):
            provenance = cli.runtime_provenance()
        self.assertEqual(provenance["git_revision"], "uncommitted")
        self.assertTrue(provenance["working_tree_dirty"])
        self.assertEqual(provenance["git_warnings"], ["git unavailable: no git"])

    def test_git_warnings_redact_this_machines_paths(self):
        import ember.cli as cli
        root, home = str(cli.ROOT), str(Path.home())
        stderr = (f"warning: could not open directory '{root}/locked/': Permission denied\n"
                  f"warning: unable to access '{home}/.gitconfig': Permission denied\n")
        provenance = self._provenance(status_stderr=stderr)
        self.assertTrue(provenance["working_tree_dirty"])
        self.assertEqual(provenance["git_warnings"], [
            "warning: could not open directory '<repo>/locked/': Permission denied",
            "warning: unable to access '~/.gitconfig': Permission denied"])
        rendered = json.dumps(provenance, ensure_ascii=False)
        self.assertNotIn(root, rendered)
        self.assertNotIn(home, rendered)

    def test_redaction_survives_a_root_or_missing_home_directory(self):
        import ember.cli as cli
        with patch.object(cli.Path, "home", return_value=Path("/")):
            self.assertEqual(cli._redact("warning: a/b"), "warning: a/b")
        with patch.object(cli.Path, "home", side_effect=RuntimeError("no home")):
            self.assertEqual(cli._redact("warning: a/b"), "warning: a/b")

    def test_selftest_executable_is_redacted(self):
        import ember.cli as cli
        executable = cli.selftest()["executable"]
        self.assertIn("python", executable)
        self.assertNotIn(str(Path.home()), executable)
        self.assertNotIn(str(cli.ROOT), executable)

    def test_git_decodes_invalid_bytes(self):
        import ember.cli as cli
        real_run = subprocess.run

        def emit_bytes(argv, **kwargs):
            if argv[0] != "git":
                return real_run(argv, **kwargs)
            if argv[-2:] == ["rev-parse", "HEAD"]:
                script = "import sys; sys.stdout.buffer.write(b'abc123\\n')"
            else:
                script = ("import sys; sys.stdout.buffer.write(b'?? bad-\\xff\\n'); "
                          "sys.stderr.buffer.write(b'warning: bad-\\xfe\\n')")
            return real_run([sys.executable, "-c", script], **kwargs)

        out, err = io.StringIO(), io.StringIO()
        with patch.object(cli.subprocess, "run", side_effect=emit_bytes), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            provenance = cli.runtime_provenance()
        self.assertEqual((out.getvalue(), err.getvalue()), ("", ""))
        self.assertEqual(provenance["git_revision"], "abc123")
        self.assertTrue(provenance["working_tree_dirty"])
        self.assertEqual(provenance["git_warnings"], [r"warning: bad-\xfe"])
        json.dumps(provenance, ensure_ascii=False).encode("utf-8")

    def test_warning_duplicates_collapse(self):
        warnings = "warning: first\n\nwarning: second\nwarning: first\n" * 100
        provenance = self._provenance(status_stderr=warnings)
        self.assertEqual(provenance["git_warnings"], ["warning: first", "warning: second"])
        self.assertTrue(provenance["working_tree_dirty"])

    def test_warning_count_has_visible_limit(self):
        warnings = "\n".join(f"warning: item {i}" for i in range(30))
        provenance = self._provenance(status_stderr=warnings)
        self.assertEqual(provenance["git_warnings"],
                         [f"warning: item {i}" for i in range(20)] +
                         ["additional git warnings omitted"])
        self.assertTrue(provenance["working_tree_dirty"])

    def test_warning_length_has_visible_limit(self):
        import ember.cli as cli
        warning = f"warning: {cli.ROOT}/" + "x" * 1000
        provenance = self._provenance(status_stderr=warning)
        rendered = provenance["git_warnings"][0]
        self.assertEqual(len(rendered), 512)
        self.assertTrue(rendered.startswith("warning: <repo>/"))
        self.assertTrue(rendered.endswith(" [truncated]"))
        self.assertNotIn(str(cli.ROOT), rendered)
        self.assertTrue(provenance["working_tree_dirty"])

    def test_known_path_prefixes_are_redacted(self):
        import ember.cli as cli
        brew = "/opt/homebrew"
        paths = ["/var/folders/fixture/T/cache", "/private/var/folders/fixture/T/cache",
                 "/tmp/cache", "/private/tmp/cache", brew + "/bin/git",
                 "/Volumes/Fixture Disk/repo/locked"]
        warnings = "\n".join(f"warning: unable to read '{path}'" for path in paths)
        with patch.dict(cli.os.environ, {"TMPDIR": "/var/folders/fixture/T/"}):
            provenance = self._provenance(status_stderr=warnings)
        self.assertEqual(provenance["git_warnings"], [
            "warning: unable to read '<tmp>/cache'",
            "warning: unable to read '<homebrew>/bin/git'",
            "warning: unable to read '<volume>/repo/locked'"])
        for path in paths:
            self.assertNotIn(path, json.dumps(provenance))

    def test_temp_root_does_not_rewrite_slashes(self):
        import ember.cli as cli
        for temp in ("/", "", "relative/path"):
            with self.subTest(temp=temp), patch.dict(cli.os.environ, {"TMPDIR": temp}):
                self.assertEqual(cli._redact("warning: /elsewhere/file"), "warning: /elsewhere/file")

    def test_prefix_siblings_are_not_rewritten(self):
        import ember.cli as cli
        with patch.dict(cli.os.environ, {"TMPDIR": "/fixture/temp/"}):
            self.assertEqual(cli._redact("/fixture/temporary/file"), "/fixture/temporary/file")

    def test_external_interpreter_is_redacted(self):
        import ember.cli as cli
        with patch.object(cli.sys, "executable", "/opt/homebrew" + "/bin/python3.10"):
            self.assertEqual(cli.selftest()["executable"], "<homebrew>/bin/python3.10")

    def test_provenance_test_doubles_pass_non_git_commands_through(self):
        import ember.cli as cli
        with patch.object(cli.subprocess, "run", side_effect=self._git_double()):
            probe = cli.subprocess.run(["uname", "-m"], capture_output=True, text=True)
        self.assertEqual(probe.returncode, 0)
        self.assertNotEqual(probe.stdout.strip(), "")


if __name__ == "__main__":
    unittest.main()
