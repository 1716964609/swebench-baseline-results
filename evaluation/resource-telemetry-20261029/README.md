# SWE-bench Verified — Resource Telemetry Source of Truth (2026-10-29)

Contains normalized, auditable per-issue and per-model-call observations for Vanilla 500 and AIVP 500, plus 22 AIVP retry/recovery records. The original Codex/Claude transcripts remain **local on Mac**.

## Files

- `vanilla-500.jsonl`: 500 Vanilla issues: input/cached/output tokens, 490 monotonic runner durations, 10 filesystem-duration estimates (explicitly labeled).
- `aivp-base-500.jsonl`: 500 AIVP issues: token, provider, timing, coverage, source SHA256.
- `aivp-additional-22.jsonl`: 15 retry records and 7 recovery records (not 22 unique issues).
- `aivp-model-calls.jsonl`: numeric call-level telemetry, including model/provider and missing values as null.
- `manifest.json`: record counts, audited totals, completeness and SHA256.
- `rebuild_telemetry.py`: extraction and audit code. Requires original local traces.

## Measurement boundaries

AIVP base contains 1,731 model calls, with token usage on 1,716 calls. 15 known missing calls are retained as missing data, not zero, and need not be reinvestigated. The `recorded_cost_usd_PARTIAL` field does NOT measure total inference spend. Do not add cached tokens to input tokens: cached input is a subset of input. `filesystem_birth_to_mtime_estimate` is NOT the same as monotonic runner timing. Agent generation time is NOT SWE-bench Docker evaluation time.

## Rebuild

On the original Mac, from this repo: `python3 evaluation/resource-telemetry-20261029/rebuild_telemetry.py`. The rebuild refuses to write outputs if issue IDs, expected row counts, or audited token totals differ.

## Outcome sources

See `../aivp-v2-shadow-500/`, `../vanilla-remaining-130/`, and historical per-batch evaluation directories. Reported resolved outcomes: Vanilla 369/500, AIVP 405/500. Ambiguous cases require separate grade review.
