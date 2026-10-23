# Ember development

This is a pre-P0 scaffold, not a trained model or an authorized Temple seat.

- Read `README.md`, `docs/p0-checklist.md`, and `docs/corpus-exclusions.md` before changing corpus or evaluation code.
- Keep the exclusion block verbatim across revisions. A changed upstream release policy requires a new corpus cut.
- Real source bodies, datasets, local audit receipts, grants, credentials, and model artifacts stay outside version control. Do not read the protected drawer to construct tests or filters.
- Keep decision labels in `src/ember/schemas/decision.schema.json`. Validate at ingestion. Never silently translate HOLD into PAUSE.
- Fit controls on training rows only. Preserve held-out denominators, hashes, constraints, predictions, and the named reader in reports.
- Corpus release approval is a separate, explicit reviewer attestation. Structural validation is not a privacy clearance or a semantic judgment.
- Do not claim a P0 exit without real held-out baseline numbers, independent reproduction, and a verified Jetson load cycle.
- Checkpoint choice, tokenizer audit, model inference, model smoke test, training, and seat deployment remain subject to the build spec's gates. The offline evaluator selftest spends none of those approvals.
- Run `.venv/bin/python -m unittest discover -s tests -v` and `.venv/bin/python scripts/check_public.py` for changes to the instruments.
- Public publishing is authorized for the initial scaffold in this session. Corpus publication and model publication are separate scopes.
- Anything committed here is published under the Apache License 2.0 and cannot be recalled. Documentation passes the publication check's allowlist, so a write-up that quotes the record needs its own release decision before it is committed.
