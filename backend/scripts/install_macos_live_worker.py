"""Install a per-user LaunchAgent; never embed credentials in the plist."""

import argparse
import os
from pathlib import Path
import plistlib
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.run_live_worker import configure

LABEL = "com.paddockbrief.live-worker"


def agent_config(backend: Path, support: Path, logs: Path) -> dict:
    return {
        "Label": LABEL,
        "ProgramArguments": [str(backend / ".venv/bin/python"), "-u", str(backend / "scripts/run_live_worker.py"), "--env-file", str(backend / ".env.live-worker"), "--health-file", str(support / "health.json")],
        "WorkingDirectory": str(backend),
        "RunAtLoad": True,
        "KeepAlive": True,
        "ThrottleInterval": 60,
        "StandardOutPath": str(logs / "worker.log"),
        "StandardErrorPath": str(logs / "worker-error.log"),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--remove", action="store_true")
    args = parser.parse_args()
    home = Path.home()
    target = home / "Library/LaunchAgents" / f"{LABEL}.plist"
    domain = f"gui/{os.getuid()}"
    if args.remove:
        subprocess.run(["launchctl", "bootout", f"{domain}/{LABEL}"], check=False)
        target.unlink(missing_ok=True)
        raise SystemExit(0)
    backend = Path(__file__).resolve().parents[1]
    for required in (backend / ".venv/bin/python", backend / ".env.live-worker"):
        if not required.exists():
            parser.error(f"Missing required file: {required}")
    env = backend / ".env.live-worker"
    env.chmod(0o600)
    configure(str(env))
    support = home / "Library/Application Support/PaddockBrief"
    logs = home / "Library/Logs/PaddockBrief"
    for directory in (target.parent, support, logs):
        directory.mkdir(parents=True, exist_ok=True)
    target.write_bytes(plistlib.dumps(agent_config(backend, support, logs)))
    target.chmod(0o600)
    subprocess.run(["launchctl", "bootout", f"{domain}/{LABEL}"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    subprocess.run(["launchctl", "bootstrap", domain, str(target)], check=True)
    print(f"Installed {LABEL}. Health: {support / 'health.json'}")
