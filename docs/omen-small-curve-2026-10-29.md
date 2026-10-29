# Omen small-model learning curve

Measured 2026-10-28 into 2026-10-29 on the Omen. Reader: Anthony and the OMEN
Claude Code seat. Recheck before changing the model, corpus, prompt, scoring, or
training recipe.

**Outcome: no adapter was accepted, and the experiment changed what we think
the grader is measuring.** An untrained Qwen2.5-1.5B-Instruct scored 0/49 strict
on the frozen lesson-v2 held-out cases. Trained on the same 36 reviewed rows with
the lesson-v2 recipe held constant, its strict score rose to the always-OPEN
control and stayed there, while a reading of the responses themselves showed the
stop behaviour the lessons teach falling to its lowest point at 24 and 48 updates
and returning only at 96 updates, as a situation-triggered reflex. One
checkpoint (96 updates) was kept at Anthony's word. It is not a deployment.

This is a public measurement summary of a private experiment, following
[Omen lesson-v2 experiment results](omen-lesson-v2-results.md). It publishes no
source bodies, example inputs, target answers, raw model responses, local audit
receipts, or adapter weights. Hashes identify the retained evidence; they do not
make this summary reproducible without access to it.

## Why a smaller model

The lesson-v2 run adapted Qwen3.5-9B under a 16 GB VRAM ceiling: NF4 weights,
attention-only LoRA on the last 16 of 32 layers, no MLP adaptation, three
quarters of the adapted modules on linear-attention paths. Every one of those
choices was forced by memory. The 9B's base already scored 40/49, with 21 cases
saturated, so the evaluation had little room to see a lesson land.

Qwen2.5-1.5B-Instruct removes the constraint. It is a dense 28-layer model that
fits the card in bf16 with room for the adapter and optimizer, so the recipe can
be run as written and the adapter placed by hypothesis rather than by memory.
Its untrained score is low enough that a lesson would be visible if it landed.
The Temple's own compass work showed a 1.5B and a 3B learning the OPEN / PAUSE /
WITNESS label space. Anthony's 2026-10-27 ruling that Ember should not settle
for a 1.5B as its model stands; this run uses the 1.5B as the instrument.

## Model and fixed experiment

- Base: **Qwen/Qwen2.5-1.5B-Instruct**, revision
  `989aa7980e4cf806f80c7fef2b1adb7bc71aa306`. 28 layers, hidden 1536, 12 heads,
  2 KV heads, vocabulary 151,936.
- bf16 weights and compute on the Omen's Radeon RX 9060 XT (16 GB). No
  quantization. `sdpa` attention. PyTorch 2.14.0+rocm10.1.0, Transformers
  5.20.2, PEFT 0.21.2.
- Recipe held constant from lesson-v2: Adam, learning rate 1e-5, betas
  0.9/0.999, epsilon 1e-8, zero weight decay and dropout, batch size 1, LoRA
  rank 8, alpha 128 (scale 16), assistant-only loss, seed 42, sequence limit
  1,024 with truncation forbidden, the same fixed row order the 9B saw.
- Lifted, and only these: the bf16 base, and LoRA on `q_proj`, `k_proj`,
  `v_proj`, `o_proj`, `gate_proj`, `up_proj`, `down_proj` in all 28 layers:
  196 modules, 9,232,384 trainable parameters (the 9B run adapted 32 modules,
  2,523,136 parameters).
- No schedule, warmup, clipping, or gradient checkpointing. No thinking mode
  exists on this base.
- Training ran to 216 updates (six passes). The live adapter was scored on all
  49 cases, and teacher-forced loss on the 12 reserved validation rows was
  recorded, at 0, 12, 24, 48, 96, 144, and 216 updates. Adapters were saved at
  each point. The 48-update point matches the 9B run's length.

## Reviewed data and evaluation design

Identical to lesson-v2: 36 training rows (18 OPEN, 9 PAUSE, 9 WITNESS) in 18
contrast pairs; 12 reserved validation rows; the same 49 held-out cases (21
original, 12 harder, 16 fresh; 26 OPEN, 16 PAUSE, 7 WITNESS; 14 matched pairs
across the harder and fresh sets). The frozen baseline scorer and the same
623-character instruction were used. Decoding was greedy, 768 new tokens
maximum; no response hit the limit.

