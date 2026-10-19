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
