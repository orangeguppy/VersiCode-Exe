import sys
import subprocess
from pathlib import Path
import processing_helpers
from typing import Any
import tempfile

def command_for_language(language: str, code: str, workdir: Path):
    language = language.lower()
    if language == "python":
        file_path = workdir / "sample.py"
        file_path.write_text(code, encoding="utf-8")
        return [sys.executable, str(file_path)], file_path, None

def execute_code_in_python_envs(code: str, workdir: Path, file_path: Path, env_names: list[str], timeout: int):
    attempts = []
    for env_name in env_names:
        command = ["conda", "run", "-n", env_name, "python", str(file_path)]
        try:
            completed = subprocess.run(command, cwd=workdir,capture_output=True, text=True, timeout=timeout, check=False)
            attempt = {
                "env_name": env_name,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
                "exit_code": completed.returncode,
                "timeout": False,
            }
            attempts.append(attempt)
            if completed.returncode == 0:
                return {
                    "status": "ok",
                    "stdout": completed.stdout,
                    "stderr": completed.stderr,
                    "exit_code": completed.returncode,
                    "timeout": False,
                    "temp_entrypoint": file_path.name,
                    "successful_env": env_name,
                    "attempts": attempts,
                }
        except subprocess.TimeoutExpired as exc:
            attempts.append(
                {
                    "env_name": env_name,
                    "stdout": processing_helpers.normalize_output(exc.stdout),
                    "stderr": processing_helpers.normalize_output(exc.stderr),
                    "exit_code": None,
                    "timeout": True,
                }
            )

    final_attempt = attempts[-1] if attempts else {}
    return {
        "status": "timeout" if final_attempt.get("timeout") else "error",
        "stdout": final_attempt.get("stdout", ""),
        "stderr": final_attempt.get("stderr", ""),
        "exit_code": final_attempt.get("exit_code"),
        "timeout": final_attempt.get("timeout", False),
        "temp_entrypoint": file_path.name,
        "successful_env": None,
        "attempts": attempts,
    }


def execute_code(sample: dict[str, Any], timeout: int, python_env_names: list[str], skip_conda_env_testing: bool = False):
    language = str(sample.get("language", "")).lower()
    code = sample.get("code")
    result = {
        "status": "skipped",
        "stdout": "",
        "stderr": "",
        "exit_code": None,
        "timeout": False,
    }

    if not isinstance(code, str) or not code.strip():
        result["stderr"] = "Missing or empty `code` field."
        return result

    with tempfile.TemporaryDirectory(prefix="versicode_run_") as temp_dir:
        workdir = Path(temp_dir)
        command, file_path, preparation_error = command_for_language(language, code, workdir)
        
        if preparation_error is not None:
            return preparation_error
        if command is None:
            result["stderr"] = f"Unsupported language or runtime not available: {language}"
            return result
        if language == "python":
            if file_path is None:
                result["stderr"] = "Missing Python entrypoint."
                return result
            if skip_conda_env_testing:
                try:
                    completed = subprocess.run(command, cwd=workdir, capture_output=True, text=True, timeout=timeout, check=False)
                    result["status"] = "ok" if completed.returncode == 0 else "error"
                    result["stdout"] = completed.stdout
                    result["stderr"] = completed.stderr
                    result["exit_code"] = completed.returncode
                    result["temp_entrypoint"] = file_path.name
                    result["skipped_conda_env_testing"] = True
                    return result
                except subprocess.TimeoutExpired as exc:
                    result["status"] = "timeout"
                    result["timeout"] = True
                    result["stdout"] = processing_helpers.normalize_output(exc.stdout)
                    result["stderr"] = processing_helpers.normalize_output(exc.stderr)
                    result["temp_entrypoint"] = file_path.name
                    result["skipped_conda_env_testing"] = True
                    return result
            return execute_code_in_python_envs(code=code, workdir=workdir, file_path=file_path, env_names=python_env_names, timeout=timeout)

        try:
            completed = subprocess.run(
                command,
                cwd=workdir,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
            result["status"] = "ok" if completed.returncode == 0 else "error"
            result["stdout"] = completed.stdout
            result["stderr"] = completed.stderr
            result["exit_code"] = completed.returncode
            if file_path is not None:
                result["temp_entrypoint"] = file_path.name
            return result
        except subprocess.TimeoutExpired as exc:
            result["status"] = "timeout"
            result["timeout"] = True
            result["stdout"] = processing_helpers.normalize_output(exc.stdout)
            result["stderr"] = processing_helpers.normalize_output(exc.stderr)
            if file_path is not None:
                result["temp_entrypoint"] = file_path.name
            return result