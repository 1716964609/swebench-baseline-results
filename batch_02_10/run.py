import json
import subprocess
from pathlib import Path

ROOT = Path.home() / "swebench-play"
BATCH = ROOT / "batch_02_10"

tasks = json.loads(
    (BATCH / "tasks.json").read_text()
)

predictions = []

for task in tasks:
    number = task["number"]
    instance_id = task["instance_id"]

    workspace = BATCH / "workspaces" / instance_id
    prompt_file = BATCH / "prompts" / f"{instance_id}.txt"
    event_file = BATCH / "logs" / f"{instance_id}.jsonl"
    error_file = BATCH / "logs" / f"{instance_id}.stderr.log"
    patch_file = BATCH / "patches" / f"{instance_id}.patch"
    status_file = BATCH / "logs" / f"{instance_id}.status.json"

    print(
        f"\n===== TASK #{number}/10: {instance_id} =====",
        flush=True
    )

    # Prepare an isolated historical checkout.
    if not (workspace / ".git").exists():
        workspace.mkdir(parents=True, exist_ok=True)

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

        # Fetch only the historical base commit.
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
            ["git", "checkout", "-q", "--detach", "FETCH_HEAD"],
            cwd=workspace,
            check=True
        )

    head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=workspace,
        text=True
    ).strip()

    if head != task["base_commit"]:
        raise RuntimeError(f"Incorrect base commit: {instance_id}")

    # Never resume a previous Codex session.
    if not status_file.exists():
        print("Starting fresh Codex Agent...", flush=True)

        command = [
            "codex", "exec",
            "--model", "gpt-5.6-terra",
            "--config", 'model_reasoning_effort="medium"',
            "--config", "features.memories=false",
            "--sandbox", "workspace-write",
            "--json",
            "-"
        ]

        with (
            prompt_file.open("r", encoding="utf-8") as prompt,
            event_file.open("w", encoding="utf-8") as events,
            error_file.open("w", encoding="utf-8") as errors
        ):
            try:
                result = subprocess.run(
                    command,
                    cwd=workspace,
                    stdin=prompt,
                    stdout=events,
                    stderr=errors,
                    timeout=1800
                )
                returncode = result.returncode
            except subprocess.TimeoutExpired:
                returncode = 124

        # Keep the outcome, including unsuccessful attempts.
        status_file.write_text(
            json.dumps({"returncode": returncode})
        )

        if returncode != 0:
            print(
                f"Codex failed: {returncode}. "
                f"Check {error_file}",
                flush=True
            )

        # Capture production-code changes, excluding test files.
        subprocess.run(
            ["git", "add", "-N", "."],
            cwd=workspace,
            check=True
        )

        patch = subprocess.check_output(
            [
                "git", "diff", "--binary", "--", ".",
                ":(exclude,glob)**/tests/**",
                ":(exclude,glob)**/test_*.py",
                ":(exclude,glob)**/conftest.py"
            ],
            cwd=workspace
        )

        patch_file.write_bytes(patch)

    patch = (
        patch_file.read_text(encoding="utf-8")
        if patch_file.exists()
        else ""
    )

    predictions.append({
        "instance_id": instance_id,
        "model_name_or_path": "gpt-5.6-terra-codex-medium",
        "model_patch": patch
    })

    print(
        f"Finished #{number}. Patch bytes: "
        f"{len(patch.encode('utf-8'))}",
        flush=True
    )

# Export all 9 predictions.
output = BATCH / "predictions.jsonl"

with output.open("w", encoding="utf-8") as file:
    for prediction in predictions:
        file.write(
            json.dumps(prediction, ensure_ascii=False) + "\n"
        )

print("\n===== BATCH COMPLETE =====")
print(f"Predictions: {len(predictions)}")
print(f"Non-empty patches: {sum(bool(p['model_patch']) for p in predictions)}")
print(f"Output: {output}")
