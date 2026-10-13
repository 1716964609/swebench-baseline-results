import json
import os
import random
import shutil
import signal
import subprocess
import time

from collections import defaultdict
from pathlib import Path

from datasets import load_dataset

BASE = Path.home() / "swebench-play"
BATCH = BASE / "batch_11_40"

WORKSPACES = BATCH / "workspaces"
PROMPTS = BATCH / "prompts"
PATCHES = BATCH / "patches"
LOGS = BATCH / "logs"
STATUS = BATCH / "status"

for directory in [
    WORKSPACES, PROMPTS, PATCHES, LOGS, STATUS
]:
    directory.mkdir(parents=True, exist_ok=True)

TASK_FILE = BATCH / "tasks.json"
PREDICTIONS = BATCH / "predictions.jsonl"

MODEL = "gpt-5.6-terra"
REASONING = "medium"
TIMEOUT = 1800


# ============================================
# STEP 1: SELECT 30 VERIFIED TASKS
# ============================================

if TASK_FILE.exists():
    tasks = json.loads(TASK_FILE.read_text())

else:
    print("Loading SWE-bench Verified...", flush=True)

    dataset = load_dataset(
        "SWE-bench/SWE-bench_Verified",
        split="test"
    )

    # Exclude the previous 10 experiments.
    excluded = {"sympy__sympy-20590"}

    old_manifest = BASE / "batch_02_10/tasks.json"

    if old_manifest.exists():
        old_tasks = json.loads(old_manifest.read_text())

        excluded.update(
            task["instance_id"]
            for task in old_tasks
        )

    groups = defaultdict(list)

    for task in dataset:
        if task["instance_id"] not in excluded:
            groups[task["repo"]].append(task)

    rng = random.Random(20261012)

    for group in groups.values():
        rng.shuffle(group)

    repos = sorted(groups)
    selected = []

    # Round-robin across repositories.
    while len(selected) < 30:

        progress = False

        for repo in rng.sample(repos, len(repos)):
            if not groups[repo]:
                continue

            selected.append(groups[repo].pop())
            progress = True

            if len(selected) == 30:
                break

        if not progress:
            raise RuntimeError("Not enough eligible tasks")

    tasks = []

    for number, task in enumerate(selected, start=11):
        tasks.append({
            "number": number,
            "instance_id": task["instance_id"],
            "repo": task["repo"],
            "base_commit": task["base_commit"],
            "problem_statement": task["problem_statement"]
        })

    TASK_FILE.write_text(
        json.dumps(tasks, indent=2, ensure_ascii=False)
    )

print("\n===== SELECTED TASKS =====")

for task in tasks:
    print(
        f"#{task['number']} "
        f"{task['instance_id']}"
    )

print(f"\nTotal: {len(tasks)}")
print(f"Repositories: {len(set(t['repo'] for t in tasks))}")


# ============================================
# STEP 2: EXPORT COMPLETED PREDICTIONS
# ============================================

def export_predictions():
    predictions = []

    for task in tasks:
        instance_id = task["instance_id"]

        status_file = STATUS / f"{instance_id}.json"
        patch_file = PATCHES / f"{instance_id}.patch"

        if not status_file.exists() or not patch_file.exists():
            continue

        status = json.loads(status_file.read_text())

        if status.get("returncode") != 0:
            continue

        predictions.append({
            "instance_id": instance_id,
            "model_name_or_path": (
                "gpt-5.6-terra-codex-medium"
            ),
            "model_patch": patch_file.read_text()
        })

    temp = PREDICTIONS.with_suffix(".jsonl.tmp")

    with temp.open("w") as file:
        for prediction in predictions:
            file.write(
                json.dumps(prediction, ensure_ascii=False)
                + "\n"
            )

    temp.replace(PREDICTIONS)

    return predictions


export_predictions()


# ============================================
# STEP 3: RUN CODEX AGENTS SERIALLY
# ============================================