Nuisance controls were fitted on training rows only, with the bundle's own
scorer. Always-OPEN scores 26/49 on these cases (0.531 exact, 0.333 macro
recall). The length rule fitted on the 36 training situations reaches only
0.556 balanced accuracy on train, so length alone does not solve this set.

## Strict results along the curve

Invalid JSON, including Markdown wrappers, receives no decision credit. The
diagnostic column removes only an outer Markdown fence; it is not an acceptance
score.

| Updates | Strict labels | Fence diagnostic | Complete JSON | Fenced | OPEN | PAUSE | WITNESS | Validation loss |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 0/49 | 8/49 | 0/49 | 42 | 0/26 | 0/16 | 0/7 | 3.023 |
| 12 | 19/49 | 19/49 | 21/49 | 0 | 19/26 | 0/16 | 0/7 | 2.656 |
| 24 | 24/49 | 24/49 | 23/49 | 0 | 23/26 | 0/16 | 1/7 | 2.400 |
| 48 | 22/49 | 22/49 | 42/49 | 0 | 22/26 | 0/16 | 0/7 | 1.929 |
| 96 | 23/49 | 23/49 | 40/49 | 0 | 15/26 | 8/16 | 0/7 | 1.739 |
| 144 | 24/49 | 24/49 | 37/49 | 0 | 8/26 | 15/16 | 1/7 | 1.725 |
| 216 | 22/49 | 22/49 | 44/49 | 0 | 14/26 | 6/16 | 2/7 | 1.977 |

Mean training loss over the twelve updates before each point: 2.83, 2.41, 1.88,
1.31, 1.09, 0.65 at 12, 24, 48, 96, 144, 216. Validation loss stopped falling
at 96 and rose between 144 and 216; the last two points are memorisation of the
36 training rows.

The untrained model wrapped 42 of 49 responses in Markdown fences and, inside
them, used label words outside the schema on 26 cases. The 9B base fenced
nothing. Twelve updates removed every fence and produced the compact single-line
form of the training targets; the output contract was fully acquired by 48
updates. No point on the curve exceeded the always-OPEN control by more than one
case. No point produced a WITNESS decision on a case that expected one.

## Response reading

The strict scorer reads the decision field. A separate reading of the whole
response asked three questions against the record each case supplied: did the
action field refrain from the proposed operation or perform it; does the
explanation name the constraint actually present in the record; does any
sentence contradict the record. This was same-model-family AI reading by the
OMEN Claude Code seat on the 23 cases expecting PAUSE or WITNESS, not human
review and not independent-substrate reproduction. Its counts are approximate
and are reported as such.

| Updates | Stop cases refused (of 23) | Action restates the proposal | Record-grounded reasons | OPEN cases over-refused (of 26) | Pairs answered differently (of 14) |
|---:|---:|---:|---|---:|---:|
| 0 | about 10 | 0 | most of the refusals | 0 | 1 |
| 12 | about 10, smeared across fields | 0 | fewer | 0 | 0 |
| 24 | 1 | 20 | one | 0 | 0 |
| 48 | 1 | 14 | one | 1 | 0 |
| 96 | 13 | 0 | most of the refusals | 11 | 1 |
| 144 | 21 | 0 | mixed | 17 | 2 |
| 216 | 17 | 0 | mixed | 11 | 1 |

The two instruments disagreed for most of the curve. Between 0 and 48 updates
the strict score rose from 0 to the control while the refusals fell from about
ten to one. The untrained model, in prose and inside its fences, declined the
proposed operation and cited the record's rule on roughly ten stop cases. At 12
updates the stop had moved into the wrong field (an OPEN decision with a
boundary word in the action slot). At 24 updates the model restated the rule,
wrote "however", and proceeded. At 48 updates it denied the record's premise so
that the rule had nothing to attach to, and restated the rule as its own
negation on several cases. Across the same span the explanations shrank from a
paragraph to a sentence, and sentences contradicting the supplied record rose
from one observed to at least four of 23.

At 96 updates the second label arrived. Twenty-four responses were PAUSE, every
one opening its action field with the verb the instruction assigns to PAUSE.
Thirteen stop cases were refused, the most of the run, and many reasons were the
record's own for the first time, including the connector case, which the model
had explained wrongly at every earlier point. In the same checkpoint, 11 of 26
OPEN cases were over-refused, and the two halves of a matched pair received the
same decision on 13 of 14 pairs. The model had learned which situations call
for a stop; it had not learned to read the proposal inside the situation.

