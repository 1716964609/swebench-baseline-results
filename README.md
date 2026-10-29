# SWE-bench Verified | Vanilla Codex vs AIVP v2 Shadow

**Reproducible research archive · 29 October 2026**

This repository preserves generated code patches, independent SWE-bench evaluation outcomes, and resource-usage telemetry for a **500-issue comparison** between a Vanilla Codex baseline and **AIVP v2 Shadow**, an experimental coding-agent harness. It is a research record, **not** an official SWE-bench leaderboard submission.

## Results at a glance

| Measure | Vanilla Codex | AIVP v2 Shadow |
| --- | ---: | ---: |
| Issues evaluated | 500 | 500 |
| Resolved | **369** | **405** |
| Observed resolved rate | **73.80%** | **81.00%** |
| Total measured input + output tokens | **147,255,946** | **285,460,411** |
| Mean generation time / issue | **122.55 s** | **186.13 s** |

**Observed quality difference: +36 issues / +7.20 percentage points** (+9.76% relative to the baseline resolved count). These are preliminary research observations, not a causal or statistically audited claim about harness performance. Ambiguous evaluations and differences in experimental execution still require analysis.

**Measurement caveats:** Vanilla token telemetry covers 500/500 issues; its first 10 duration values are filesystem-timestamp estimates, not monotonic-clock measurements. AIVP covers 500/500 runs, with missing token usage for 15 of 1,731 model calls. Token totals therefore reflect *recorded* usage. API-equivalent costs are estimates, not account billing.

## Find the evidence

| Need | Canonical location |
| --- | --- |
| AIVP 500 generated patches and per-issue evaluation results | [`evaluation/aivp-v2-shadow-500/`](evaluation/aivp-v2-shadow-500/) |
| **Vanilla 500 generated patches (canonical merged file)** | [`evaluation/vanilla-500/`](evaluation/vanilla-500/) |
| Vanilla final 130 evaluation outcomes | [`evaluation/vanilla-remaining-130/`](evaluation/vanilla-remaining-130/) |
| Earlier Vanilla evaluation reports | [`evaluation/aws-baseline-*/`](evaluation/) and [`evaluation/codex-batch-*/`](evaluation/) |
| **Per-issue tokens, runtimes, per-model calls, provenance and hashes** | [`evaluation/resource-telemetry-20261029/`](evaluation/resource-telemetry-20261029/) |
| Vanilla task order (500 instance IDs and source batches) | [`docs/research/Vanilla_Baseline_Instance_Order.json`](docs/research/Vanilla_Baseline_Instance_Order.json) |
| Historical Vanilla generation batches / scripts | [`experiments/vanilla/`](experiments/vanilla/) |
| Original AIVP single-issue pilot | [`experiments/aivp/pilot_001/`](experiments/aivp/pilot_001/) |
| Historical Vanilla experiment handover | [`docs/research/SWE-bench_Verified_Vanilla_Baseline_Handover_2026-10-14.md`](docs/research/SWE-bench_Verified_Vanilla_Baseline_Handover_2026-10-14.md) |
| Relocation map and archive conventions | [`docs/REPOSITORY_LAYOUT.md`](docs/REPOSITORY_LAYOUT.md) |

## Repository layout

```text
.
├── README.md
├── docs/
│   ├── REPOSITORY_LAYOUT.md
│   └── research/
├── evaluation/
│   ├── aivp-v2-shadow-500/       # AIVP predictions + grading
│   ├── vanilla-500/              # Canonical Vanilla predictions
│   ├── vanilla-remaining-130/    # Final Vanilla grading batch
│   ├── resource-telemetry-20261029/ # Numeric research dataset
│   └── ...                       # Historical per-batch grading reports
└── experiments/
    ├── aivp/pilot_001/           # AIVP pilot artifacts
    └── vanilla/batch_*/          # Original Vanilla batch artifacts
```

## Verify integrity

For the archived numeric telemetry, from the repository root:

```bash
(cd evaluation/resource-telemetry-20261029 && shasum -a 256 -c SHA256SUMS)
```

The `manifest.json` records data coverage and SHA-256 checksums. `rebuild_telemetry.py` documents how the numeric dataset was extracted from **local original logs**; the full private execution traces are **not** bundled here.

The canonical Vanilla prediction file is constructed from the frozen 500-issue order and the original per-batch predictions without changing any patch text. See its [`manifest.json`](evaluation/vanilla-500/manifest.json).

### Data handling

- Source generation scripts and historical evaluation reports are preserved unedited. Their historical `~/swebench-play/batch_*` runtime paths remain intentional; relocating them inside this GitHub repository does **not** relocate Mac execution workspaces.
- This is a public archive. Raw model conversations, prompts, session traces, API credentials, and proprietary research data must not be committed.
- Reported quality outcomes are separate from generated patch availability; a non-empty patch is **not** proof of a resolved issue.
