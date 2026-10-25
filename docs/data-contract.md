# P0 data contract

The JSON schemas live under `src/ember/schemas/`. The evaluator accepts reviewed, already sanitized query windows. It cannot retrieve or export a corpus.

## A pair

Each JSONL row carries:

| Field | Meaning |
| --- | --- |
| `pair_id` | Unique pair identifier across both splits |
| `source_kind` | Must be `temple_record`; synthetic-origin examples are rejected |
| `source_claim_ids` | Nonempty source receipts, all present in evidence |
| `recorded_at` | Timestamp of the recorded decision, with timezone |
| `shape` | `catch`, `judged_gate`, `close`, `supersession`, `ruling`, or `open_thread` |
| `pair_class` | `observed-stop`, `retrospective-rule`, or `over-stop`; mandatory, never inferred from the decision label |
| `holdout` | `none` or `robot_stop`; robot events must be on the manifest's reserved claim list |
| `situation` | Reviewed situation text, excluding the answer |
| `evidence` | Claim ID, timestamp, and reviewed query-window text per source |
| `target` | Decision, rationale, cited claim IDs, and whether the response is factual |
| `review` | Named reader, review receipt, `label_source_claim_id`, negations checked, unverified claims tagged |

The parser rejects duplicate JSON keys and non-finite values. Evidence IDs must be unique within a row. Every target needs a cited receipt. Evidence timestamps cannot be later than the recorded decision. Evidence budgets count the complete rendered window, including IDs, timestamps, and separators. No automatic clipping or prefix selection occurs.

The target's citation IDs must name structured evidence items. This does not establish that the prose follows from the cited text, that the source was quoted faithfully before release, or that an event really happened. A human reviews those meanings.

For catch-derived pairs, evidence contains only claims available to the acting seat
at the decision time. `recorded_at` is that decision time, never the later catch's
filing timestamp. An unresolved decision time stays unresolved in the authoring
queue; the evaluator cannot infer it from a date-only account or authenticate a
supplied timestamp. The target cites the pre-decision evidence claims. The catch
that supports the label is identified separately by `review.label_source_claim_id`;
that ID is forbidden in the evidence and consequently cannot be a target citation.
This field is provenance for the review, not model input. Its presence does not
prove that the reviewer read the source or that the label is correct.

The first-cut manifest requires `constraints.pair_classes: ["observed-stop"]`.
Both splits reject `retrospective-rule` (a stop prescribed after the fact) and
`over-stop` (the recorded error was excessive stopping), even when their rows pass
the pair schema. Neither class may be silently translated into an observed stop
or an OPEN label. `pair_class` describes the event; `target.decision` remains the
separate OPEN/PAUSE/WITNESS judgment. Choosing the class and decision requires
source review; schemas do not perform that judgment.

Authoring drafts remain in the private review queue. False review flags are honest
draft metadata and intentionally fail this reviewed-corpus schema. Only the named
reviewer supplies the completed attestations. There is no automatic migration of
old rows missing the new fields. These are pre-P0 amendments to the 0.1 contract;
old trial bytes remain review inputs, not an accepted corpus.

## A manifest

`config/manifest.template.json` is deliberately invalid until its pending values are replaced. Copy it into an ignored directory such as `local/corpus/`, alongside the files it names. Relative file paths must remain within that directory, including after symlink resolution.

The manifest binds train and heldout JSONL byte hashes, the freeze timestamp, reserved robot-stop claim IDs, release-review receipt, release-policy file, exclusion document hash, constraints, and the run's reader/cadence.

Training decisions must predate the freeze. Temporal heldout decisions must be at or after it. Reserved robot-stop decisions are always held out, including events before the freeze. Every reserved claim must occur in the heldout evidence or label-source provenance, and must be tagged `robot_stop`. No evidence or label-source claim, including an evidence-to-label match, or normalized identical situation may cross splits. Each training class must represent at least one quarter of the training rows. Both binary classes must occur in each split for balanced accuracy to be defined.

