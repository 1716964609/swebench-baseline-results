import json
import os
import random
import shutil
import signal
import subprocess
import threading
import time

from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

from datasets import load_dataset

ROOT = Path.home() / "swebench-play"
BATCH = ROOT / "batch_171_230"

WORK = BATCH / "workspaces"
PATCHES = BATCH / "patches"
PROMPTS = BATCH / "prompts"
LOGS = BATCH / "logs"
STATUS = BATCH / "status"

for directory in [WORK, PATCHES, PROMPTS, LOGS, STATUS]:
    directory.mkdir(parents=True, exist_ok=True)

TASK_FILE = BATCH / "tasks.json"
PREDICTIONS = BATCH / "predictions.jsonl"

MODEL = "gpt-5.6-terra"
EFFORT = "medium"
MAX_WORKERS = 10
TIMEOUT = 1800

STOP = threading.Event()
LOCK = threading.Lock()
RUNNING = {}


# ============================================
# STOP ACTIVE AGENTS ON CTRL+C
# ============================================

def stop_agents(signum, frame):
    STOP.set()

    print(
        "\nStopping active Codex agents...",
        flush=True
    )

    with LOCK:
        processes = list(RUNNING.values())

    for process in processes:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass


signal.signal(signal.SIGINT, stop_agents)


# ============================================
# SELECT 20 NEW VERIFIED TASKS
# ============================================

if TASK_FILE.exists():
    tasks = json.loads(TASK_FILE.read_text())

else:
    excluded = {"sympy__sympy-20590"}

    for previous_batch in [
        "batch_02_10",
        "batch_11_40",
        "batch_41_60",
        "batch_61_100",
        "batch_101_150",
        "batch_151_170",
    ]:
        manifest = ROOT / previous_batch / "tasks.json"

        if not manifest.exists():
            raise RuntimeError(
                f"Previous manifest missing: {manifest}"
            )

        previous_tasks = json.loads(manifest.read_text())

        excluded.update(
            task["instance_id"]
            for task in previous_tasks
        )

    if len(excluded) != 170:
        raise RuntimeError(
            f"Expected 170 previous tasks, found "
            f"{len(excluded)} unique IDs."
        )

    print(
        "Loading SWE-bench Verified...",
        flush=True
    )

    dataset = load_dataset(
        "SWE-bench/SWE-bench_Verified",
        split="test"
    )

    groups = defaultdict(list)

    for task in dataset:
        if task["instance_id"] not in excluded:
            groups[task["repo"]].append(task)

    rng = random.Random(20261017)

    for group in groups.values():
        rng.shuffle(group)

    selected = []

    while len(selected) < 60:
        available_repos = [
            repo for repo, group in groups.items()
            if group
        ]

        if not available_repos:
            raise RuntimeError(
                "Not enough unused Verified tasks."
            )

        for repo in rng.sample(
            available_repos,
            len(available_repos)
        ):
            selected.append(groups[repo].pop())

            if len(selected) == 60:
                break

    tasks = []

    for number, task in enumerate(selected, start=171):
        tasks.append({
            "number": number,
            "instance_id": task["instance_id"],
            "repo": task["repo"],
            "base_commit": task["base_commit"],
            "problem_statement": task["problem_statement"]
        })

    TASK_FILE.write_text(
        json.dumps(
            tasks,
            indent=2,
            ensure_ascii=False
        )
    )


print("\n===== SELECTED TASKS =====")

for task in tasks:
    print(
        f"#{task['number']} "
        f"{task['instance_id']}"
    )

print(f"\nTotal: {len(tasks)}")
print(
    "Repositories:",
    len(set(t["repo"] for t in tasks))
)


# ============================================
# RECORD EXPERIMENT CONFIGURATION
# ============================================

version = subprocess.run(
    ["codex", "--version"],
    capture_output=True,
    text=True,
    check=True
).stdout.strip()

metadata = {
    "model": MODEL,
    "reasoning_effort": EFFORT,
    "codex_version": version,
    "max_workers": MAX_WORKERS,
    "timeout_seconds": TIMEOUT,
    "created_or_resumed_at": datetime.now(
        timezone.utc
    ).isoformat()
}

(BATCH / "execution_metadata.json").write_text(
    json.dumps(metadata, indent=2)
)

print(f"\nCodex: {version}")
print(f"Concurrent agents: {MAX_WORKERS}")


# ============================================
# COLLECT PREDICTIONS
# CALLED ONLY BY MAIN THREAD
# ============================================

def export_predictions():
    predictions = []

    for task in tasks:
        instance_id = task["instance_id"]

        status_file = STATUS / f"{instance_id}.json"
        patch_file = PATCHES / f"{instance_id}.patch"

        if not status_file.exists():
            continue

        if not patch_file.exists():
            continue

        status = json.loads(
            status_file.read_text()
        )

        if status.get("returncode") != 0:
            continue

        predictions.append({
            "instance_id": instance_id,
            "model_name_or_path":
                "gpt-5.6-terra-codex-medium",
            "model_patch": patch_file.read_text()
        })

    temp = BATCH / "predictions.jsonl.tmp"

    with temp.open("w") as file:
        for prediction in predictions:
            file.write(
                json.dumps(
                    prediction,
                    ensure_ascii=False
                ) + "\n"
            )

    os.replace(temp, PREDICTIONS)

    return predictions


# ============================================
# ONE INDEPENDENT CODEX AGENT
# ============================================

