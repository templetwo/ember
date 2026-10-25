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
| `recorded_at_precision` | Required `clock`, `day`, or `bounded-by-records`; no inferred default |
| `shape` | `catch`, `judged_gate`, `close`, `supersession`, `ruling`, or `open_thread` |
| `pair_class` | `observed-decision` or `retrospective-rule`; mandatory, never inferred from the decision label |
| `holdout` | `none` or `robot_stop`; robot events must be on the manifest's reserved claim list |
| `situation` | Reviewed situation text, excluding the answer |
| `evidence` | Claim ID, `source_row_id`, resolved timestamp, and reviewed query-window text per source |
| `target` | Decision, rationale, cited claim IDs, and whether the response is factual |
| `review` | Named reader, review receipt, `label_source_claim_id`, `label_source_row_id`, `observed_act` (`proceed` or `stop`), negations checked, unverified claims tagged |

The parser rejects duplicate JSON keys and non-finite values. Evidence IDs must be unique within a row. Every target needs a cited receipt. Evidence timestamps cannot be later than the recorded decision. Evidence budgets count the complete rendered window, including IDs, timestamps, and separators. No automatic clipping or prefix selection occurs.

The target's citation IDs must name structured evidence items. This does not establish that the prose follows from the cited text, that the source was quoted faithfully before release, or that an event really happened. A human reviews those meanings.

For catch-derived pairs, evidence contains only claims available to the acting seat
at the decision time. `recorded_at` is that decision time, never the later catch's
filing timestamp. An unresolved decision time stays unresolved in the authoring
queue; the evaluator cannot infer it from a date-only account or authenticate a
supplied timestamp. The target cites the pre-decision evidence claims. The catch
that supports the label is identified separately by `review.label_source_claim_id`;
that ID is forbidden in the evidence and consequently cannot be a target citation.
This field is provenance for the review, not model input. Ingestion also rejects
its full ID in situation, every evidence text, target rationale and model-facing
claim-ID fields. For a hexadecimal label ID, any prefix of 12 or more characters
is rejected too. Comparisons remove whitespace and case-fold both IDs and searched
text, without rewriting reviewed bytes. Evidence membership, duplicate detection,
split grouping and robot reservations use the same normalized ID comparisons.
This is a bounded literal check: it cannot recognize paraphrased label provenance
or all encodings. A reviewer still checks that the evidence excludes the answer.
The ID's presence in the review does not prove the source was read or the label is correct.

The first-cut manifest requires `constraints.pair_classes: ["observed-decision"]`.
The loader passes that field to the split validator; both train and heldout reject
classes outside it. `retrospective-rule` remains representable for review but
excluded from this cut. The former `observed-stop` and `over-stop` class values are
rejected, not silently migrated.

`review.observed_act` states what the seat actually did, as established by the
record: `proceed` or `stop`. It is required and cannot be filled by guessing from
the target label. An admitted `observed-decision` row must agree with its target
on OPEN versus stop: `proceed` with OPEN, or `stop` with PAUSE/WITNESS. The validator
derives `over-stop` for a recorded stop labelled OPEN and `hindsight-stop` for a
recorded proceed labelled PAUSE/WITNESS. These are disagreement flags, not author
selectable classes; either disagreement refuses admission. This check establishes
internal consistency only. A reviewer must verify the observed act, class and label
against the source. An unknown observed act stays in the draft queue.

Authoring drafts remain in the private review queue. False review flags are honest
draft metadata and intentionally fail this reviewed-corpus schema. Only the named
reviewer supplies the completed attestations. There is no automatic migration of
old rows missing the new fields. These are pre-P0 amendments to the 0.1 contract;
old trial bytes remain review inputs, not an accepted corpus.

### Decision-time precision

For `clock`, evidence may be filed at or before the decision instant. For `day`,
the reviewer first resolves the Eastern **event date**, recorded as
`review.event_date`, with supporting `review.event_date_claim_ids`. The label
source's metadata must carry a matching `decision_day_review` with those fields,
a named reader and a receipt. A UTC filing date alone does not establish an event
date. `recorded_at` must equal that date's midnight in `America/New_York`, converted
to an explicit-offset instant (04:00 UTC in summer, 05:00 UTC in winter). Only
evidence strictly earlier than that floor is admitted. The evaluator checks the
review binding and floor; the reviewer establishes what date the record supports.

