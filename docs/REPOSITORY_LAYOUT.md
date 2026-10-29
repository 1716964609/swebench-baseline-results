# Repository structure and provenance

This document explains the navigation-only restructuring on 2026-10-29.
No historical experimental artifact was deleted or edited during relocation.

## Location mapping

| Previous location | Current location | Purpose |
| --- | --- | --- |
| `batch_*/` (14 root folders) | `experiments/vanilla/batch_*/` | Frozen Vanilla patch-generation batches, including legacy overlapping/auxiliary directories |
| `aivp_v2/pilot_001/` | `experiments/aivp/pilot_001/` | Original AIVP pilot evidence |
| `evaluation/` | `evaluation/` (unchanged) | Grading outputs and resource telemetry |
| `docs/research/` | `docs/research/` (unchanged) | Historical handovers and immutable task ordering |

All moved files retain their original Git blob SHA and content. A Git commit/PR records the path changes; pre-existing commit hashes remain accessible through Git history.

## Canonical Vanilla predictions

`evaluation/vanilla-500/predictions.jsonl` provides the **single 500-issue Vanilla prediction file** for research analysis. Its ordering and original source batch are derived from `docs/research/Vanilla_Baseline_Instance_Order.json`.

- Issue #1 was generated separately. Its original `~/swebench-play/prediction.jsonl` on the research Mac supplies that patch.
- Issues #2–500 are taken from the matching archived batch `predictions.jsonl` files.
- Each candidate prediction must have the expected issue ID, a nonempty patch, and a unique place in the frozen 500-issue order.
- `evaluation/vanilla-500/manifest.json` records SHA-256 evidence, source paths, and row counts; copies are only for navigation, not a new model execution.

## Telemetry and source-of-truth rules

- Patch sources: AIVP `evaluation/aivp-v2-shadow-500/predictions.jsonl` and Vanilla `evaluation/vanilla-500/predictions.jsonl`.
- Grading: AIVP per-issue `results.json`; Vanilla historical `evaluation/codex-*/` and `evaluation/aws-baseline-*/` reports plus `evaluation/vanilla-remaining-130/results-130.json`.
- Numeric resource measurement: `evaluation/resource-telemetry-20261029/`.
- Local original event traces are retained on the research Mac. Scripts in the historical batch folders still refer to the original local `~/swebench-play/batch_*` directories, by design.
- AIVP's 15 missing token-usage calls are explicitly marked missing, not zero. First 10 Vanilla times are filesystem approximations. Recorded pricing and API-equivalent costs should not be confused with actual billing.

## Compatibility

External URLs that referenced old root-level batch paths require updating after this change. Use the mapping above. Git history retains old paths at the original commit SHA.