for task in tasks:

    number = task["number"]
    instance_id = task["instance_id"]

    workspace = WORKSPACES / instance_id
    prompt_file = PROMPTS / f"{instance_id}.txt"
    patch_file = PATCHES / f"{instance_id}.patch"
    status_file = STATUS / f"{instance_id}.json"

    events_file = LOGS / f"{instance_id}.events.jsonl"
    errors_file = LOGS / f"{instance_id}.stderr.log"

    # Skip successfully completed tasks on restart.
    if status_file.exists() and patch_file.exists():
        old_status = json.loads(status_file.read_text())

        if old_status.get("returncode") == 0:
            print(f"SKIP: {instance_id}", flush=True)
            continue

    print(
        f"\n===== TASK #{number}/40 =====",
        flush=True
    )
    print(instance_id, flush=True)

    # Guard against exhausting available disk space.
    free_gb = shutil.disk_usage(BASE).free / (1024 ** 3)

    if free_gb < 20:
        raise RuntimeError(
            f"Only {free_gb:.1f} GiB free. "
            "Stopping to protect disk space."
        )

    # Reset an interrupted workspace.
    # This directory is dedicated to this batch.
    if workspace.exists():
        shutil.rmtree(workspace)

    workspace.mkdir(parents=True)

    # Fetch only the historical base commit.
    subprocess.run(
        ["git", "init", "-q"],
        cwd=workspace,
        check=True
    )

    subprocess.run(
        [
            "git", "remote", "add", "origin",
            f"https://github.com/{task['repo']}.git"
        ],
        cwd=workspace,
        check=True
    )

    subprocess.run(
        [
            "git", "fetch",
            "--depth=1",
            "--filter=blob:none",
            "origin",
            task["base_commit"]
        ],
        cwd=workspace,
        check=True
    )

    subprocess.run(
        ["git", "checkout", "--detach", "-q", "FETCH_HEAD"],
        cwd=workspace,
        check=True
    )

    prompt = f"""
You are an autonomous software engineering agent.

Solve the following SWE-bench Verified issue.

Repository: {task['repo']}
Instance: {instance_id}

Rules:
- Investigate the repository independently.
- Identify the root cause.
- Implement the smallest correct fix.
- Run relevant tests when possible.
- Do not modify existing tests or test configurations.
- Do not commit changes.
- Do not consult original PRs, reference patches,
  remote Git history, or benchmark solutions.
- Do not search the web for the solution.
- Do not access other benchmark tasks.
- Do not modify files outside this repository.

ISSUE:

{task['problem_statement']}
"""

    prompt_file.write_text(prompt)

    command = [
        "codex", "exec",
        "--model", MODEL,
        "--config",
        f'model_reasoning_effort="{REASONING}"',
        "--config",
        "features.memories=false",
        "--sandbox", "workspace-write",
        "--json",
        "-"
    ]

    print("Starting fresh Codex Agent...", flush=True)

    started = time.monotonic()
    timed_out = False

    with (
        events_file.open("w") as events,
        errors_file.open("w") as errors
    ):
        process = subprocess.Popen(
            command,
            cwd=workspace,
            stdin=subprocess.PIPE,
            stdout=events,
            stderr=errors,
            text=True,
            start_new_session=True
        )

        try:
            process.communicate(
                input=prompt,
                timeout=TIMEOUT
            )

        except (subprocess.TimeoutExpired, KeyboardInterrupt) as exc:
            os.killpg(process.pid, signal.SIGTERM)
            process.wait()

            if isinstance(exc, KeyboardInterrupt):
                raise

            timed_out = True

    elapsed = round(time.monotonic() - started, 2)
    returncode = process.returncode

    # Include new files in the Git diff.
    subprocess.run(
        ["git", "add", "-N", "."],
        cwd=workspace,
        check=True
    )

    patch = subprocess.check_output(
        [
            "git", "diff", "--binary", "HEAD", "--",
            ".",
            ":(exclude,glob)**/tests/**",
            ":(exclude,glob)**/test_*.py",
            ":(exclude,glob)**/conftest.py"
        ],
        cwd=workspace
    )

    patch_file.write_bytes(patch)

    status_file.write_text(
        json.dumps({
            "instance_id": instance_id,
            "returncode": returncode,
            "timed_out": timed_out,
            "elapsed_seconds": elapsed,
            "patch_bytes": len(patch)
        }, indent=2)
    )

    predictions = export_predictions()

    print(
        f"Finished #{number}: "
        f"exit={returncode}, "
        f"time={elapsed:.1f}s, "
        f"patch={len(patch)} bytes",
        flush=True
    )

    print(
        f"Completed predictions: {len(predictions)}/30",
        flush=True
    )

    # Stop on execution errors instead of wasting quota.
    if returncode != 0:
        print(
            f"Codex execution failed. "
            f"Check {errors_file}. "
            "Rerun this script to retry.",
            flush=True
        )
        raise SystemExit(1)


# ============================================
# FINAL SUMMARY
# ============================================

predictions = export_predictions()

print("\n===== BATCH COMPLETE =====")
print(f"Predictions: {len(predictions)}/30")
print(
    "Non-empty patches:",
    sum(bool(p["model_patch"]) for p in predictions)
)
print(f"Output: {PREDICTIONS}")
