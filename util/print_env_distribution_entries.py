#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
from typing import Any

import json_helpers
import env_helpers

BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_INPUT_ROOT = BASE_DIR / "data" / "code_field_validation_results"
DEFAULT_ENV_CONFIG = BASE_DIR / "util" / "versicode_env_configs.json"

# This is an important data object that helps to
# definee the table rows and which dataset file corresponds to each row
DEFAULT_ROW_SPECS = [
    (
        "Downstream App. Code (block)",
        "code_completion/downstream_application_code/downstream_application_code_block.json",
    ),
    (
        "Downstream App. Code (line)",
        "code_completion/downstream_application_code/downstream_application_code_line.json",
    ),
    (
        "Downstream App. Code (token)",
        "code_completion/downstream_application_code/downstream_application_code_token.json",
    ),
    (
        "Library Source Code (block)",
        "code_completion/library_source_code/library_source_code_block.json",
    ),
    (
        "Library Source Code (line)",
        "code_completion/library_source_code/library_source_code_line.json",
    ),
    (
        "Library Source Code (token)",
        "code_completion/library_source_code/library_source_code_token.json",
    ),
    (
        "StackOverflow (block)",
        "code_completion/stackoverflow/python/stackoverflow_block.json",
    ),
    (
        "StackOverflow (line)",
        "code_completion/stackoverflow/python/stackoverflow_line.json",
    ),
    (
        "StackOverflow (token)",
        "code_completion/stackoverflow/python/stackoverflow_token.json",
    ),
]

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    # This points to the root directory containing validation result JSON files
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT_ROOT)
    
    # Points to the env config specification
    parser.add_argument("--env-config", type=Path, default=DEFAULT_ENV_CONFIG)

    # Number of decimal places for numbers
    parser.add_argument("--decimals", type=int, default=1)
    return parser.parse_args()

def format_entry(count: int, total: int, decimals: int):
    # Compute the percentages to fill the table
    percentage = 0.0 if total == 0 else (count / total) * 100
    return f"{count} ({percentage:.{decimals}f}%)"

def summarize_file(path: Path, env_names: list[str]):
    """
    Reads one JSON file and counts how many successful samples came from each env
    """
    payload = json_helpers.load_json(path)
    summary = payload.get("summary", {})
    total = int(summary.get("total", 0))
    ok_count = 0
    env_counts = {env_name: 0 for env_name in env_names}

    for item in payload.get("data", []):
        if item.get("status") != "ok":
            continue
        ok_count += 1
        env_name = item.get("env_name")
        if env_name in env_counts:
            env_counts[env_name] += 1

    return total, env_counts, ok_count

def build_rows(input_root: Path, env_names: list[str]):
    """Create horizontal lines of the table, each row corresponding to a dataset JSON category"""
    rows: list[list[str]] = []
    totals_per_env = [0 for _ in env_names]
    row_denominators: list[int] = []

    for label, relative_path in DEFAULT_ROW_SPECS:
        json_path = input_root / relative_path
        total, env_counts, _ = summarize_file(json_path, env_names)
        row_denominators.append(total)
        rows.append([label] + [str(env_counts[env_name]) for env_name in env_names])
        for index, env_name in enumerate(env_names):
            totals_per_env[index] += env_counts[env_name]

    return rows, totals_per_env, row_denominators


def print_table(input_root: Path, env_names: list[str], decimals: int):
    """
    For each dataset, it reads the dataset JSON file, counts successes per env, then converts to percentages. Then, it
    prints a nicely formatted table
    """
    header = ["Category", *env_names]
    rows: list[list[str]] = []
    total_denominator = 0
    totals_per_env = [0 for _ in env_names]

    for label, relative_path in DEFAULT_ROW_SPECS:
        json_path = input_root / relative_path
        total, env_counts, ok_count = summarize_file(json_path, env_names)
        total_denominator += total

        row = [label]
        for index, env_name in enumerate(env_names):
            count = env_counts[env_name]
            totals_per_env[index] += count
            row.append(format_entry(count, total, decimals))
        rows.append(row)

        if ok_count != sum(env_counts.values()):
            raise ValueError(
                f"Found successful samples in unknown environments for {json_path}."
            )

    total_row = ["Total"]
    for count in totals_per_env:
        total_row.append(format_entry(count, total_denominator, decimals))
    rows.append(total_row)

    widths = [len(column) for column in header]
    for row in rows:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], len(cell))

    def render(row: list[str]) -> str:
        return " | ".join(cell.ljust(widths[index]) for index, cell in enumerate(row))

    print(render(header))
    print("-+-".join("-" * width for width in widths))
    for row in rows:
        print(render(row))


def main():
    args = parse_args()
    input_root = args.input.resolve()
    env_names = env_helpers.load_env_names(args.env_config.resolve())

    if not env_names:
        raise ValueError("No environment names found in the environment config.")

    print_table(input_root=input_root, env_names=env_names, decimals=args.decimals)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
