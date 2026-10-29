#!/usr/bin/env python3
"""Create shareable, aggregate-only SWE-bench telemetry from LOCAL run artifacts.

NO raw Codex/Claude transcripts, prompts, command output, or repositories are copied.
Does not access the network or execute any AI models.
Place this script in ~/swebench-results/evaluation/resource-telemetry-20261029/
and run it there with python3.
"""
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

HOME = Path.home()
PLAY = HOME / "swebench-play"
DIAG = HOME / "swebench-aivp-pilot-010" / "diagnostics"
REPO = HOME / "swebench-results"
DEST = Path(__file__).resolve().parent
AIVP_PRED = REPO / "evaluation/aivp-v2-shadow-500/predictions.jsonl"
AIVP_RESULTS = REPO / "evaluation/aivp-v2-shadow-500/results.json"
VANILLA_130 = REPO / "evaluation/vanilla-remaining-130/summary-130.json"

BATCHES = (
    "batch_11_40", "batch_41_60", "batch_61_100", "batch_101_150",
    "batch_151_170", "batch_171_230", "batch_231_240", "batch_241_300",
    "batch_301_360", "batch_361_370", "batch_371_430", "batch_431_500",
)


def read_json(p):
    return json.loads(p.read_text(encoding="utf-8"))


def sha256(p):
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def source(p):
    return {"local_source": str(p.relative_to(HOME)), "local_sha256": sha256(p)}


def require(ok, msg):
    if not ok:
        raise RuntimeError(msg)


def usage_from_codex_trace(p):
    completed = []
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        e = json.loads(line)
        if e.get("type") == "turn.completed" and isinstance(e.get("usage"), dict):
            completed.append(e["usage"])
    require(len(completed) == 1, f"Expected ONE completed usage in {p}, found {len(completed)}")
    u = completed[0]
    required = ("input_tokens", "cached_input_tokens", "output_tokens")
    require(all(type(u.get(k)) is int and u[k] >= 0 for k in required), f"Incomplete usage: {p}")
    require(u["cached_input_tokens"] <= u["input_tokens"], f"Cached > input: {p}")
    return u


def build_vanilla_record(iid, trace, status_path, batch, time_kind):
    require(trace.is_file(), f"Trace missing: {trace}")
    u = usage_from_codex_trace(trace)
    if time_kind == "monotonic_runner":
        require(status_path is not None and status_path.is_file(), f"Status missing: {status_path}")
        status = read_json(status_path)
        duration = status.get("elapsed_seconds")
        require(isinstance(duration, (float, int)) and duration >= 0, f"Duration missing: {status_path}")
        duration = float(duration)
    else:
        require(hasattr(trace.stat(), "st_birthtime"), f"macOS birthtime unavailable: {trace}")
        duration = trace.stat().st_mtime - trace.stat().st_birthtime
        require(0 < duration < 1800, f"Suspicious file times: {trace} ({duration})")
        if status_path and status_path.exists():
            lag = status_path.stat().st_mtime - trace.stat().st_mtime
            require(0 <= lag <= 30, f"Suspicious status lag: {status_path} ({lag})")
    rec = {
        "instance_id": iid,
        "batch": batch,
        "input_tokens": u["input_tokens"],
        "cached_input_tokens": u["cached_input_tokens"],
        "uncached_input_tokens": u["input_tokens"] - u["cached_input_tokens"],
        "output_tokens": u["output_tokens"],
        "total_tokens": u["input_tokens"] + u["output_tokens"],
        "elapsed_seconds": round(duration, 4),
        "elapsed_method": time_kind,
        "elapsed_is_estimate": time_kind != "monotonic_runner",
        "trace": source(trace),
    }
    if status_path is not None and status_path.is_file():
        rec["status"] = source(status_path)
    return rec