Related pairs sharing a label-source claim stay together even if their evidence
windows differ. Other related-event links still need explicit human grouping before
the split. A pre-decision evidence claim can predate the freeze while supporting a
heldout decision; the decision selects the temporal split, and claim grouping
prevents reusing that evidence in training. A later catch filing does not move an
earlier decision into heldout. Training/validation subdivision must enforce the
same evidence-plus-label grouping, and label-source IDs must stay out of exports.

`release_review.status` must be `passed`. The separate receipt file has these fields:

```json
{
  "status": "passed",
  "reader": "NAMED_REVIEWER",
  "corpus_sha256": {"train": "TRAIN_SHA256", "heldout": "HELDOUT_SHA256"},
  "policy_sha256": "RELEASE_POLICY_SHA256",
  "exclusions_sha256": "EXCLUSIONS_DOCUMENT_SHA256"
}
```

The policy file must be the reviewed release policy used for that cut, including the mirror's current withheld-path rules and the added time cut. Its format is not yet interpreted by the evaluator. It is hashed and bound through the review receipt. There is no receipt-creation command: software cannot grant itself a review. These receipts are attestations, not digital signatures or independently verified source truth.

## Baseline reports

All three controls receive the same ordered heldout rows and use:

`balanced accuracy = (stop recall + OPEN recall) / 2`

Always-stop predicts PAUSE. Keyword-stop predicts PAUSE on whole-word matches from the five fixed keywords, otherwise OPEN. Length-stop fits its threshold and direction on training situation lengths only; equal training scores choose the smallest threshold, then the `>=` direction. Target text and evidence length are not inputs to any predictor.

Reports include complete per-pair predictions, expected labels, confusion counts, denominators, stop rates, the fitted rule, file hashes, actual code hashes, dependency versions, constraints, and the manifest's reader. They intentionally omit raw situations and evidence. A baseline report contains no declare-before-verify score, entropy measure, model receipt rate, model OOM result, or deployment decision.

### Runtime provenance

`provenance.git_revision` records Git's HEAD, or `uncommitted` if it cannot be read.
`working_tree_dirty` means **modified, untracked, or not fully inspected**. Any
nonblank Git diagnostic, nonzero exit, or failure to run Git marks it true, even
when `git status` returns no filenames. False means the two Git commands completed
without warnings and status reported no changes; ignored files are outside this
check. The code hashes bind the actual instrument bytes separately from Git state.

`git_warnings` carries captured diagnostics and exit failures without printing them
to the console. Git output is decoded as UTF-8; invalid bytes are preserved as
backslash escapes. Warnings are redacted, limited to 512 characters each (including
` [truncated]` when shortened), then deduplicated in first-seen order. At most 20
distinct rendered warnings are kept, followed by `additional git warnings omitted`
if more exist. These are report-size limits, not subprocess memory limits. Shortening
or deduplicating warnings never turns an incomplete inspection into a clean result.

Warnings and `selftest.executable` replace the repository root with `<repo>`, the
home directory with `~`, the current `TMPDIR` and standard temporary roots with
`<tmp>`, the Apple Silicon Homebrew prefix with `<homebrew>`, and mounted volume
names beneath `/Volumes` with `<volume>`. The temporary directory's `/var` and
`/private/var` spellings are both recognized. Longer prefixes take priority. These
replacements cover literal known paths; arbitrary paths, escaped path spellings,
filenames, and other private diagnostic text are not a general privacy clearance.
Reports still belong in ignored local storage and need review before sharing.

## Known detector limits

Hashes detect changes relative to a trusted manifest and release receipt; a person who rewrites all three can fabricate a new attestation. Exact situation matching does not find semantic paraphrases or all related-event leakage. The `source_kind` field does not authenticate authorship. Robot exclusions rely on a complete reserved claim list. Negation review flags record a person's review; they do not perform it. Balanced accuracy does not by itself establish an appropriate stop rate or zero declare-before-verify.

The four sealed harness probe classes from the spec remain pending. Unit checks for fake extra trace fields, changed quote bytes, cherry-picked denominators, and imbalanced-accuracy errors are limited software defenses, not those sealed probes or an independent second-seat review.
