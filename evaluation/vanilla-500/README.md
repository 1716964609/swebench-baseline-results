# Vanilla Codex — canonical SWE-bench Verified predictions

`predictions.jsonl` contains exactly **500** issue-level predictions in the frozen Vanilla order. It is a **lossless consolidation**, not a re-run or re-evaluation.

- `docs/research/Vanilla_Baseline_Instance_Order.json` selects the unique `instance_id` and authoritative source batch for each row.
- Issue #1 (`sympy__sympy-20590`) came from the separate first-generation local `~/swebench-play/prediction.jsonl`.
- The remaining issues come from `experiments/vanilla/batch_*/predictions.jsonl`.
- `manifest.json` records the SHA-256 digest of every source prediction JSONL and the canonical file.
- Grading outcomes remain under `evaluation/codex-*`, `evaluation/aws-baseline-*`, and `evaluation/vanilla-remaining-130/`.

The JSONL uses the SWE-bench `instance_id`, `model_name_or_path`, `model_patch` schema. The final combined file's encoding/ordering is normalized to one JSON object per line; patch *strings* remain exactly as originally exported.