def vanilla_records():
    records = []
    records.append(build_vanilla_record(
        "sympy__sympy-20590", PLAY / "codex_events.jsonl", None,
        "first_manual_run", "filesystem_birth_to_mtime_estimate"))
    early = PLAY / "batch_02_10"
    tasks = read_json(early / "tasks.json")
    require(len(tasks) == 9, f"Expected 9 early tasks, found {len(tasks)}")
    for task in tasks:
        iid = task["instance_id"]
        records.append(build_vanilla_record(
            iid, early / "logs" / f"{iid}.jsonl",
            early / "logs" / f"{iid}.status.json",
            "batch_02_10", "filesystem_birth_to_mtime_estimate"))
    for batch in BATCHES:
        root = PLAY / batch
        tasks = read_json(root / "tasks.json")
        for task in tasks:
            iid = task["instance_id"]
            records.append(build_vanilla_record(
                iid, root / "logs" / f"{iid}.events.jsonl",
                root / "status" / f"{iid}.json", batch, "monotonic_runner"))
    return sorted(records, key=lambda r: r["instance_id"])


def classify(group):
    if group.startswith("e2e-"):
        return "e2e_excluded"
    if group.startswith("recovery-"):
        return "recovery_extra"
    if "-retry-" in group:
        return "retry_extra"
    if group.startswith(("phase-", "parallel-unrestricted-")):
        return "base"
    raise RuntimeError(f"Unknown AIVP group: {group}")


def aivp_records():
    base, extra, calls, excluded = [], [], [], []
    for p in sorted(DIAG.rglob("run-summary.json")):
        rel = p.relative_to(DIAG)
        require(len(rel.parts) >= 3, f"Unexpected AIVP path: {p}")
        group = rel.parts[0]
        category = classify(group)
        iid = rel.parts[1] if len(rel.parts) > 1 else "unknown"
        if category == "e2e_excluded":
            excluded.append(str(rel))
            continue
        d = read_json(p)
        tokens = d.get("tokens") or {}
        time = d.get("time") or {}
        model = d.get("model_calls") or {}
        cost = d.get("cost") or {}
        n_calls = model.get("count")
        require(type(n_calls) is int, f"Model call count missing: {p}")
        duration = time.get("run_elapsed_seconds")
        require(isinstance(duration, (int, float)), f"Run elapsed missing: {p}")
        for key in ("input_tokens", "cached_tokens", "output_tokens"):
            require(isinstance(tokens.get(key), (int, float)), f"Missing {key}: {p}")
        providers = {}
        for provider, v in (model.get("by_provider") or {}).items():
            providers[provider] = {k: v.get(k) for k in (
                "calls", "latency_ms", "input_tokens", "cached_tokens",
                "output_tokens", "cost_usd", "cost_known_calls")}
        rec = {
            "instance_id": iid,
            "category": category,
            "group": group,
            "run_id": d.get("run_id"),
            "status": d.get("status"),
            "elapsed_seconds": duration,
            "elapsed_method": "aivp_run_summary",
            "model_calls": n_calls,
            "input_tokens_recorded": tokens["input_tokens"],
            "cached_tokens_recorded": tokens["cached_tokens"],
            "output_tokens_recorded": tokens["output_tokens"],
            "total_tokens_recorded": tokens["input_tokens"] + tokens["output_tokens"],
            "input_known_calls": tokens.get("input_known_calls"),
            "cached_known_calls": tokens.get("cached_known_calls"),
            "output_known_calls": tokens.get("output_known_calls"),
            "cost_known_calls": cost.get("known_calls"),
            "cost_total_calls": cost.get("total_calls"),
            "recorded_cost_usd_PARTIAL": cost.get("total_usd"),
            "by_provider": providers,
            "pricing_version": d.get("pricing_version"),
            "run_summary": source(p),
        }
        (base if category == "base" else extra).append(rec)
        for step in (model.get("by_step") or []):
            calls.append({
                "instance_id": iid,
                "category": category,
                "run_id": d.get("run_id"),
                "step_id": step.get("step_id"),
                "provider": step.get("provider"),
                "model": step.get("model"),
                "status": step.get("status"),
                "latency_ms": step.get("latency_ms"),
                "input_tokens": step.get("input_tokens"),
                "cached_tokens": step.get("cached_tokens"),
                "output_tokens": step.get("output_tokens"),
                "recorded_cost_usd": step.get("cost_usd"),
            })
    return (sorted(base, key=lambda r:r["instance_id"]),
            sorted(extra, key=lambda r:(r["category"],r["group"],r["instance_id"])),
            sorted(calls, key=lambda r:(r["category"],r["instance_id"],r["run_id"] or "",r["step_id"] or "")),
            excluded)