At 144 updates the default flipped: 36 of 49 decisions were PAUSE, 21 of 23
stop cases were refused and 17 of 26 OPEN cases were over-refused. The first
WITNESS decisions appeared, on both halves of one matched pair with the same
reason. At 216 updates eleven responses said WITNESS (two on cases expecting
it, five on PAUSE cases, four on OPEN cases), each action phrased as a
prohibition in the register of the training targets' WITNESS rows. The three
labels arrived in the order of their frequency in the targets, each first as a
reflex on a situation; at no point did the model answer more than two of the 14
matched pairs differently.

One case expecting a hard boundary moved through six forms across the run:
refuse and cite the rule (0); refuse in the wrong field (12); cite the rule and
override it (24); deny the record's premise (48 and 96); refuse with the right
action and a weak reason (144); refuse with the right label, action, and rule
named (216). By the time it answered correctly, validation loss was rising and
the model refused 11 of 26 operations it should have allowed.

A separate observation, made through the Ollama copy of the same base model
(Q4_K_M quantization, temperature 0) rather than the bf16 copy under training:
with the output-contract sentence removed from the instruction and everything
else kept, the untrained model answered three of the frozen cases in prose. On
two it refused the proposal, cited the record's constraint correctly, and
proposed a sensible next step. The strict scorer scores all three zero. This is
three cases on a different quantization; it is recorded as an observation, not a
measurement.

## What this changes

- **The strict label score on this task does not measure the stop.** It
  rewarded the 9B for right labels over actions that named the prohibited
  operation (see the pilot baseline), and penalised the 1.5B for refusals that
  used the wrong label word or a Markdown fence. A grader for Ember should read
  the action against the proposal and the explanation against the record, with
  the label as a consistency check. Law 10 applies to that grader as much as to
  this one: it must be shown to fail on a length or keyword proxy before it is
  trusted.
- **The output contract competes with the lesson for a small model's
  capacity.** The compact eight-field target was learned first and at the
  expense of the judgment present in the untrained model's prose. Where
  structure is needed for a router, asking for the label after the reasoning,
  or classifying the prose downstream, keeps the structure on the reading
  rather than on the speaking.
- **Matched pairs are the control that matters.** A model that answers both
  halves of a pair the same way has learned the situation, not the decision.
  Pair discrimination should be a reported acceptance number, as it was in the
  lesson-v2 results.
- **The 96-update adapter is kept, not adopted.** Anthony asked for it to be
  retained as the first point at which behaviour moved toward the lesson. It is
  stored privately with its evaluation and hash receipts.

## Training verification and temperatures

Training and evaluation ran under the Omen's thermal guard with stops at 80 C
edge, 90 C junction, 90 C memory. Peak temperatures across the run were 60 C edge,
83 C junction, 66 C memory; no stop fired. All 216 updates took 59.3 seconds of
training time in total; peak allocated memory was 6.01 GB. Generation ran at
about 7 to 14 s per case; a full 49-case pass took six to ten minutes, and the
seven passes dominated the run's two and a half hours. The run was detached and
supervised, and every checkpoint adapter carries a sha256 in the run record.

## Private evidence (hashes)

- Script: `small_curve.py` in the Omen kit repository, commit `24e14ef`.
- Training architecture snapshot of the lesson-v2 run this answers: Omen kit
  commit `721268c`, sha256 `13c6cac9c41b4e42feccf02870c5e72229bdf48caf578f82e66c666c49dccf39`.
- Kept checkpoint `ember-small-u96-20261029`: adapter weights sha256
  `5bdf402bfa9cb29a...`, its 49 raw predictions `7bbc9a3e40dfa38c...`, receipt
  file sha256 `1aedcfff4ef1ae1e116b49958096be51b20e0358f356885d2c45bc042a84a3d7`.
- Chronicle claims, in order: launch `d7452490`, point 0 `54e784c6`, readings
  `38b98e0e`, point 12 `892266e6`, grading `a20a83cf`, point 24 `7c699f1e`,
  structure `fab1aeac`, the "however" `2f726a31`, point 48 `0963780f`,
  point 96 `1066903f`, checkpoint kept `f63d4092`, point 144 `f478b409`,
  point 216 and run complete: see the chronicle entry of 2026-10-29 in the
  domain beginning `ember,small-curve,qwen2.5-1.5b,observed,u216`.
