#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_INPUT_ROOT = Path(__file__).resolve().parents[1] / "data" / "code_field_run_results"
DEFAULT_OUTPUT_ROOT = (
    Path(__file__).resolve().parents[1] / "data" / "code_field_run_results_exit_code_0"
)
DEFAULT_ENV_CONFIG = Path(__file__).resolve().with_name("versicode_env_configs.json")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Mirror code_field_run_results into a new directory tree while keeping only "
            "samples whose run_result.exit_code == 0."
        )
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT_ROOT,
        help="Input directory containing run result JSON files.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_ROOT,
        help="Output directory for filtered JSON files.",
    )
    parser.add_argument(
        "--env-config",
        type=Path,
        default=DEFAULT_ENV_CONFIG,
        help="JSON manifest listing the Conda environments that count as valid successes.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing filtered files.",
    )
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def iter_json_files(input_root: Path) -> list[Path]:
    return sorted(input_root.rglob("*.json"))


def load_valid_env_names(config_path: Path) -> set[str]:
    config = load_json(config_path)
    environments = config.get("environments", [])
    return {
        env["name"]
        for env in environments
        if isinstance(env, dict) and env.get("name")
    }


def has_success_in_valid_env(
    run_result: dict[str, Any], valid_env_names: set[str]
) -> bool:
    successful_env = run_result.get("successful_env")
    if successful_env in valid_env_names:
        return True

    attempts = run_result.get("attempts", [])
    if not isinstance(attempts, list):
        return False

    for attempt in attempts:
        if not isinstance(attempt, dict):
            continue
        if (
            attempt.get("env_name") in valid_env_names
            and attempt.get("exit_code") == 0
        ):
            return True
    return False


def filter_successes(
    samples: list[dict[str, Any]], valid_env_names: set[str]
) -> list[dict[str, Any]]:
    kept = []
    for sample in samples:
        run_result = sample.get("run_result", {})
        if (
            run_result.get("exit_code") == 0
            and has_success_in_valid_env(run_result, valid_env_names)
        ):
            kept.append(sample)
    return kept


def main() -> int:
    args = parse_args()
    input_root = args.input.resolve()
    output_root = args.output.resolve()
    valid_env_names = load_valid_env_names(args.env_config.resolve())

    json_files = iter_json_files(input_root)
    if not json_files:
        raise FileNotFoundError(f"No JSON files found under {input_root}")

    total_in = 0
    total_kept = 0

    for input_path in json_files:
        relative_path = input_path.relative_to(input_root)
        output_path = output_root / relative_path

        if output_path.exists() and not args.overwrite:
            print(f"Skipping existing file: {output_path}")
            continue

        payload = load_json(input_path)
        samples = payload.get("data", [])
        filtered_samples = filter_successes(samples, valid_env_names)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as handle:
            json.dump({"data": filtered_samples}, handle, indent=2, ensure_ascii=False)

        total_in += len(samples)
        total_kept += len(filtered_samples)
        print(
            f"{input_path} -> {output_path}: kept {len(filtered_samples)} / {len(samples)}"
        )

    print(f"Done. Kept {total_kept} / {total_in} sample(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
