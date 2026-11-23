"""Install a per-user LaunchAgent; never embed credentials in the plist."""

import argparse
import os
from pathlib import Path
import plistlib
import subprocess
import sys
import shutil

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.run_live_worker import configure

LABEL = "com.paddockbrief.live-worker"


def agent_config(backend: Path, support: Path, logs: Path, gh_path: str | None = None) -> dict:
    config = {
        "Label": LABEL,
        "ProgramArguments": [str(backend / ".venv/bin/python"), "-u", str(backend / "scripts/run_live_worker.py"), "--env-file", str(backend / ".env.live-worker"), "--health-file", str(support / "health.json")],
        "WorkingDirectory": str(backend),
        "RunAtLoad": True,
        "KeepAlive": True,
        "ThrottleInterval": 60,
        "StandardOutPath": str(logs / "worker.log"),
        "StandardErrorPath": str(logs / "worker-error.log"),
    }
    if gh_path:
        config["ProgramArguments"] = [str(backend / ".venv/bin/python"), "-u", str(backend / "scripts/run_github_live_worker.py"), "--gh-path", gh_path, "--health-file", str(support / "health.json")]
    return config


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--remove", action="store_true")
    parser.add_argument("--github-dispatch", action="store_true")
    args = parser.parse_args()
    home = Path.home()
    target = home / "Library/LaunchAgents" / f"{LABEL}.plist"
    domain = f"gui/{os.getuid()}"
    if args.remove:
        subprocess.run(["launchctl", "bootout", f"{domain}/{LABEL}"], check=False)
        target.unlink(missing_ok=True)
        raise SystemExit(0)
    backend = Path(__file__).resolve().parents[1]
    required_files = [backend / ".venv/bin/python"]
    if not args.github_dispatch:
        required_files.append(backend / ".env.live-worker")
    for required in required_files:
        if not required.exists():
            parser.error(f"Missing required file: {required}")
    gh_path = shutil.which("gh") if args.github_dispatch else None
    if args.github_dispatch:
        if not gh_path:
            parser.error("GitHub CLI is required")
        subprocess.run([gh_path, "auth", "status"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        env = backend / ".env.live-worker"
        env.chmod(0o600)
        configure(str(env))
    support = home / "Library/Application Support/PaddockBrief"
    logs = home / "Library/Logs/PaddockBrief"
    for directory in (target.parent, support, logs):
        directory.mkdir(parents=True, exist_ok=True)
    target.write_bytes(plistlib.dumps(agent_config(backend, support, logs, gh_path)))
    target.chmod(0o600)
    subprocess.run(["launchctl", "bootout", f"{domain}/{LABEL}"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    subprocess.run(["launchctl", "bootstrap", domain, str(target)], check=True)
    print(f"Installed {LABEL}. Health: {support / 'health.json'}")
