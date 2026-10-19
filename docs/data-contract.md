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
| `holdout` | `none` or `robot_stop`; robot events must be on the manifest's reserved claim list |
| `situation` | Reviewed situation text, excluding the answer |
| `evidence` | Claim ID, timestamp, and reviewed query-window text per source |
| `target` | Decision, rationale, cited claim IDs, and whether the response is factual |
| `review` | Named reader, review receipt, negations checked, unverified claims tagged |

The parser rejects duplicate JSON keys and non-finite values. Evidence IDs must be unique within a row. Every target needs a cited receipt. Evidence timestamps cannot be later than the recorded decision. Evidence budgets count the complete rendered window, including IDs, timestamps, and separators. No automatic clipping or prefix selection occurs.

The target's citation IDs must name structured evidence items. This does not establish that the prose follows from the cited text, that the source was quoted faithfully before release, or that an event really happened. A human reviews those meanings.

## A manifest

`config/manifest.template.json` is deliberately invalid until its pending values are replaced. Copy it into an ignored directory such as `local/corpus/`, alongside the files it names. Relative file paths must remain within that directory, including after symlink resolution.

The manifest binds train and heldout JSONL byte hashes, the freeze timestamp, reserved robot-stop claim IDs, release-review receipt, release-policy file, exclusion document hash, constraints, and the run's reader/cadence.

Training decisions must predate the freeze. Temporal heldout decisions must be at or after it. Reserved robot-stop decisions are always held out, including events before the freeze. Every reserved claim must occur in the heldout evidence, and must be tagged `robot_stop`. No evidence claim or normalized identical situation may cross splits. Each training class must represent at least one quarter of the training rows. Both binary classes must occur in each split for balanced accuracy to be defined.

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

## Known detector limits

Hashes detect changes relative to a trusted manifest and release receipt; a person who rewrites all three can fabricate a new attestation. Exact situation matching does not find semantic paraphrases or all related-event leakage. The `source_kind` field does not authenticate authorship. Robot exclusions rely on a complete reserved claim list. Negation review flags record a person's review; they do not perform it. Balanced accuracy does not by itself establish an appropriate stop rate or zero declare-before-verify.

The four sealed harness probe classes from the spec remain pending. Unit checks for fake extra trace fields, changed quote bytes, cherry-picked denominators, and imbalanced-accuracy errors are limited software defenses, not those sealed probes or an independent second-seat review.
