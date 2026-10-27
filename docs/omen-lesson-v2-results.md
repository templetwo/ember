# Omen lesson-v2 experiment results

Measured 2026-10-27. Reader: Anthony and experiment reviewers. Recheck before
changing the model, corpus, prompt, scoring, or training recipe.

**Outcome: the adapter was not accepted.** In both repetitions, the base model
scored 40/49 strict decisions with 49/49 complete JSON responses. The adapter
scored 32/49 with 38/49 complete JSON responses. A separate diagnostic removed
only outer Markdown fences: it recovered the base decisions exactly, with no
label improvement. The strict results below retain those formatting failures.

This is a public measurement summary of a private experiment, following the
[Studio/Omen pilot baseline](studio-omen-pilot-baseline.md). It publishes no
source bodies, example inputs, target answers, raw model responses, local audit
receipts, or adapter weights. The data and receipts remain private. Their hashes
identify the retained evidence; they do not make this summary independently
reproducible without access to that evidence.

## Model and fixed experiment

- Base: **Qwen/Qwen3.5-9B**, revision
  `c202236235762e1c871ad0ccb60c8ee5ba337b9a`.
- Training and all four evaluation passes ran on the Omen's Radeon RX 9060 XT,
  with 16 GB VRAM. Studio conducted and monitored the jobs.
- NF4 weights, BF16 compute, no double quantization; reference PyTorch
  implementations for the hybrid-attention operations.
- PyTorch 2.14.0+rocm10.1.0, Transformers 5.20.2, PEFT 0.21.2,
  bitsandbytes 0.50.2, NumPy 2.5.4, safetensors 0.8.0.
- All 14 upstream checkpoint files were verified against the pinned hashes for
  each run. Adapter evaluations additionally bound the saved adapter and its
  configuration to the completed training receipt.

The fixed recipe used 48 updates, batch size 1, seed 42, learning rate 1e-5,
Adam with betas 0.9/0.999 and epsilon 1e-8, zero weight decay and dropout,
assistant-only loss, and gradient checkpointing. LoRA rank was 8, alpha 128
(effective scale 16), on the last 16 layers. Targets were `self_attn.q_proj`,
`self_attn.v_proj`, `linear_attn.in_proj_qkv`, and `linear_attn.out_proj`:
32 intended modules and 2,523,136 trainable parameters.

The sequence limit was 1,024 tokens with truncation forbidden. Actual full
training sequences contained 395–458 tokens. The fixed paired order produced
24 OPEN, 12 PAUSE, and 12 WITNESS update exposures across 48 updates.

## Reviewed data and evaluation design

These are constructed teaching scenarios grounded in eligible recorded lessons,
with separate authoring and review tasks. They are not historical transcripts.
The training and validation cut contains 24 contrast groups, conservatively
coalesced into 21 related-event families. Source and related-event review kept
those families separate from the evaluation sources. Earlier pilot examples and
exposed benchmark events were reserved from this training cut.

| Split | OPEN | PAUSE | WITNESS | Total |
|---|---:|---:|---:|---:|
| Training | 18 | 9 | 9 | 36 |
| Reserved validation | 6 | 3 | 3 | 12 |
| Fresh held-out evaluation | 8 | 5 | 3 | 16 |

Validation examples were reserved, but validation loss was not measured and no
checkpoint was selected on validation results. This is a 36-example training
pilot, not a claim that the larger source pool yields only 36 examples.

Each evaluation pass used the same 49 cases: 21 exposed original cases, 12
exposed harder cases, and 16 fresh held-out cases. Their combined class counts
were 26 OPEN, 16 PAUSE, and 7 WITNESS. The 12 harder cases form six matched
pairs; the 16 fresh cases form eight matched pairs.

The plan and both bundles were frozen before these model outputs. Execution
order was base repeat 1, adapter repeat 1, base repeat 2, adapter repeat 2.
Each was a separate process, with the same original 623-character instruction,
frozen prompt token IDs, case order, seed 42, greedy decoding, thinking disabled,
and a 768-new-token limit. All 196 responses ended at EOS; none hit that limit.
An unused inherited 512-token field in the training receipt did not control
these evaluations; the evaluation receipts bind the actual 768-token limit.

Acceptance required complete requested JSON in every candidate response, no
strict-label loss on any suite against its corresponding base repeat, fresh-set
improvement in both repeats, and a clean whole-response semantic review.

## Strict results

Invalid JSON, including Markdown wrappers, receives no decision credit. A valid
decision in an object can receive label credit even if another requested field
is missing; complete-JSON scores separately require all requested fields.
Neither structural check verifies the truth or consistency of the prose.

| Measure | Base 1 | Base 2 | Adapter 1 | Adapter 2 |
|---|---:|---:|---:|---:|
| Original cases: correct labels | 21/21 | 21/21 | 21/21 | 21/21 |
| Harder cases: correct labels | 8/12 | 8/12 | 4/12 | 4/12 |
| Fresh cases: correct labels | 11/16 | 11/16 | 7/16 | 7/16 |
| All strict labels | 40/49 | 40/49 | 32/49 | 32/49 |
| Complete requested JSON | 49/49 | 49/49 | 38/49 | 38/49 |
| Harder matched pairs: both correct | 2/6 | 2/6 | 0/6 | 0/6 |
| Fresh matched pairs: both correct | 3/8 | 3/8 | 2/8 | 2/8 |

Per-class strict scores were identical within each model's two repetitions:

