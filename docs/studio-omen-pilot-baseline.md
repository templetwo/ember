# Studio / Omen lesson pilot baseline

Measured 2026-10-27, before lesson fine-tuning. Reader: Anthony and the pilot
reviewers. Recheck whenever the corpus, checkpoint, runtime, or configuration changes.

## Model and scope

The candidate is **Qwen3.5-9B**, upstream revision
`c202236235762e1c871ad0ccb60c8ee5ba337b9a`.
All 14 downloaded upstream files were hash-compared between machines and matched.
The Studio conversion was made from those pinned upstream bytes.

This compares practical training stacks: MLX affine 4-bit (group size 64) on
the M4 Max Studio, and bitsandbytes NF4 on the Radeon RX 9060 XT Omen. The
quantizers, kernels, and random-number implementations differ, so results must
not be presented as a pure hardware comparison.

## Data

The private pilot contains 32 independently source/label-reviewed constructed
lessons: the original 12 distillations and a new 20-example batch. They are
lessons derived from recorded sources, not reconstructed historical conversations.

| Split | OPEN | PAUSE | Total |
|---|---:|---:|---:|
| Training | 13 | 7 | 20 |
| Validation | 3 | 1 | 4 |
| Test | 5 | 3 | 8 |

Related sources and selected related lesson families stay together. No WITNESS
examples are included. The eight-item test supports exploratory comparison, not
a general safety claim or P0 exit. No final-test tuning is planned.

The frozen manifest hash is
`0abc611e266b410e79d9d55f3a9f7fa23d22833d07dcfdd5b9eb2453c9c46942`.
The private corpus, source records, predictions, and adapters are not published
by this baseline summary.

The larger source snapshot contains 4,515 records. Re-evaluation found 4,288
available for lesson review, with 4,177 distinct normalized bodies and about
1.03 million whitespace-delimited words. The 2,173 lexical lesson leads are a
review queue, not verified examples. The pilot is not an estimate of the pool's yield.

## Numerical training checks

Both machines completed two LoRA updates on the same public numerical fixture,
saved a nonzero finite adapter, and reproduced logits after adapter reload.
No Ember lesson entered these smoke tests.

| Measurement | Studio | Omen |
|---|---:|---:|
| Trainable parameters | 2,523,136 | 2,523,136 |
| Updates | 2 | 2 |
| Supervised tokens | 334 | 334 |
| Train time, including compilation and save | 27.173 s | 18.524 s |
| Peak allocated memory | 14,236,437,124 bytes | 10,286,151,680 bytes |
| Reload maximum absolute logit error | 0.0 | 0.0 |

The Studio check reloaded the model and adapter. The Omen check zeroed the
adapter tensors and reloaded them into the same frozen base. These checks show
runtime feasibility, not learning quality or steady-state throughput.

## Untrained baseline

Greedy decoding, thinking disabled, maximum 512 new tokens, identical frozen
prompt tokens. Invalid JSON counts as an incorrect decision. Reported field
completeness follows the prompt's requested fields, without imposing unrequested
nested list types. Original outputs and the scoring correction are retained privately.

| Measurement | Studio | Omen |
|---|---:|---:|
| Correct decisions | 6 / 8 | 7 / 8 |
| OPEN correct | 3 / 5 | 4 / 5 |
| PAUSE correct | 3 / 3 | 3 / 3 |
| Balanced accuracy | 0.80 | 0.90 |
| Complete requested JSON fields | 7 / 8 | 8 / 8 |

Always OPEN scores 5 / 8 accuracy and 0.50 balanced accuracy on this split.
Explanation and stakes correctness still require independent semantic review.
Do not choose a winner from eight items or attribute the difference solely to hardware.

## Fixed pilot configuration

40 updates, batch size 1, two passes through the same 20 training examples in
the same order, 640-token maximum with no truncation, assistant-only loss,
last 16 layers, rank 8, effective LoRA scale 16 (PEFT alpha 128), dropout 0,
gradient checkpointing, Adam at 1e-5, betas 0.9/0.999, epsilon 1e-8, seed 42.

Omen runtime: PyTorch 2.14.0+rocm10.1.0, Transformers 5.20.2, PEFT 0.21.2,
bitsandbytes 0.50.2. Its working bitsandbytes path falls back to the ROCm 7.15
binary, and hybrid-attention operations use reference PyTorch implementations.
Studio runtime: MLX 0.32.2, mlx-lm 0.31.3, Transformers 5.17.0.

The Omen launcher samples temperature every two seconds and stops its own job
at 80 C edge, 90 C junction, or 90 C memory. These are conservative pilot
limits, not manufacturer maximum ratings. Missing required telemetry also
stops the monitored job. The guard does not change fan curves or power limits.

This document freezes the baseline before the paired lesson-training run.
