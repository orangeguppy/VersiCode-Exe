import json_helpers
from pathlib import Path
import json
import subprocess
from typing import Any

def collect_required_env_names(json_files: list[Path], limit: int | None = None):
    env_names: set[str] = set()
    for json_path in json_files:
        payload = json_helpers.load_json(json_path)
        samples = payload.get("data", [])
        if limit is not None:
            samples = samples[:limit]
        for sample in samples:
            env_name = sample.get("run_result", {}).get("successful_env")
            if env_name:
                env_names.add(str(env_name))
    return env_names

def load_env_definitions(config_path: Path):
    config = json_helpers.load_json(config_path)
    environments = config.get("environments", [])
    return {
        env["name"]: env
        for env in environments
        if isinstance(env, dict) and env.get("name")
    }

def load_env_names(config_path: Path) -> list[str]:
    payload = json_helpers.load_json(config_path)
    environments = payload.get("environments", [])
    return [
        env["name"]
        for env in environments
        if isinstance(env, dict) and isinstance(env.get("name"), str)
    ]

def load_python_env_names(config_path: Path) -> list[str]:
    config = json_helpers.load_json(config_path)
    environments = config.get("environments", [])
    return [env["name"] for env in environments if env.get("name")]

def run_command(command: list[str], *, cwd: Path | None = None):
    return subprocess.run(command, cwd=cwd, capture_output=True, text=True, check=False)

def get_existing_conda_env_names() -> set[str]:
    completed = run_command(["conda", "env", "list", "--json"])
    if completed.returncode != 0:
        raise RuntimeError(
            "Failed to list Conda environments.\n"
            f"stdout:\n{completed.stdout}\n"
            f"stderr:\n{completed.stderr}"
        )

    payload = json.loads(completed.stdout or "{}")
    env_paths = payload.get("envs", [])
    return {Path(env_path).name for env_path in env_paths}

def build_conda_create_command(env_definition: dict[str, Any]) -> list[str]:
    """
    This fxn builds and returns a conda create command (as a list of strings) from an env definition dict
    """
    command = ["conda", "create", "-n", env_definition["name"], "-y"]
    for channel in env_definition.get("channels", []):
        command.extend(["-c", str(channel)])

    python_version = env_definition.get("python")
    if python_version:
        command.append(f"python={python_version}")

    command.extend(str(package) for package in env_definition.get("conda_packages", []))
    return command

def ensure_conda_env(env_definition: dict[str, Any]) -> None:
    env_name = env_definition["name"]
    print(f"Creating missing Conda env: {env_name}")

    create_command = build_conda_create_command(env_definition)
    completed = run_command(create_command)
    if completed.returncode != 0:
        raise RuntimeError(
            f"Failed to create Conda env {env_name}.\n"
            f"stdout:\n{completed.stdout}\n"
            f"stderr:\n{completed.stderr}"
        )

    pip_packages = env_definition.get("pip_packages", [])
    if pip_packages:
        completed = run_command(["conda", "run", "-n", env_name, "python", "-m", "pip", "install", *map(str, pip_packages)])
        
        if completed.returncode != 0:
            raise RuntimeError(
                f"Failed to install pip packages for Conda env {env_name}.\n"
                f"stdout:\n{completed.stdout}\n"
                f"stderr:\n{completed.stderr}"
            )

    for post_command in env_definition.get("post_commands", []):
        completed = run_command(["conda", "run", "-n", env_name, *map(str, post_command)])
        if completed.returncode != 0:
            raise RuntimeError(
                f"Failed post-create command for Conda env {env_name}: {post_command}\n"
                f"stdout:\n{completed.stdout}\n"
                f"stderr:\n{completed.stderr}"
            )

def ensure_required_envs_exist(required_env_names: set[str], config_path: Path) -> None:
    if not required_env_names:
        return

    env_definitions = load_env_definitions(config_path)
    existing_env_names = get_existing_conda_env_names()
    missing_env_names = sorted(required_env_names - existing_env_names)
    if not missing_env_names:
        return

    undefined_env_names = [name for name in missing_env_names if name not in env_definitions]
    if undefined_env_names:
        raise KeyError(
            "Missing env definitions in config for: " + ", ".join(undefined_env_names)
        )

    for env_name in missing_env_names:
        ensure_conda_env(env_definitions[env_name])

def existing_env_names():
    completed = subprocess.run(["conda", "env", "list", "--json"], capture_output=True, text=True, check=True)
    payload = json.loads(completed.stdout)
    env_paths = payload.get("envs", [])
    return {Path(path).name for path in env_paths}