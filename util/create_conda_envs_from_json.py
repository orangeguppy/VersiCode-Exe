#!/usr/bin/env python3
import argparse
import json
import subprocess
from pathlib import Path

import env_helpers

# Default path to the environment configuration JSON file
DEFAULT_CONFIG = Path(__file__).resolve().with_name("versicode_env_configs.json")

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help="Path to the environment config JSON file.")
    parser.add_argument("--only", action="append", dest="only", help="Only create the named environment. Can be passed multiple times.")
    return parser.parse_args()

def run_command(command: list[str]) -> None:
    """Execute a shell command and raise an error if it fails."""
    print("Running:", " ".join(command))
    subprocess.run(command, check=True)

def main():
    """
    Create or update Conda environments based on the JSON configs.

    For each env:
    - Create it if it doesnt exist, otherwise, install/upgrade required packages
    - Install pip packages if specified
    - Execute any post-setup commands
    """
    args = parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    only = set(args.only or [])
    existing_envs = env_helpers.existing_env_names() # Return the set of existing Conda environment names

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
