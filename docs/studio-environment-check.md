# Studio environment probe for HQ

Reader: HQ. Cadence: run and review before the P1 environment approval. Status: prepared on the MacBook; the real MLX step has not been executed by this seat. No Studio or Jetson connection was made. Update 2026-10-21: HQ executed the probe once on the Studio on 2026-10-19 and it passed (MLX 0.32.2 / mlx-lm 0.31.3, GPU, 8 of 8 checks; claim `af874e64`); the receipt lives on the Studio, not in this repository.

Use the absolute path of the **existing Studio interpreter under review**, and the absolute path of this script in the Studio checkout. The evaluator's `.venv` is not the training environment. No installation or environment upgrade is part of the probe.

```sh
/ABSOLUTE/STUDIO/ENV/bin/python /ABSOLUTE/ember/scripts/check_studio_environment.py \
  --output /ABSOLUTE/ember/local/audit/studio-environment-001.json \
  --reader HQ --cadence 'before P1 environment approval'
```

The script records Python's executable, resolved binary, version and prefixes; user-site enablement; installed MLX and mlx-lm versions and distribution locations; host/platform; script and synthetic-fixture hashes. The expected pair defaults to **MLX 0.32.2 / mlx-lm 0.31.3**, as named in the build spec. A different installed pair is reported as a mismatch even if its numerical check passes. HQ can explicitly set `--expect-mlx` and `--expect-mlx-lm` to investigate another pair; the receipt records that choice.

The dry step constructs a disposable 4-input, 3-output linear layer with 12 fixed base weights and a rank-2 LoRA adapter with 14 parameters. Two fixed numerical rows provide the entire fixture. The base is frozen; one SGD update is evaluated in memory. The probe checks the trainable parameter set, finite nonzero gradients, unchanged base weights, changed adapter weights, finite parameters/losses, a reduced fixture loss, and exactly one optimizer step. It writes no weights and loads no model, tokenizer, checkpoint, or Temple record.

The default device is GPU; missing Metal fails rather than falling back to CPU. An explicit `--device cpu` is recorded as a CPU check and cannot establish GPU readiness. The worker uses the same absolute interpreter as the parent, has a 45-second default timeout, and requests offline mode for Hugging Face/Transformers. Child crashes, timeouts, invalid results, and missing packages produce failed receipts. Existing receipts cannot be overwritten. Output must remain in the checkout's ignored `local/` directory.

`--metadata-only` records the package/interpreter inventory without importing MLX or executing the step. Its status is `metadata-only`, never `passed`. Exit 0 in that mode means the inventory was recorded. A full run exits 0 only when the requested pair matches and the synthetic step passes; otherwise it exits 2. Every receipt remains `pending-HQ` review.

A passing result establishes this tiny adapter's forward/gradient/update path in the observed environment. It does not establish full-model training, tokenizer correctness, quantized training, the mlx-lm trainer CLI, checkpoint compatibility, or memory sufficiency. P1's tokenizer audit remains a separate explicit approval, as corrected by Fable.

The implementation uses the upstream [mlx-lm 0.31.3 LoRALinear](https://github.com/ml-explore/mlx-lm/blob/v0.31.3/mlx_lm/tuner/lora.py), [MLX 0.32.2 value-and-gradient utility](https://github.com/ml-explore/mlx/blob/v0.32.2/python/mlx/nn/utils.py), and [optimizer update API](https://github.com/ml-explore/mlx/blob/v0.32.2/python/mlx/optimizers/optimizers.py). The local tests exercise reporting and failure handling with mocked worker results; they are not evidence that the numerical step passed on any machine.
