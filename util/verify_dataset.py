#!/usr/bin/env python3
import argparse
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any
import json_helpers
import env_helpers

from tqdm import tqdm

# BASE_DIR points to the root directory off the projecet
BASE_DIR = Path(__file__).resolve().parents[1]

# DEFAULT_INPUT_ROOT points to the samples with exit code 0 during the Env Debugging Step
# As environment configurations evolve during iterative debugging, modifications
# introduced to resolve failures in later samples may inadvertently
# break compatibility for earlier ones. Hence, we re-verify recorded samples even if they have an
# exit_code of 0, which is what this script does.
DEFAULT_INPUT_ROOT = BASE_DIR / "data" / "code_field_run_results_exit_code_0"
DEFAULT_OUTPUT_ROOT = BASE_DIR / "data" / "code_field_validation_results"
DEFAULT_ENV_CONFIG = BASE_DIR / "util" / "versicode_env_configs.json" # Path to our 4 defined environment configurations
DEFAULT_TIMEOUT = 30 # threshold to mark a sample as timed out

def run_command(command: list[str], *, cwd: Path | None = None):
    return subprocess.run(command, cwd=cwd, capture_output=True, text=True, check=False)

def parse_args():
    """
    Just adding args for the Python script
    """
    parser = argparse.ArgumentParser()
    # These arguments give you the option to change the default paths specified in the code block above
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--env-config", type=Path, default=DEFAULT_ENV_CONFIG)

    # You can change the default timeout here
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)

    # You can limit the execution to validating the first N samples from each JSON file
    # by changing this argument
    parser.add_argument("--limit", type=int, default=None)

    # Off by default. This overwrites existing validation result files
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()

def verify_sample(sample: dict[str, Any], timeout: int):
    """Main fxn in verify_dataset.pt. It takes a dataset sample, checks if it’s valid (Python code, has environment, etc), runs the 
    code in the correct Conda env then returns what happened (success, failure, timeout, skipped) + output and errors"""
    sample_id = sample.get("id")
    language = str(sample.get("language", "")).lower()
    run_result = sample.get("run_result", {})
    env_name = run_result.get("successful_env")
    code = sample.get("code")

    # We only support Python samples to limit the scope of this project
    if language != "python":
        return {
            "sample_id": sample_id,
            "status": "skipped",
            "reason": f"Unsupported language for Conda validation: {language or '<missing>'}",
            "env_name": env_name,
            "exit_code": None,
            "stdout": "",
            "stderr": "",
        }

    # If the code sample has no identified successful environments, we can't run it
    if not env_name:
        return {
            "sample_id": sample_id,
            "status": "skipped",
            "reason": "Missing `run_result.successful_env`.",
            "env_name": None,
            "exit_code": None,
            "stdout": "",
            "stderr": "",
        }


    # This block writes the sample’s code to a temporary file, runs it in the specified Conda environment, and handles timeouts safely
    with tempfile.TemporaryDirectory(prefix="versicode_verify_") as temp_dir:
        workdir = Path(temp_dir)
        file_path = workdir / "sample.py"
        file_path.write_text(code, encoding="utf-8")

        command = ["conda", "run", "-n", str(env_name), "python", str(file_path)]
        try:
            completed = subprocess.run(command, cwd=workdir, capture_output=True, text=True, timeout=timeout, check=False)
        except subprocess.TimeoutExpired as exc:
            return {
                "sample_id": sample_id,
                "status": "timeout",
                "reason": f"Timed out after {timeout} seconds.",
                "stdout": exc.stdout or "",
                "stderr": exc.stderr or "",
                "exit_code": None,
                "env_name": env_name,
            }

    # Return the final results for the sample
    return {
        "sample_id": sample_id,
        "status": "ok" if completed.returncode == 0 else "error",
        "reason": "" if completed.returncode == 0 else "Non-zero exit code during validation.",
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "exit_code": completed.returncode,
        "env_name": env_name,
    }

def build_validation_payload(samples: list[dict[str, Any]], timeout: int, dataset_path: Path):
    """
    Runs validation on all samples in a dataset, collects their results, and returns a summary plus detailed outputs. This fxn
    mainly calls verify_sample for each sample
    """
    results = []
    counts = {"ok": 0, "failed": 0, "skipped": 0} # possible status codes

    for sample in tqdm(samples, desc=dataset_path.name, unit="sample", leave=False):
        result = verify_sample(sample, timeout=timeout)
        results.append(result)

        if result["status"] == "ok": # ok
            counts["ok"] += 1
        elif result["status"] == "skipped": # skipped samples due to some issue
            counts["skipped"] += 1
        else:
            counts["failed"] += 1 # code did not successfully run
            print(
                f"Validation failed for {result.get('sample_id', '<unknown>')} "
                f"in env {result.get('env_name', '<unknown>')}: "
                f"status={result['status']} exit_code={result.get('exit_code')}"
            )

    payload = {
        "summary": {
            "dataset": str(dataset_path),
            "total": len(samples),
            "ok": counts["ok"],
            "failed": counts["failed"],
            "skipped": counts["skipped"],
            "timeout_seconds": timeout,
        },
        "data": results,
    }
    return payload, counts

def main():
    args = parse_args()
    # Resolve dataset paths
    input_root = args.input.resolve()
    output_root = args.output.resolve()
    env_config = args.env_config.resolve()

    # Get the JSON files present at the input direcotry path
    json_files = json_helpers.iter_json_files(input_root)
    if not json_files:
        raise FileNotFoundError(f"No JSON files found under {input_root}")

    required_env_names = env_helpers.collect_required_env_names(json_files, limit=args.limit)
    env_helpers.ensure_required_envs_exist(required_env_names, env_config)

    # Keep track of the number of samples for each possible outcome
    total_rows, total_ok, total_failed, total_skipped = 0, 0, 0, 0

    # Iterate all JSON dataset file categories. Each JSON file corresponds to one dataset category
    # e.g. for downstream_block, downstream_token, stackoverflow_token etc etc
    for json_path in json_files:
        output_path = json_helpers.output_path_for(json_path, input_root, output_root)
        if output_path.exists() and not args.overwrite:
            print(f"Skipping existing validation file: {output_path}")
            continue

        payload = json_helpers.load_json(json_path)
        samples = payload.get("data", [])
        if args.limit is not None:
            samples = samples[: args.limit]

        validation_payload, counts = build_validation_payload(samples=samples, timeout=args.timeout, dataset_path=json_path)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as handle:
            json.dump(validation_payload, handle, indent=2, ensure_ascii=False)

        total_rows += len(samples)
        total_ok += counts["ok"]
        total_failed += counts["failed"]
        total_skipped += counts["skipped"]

        print(f"{json_path} -> {output_path}: ok={counts['ok']}")
        print(f"failed={counts['failed']} skipped={counts['skipped']} total={len(samples)}")

    print(
        f"Done. validated={total_rows} ok={total_ok} failed={total_failed} "
        f"skipped={total_skipped}"
    )
    return 0 if total_failed == 0 else 1

if __name__ == "__main__":
    raise SystemExit(main())