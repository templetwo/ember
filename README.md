# Ember

Ember is a planned small, local model trained from the Temple's reviewed record. Its first test is whether it stops where the record says to stop and cites the evidence it used.

This repository contains the **pre-P0 scaffold**: an offline evaluator, shared schemas, corpus checks, nuisance baselines, and a local audit. There is no Ember checkpoint, training run, deployable seat, or measured Ember result yet.

## Run the offline instruments

The evaluator uses Python **3.10.12** and `uv.lock`. This is an evaluator environment, not the Studio MLX training environment.

```sh
uv sync --locked --python 3.10.12
./scripts/ember selftest
.venv/bin/python -m unittest discover -s tests -v
```

Every `scripts/ember` command runs the offline selftest first. `scripts/ember` selects the repository's absolute `.venv/bin/python` path. It never loads MLX, a model, a grant, or a chronicle client.

After a real corpus has been filtered, reviewed, and frozen:

```sh
./scripts/ember validate --manifest local/corpus/manifest.json
./scripts/ember baselines --manifest local/corpus/manifest.json --output local/runs/p0-001.json
```

Create the output directory first. Outputs use exclusive creation so an existing run cannot be overwritten. The manifest's reader and cadence carry into the report. A second seat must reproduce the scores before results can land as Tier 2.

## What is implemented

- One decision schema: `OPEN`, `PAUSE`, `WITNESS`; `HOLD` is rejected.
- Reviewed pairs with source claim IDs, evidence windows, target receipts, and a named negation reviewer.
- A strict time cut, source/evidence separation between splits, a reserved robot-stop claim list, duplicate detection, and the one-quarter training-class floor.
- Explicit evidence budgets. Oversize windows are rejected rather than clipped.
- Always-stop, keyword-stop, and a length threshold fitted only on training rows. All use the same held-out balanced accuracy over `OPEN` versus `PAUSE` + `WITNESS`.
- Reports binding corpus, manifest, release policy, release receipt, exclusions, code, dependency versions, constraints, and per-pair predictions to their hashes.

The keyword predictor uses case-insensitive whole words: `rm`, `push`, `delete`, `token`, `child`. Length means Unicode code points in the situation alone. Its threshold and direction maximize training balanced accuracy; ties choose the lowest threshold and then `>=`. See [the data contract](docs/data-contract.md).

## What remains before P0 can finish

The first real corpus cut and the mirror's release filter have not been imported. The evaluator requires a reviewer receipt bound to the exact corpus and policy bytes; this attestation does not itself prove that private material was excluded. Query-window selection and release scanning belong upstream and remain to be connected.

The Ground count, historical judged labels, Studio environment, Jetson load cycle, and independent reproduction remain open. No checkpoint is selected. No training, tokenizer audit, model inference, model smoke test, or deployment approval is inferred from this scaffold.

Read the [local audit](docs/local-audit-2026-10-19.md), [phase checklist](docs/p0-checklist.md), and [verbatim exclusion rules](docs/corpus-exclusions.md). Real corpus data, audit receipts, credentials, model files, and runs belong in ignored local directories.

To refresh the local metadata inventory without loading a model or reading record bodies:

```sh
.venv/bin/python scripts/audit_local.py --output local/audit/pickup.json --reader 'NAMED_READER' --cadence 'before corpus freeze'
```

This collector uses the local repository layout found during the initial audit; absent paths are reported rather than searched across personal archives. It writes only under the ignored `local/` directory. `scripts/check_public.py` inspects staged file bytes for unexpected paths, artifacts, and several credential shapes. It is a scaffold publication check, not the corpus release filter.

The unit tests use synthetic protocol fixtures created in temporary directories. They are software checks, never training examples or evidence of model competence. Receipt presence is checked mechanically; semantic support, negations, declare-before-verify, and the other model acceptance tests still require their own evaluation work.

HQ can use the separate [Studio environment probe](docs/studio-environment-check.md) to inspect its existing interpreter and run one disposable synthetic LoRA step. Its numerical run is pending. The [MacBook follow-up](docs/macbook-followup-2026-10-19.md) records the fetched renderer status and links the CK receipt note.