def totals(rows, fields):
    return {key: sum(r.get(key) or 0 for r in rows) for key in fields}


def write_jsonl(path, records):
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")


def main():
    require(PLAY.is_dir() and DIAG.is_dir() and REPO.is_dir(), "One of the local source directories is missing")
    require(DEST == REPO / "evaluation" / "resource-telemetry-20261029",
            f"Place the script at ~/swebench-results/evaluation/resource-telemetry-20261029/rebuild_telemetry.py; current: {DEST}")
    expected = {json.loads(line)["instance_id"] for line in AIVP_PRED.read_text(encoding="utf-8").splitlines() if line.strip()}
    require(len(expected) == 500, f"Expected 500 AIVP prediction IDs, got {len(expected)}")
    aivp_results = read_json(AIVP_RESULTS)
    require(len(aivp_results) == 500, "AIVP evaluation results should have 500 rows")
    require({r["instance_id"] for r in aivp_results} == expected, "AIVP eval IDs differ from predictions")
    require(sum(bool(r["resolved"]) for r in aivp_results) == 405, "AIVP resolved count mismatch")
    require(read_json(VANILLA_130).get("resolved") == 100, "Vanilla last 130 resolved count mismatch")

    v = vanilla_records()
    a, x, c, excluded = aivp_records()
    for label, rows, n in (("Vanilla",v,500),("AIVP base",a,500),("AIVP extra",x,22)):
        require(len(rows) == n, f"{label} expected {n}, got {len(rows)}")
    require(len(excluded) == 2, f"Expected 2 unrelated E2E runs, got {len(excluded)}")
    require({r["instance_id"] for r in v} == expected, "Vanilla IDs do not match 500 AIVP prediction IDs")
    require(len({r["instance_id"] for r in v}) == 500, "Duplicate Vanilla issue ID")
    require(len({r["instance_id"] for r in a}) == 500, "Duplicate AIVP base issue ID")
    vt = totals(v, ("input_tokens","cached_input_tokens","output_tokens","total_tokens"))
    at = totals(a, ("input_tokens_recorded","cached_tokens_recorded","output_tokens_recorded","model_calls","input_known_calls","output_known_calls"))
    require(vt == {"input_tokens":145764941,"cached_input_tokens":132534528,
                   "output_tokens":1491005,"total_tokens":147255946},
            f"Vanilla totals disagree with the 2026-10-29 audit: {vt}")
    require(at == {"input_tokens_recorded":281346935,"cached_tokens_recorded":184156928,
                   "output_tokens_recorded":4113476,"model_calls":1731,
                   "input_known_calls":1716,"output_known_calls":1716},
            f"AIVP totals disagree with the 2026-10-29 audit: {at}")
    require(sum(r["elapsed_is_estimate"] for r in v) == 10, "Vanilla time-estimate count must be exactly 10")
    require(len([r for r in c if r["category"] == "base"]) == 1731,
            "AIVP by_step model-call count did not match 1,731")
    # Schema supports incomplete token accounting: do not replace missing values with zero.
    DEST.mkdir(parents=True, exist_ok=True)
    files = {
        "vanilla-500.jsonl":v,
        "aivp-base-500.jsonl":a,
        "aivp-additional-22.jsonl":x,
        "aivp-model-calls.jsonl":c,
    }
    for name,rows in files.items():
        write_jsonl(DEST / name, rows)
    manifest = {
        "schema_version":1,
        "research_date":"2026-10-29",
        "dataset":"SWE-bench Verified (500)",
        "vanilla":{"issues":500,"resolved_reported":369,"tokens":vt,
                   "direct_monotonic_time_records":490,"estimated_filesystem_time_records":10,
                   "summed_task_elapsed_seconds":round(sum(r["elapsed_seconds"] for r in v),4),
                   "mean_task_elapsed_seconds":round(sum(r["elapsed_seconds"] for r in v)/500,4)},
        "aivp_base":{"issues":500,"resolved":405,"telemetry":at,
                     "duration_coverage":500,"mean_task_elapsed_seconds":round(sum(r["elapsed_seconds"] for r in a)/500,4),
                     "model_usage_missing_calls":15},
        "aivp_additional":{"records":22,"retry_records":15,"recovery_records":7,
                           "note":"Recovery includes a non-issue identifier, previous-results."},
        "excluded_e2e":{"records":2},
        "scope":"Per-issue/per-call NUMERIC telemetry; no raw traces, prompts, full command output, or source checkout.",
        "cost_semantics":"Recorded costs are PARTIAL, mostly Claude only; NOT complete billing or API-equivalent total.",
        "raw_source_policy":"Original logs remain local to Mac and are referenced by path relative to HOME and SHA256.",
        "source_of_truth_evaluation":"evaluation/aivp-v2-shadow-500/results.json + historical Vanilla reports + evaluation/vanilla-remaining-130/results-130.json",
        "files":{"rebuild_telemetry.py":{"sha256":sha256(DEST / "rebuild_telemetry.py")}},
    }
    for name in files:
        manifest["files"][name] = {"rows":len(files[name]),"sha256":sha256(DEST / name)}
    (DEST / "manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    (DEST / "README.md").write_text(
        "# SWE-bench Verified — Resource Telemetry Source of Truth (2026-10-29)\n\n"
        "Contains normalized, auditable per-issue and per-model-call observations for Vanilla 500 and AIVP 500, "
        "plus 22 AIVP retry/recovery records. The original Codex/Claude transcripts remain **local on Mac**.\n\n"
        "## Files\n\n"
        "- `vanilla-500.jsonl`: 500 Vanilla issues: input/cached/output tokens, 490 monotonic runner durations, "
        "10 filesystem-duration estimates (explicitly labeled).\n"
        "- `aivp-base-500.jsonl`: 500 AIVP issues: token, provider, timing, coverage, source SHA256.\n"
        "- `aivp-additional-22.jsonl`: 15 retry records and 7 recovery records (not 22 unique issues).\n"
        "- `aivp-model-calls.jsonl`: numeric call-level telemetry, including model/provider and missing values as null.\n"
        "- `manifest.json`: record counts, audited totals, completeness and SHA256.\n"
        "- `rebuild_telemetry.py`: extraction and audit code. Requires original local traces.\n\n"
        "## Measurement boundaries\n\n"
        "AIVP base contains 1,731 model calls, with token usage on 1,716 calls. 15 known missing calls are retained "
        "as missing data, not zero, and need not be reinvestigated. The `recorded_cost_usd_PARTIAL` field "
        "does NOT measure total inference spend. Do not add cached tokens to input tokens: cached input is a subset "
        "of input. `filesystem_birth_to_mtime_estimate` is NOT the same as monotonic runner timing. "
        "Agent generation time is NOT SWE-bench Docker evaluation time.\n\n"
        "## Rebuild\n\n"
        "On the original Mac, from this repo: `python3 evaluation/resource-telemetry-20261029/rebuild_telemetry.py`. "
        "The rebuild refuses to write outputs if issue IDs, expected row counts, or audited token totals differ.\n\n"
        "## Outcome sources\n\n"
        "See `../aivp-v2-shadow-500/`, `../vanilla-remaining-130/`, and historical per-batch evaluation directories. "
        "Reported resolved outcomes: Vanilla 369/500, AIVP 405/500. Ambiguous cases require separate grade review.\n",
        encoding="utf-8")
    hash_targets = ["README.md","rebuild_telemetry.py",*files.keys(),"manifest.json"]
    (DEST / "SHA256SUMS").write_text("".join(f"{sha256(DEST / name)}  {name}\n" for name in hash_targets),encoding="utf-8")
    print("=== TELEMETRY SNAPSHOT VERIFIED ===")
    print("Vanilla 500/500, total tokens:",vt["total_tokens"])
    print("AIVP base 500/500, input tokens:",at["input_tokens_recorded"])
    print("AIVP model calls:",at["model_calls"],"usage-known:",at["input_known_calls"])
    print("Additional AIVP runs:",len(x),"Excluded E2E:",len(excluded))
    print("Vanilla time: 490 monotonic + 10 estimated")
    print("Output:",DEST)
    print("NO RAW TRACES EXPORTED")

if __name__ == "__main__":
    main()
