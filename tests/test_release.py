"""Synthetic scanner checks only. No live sources or private needles are read."""
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from ember import cli, release
from ember.validation import ROOT, InvalidCorpus, digest, load_manifest


def candidate_fixture(base, text="Synthetic scanner fixture", needles=None):
    def put(name, value):
        data = json.dumps(value).encode("utf-8")
        (base / name).write_bytes(data)
        return {"path": name, "sha256": digest(data)}

    candidate = {
        "schema_version": "0.1", "purpose": "p0-candidate-scan", "scope": "private-training",
        "corpus": {"train": put("train.jsonl", {"text": text}),
                   "heldout": put("heldout.jsonl", {"text": "Synthetic heldout scanner fixture"})},
        "policy": put("policy.json", {"scope": "private-training", "fixture_only": True}),
        "needles": put("needles.json", [] if needles is None else needles),
        "exclusions_sha256": digest((ROOT / "docs/corpus-exclusions.md").read_bytes()),
        "reader": {"name": "test-fixture", "cadence": "during this unit test"},
    }
    path = base / "candidate.json"
    path.write_text(json.dumps(candidate))
    return path, candidate


class MatcherTests(unittest.TestCase):
    def test_shape_controls_use_real_matcher(self):
        self.assertEqual(release.controls(), 17)
        with patch.dict(release.PATTERNS, {"bridge-bearer": __import__("re").compile(r"(?!)")}):
            with self.assertRaises(InvalidCorpus):
                release.controls()

    def test_extra_rule_needs_control(self):
        with patch.dict(release.PATTERNS, {"new-shape": __import__("re").compile("fixture")}):
            with self.assertRaises(InvalidCorpus):
                release.controls()

    def test_controls_refuse_narrow_alphabet_and_overmatching(self):
        for expression in (r"svs_a{16,}", r".*"):
            with self.subTest(expression=expression), patch.dict(
                    release.PATTERNS, {"bridge-bearer": __import__("re").compile(expression)}):
                with self.assertRaises(InvalidCorpus):
                    release.controls()

    def test_nested_encoded_credential_found(self):
        secret = "svs_" + "x" * 24
        encoded = "".join("\\u%04x" % ord(char) for char in secret)
        for _ in range(3):
            encoded = json.dumps({"quoted": encoded})
        hits, complete = release.scan_text(encoded, [])
        self.assertTrue(complete)
        self.assertIn("bridge-bearer", hits)
        self.assertNotIn(secret, json.dumps(hits))

    def test_hex_and_octal_decoding(self):
        for prefix in (r"\x73\x76\x73_", r"\163\166\163_"):
            hits, complete = release.scan_text(prefix + "a" * 24, [])
            self.assertTrue(complete)
            self.assertIn("bridge-bearer", hits)

    def test_literal_whitespace_and_unicode(self):
        text = json.dumps({"text": "private  fixture\n\nmarker 🔥"})
        hits, complete = release.scan_text(text, ["private fixture marker 🔥"])
        self.assertTrue(complete)
        self.assertIn("literal-1", hits)

    def test_bound_is_incomplete(self):
        text = r"\u0073vs_" + "a" * 24
        for _ in range(10):
            text = json.dumps(text)
        _, complete = release.scan_text(text, [])
        self.assertFalse(complete)

    def test_id_cannot_suppress_secret(self):
        hits, complete = release.scan_text("token_id=none password=" + "a" * 20, [])
        self.assertTrue(complete)
        self.assertIn("secret-assignment", hits)

    def test_request_ids_still_flagged(self):
        for value in ("Grant " + "a" * 12, "arq_" + "x" * 24):
            self.assertIn("grant-id", release.scan_text(value, [])[0])


class CandidateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)

    def test_clear_is_not_a_release(self):
        path, candidate = candidate_fixture(self.base)
        report = release.scan_candidate(path)
        self.assertEqual(report["status"], "clear")
        self.assertEqual(report["release_review"], "pending")
        self.assertEqual(report["row_counts"], {"train": 1, "heldout": 1})
        self.assertEqual(report["corpus_sha256"], {k: v["sha256"] for k, v in candidate["corpus"].items()})
        self.assertEqual(report["candidate_sha256"], digest(path.read_bytes()))
        self.assertNotIn("Synthetic", json.dumps(report))
        self.assertNotIn(str(self.base), json.dumps(report))
        with self.assertRaises(InvalidCorpus):
            load_manifest(path)

    def test_blocked_report_has_no_values(self):
        secret = "svs_" + "a" * 24
        path, _ = candidate_fixture(self.base, text=secret + " private marker", needles=["private marker"])
        report = release.scan_candidate(path)
        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["findings"]["train"]["rules"], ["bridge-bearer", "literal-1"])
        rendered = json.dumps(report)
        self.assertNotIn(secret, rendered)
        self.assertNotIn("private marker", rendered)

    def test_changed_inputs_refused(self):
        for filename in ("train.jsonl", "heldout.jsonl", "policy.json", "needles.json"):
            with self.subTest(filename=filename):
                path, _ = candidate_fixture(self.base)
                (self.base / filename).write_text("changed")
                with self.assertRaises(InvalidCorpus):
                    release.scan_candidate(path)

    def test_public_policy_refused(self):
        path, candidate = candidate_fixture(self.base)
        raw = b'{"scope":"public-mirror"}'
        (self.base / "policy.json").write_bytes(raw)
        candidate["policy"]["sha256"] = digest(raw)
        path.write_text(json.dumps(candidate))
        with self.assertRaises(InvalidCorpus):
            release.scan_candidate(path)

    def test_empty_data_refused(self):
        path, candidate = candidate_fixture(self.base)
        (self.base / "train.jsonl").write_bytes(b"")
        candidate["corpus"]["train"]["sha256"] = digest(b"")
        path.write_text(json.dumps(candidate))
        with self.assertRaises(InvalidCorpus):
            release.scan_candidate(path)

    def test_empty_object_row_refused_in_either_split(self):
        for split in ("train", "heldout"):
            with self.subTest(split=split):
                path, candidate = candidate_fixture(self.base)
                raw = b'{"text":"valid fixture"}\n{}\n'
                (self.base / (split + ".jsonl")).write_bytes(raw)
                candidate["corpus"][split]["sha256"] = digest(raw)
                path.write_text(json.dumps(candidate))
                with self.assertRaisesRegex(InvalidCorpus, "nonempty JSON objects"):
                    release.scan_candidate(path)

    def test_blank_needle_refused(self):
        path, _ = candidate_fixture(self.base, needles=["  \n"])
        with self.assertRaises(InvalidCorpus):
            release.scan_candidate(path)

    def test_invalid_utf8_refused(self):
        path, candidate = candidate_fixture(self.base)
        raw = b'{"text":"\xff"}'
        (self.base / "train.jsonl").write_bytes(raw)
        candidate["corpus"]["train"]["sha256"] = digest(raw)
        path.write_text(json.dumps(candidate))
        with self.assertRaises(UnicodeDecodeError):
            release.scan_candidate(path)

    def test_duplicate_keys_refused(self):
        path, candidate = candidate_fixture(self.base)
        raw = b'{"text":"a","text":"b"}'
        (self.base / "train.jsonl").write_bytes(raw)
        candidate["corpus"]["train"]["sha256"] = digest(raw)
        path.write_text(json.dumps(candidate))
        with self.assertRaises(InvalidCorpus):
            release.scan_candidate(path)

    def test_size_limit_never_clips(self):
        path, _ = candidate_fixture(self.base)
        with patch.object(release, "MAX_FILE_BYTES", 10):
            with self.assertRaises(InvalidCorpus):
                release.scan_candidate(path)
        path, candidate = candidate_fixture(self.base, text="x" * 5000)
        with patch.object(release, "MAX_FILE_BYTES", 4096):
            with self.assertRaises(InvalidCorpus):
                release.scan_candidate(path)

    def test_escape_path_refused(self):
        path, candidate = candidate_fixture(self.base)
        for name in ("../outside", "/outside"):
            candidate["corpus"]["train"]["path"] = name
            path.write_text(json.dumps(candidate))
            with self.assertRaises(InvalidCorpus):
                release.scan_candidate(path)

    def test_token_filename_not_opened(self):
        path, candidate = candidate_fixture(self.base)
        candidate["corpus"]["train"]["path"] = "cbr_" + "a" * 24 + ".jsonl"
        path.write_text(json.dumps(candidate))
        # No such file exists: InvalidCorpus rather than FileNotFound proves pre-open refusal.
        with self.assertRaises(InvalidCorpus):
            release.scan_candidate(path)

    def test_cli_status_and_exclusive_output(self):
        for text, expected_status, expected_rc in (("clean fixture", "clear", 0),
                                                  ("svs_" + "a" * 24, "blocked", 2)):
            path, _ = candidate_fixture(self.base, text=text)
            (self.base / "local").mkdir(exist_ok=True)
            output = self.base / "local" / (expected_status + ".json")
            out, err = io.StringIO(), io.StringIO()
            with patch.object(cli, "ROOT", self.base), patch.object(cli, "runtime_provenance", return_value={}), \
                    contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                rc = cli.main(["scan", "--candidate", str(path), "--output", str(output)])
            self.assertEqual(rc, expected_rc, err.getvalue())
            self.assertEqual(err.getvalue(), "")
            summary = json.loads(out.getvalue())
            self.assertEqual(summary["status"], expected_status)
            original = output.read_bytes()
            self.assertEqual(summary["report_sha256"], digest(original))
            with patch.object(cli, "ROOT", self.base), patch.object(cli, "runtime_provenance", return_value={}), \
                    contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(cli.main(["scan", "--candidate", str(path), "--output", str(output)]), 2)
            self.assertEqual(output.read_bytes(), original)

    def test_cli_cannot_write_public_report(self):
        path, _ = candidate_fixture(self.base)
        for symlink in (False, True):
            if symlink:
                (self.base / "local").symlink_to(self.base, target_is_directory=True)
                output = self.base / "local" / "report.json"
            else:
                output = self.base / "report.json"
            with patch.object(cli, "ROOT", self.base), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(cli.main(["scan", "--candidate", str(path), "--output", str(output)]), 2)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
