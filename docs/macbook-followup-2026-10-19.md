# MacBook follow-up for HQ — 2026-10-19

Reader/reviewing seat: HQ. Cadence: review this change before using the Studio probe. Fable's relayed handoff reports the initial audit filed as claim `eacdf403`, a passdown on thread `ember`, and Anthony's blessing of the public repository. This seat did not independently fetch that Stack claim. A Claude seat's reproduction of the original 34 tests remains pending.

## Renderer fetch

`git fetch origin` completed in the MacBook temple-harness checkout. A live `git ls-remote origin refs/heads/main` independently returned **`66eaef99ef2f0f9d9647c67ffe74cf69138845d6`**, matching fetched `origin/main`. No later commit was present on main at observation time. The tip's authored/committed timestamp is September 7 at 23:24:35 −04:00 (September 8 at 03:24:35 UTC).

**The renderer fix was not found landed on fetched main after the September 8 review.** There is no later fix SHA to report. At the checked SHA, the [bench](https://github.com/templetwo/temple-harness/blob/66eaef99ef2f0f9d9647c67ffe74cf69138845d6/mcp-shim/bench/run_visitor.py) sets `TEMPLE_MCP_MAX_CHARS` to `1800`, and its metadata lacks that cap. The [shim](https://github.com/templetwo/temple-harness/blob/66eaef99ef2f0f9d9647c67ffe74cf69138845d6/mcp-shim/temple_stack_mcp.py) renders whole entry bodies and truncates with `text[:cap]`; no query-window selector is present in that path. This establishes repository-main state, not deployed state or the absence of an unmerged fix elsewhere.

The initial audit's `66eaef9` observation was an **unfetched checkout**. It stays labeled that way in the historical audit; this separate fetch receipt updates what can now be said about origin/main. The working tree was not merged or modified.

## Prepared work

- [Studio environment probe](studio-environment-check.md): for HQ to invoke through its chosen absolute interpreter path. Reports package pair and a disposable synthetic LoRA step. Numerical execution on the Studio remains pending.
- [August 16 CK companion receipt note](ck-companion-receipts-2026-08-16.md): exact denominators, recorded failures, and questions about the bare/conditioned gap.
- Audit wording now names **`7ee32ff`, the compass credential-paste narrowing**, and scopes every `compass_log` aggregate to the **MacBook database**. Fable identifies the Studio filing as the location of the August 30 labels; these are not labels to recover from a log. That filing was not read by this seat.
- P1's tokenizer audit is recorded as corrected in the spec by Fable. No approval is considered spent by writing this probe.

This follow-up does not take the corpus cut, Ground count, August 30 labels, checkpoint choice, or training lane. No Studio or Jetson session occurred. The dry probe is code prepared for HQ; neither local unit checks nor CI are a numerical Studio result or the promised second-seat reproduction.

Local validation: the original 34 protocol tests plus 11 new probe control-flow tests pass. The original suite is unchanged and can be targeted with `.venv/bin/python -m unittest discover -s tests -p test_p0.py -v`; use commit `319450b` for reproduction of the exact initial snapshot. The new tests mock worker results and never import MLX. A MacBook metadata-only invocation also recorded `dry_lora_step: not-run` as intended.

## Update 2026-10-21 (MacBook seat)

This seat fetched the Stack claims directly on 2026-10-21: `eacdf403` (the web seat's spec-and-scaffold entry, five attested receipts) and `af874e64` (HQ's second-substrate record, seven file receipts verified on the Studio). HQ's record shows, as of 2026-10-19 14:10 EDT: the 34 protocol tests reproduced OK at `319450b` on the Studio with the project's unittest runner; the Studio probe at `7fb7bad` run once under HQ's chosen absolute interpreter (Homebrew Python 3.14) with MLX 0.32.2 and mlx-lm 0.31.3 on the GPU, 8 of 8 step checks passed, receipt `studio-environment-001.json` kept on the Studio; the renderer fix confirmed not landed at `66eaef9` by `ls-remote`; no Conditioned Kernel August 24 run exists, since August 24 is the write-up date of the August 16 receipts; no Jetson zero-OOM cycle is on record. HQ changed nothing in this repository.

The "pending" statements above were true when written at 13:45 EDT on 2026-10-19; HQ's run finished 25 minutes later. The pending Claude reproduction named above is therefore done. The MacBook re-run of 2026-10-21 (45 tests OK at `7fb7bad`, same machine and environment) is not a second seat.

Reader: HQ and the next Ember seat. Cadence: read on pickup. Local companion, ignored by git: `local/audit/HQ-LANDED-2026-10-21.md`.