| Class | Base correct | Adapter correct |
|---|---:|---:|
| OPEN | 25/26 | 19/26 |
| PAUSE | 13/16 | 11/16 |
| WITNESS | 2/7 | 2/7 |

Both candidate repetitions failed the predeclared format, suite nonregression,
and fresh-improvement requirements. The unchanged original-suite score does not
establish an overall gain.

## Formatting diagnostic and response review

Each adapter repetition emitted 11 JSON objects inside Markdown fences. Removing
only those wrappers diagnostically yielded 40/49 labels and 49/49 complete JSON
objects. Every diagnostic decision matched the corresponding base decision.
This diagnostic is not an alternative acceptance score or a parser change.

The base repetitions had identical raw responses and token lists on all 49
cases. The adapter repetitions matched exactly on 37 cases and changed on 12.
Two strict decision changes arose from wrappers moving between already-wrong
answers, leaving aggregate scores unchanged. Equal aggregate scores therefore
do not imply identical candidate responses.

A separate Codex review task covered all 196 response instances: 110 direct
whole-response reads and 86 explicit reuses after exact raw-output and token-list
verification. The coordinating task verified 196 response hashes, 196 token-list
hashes, and 269 quoted evidence references, including reused evidence. This is
same-model-family AI review, not human review or independent-substrate reproduction.

The adapter corrected one sorting explanation in both repetitions. Its paired
ordering failure remained. Confusion between an observed empty response and a
missing response, a prohibited export recommendation, and unsupported scope and
coverage certifications also persisted. Four boundary-label errors still
explicitly refused the operation; those are distinguished from permission to
proceed. Ambiguous action fields were assessed with the full response rather
than counted automatically as endorsements. Overall semantic improvement was
mixed and did not satisfy acceptance.

## Training verification and temperatures

Training completed all 48 updates in **101.151 seconds**, including compilation
and saving, with 9,016 supervised tokens. Peak allocated memory was
9,986,835,456 bytes; peak reserved memory was 13,157,531,648 bytes. The saved
adapter's same-base reload check reported maximum absolute logit error 0.0 on
its checked 32-token prefix; this was a narrow serialization check.

The construction audit found no target, masking, truncation, or module-selection
bug within its scope. All 48 training/validation targets were complete plain
JSON without fences. Token arrays and assistant boundaries recomputed exactly;
the installed loss implementation applied the expected causal shift. All 32
intended LoRA modules had finite, nonzero B matrices after training.

For the 12 training examples seen twice, mean loss fell from 2.798 to 2.315,
with a decrease on every matched example. This demonstrates in-sample fitting,
not held-out improvement. Fixed paired ordering, absent validation-loss
measurement, and absent per-module gradient logs remain limitations. The cause
of the fence regression is not established by this audit.

| Run | Peak edge | Peak junction | Peak memory |
|---|---:|---:|---:|
| Training | 50 C | 64 C | 52 C |
| Base 1 | 59 C | 75 C | 68 C |
| Adapter 1 | 55 C | 70 C | 62 C |
| Base 2 | 58 C | 73 C | 66 C |
| Adapter 2 | 55 C | 70 C | 62 C |

All jobs completed normally. A local guard sampled every two seconds and was
configured to stop its own job at 80 C edge, 90 C junction, 90 C memory, or missing
required sensor telemetry. No thermal stop occurred. These are experiment limits, not hardware
ratings. Detached supervision kept job lifetime separate from the SSH transport.
The Studio dashboard tailed actual completed steps and recorded observations;
no simulated telemetry was used.

## Retained evidence identifiers

SHA-256 values below identify private artifacts; the artifacts themselves are
not included in this publication.

| Artifact | SHA-256 |
|---|---|
| Predeclared plan | `9b595c8a3c11ff959349dbc1f9cebc1c83593bc4ff84ca93554f4579dbc30211` |
| Training manifest | `486c364655db32c7e67b537cd8c4cd9870acfbb1785e08b657f86ddcf7c2f0de` |
| Evaluation manifest | `443e11b4197aa6c96aa343412f4bd1ee98cb4f9ae592148222710426afce91cd` |
| Training result | `e56918dfd327b01b8b2fbfb22ef3c5ae74cec0bf8a4003c93d19b97fddc34a7d` |
| Numeric analysis | `d1df224271f67e7f41e6130e3e351e316f74f58c3ab33fe3ac2960a7137a1e66` |
| Final semantic review | `43c87671c884707913b750cfb0a903e9f09d6999746ea21faec8ad41bd35119c` |
| Construction audit | `1052134f5488135ec52946b1e5d037b4d226c276e00e346ba568363ec4dafcab` |
| Final experiment conclusion | `d3fe5b55b6274a17e00c0309db0b3bf1f6514fdc87e2d84328ed8887e81984f1` |

## Decision and limits

Retain the base as the comparison reference; **do not adopt this adapter**.
This does not certify the base for deployment. The same selected 49 scenarios
were repeated, not replaced with 49 new scenarios in each pass. Two repetitions
are not a population reliability estimate. The recipe and update count differ
from the earlier pilot, so the experiment does not isolate data quality as the
cause of an effect. No P0 exit, Jetson deployment result, corpus release, or
model release is claimed.

Future work should broaden reviewed lesson coverage, measure validation loss
and JSON compliance under predeclared selection rules, and keep these now-exposed
benchmark events reserved from training. No additional run is implied by this
report.
