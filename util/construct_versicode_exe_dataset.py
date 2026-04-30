#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parents[1]

DEFAULT_ORIGINAL_ROOT = BASE_DIR / "data" / "VersiCode_Benchmark"
DEFAULT_VALIDATION_ROOT = BASE_DIR / "data" / "code_field_validation_results"
DEFAULT_OUTPUT_ROOT = BASE_DIR / "data" / "VersiCode_Exe"

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--original-root",
        type=Path,
        default=DEFAULT_ORIGINAL_ROOT,
        help="Root directory containing the original VersiCode benchmark JSON files.",
    )
    parser.add_argument(
        "--validation-root",
        type=Path,
        default=DEFAULT_VALIDATION_ROOT,
        help="Root directory containing validation result JSON files.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_OUTPUT_ROOT,
        help="Root directory where constructed VersiCode-Exe JSON files will be written.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing output files.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail if a validation file has no matching original benchmark file.",
    )
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def iter_validation_files(root: Path) -> list[Path]:
    return sorted(root.rglob("*.json"))

def build_original_index(samples: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for sample in samples:
        sample_id = sample.get("id")
        if isinstance(sample_id, str):
            index[sample_id] = sample
    return index

def build_run_result(validation_item: dict[str, Any]) -> dict[str, Any]:
    env_name = validation_item.get("env_name")
    stdout = validation_item.get("stdout", "")
    stderr = validation_item.get("stderr", "")
    exit_code = validation_item.get("exit_code")
    timeout = validation_item.get("status") == "timeout"

    return {
        "status": validation_item.get("status"),
        "stdout": stdout,
        "stderr": stderr,
        "exit_code": exit_code,
        "timeout": timeout,
        "successful_env": env_name,
        "attempts": [
            {
                "env_name": env_name,
                "stdout": stdout,
                "stderr": stderr,
                "exit_code": exit_code,
                "timeout": timeout,
            }
        ],
    }


def construct_output_payload(
    original_payload: dict[str, Any], validation_payload: dict[str, Any], original_path: Path
) -> dict[str, Any]:
    original_samples = original_payload.get("data", [])
    validation_items = validation_payload.get("data", [])
    original_index = build_original_index(original_samples)

    kept_samples: list[dict[str, Any]] = []
    missing_ids: list[str] = []

    for item in validation_items:
        if item.get("status") != "ok":
            continue

        sample_id = item.get("sample_id")
        if not isinstance(sample_id, str):
            continue

        original_sample = original_index.get(sample_id)
        if original_sample is None:
            missing_ids.append(sample_id)
            continue

        combined_sample = dict(original_sample)
        combined_sample["run_result"] = build_run_result(item)
        kept_samples.append(combined_sample)

    summary = {
        "original_dataset": str(original_path),
        "original_total": len(original_samples),
        "validated_total": int(validation_payload.get("summary", {}).get("total", 0)),
        "validated_ok": len(kept_samples),
        "validated_failed": int(validation_payload.get("summary", {}).get("failed", 0)),
        "validated_skipped": int(validation_payload.get("summary", {}).get("skipped", 0)),
        "missing_original_ids": missing_ids,
    }

    return {"summary": summary, "data": kept_samples}


def main() -> int:
    args = parse_args()
    original_root = args.original_root.resolve()
    validation_root = args.validation_root.resolve()
    output_root = args.output_root.resolve()

    validation_files = iter_validation_files(validation_root)
    if not validation_files:
        raise FileNotFoundError(f"No validation JSON files found under {validation_root}")

    written = 0
    skipped_missing_original = 0
    total_kept = 0

    for validation_path in validation_files:
        relative_path = validation_path.relative_to(validation_root)
        original_path = original_root / relative_path
        output_path = output_root / relative_path

        if not original_path.exists():
            message = f"Missing original benchmark file for {relative_path}: {original_path}"
            if args.strict:
                raise FileNotFoundError(message)
            print(f"Skipping: {message}")
            skipped_missing_original += 1
            continue

        if output_path.exists() and not args.overwrite:
            print(f"Skipping existing output file: {output_path}")
            continue

        original_payload = load_json(original_path)
        validation_payload = load_json(validation_path)
        output_payload = construct_output_payload(
            original_payload=original_payload,
            validation_payload=validation_payload,
            original_path=original_path,
        )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as handle:
            json.dump(output_payload, handle, indent=2, ensure_ascii=False)

        kept = len(output_payload.get("data", []))
        total_kept += kept
        written += 1
        print(
            f"{validation_path} -> {output_path}: kept {kept} validated-ok sample(s)"
        )

        missing_ids = output_payload.get("summary", {}).get("missing_original_ids", [])
        if missing_ids:
            print(
                f"Warning: {len(missing_ids)} validated sample_id(s) were not found "
                f"in the original dataset for {relative_path}"
            )

    print(
        f"Done. wrote={written} skipped_missing_original={skipped_missing_original} "
        f"total_kept={total_kept}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())