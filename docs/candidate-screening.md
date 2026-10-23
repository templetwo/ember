# Screening a private corpus candidate

`scan` screens proposed JSONL files before a release reviewer approves them. It
reads only files explicitly named in a candidate descriptor; it never retrieves
the chronicle, looks up protected bodies, or loads a model. A clear scan still
has `release_review: pending` and cannot serve as a baseline manifest or a release
receipt. It does not create or rewrite pairs.

Keep the descriptor, corpus, policy, optional literal needles, and reports under
ignored `local/` storage. The command enforces that its output resolves below the
repository's physical `local/` directory and refuses overwrites.

```sh
./scripts/ember scan --candidate local/corpus/candidate.json --output local/runs/candidate-scan.json
```

Create the output directory first. The command runs the offline selftest and
scanner controls, then reads a descriptor matching
`src/ember/schemas/candidate.schema.json`. Its shape is shown below; the values in
capitals are deliberately invalid placeholders, not a prepared corpus.

```json
{
  "schema_version": "0.1",
  "purpose": "p0-candidate-scan",
  "scope": "private-training",
  "corpus": {
    "train": {"path": "train.jsonl", "sha256": "SHA256_OF_EXACT_BYTES"},
    "heldout": {"path": "heldout.jsonl", "sha256": "SHA256_OF_EXACT_BYTES"}
  },
  "policy": {"path": "policy.json", "sha256": "SHA256_OF_EXACT_BYTES"},
  "needles": {"path": "needles.json", "sha256": "SHA256_OF_EXACT_BYTES"},
  "exclusions_sha256": "SHA256_OF_REPOSITORY_EXCLUSIONS_DOCUMENT",
  "reader": {"name": "NAMED_READER", "cadence": "before release review"}
}
```

All referenced paths must stay within the descriptor's directory after symlink
resolution. The policy must be a JSON object declaring `scope: private-training`.
Its remaining contents are bound by hash for the reviewer; the scanner does not
interpret them as authorization. A mirror policy is not an Ember corpus policy.
The original exclusion document remains unchanged; a private policy must carry
the applicable subsequent decisions explicitly, and changed policy bytes require
a new candidate and review. Public-repository publication rules still apply.

`needles.json` is an explicit list of literal strings, or `[]` when no literal
needles were supplied. It is required even when empty, so its absence cannot
silently disable a check. The report records its hash and needle count, not its
values. The operator supplies only needles appropriate to the candidate's scope.
There is no automatic reading of console credentials, protected indexes, or other
host files. Normalized whitespace is used for literal matching; matching remains
case-sensitive. Each supplied needle must pass the same matcher as the candidate.

The scanner uses the mirror's October 22 credential-shape vocabulary: bridge and
connector tokens, provider keys, authorization headers, private keys, JWTs,
secret assignments, bare 43-character stems, and grant/request IDs. It deliberately
does not inherit the mirror's release of grant IDs or its line-wide suppressions.
A finding blocks this preflight even if it could be a false positive; no values
are silently scrubbed and no command approves an exception.

Matching examines the stored text and up to eight decoded escape levels, including
JSON Unicode escapes, surrogate pairs, and Python-style hex/octal escapes. A
still-changing ninth level produces `incomplete`, never `clear`. This is not a
general decoder for every encoding. Each input file is limited to 16 MiB, and the
needle list to 1,024 entries; oversize inputs are refused rather than clipped.
Both proposed corpus files must contain nonempty JSON objects in JSONL form.
Invalid UTF-8, duplicate keys, missing files, hash mismatches, and path escapes
are refusals. Credential-shaped filenames are refused before opening them.

Reports contain exact input hashes, row counts, matcher controls, findings by
split and fixed rule name, code hashes, and the reader/cadence. They omit corpus
text, needle values, input filenames, and matching excerpts. Literal rules are
numbered by their position in the supplied list. These reports remain private.

Exit 0 means the bounded scan completed with no configured findings. Exit 2 means
findings, incomplete scanning, or invalid input. Findings and incomplete scans
produce an exclusive report; invalid input is refused without a report. The
console emits only status and report hash, or a value-free refusal.

Source eligibility, historical authorship, protected-record coupling, lineage
letters, evidence-window selection, semantic support, negation review, the time
cut, class balance, and the reserved robot-stop list remain separate checks. Use
the reviewed-pair validator and an independently authored release receipt before
running baselines. A source snapshot with no train/heldout split is not ready for
this command; choosing the split is not a side effect of scanning.
