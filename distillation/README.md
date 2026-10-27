# Chronicle distillation drafts

This folder holds draft teaching material for Ember that is separate from the P0 corpus track. It was added on 2026-10-27 at Anthony Vasquez Sr.'s instruction to put it in this public repository.

## `ember_chronicle_distillation_pairs_v0_1.json`

| Field | Value |
| --- | --- |
| Schema | `temple-ember-lesson-distillation/0.1` |
| Written by | ChatGPT, through an OpenAI connector seat, 2026-10-27 (provenance, under Anthony's direction) |
| Status | `draft_for_review` |
| Pairs | 12 (11 OPEN, 1 PAUSE, 0 WITNESS) |
| Sources | 12 Sovereign Stack chronicle claims, named by claim id in `sources` |
| sha256 | `fdc31d2dafa26617b1404e6594e4f182a9baba8a84dc1c1f7505bf4b45be2b4e` |

Each pair is a constructed teaching scenario based on a recorded lesson, not a verbatim record or a reconstruction of what a seat saw at decision time. Names, paths, commands, and identifiers were left out of the model-facing text by its author. The file is committed byte for byte as it was handed over.

What it is not:

- Not the Ember training corpus. Its `source_kind` is `chronicle_lesson_distillation`, so the P0 data contract (`docs/data-contract.md`), which admits only `temple_record` pairs, rejects it by design. The file says so in `compatibility`.
- Not reviewed. Every pair carries `independent_review: pending`, `human_review: pending`, and `approved_for_ember_training: false`. Its own `validation` block reports structural checks only, with no semantic review, no receipt verification, no Ember validator run, and no tokenizer or model test.
- Not balanced. The batch deliberately leans toward justified proceeding and is not a gate-classification benchmark.
- Not a release of the chronicle. The `sources` entries cite claim ids and topics; reading a claim is not verification of the event it records.

Using it for training needs, first, a reviewed mapping into the current data contract and the approvals the build spec names. Committing it here spends none of those approvals.