For `bounded-by-records`, `review.decision_time_bounds` requires `start_claim_id`,
`end_claim_id`, and `end_at`. The distinct bounding claims must differ from the
label source. Their resolved source timestamps must equal `recorded_at` and
`end_at`, respectively, and the end must follow the start. Evidence may run up to
the start. The claim timestamps alone do not prove they bracket the event; that
relationship is reviewed. Other precision classes cannot carry these bounds;
only day precision carries the event-date fields.

### Source metadata and review gates

The manifest's `source_index` binds a metadata-only JSON file by byte hash. Its
rows identify source rows and claims, canonical-record hashes, resolved
`source_utc`, timestamp basis, seed-backfill status, review holds, and name-screen
receipts. It contains no source bodies or person-name lists. Every evidence item
and label source must match a row and claim in this index. Evidence timestamps
must equal the resolved source instant. Bounds and event-date supporting claims
must resolve uniquely in the index; ambiguous variants stay held.

Private preparation recomputes timezone-less live-server clocks in
`America/New_York` only where the chronology evidence establishes that basis.
Unresolved vault-import clocks stay null and cannot be used. Nonexistent or
ambiguous local clocks are refused. No timezone is guessed from the machine's
current setting. Any source review hold blocks selection. Seed-backfill rows
cannot supply earlier evidence or decision bounds; they may supply later label
provenance subject to the other reviews.

Name status defaults to `pending`, never cleared by a detector's silence. A
selected source requires a named review receipt with `no-person-named`, or
`public-record-only` plus public-record references. `pending` and `held` refuse
selection. The explicit cluster awaiting Anthony's names review retains its hold
even if another screen field says clear. These fields record reviews; they do
not authenticate public status or grant permission to read protected material.
Private preparation binds supplied name and event-date reviews to the exact
canonical source-record hash. Missing event-date reviews remain unresolved.

## A manifest

`config/manifest.template.json` is deliberately invalid until its pending values are replaced. Copy it into an ignored directory such as `local/corpus/`, alongside the files it names. Relative file paths must remain within that directory, including after symlink resolution.

The manifest binds train and heldout JSONL byte hashes, the source metadata index, the freeze timestamp, reserved robot-stop claim IDs, release-review receipt, release-policy file, exclusion document hash, constraints, and the run's reader/cadence.

Training decisions must predate the freeze. Temporal heldout decisions must be at or after it. Reserved robot-stop decisions are always held out, including events before the freeze. Every reserved claim must occur in the heldout evidence or label-source provenance, and must be tagged `robot_stop`. No evidence or label-source claim, including an evidence-to-label match, or normalized identical situation may cross splits. Each training class must represent at least one quarter of the training rows. Both binary classes must occur in each split for balanced accuracy to be defined.

Related pairs sharing a label-source claim stay together even if their evidence
windows differ. Other related-event links still need explicit human grouping before
the split. A pre-decision evidence claim can predate the freeze while supporting a
heldout decision; the decision selects the temporal split, and claim grouping
prevents reusing that evidence in training. A later catch filing does not move an
earlier decision into heldout. Training/validation subdivision must enforce the
same evidence-plus-label grouping, and label-source IDs must stay out of exports.

Grouping also includes bounding claims and event-date supporting claims, across
all roles. Shared evidence cannot cross splits even when label sources differ.
A day-precision row is excluded from both splits if its Eastern calendar date is
within one day of the freeze's Eastern calendar date, including reserved robot
rows. A bounded window with start before the freeze and end at or after it is
also excluded. These guards apply before ordinary temporal and robot assignment.

`release_review.status` must be `passed`. The separate receipt file has these fields:

```json
{
  "status": "passed",
  "reader": "NAMED_REVIEWER",
  "corpus_sha256": {"train": "TRAIN_SHA256", "heldout": "HELDOUT_SHA256"},
  "source_index_sha256": "SOURCE_INDEX_SHA256",
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

`result.label_shape_class_counts` reports the joint label × shape × pair-class
counts separately for train and heldout. The nonzero cells sum to each split's
denominator. Inspect this table for source-shape confounding; it does not measure
or correct that confounding, and the counts are never predictor inputs.

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
