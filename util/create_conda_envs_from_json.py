#!/usr/bin/env python3
import argparse
import json
import subprocess
from pathlib import Path


DEFAULT_CONFIG = Path(__file__).resolve().with_name("versicode_env_configs.json")

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create conda environments from a JSON manifest.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help="Path to the environment config JSON file.")
    parser.add_argument("--only", action="append", dest="only", help="Only create the named environment. Can be passed multiple times.")
    return parser.parse_args()

def run_command(command: list[str]) -> None:
    print("Running:", " ".join(command))
    subprocess.run(command, check=True)

def existing_env_names() -> set[str]:
    completed = subprocess.run(["conda", "env", "list", "--json"], capture_output=True, text=True, check=True)
    payload = json.loads(completed.stdout)
    env_paths = payload.get("envs", [])
    return {Path(path).name for path in env_paths}

def main() -> int:
    args = parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    only = set(args.only or [])
    existing_envs = existing_env_names()

    for env in config["environments"]:
        env_name = env["name"]
        if only and env_name not in only:
            continue

        channels = []
        for channel in env.get("channels", []):
            channels.extend(["-c", channel])

        if env_name in existing_envs:
            conda_cmd = ["conda", "install", "-n", env_name, *env.get("conda_packages", []), "-y", *channels]
        else:
            conda_cmd = ["conda", "create", "-n", env_name, f"python={env['python']}", *env.get("conda_packages", []), "-y", *channels]
        run_command(conda_cmd)

        pip_packages = env.get("pip_packages", [])
        for pip_package in pip_packages:
            pip_cmd = ["conda", "run", "-n", env_name, "python", "-m", "pip", "install", pip_package]
            run_command(pip_cmd)

        for post_command in env.get("post_commands", []):
            command = ["conda", "run", "-n", env_name, *post_command]
            run_command(command)

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