def run_task(task):
    instance_id = task["instance_id"]
    number = task["number"]

    workspace = WORK / instance_id

    prompt_file = PROMPTS / f"{instance_id}.txt"
    patch_file = PATCHES / f"{instance_id}.patch"
    status_file = STATUS / f"{instance_id}.json"

    events_file = LOGS / f"{instance_id}.events.jsonl"
    errors_file = LOGS / f"{instance_id}.stderr.log"
    fetch_file = LOGS / f"{instance_id}.git.log"

    if STOP.is_set():
        return instance_id, "STOPPED"

    # Resume: skip completed tasks.
    if status_file.exists() and patch_file.exists():
        status = json.loads(status_file.read_text())

        if status.get("returncode") == 0:
            return instance_id, "SKIPPED"

    print(
        f"START #{number}: {instance_id}",
        flush=True
    )

    started = time.monotonic()

    try:
        free_gb = (
            shutil.disk_usage(ROOT).free / (1024 ** 3)
        )

        if free_gb < 20:
            raise RuntimeError(
                f"Low disk space: {free_gb:.1f} GiB"
            )

        # Dedicated workspace.
        if workspace.exists():
            shutil.rmtree(workspace)

        workspace.mkdir(parents=True)

        with fetch_file.open("w") as fetch_log:

            subprocess.run(
                ["git", "init", "-q"],
                cwd=workspace,
                check=True,
                stdout=fetch_log,
                stderr=subprocess.STDOUT
            )

            subprocess.run(
                [
                    "git", "remote", "add", "origin",
                    f"https://github.com/{task['repo']}.git"
                ],
                cwd=workspace,
                check=True,
                stdout=fetch_log,
                stderr=subprocess.STDOUT
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
                check=True,
                stdout=fetch_log,
                stderr=subprocess.STDOUT
            )

            subprocess.run(
                [
                    "git", "checkout",
                    "--detach", "-q", "FETCH_HEAD"
                ],
                cwd=workspace,
                check=True,
                stdout=fetch_log,
                stderr=subprocess.STDOUT
            )

        if STOP.is_set():
            return instance_id, "STOPPED"

        prompt = f"""
You are an autonomous software engineering agent.

Solve this SWE-bench Verified issue.

Repository: {task['repo']}
Instance: {instance_id}

Instructions:
- Investigate the repository independently.
- Identify the root cause.
- Implement the smallest correct fix.
- Run relevant tests when possible.
- Do not modify existing tests or test configurations.
- Do not commit changes.
- Do not access original PRs or reference solutions.
- Do not access remote Git history.
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
            f'model_reasoning_effort="{EFFORT}"',
            "--config",
            "features.memories=false",
            "--sandbox", "workspace-write",
            "--json",
            "-"
        ]

        with (
            events_file.open("w") as events,
            errors_file.open("w") as errors
        ):
            with LOCK:
                if STOP.is_set():
                    return instance_id, "STOPPED"

                process = subprocess.Popen(
                    command,
                    cwd=workspace,
                    stdin=subprocess.PIPE,
                    stdout=events,
                    stderr=errors,
                    text=True,
                    start_new_session=True
                )

                RUNNING[instance_id] = process

            try:
                try:
                    process.communicate(
                        input=prompt,
                        timeout=TIMEOUT
                    )

                except subprocess.TimeoutExpired:
                    os.killpg(
                        process.pid,
                        signal.SIGTERM
                    )

                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        os.killpg(
                            process.pid,
                            signal.SIGKILL
                        )
                        process.wait()

            finally:
                with LOCK:
                    RUNNING.pop(instance_id, None)

        returncode = process.returncode

        # Capture production changes.
        # Keep the same test exclusion as previous batches.
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

        elapsed = round(
            time.monotonic() - started,
            2
        )

        status_file.write_text(
            json.dumps({
                "instance_id": instance_id,
                "returncode": returncode,
                "elapsed_seconds": elapsed,
                "patch_bytes": len(patch),
                "codex_version": version
            }, indent=2)
        )

        if returncode != 0:
            STOP.set()

            return (
                instance_id,
                f"FAILED exit={returncode}"
            )

        return (
            instance_id,
            f"OK {elapsed:.1f}s "
            f"patch={len(patch)} bytes"
        )

    except Exception as exc:
        status_file.write_text(
            json.dumps({
                "instance_id": instance_id,
                "returncode": 999,
                "error": repr(exc)
            }, indent=2)
        )

        STOP.set()

        return instance_id, f"ERROR: {exc}"


# ============================================
# RUN 3 AGENTS IN PARALLEL
# ============================================

export_predictions()

print("\n===== PARALLEL EXECUTION =====")
print("Workers: 10")
print("Tasks: 60")
print("==============================\n")

with ThreadPoolExecutor(
    max_workers=MAX_WORKERS
) as executor:

    futures = [
        executor.submit(run_task, task)
        for task in tasks
    ]

    for future in as_completed(futures):
        instance_id, outcome = future.result()

        predictions = export_predictions()

        print(
            f"FINISH {instance_id}: {outcome}"
            f" | saved={len(predictions)}/60",
            flush=True
        )


# ============================================
# FINAL REPORT
# ============================================

predictions = export_predictions()

print("\n===== BATCH COMPLETE =====")
print(f"Predictions: {len(predictions)}/60")
print(
    "Non-empty patches:",
    sum(bool(p["model_patch"]) for p in predictions)
)
print(f"Output: {PREDICTIONS}")

if len(predictions) != 60:
    raise SystemExit(
        "Batch incomplete. Rerun the same command "
        "to resume unfinished tasks."
    )
