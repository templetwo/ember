# Phase status

Initial state: **pre-P0; no real corpus cut or held-out baseline number**.

## Completed for the scaffold

- [x] Local MacBook audit with source hashes retained outside version control.
- [x] Separate evaluator environment, Python 3.10.12, locked dependencies, absolute interpreter launcher, offline selftest.
- [x] Shared decision schema and reviewed-pair contract.
- [x] Manifest-bound baseline evaluator with time-cut and reserved robot-stop checks.
- [x] Synthetic protocol tests; no synthetic training data.
- [x] Offline private-candidate screening with hash-bound inputs, credential and
  explicit literal checks, positive controls, and no automatic release approval.
  See [candidate screening](candidate-screening.md).

## Before a real P0 exit

- [ ] Read current mirror release pipeline and its 17-path withheld policy; integrate its needle and credential scans without opening protected bodies.
  Update 2026-10-22: the current scanner code and the October 19/21 policy metadata
  were read. Credential shapes and supplied literal matching are now implemented
  offline. Automatic drawer retrieval and claim-ID filtering are not imported;
  private-training scope must be reconciled with subsequent rulings before a cut.
- [x] Confirm the Ground ledger count and span from the authorized surface. Done by HQ on the Studio, 2026-10-19 (claim `af874e64`): 40 entries, 39 catches, events 2026-05-03 to 2026-10-04; one entry breaks the leading-tag rule.
- [ ] HQ: use the August 30 judged labels from the Studio filing identified by Fable; the MacBook log is a different surface and is not their source. Update 2026-10-21: HQ located them on 2026-10-19 (claim `af874e64`): the filing's 39 credential-paste incidents have 0 true positives and its 11 rm-rf-wildcard rows are 9 false positives and 2 correct; the per-row labels are in the Studio workflow journal and predate the refutation of an earlier "11 true positives" reading, which survives only in a superseded draft; `compass_log` keeps a rolling 30-day window and has no judge column, so the August 30 rows are absent from it on every machine. Using them in pairing is still open.
- [ ] Review claim/related-event groups and the reserved robot-stop claim list under the current source-exclusion policy. The 2026-10-24 ruling removes the temporal cut and general names-screen gate; standing specific exclusions remain.
- [ ] Produce record-derived pairs under the specified authoring/review terms; every negation gets its named review.
- [ ] Validate class balance and freeze the reviewed manifest/release receipt.
- [x] Establish the single Studio MLX environment by absolute path and test the intended version pair there. Done by HQ on 2026-10-19 (claim `af874e64`): the probe passed under HQ's chosen absolute Homebrew Python 3.14 interpreter with MLX 0.32.2 and mlx-lm 0.31.3 on the GPU, 8 of 8 step checks; login shells there still resolve `python3` elsewhere, so the absolute path is the environment.
- [ ] Run all three nuisance baselines on a real heldout set; retain every prediction, constraint, and denominator.
- [ ] Have a second seat reproduce those numbers from the frozen inputs on another substrate.
- [ ] Verify the Jetson's zero-OOM load/evict/reload cycle with its pinned existing base and eviction barrier, within applicable approvals.

The evaluator environment does not satisfy the Studio training-environment requirement. Existing Conditioned Kernel companion receipts do not satisfy Ember's baseline or OOM exit tests.

## Later gates remain open

No checkpoint is chosen. Checkpoint choice, tokenizer audit, inference, model smoke test, and training retain the spec's separate approval shape. Fable reports that the spec now assigns the tokenizer audit explicitly to P1. Writing the synthetic environment probe does not spend that approval.

The six reserved rulings remain open: delegation placement, substrate trust, write scope, letters in weights, handle treatment, and approval grouping. Ember has no chronicle write lane and no robot motion lane. P1 model scoring, sealed harness probes, entropy comparison, Studio/Jetson parity, commissioning, and P3 are unimplemented.

Every new artifact needs a named reader and cadence. The next local audit is read when work resumes or before the first corpus cut. Run reports carry their own named reader/cadence. No independent verification is claimed by this scaffold. Update 2026-10-21: independent verification of the scaffold's tests and selftest now exists (HQ, claim `af874e64`); no verification of any corpus or model result exists. When a Stack claim resolves an item on this list, the next MacBook seat folds it into these docs with the claim id and the date, and earlier wording stays as history. The repository is a public surface, so each such fold lands at Anthony's word.

The current MacBook lane prepares the [Studio environment probe](studio-environment-check.md) and reads existing CK receipts. HQ owns the corpus, Ground count, Studio filing, checkpoint and training work. A Claude seat will reproduce the original 34 protocol tests; that reproduction remains pending. Update 2026-10-21: done. HQ (Claude, Mac Studio) reproduced the 34 tests at `319450b` on 2026-10-19 with the project's unittest runner, with selftest and `check_public.py` passing (claim `af874e64`); that is the Tier 2 second-seat check for the scaffold. A MacBook re-run on 2026-10-21 at `7fb7bad` (45 tests) is the same machine and environment and does not count as a second seat.
