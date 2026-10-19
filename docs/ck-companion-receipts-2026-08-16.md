# Reading the August 16 CK companion receipts

Reader: HQ. Cadence: review with this Ember handoff, then when deciding whether a CK rerun is warranted. Scope: existing local artifacts only; no device run. These receipts concern Project Companion Benchmark v0, not Ember or the unread August 24 companion loss.

The frozen benchmark compared the same local model through bare and conditioned paths on person continuity, design intent, speaker discipline, edge honesty, and structural behavior. Although the design prose says twelve cells, its enumeration and scorer use **14 cells per arm**: 28 scored rows per run, with each arm's denominator kept at 14. A cell's overall pass requires both structural and companion checks. “Bare” receives a preamble containing fixture operator, device, design intent, and research goal; it is not an evidence-free arm. See the [fixture](https://github.com/templetwo/conditioned-kernel/blob/6cc09868f6557ce81bf6cebb3fd3fae4e729c2f2/benchmarks/project_companion_v0/FIXTURE.md) and [runner](https://github.com/templetwo/conditioned-kernel/blob/6cc09868f6557ce81bf6cebb3fd3fae4e729c2f2/benchmarks/project_companion_v0/run.py).

| Receipt (UTC) | Bare structural / companion / overall | CK structural / companion / overall | Recorded status |
| --- | --- | --- | --- |
| [0.8B, 12:52:16](https://github.com/templetwo/conditioned-kernel/blob/6cc09868f6557ce81bf6cebb3fd3fae4e729c2f2/benchmarks/project_companion_v0/receipts/qwen3.5_0.8b__jetson__live__20260816T125216Z.json) | 14/14 · 10/14 · 10/14 | 12/14 · 7/14 · 7/14 | shakedown; `CK_fails_claim` |
| [0.8B, 12:58:19](https://github.com/templetwo/conditioned-kernel/blob/6cc09868f6557ce81bf6cebb3fd3fae4e729c2f2/benchmarks/project_companion_v0/receipts/qwen3.5_0.8b__jetson__live__20260816T125819Z.json) | 14/14 · 10/14 · 10/14 | 12/14 · 7/14 · 7/14 | repeated shakedown; `CK_fails_claim` |
| [2B, 13:38:16](https://github.com/templetwo/conditioned-kernel/blob/6cc09868f6557ce81bf6cebb3fd3fae4e729c2f2/benchmarks/project_companion_v0/receipts/qwen3.5_2b__jetson__live__20260816T133816Z.json) | 14/14 · 13/14 · 13/14 | 14/14 · 8/14 · 8/14 | non-shakedown; `Bare_wins` |

Both model tags used Q8_0, think off, context 2048, temperature 0.3, and seed 42. The two 0.8B receipts have the same pass/fail pattern and are not independent seeds. Their CK P1 and R2 rows timed out and remain failures in the 14-cell denominator. The 2B receipt reports zero infrastructure faults/retries; all CK rows were structurally accepted, but P1, P3, I3, R3, E2, and S2 failed companion checks. No CK packet or recent-turn budget violation is recorded in any of the three receipts.

Why did bare score higher here?

- Did the direct bare preamble expose operator/device facts more effectively than the measured CK packet, and would an evidence-matched comparison distinguish missing compilation from model behavior?
- At 2B I3, did the recorded authoritative fallback to design intent cause the anti-parrot failure? What changed between the original candidate and the accepted answers on the five other misses, whose receipts show repair pass 1?
- How much of the 0.8B deficit came from timeout/decoding behavior versus continuity and recall? The 2B gap persists without infrastructure faults, so timeout alone cannot explain both runs.
- Would the subsequent [operator/intent/recall patch `6cc0986`](https://github.com/templetwo/conditioned-kernel/commit/6cc09868f6557ce81bf6cebb3fd3fae4e729c2f2) change these scores under the same frozen 14-cell protocol? The three receipts precede that patch; this reading supplies no post-patch result.

The receipts locate failures and motivate these questions. They do not isolate a causal mechanism or establish that bare generally beats conditioning.
