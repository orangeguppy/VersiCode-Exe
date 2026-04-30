#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
from typing import Any
from tqdm import tqdm

import json_helpers
import env_helpers
import processing_helpers
import code_execution_helpers

# BASE_DIR points to the root directory off the projecet
BASE_DIR = Path(__file__).resolve().parents[1]

# DEFAULT_BENCHMARK_ROOT points to the provided JSON dataset files from the original VersiCode repository
DEFAULT_BENCHMARK_ROOT = BASE_DIR  / "data" / "VersiCode_Benchmark"
DEFAULT_OUTPUT_ROOT = BASE_DIR / "data" / "code_field_run_results"
DEFAULT_ENV_CONFIG = BASE_DIR / "util" / "versicode_env_configs.json"

MAX_SUCCESSFUL_SAMPLES_PER_DATASET_FILE = 20
DATASET_PATHS_TO_SKIP_CONDA_ENV_TESTING = { 
    # Paths are relative to DEFAULT_BENCHMARK_ROOT.
    # Example:
    # "code_completion/downstream_application_code/downstream_application_code_block.json",
    # "code_completion/downstream_application_code/downstream_application_code_line.json",
    # "code_completion/downstream_application_code/downstream_application_code_token.json",
    # "code_completion/library_source_code/library_source_code_block.json",
}

def parse_args():
    parser = argparse.ArgumentParser(description="Execute the raw `code` field for VersiCode samples.")
    # Specifies either the JSON root direcotry or the exact poath to a JSON dataset file
    parser.add_argument("--input", type=Path, default=DEFAULT_BENCHMARK_ROOT)

    # Output dir of the results output
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_ROOT)

    # Specify the sample languages to include. Technically this option exists, but in reality we only run on
    # Python samples
    parser.add_argument("--language", action="append", dest="languages")
    parser.add_argument("--limit", type=int, default=None) # Only run the first N samples from each dataset file
    parser.add_argument("--timeout", type=int, default=15) # Threshold to define a sample has timed out
    parser.add_argument("--overwrite", action="store_true") # Overwrite existing result files instead of resuming from them
    parser.add_argument("--env-config", type=Path, default=DEFAULT_ENV_CONFIG) # Points to the defined 4 env configs
    return parser.parse_args()

def dataset_relative_path(dataset_path: Path, input_root: Path):
    """
    Returns the dataset's path relative to a base directory, fall back to just the filename if needed.
    """
    try:
        return dataset_path.relative_to(input_root)
    except ValueError:
        try:
            return dataset_path.relative_to(DEFAULT_BENCHMARK_ROOT)
        except ValueError:
            return Path(dataset_path.name)

def should_skip_conda_env_testing(dataset_path: Path, input_root: Path):
    """
    Checks whether a dataset file should skip Conda environment testing based on the skip list, defined in DATASET_PATHS_TO_SKIP_ENV_TESTING
    """
    if not DATASET_PATHS_TO_SKIP_CONDA_ENV_TESTING:
        return False

    relative_path = dataset_relative_path(dataset_path, input_root)
    return str(relative_path).replace("\\", "/") in DATASET_PATHS_TO_SKIP_CONDA_ENV_TESTING

def run_dataset_file(dataset_path, input_root, output_root, languages, limit, timeout: int, overwrite: bool, python_env_names: list[str]):
    """
    run_dataset_file loads one dataset file, executes each sample in the dataset file, writes results to an output JSON file, and 
    returns how many samples were run or skipped
    """
    # Load the JSON dataset file
    source_data = json_helpers.load_json(dataset_path)

    # Get a list of the samples in the dataset file
    samples = source_data.get("data", [])

    # Limit the number of samples to execute if specified
    if limit is not None:
        samples = samples[:limit]

    # Declare the output path to store the results JSON
    output_path = json_helpers.output_path_for(dataset_path, input_root, output_root)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Checks whether a dataset file should skip Conda environment testing based on the skip list,
    # defined in DATASET_PATHS_TO_SKIP_ENV_TESTING
    skip_conda_env_testing = should_skip_conda_env_testing(dataset_path, input_root)
    if skip_conda_env_testing:
        print(f"Skipping dataset without execution: {dataset_relative_path(dataset_path, input_root)}")
        return 0, len(samples), output_path

    # Loads previous results if not overwriting and builds a lookup table to avoid re-running samples that were already processed
    existing = None if overwrite else json_helpers.load_existing_results(output_path)
    existing_by_id = {}
    if existing:
        for sample in existing.get("data", []):
            sample_id = sample.get("id")
            if sample_id is not None:
                existing_by_id[sample_id] = sample

    results = {"data": []} # store output results here
    ran, successful, skipped = 0, 0, 0 # counter variables

    # Iterate each sample in this dataset JSON file
    for sample in tqdm(samples, desc=dataset_path.name, unit="sample", leave=False):
        sample_id = sample.get("id")
        language = str(sample.get("language", "")).lower()

        # Do not run unsupported languages
        if languages and language not in languages:
            skipped += 1
            continue

        # If the sample has been run before, don't run it again
        if sample_id in existing_by_id:
            results["data"].append(existing_by_id[sample_id])
            continue

        sample_result = dict(sample)
        # Main fxn here: Execute the code in each of the environments
        sample_result["run_result"] = code_execution_helpers.execute_code(sample, timeout, python_env_names, skip_conda_env_testing=skip_conda_env_testing)
        
        # Mark if the code failed in all environments
        if (not sample_result["run_result"].get("skipped_conda_env_testing") and sample_result["run_result"].get("successful_env") is None):
            print(
                "All envs failed for sample "
                f"{sample_result.get('id', '<unknown>')}:\n"
                f"{json.dumps(sample_result['run_result'].get('attempts', []), ensure_ascii=False, indent=2)}"
            )
        
        # Mark if a sample was skipped
        elif sample_result["run_result"].get("skipped_conda_env_testing") and sample_result["run_result"].get("status") != "ok":
            print(
                "Skipped conda env testing for sample "
                f"{sample_result.get('id', '<unknown>')} and local execution failed:\n"
                f"{sample_result['run_result'].get('stderr', '')}"
            )

        results["data"].append(sample_result)
        ran += 1
        if sample_result["run_result"].get("exit_code") == 0:
            successful += 1

        json_helpers.write_json_atomic(output_path, results)

    json_helpers.write_json_atomic(output_path, results)

    return ran, skipped, output_path

def main():
    args = parse_args()
    input_path = args.input.resolve()
    output_root = args.output_dir.resolve()
    languages = processing_helpers.normalize_languages(args.languages)
    python_env_names = env_helpers.load_python_env_names(args.env_config.resolve())

    dataset_files = json_helpers.iter_json_files(input_path)
    if not dataset_files:
        raise FileNotFoundError(f"No JSON files found under {input_path}")

    total_ran, total_skipped = 0, 0
    dataset_progress = tqdm(dataset_files, desc="Datasets", unit="file") # iterate all dataset files
    for dataset_path in dataset_progress:
        ran, skipped, output_path = run_dataset_file(dataset_path=dataset_path, input_root=input_path, output_root=output_root, languages=languages, limit=args.limit,
            timeout=args.timeout, overwrite=args.overwrite, python_env_names=python_env_names)
        total_ran += ran
        total_skipped += skipped
        dataset_progress.set_postfix(ran=total_ran, filtered=total_skipped)
        print(f"{dataset_path}: ran {ran} sample(s), filtered {skipped}, saved to {output_path}")

    print(f"Done. Ran {total_ran} sample(s); filtered {total_skipped} sample(s).")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())