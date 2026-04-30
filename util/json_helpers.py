from pathlib import Path
from typing import Any
import json
import tempfile
import os

def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)

def iter_json_files(input_path: Path) -> list[Path]:
    """ This fxn will return whatever JSON files in the input path, regardless of
    whether the input path points to a single JSON file or a directory containing JSONs"""
    if input_path.is_file():
        return [input_path]
    return sorted(input_path.rglob("*.json"))

def output_path_for(dataset_path: Path, input_root: Path, output_root: Path):
    """Takes an input file (dataset_path) and maps it to a corresponding output path inside 
    output_root, while preserving folder structure"""
    if input_root.is_file():
        relative_path = Path(dataset_path.name)
    else:
        relative_path = dataset_path.relative_to(input_root)
    return output_root / relative_path

def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        temp_path = Path(handle.name)
    os.replace(temp_path, path)

def load_existing_results(path: Path):
    if not path.exists():
        return None
    try:
        return load_json(path)
    except json.JSONDecodeError as exc:
        print(
            f"Warning: ignoring malformed existing results file {path}: "
            f"{exc.msg} at line {exc.lineno} column {exc.colno}"
        )
        return None
    
def iter_validation_files(root: Path) -> list[Path]:
    return sorted(root.rglob("*.json"))