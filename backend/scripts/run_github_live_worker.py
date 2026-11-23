"""Start the existing GitHub collector at session time without copying DB secrets."""
from __future__ import annotations

import argparse
import fcntl
import asyncio
from datetime import UTC, datetime, timedelta
import json
import os
from pathlib import Path
import signal
import sys
import shutil

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.run_live_worker import run_worker

REPOSITORY = "longjae/paddock-brief"
WORKFLOW = "collect-live-timing.yml"
ACTIVE = {"queued", "in_progress", "pending", "waiting", "requested"}


def scheduled_session(event: dict, now: datetime) -> dict | None:
    candidates = []
    for session in event.get("sessions", []):
        try:
            start = datetime.fromisoformat(session["startsAt"].replace(" ", "T") + ":00+09:00")
        except (KeyError, TypeError, ValueError):
            continue
        duration = timedelta(hours=3 if session.get("shortName") == "R" else 1.5)
        if start - timedelta(minutes=10) <= now <= start + duration + timedelta(minutes=10):
            candidates.append((start, session))
    return max(candidates, key=lambda item: item[0])[1] if candidates else None


async def gh_json(gh: str, *args: str):
    process = await asyncio.create_subprocess_exec(gh, *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    try:
        stdout, _ = await asyncio.wait_for(process.communicate(), timeout=30)
    except BaseException:
        process.kill()
        await process.wait()
        raise
    if process.returncode:
        raise RuntimeError("GitHub command unavailable")
    text = stdout.decode().strip()
    return json.loads(text) if text.startswith(("[", "{")) else text


async def dispatch_cycle(event: dict, now: datetime, metadata: dict, command, *, allow_dispatch: bool = True) -> None:
    session = scheduled_session(event, now)
    metadata.update(mode="github-dispatch", event=event.get("slug"), session=session.get("name") if session else None)
    if not session:
        metadata["workflowStatus"] = "outside-session"
        return
    runs = await command("run", "list", "--repo", REPOSITORY, "--workflow", WORKFLOW, "--limit", "10", "--json", "databaseId,status,createdAt")
    running = next((run for run in runs if run.get("status") in ACTIVE), None)
    if running:
        metadata.update(workflowStatus=running["status"], workflowRunId=running["databaseId"])
        return
    previous = metadata.get("lastDispatchAt")
    if previous and (now - datetime.fromisoformat(previous)).total_seconds() < 300:
        metadata["workflowStatus"] = "dispatch-cooldown"
        return
    if not allow_dispatch:
        metadata["workflowStatus"] = "ready-to-dispatch"
        return
    await command("workflow", "run", WORKFLOW, "--repo", REPOSITORY, "--ref", "main", "-f", "duration_seconds=14400")
    metadata.update(lastDispatchAt=now.isoformat(), workflowStatus="dispatched")


async def main(args) -> int:
    gh = args.gh_path or shutil.which("gh")
    if not gh:
        raise RuntimeError("GitHub CLI is required")
    stop = asyncio.Event()
    for name in (signal.SIGTERM, signal.SIGINT):
        asyncio.get_running_loop().add_signal_handler(name, stop.set)
    metadata = {"mode": "github-dispatch"}
    # Preserve cooldown across process restarts. No credentials are stored here.
    if args.health_file.exists():
        try:
            prior = json.loads(args.health_file.read_text())
            if prior.get("lastDispatchAt"):
                metadata["lastDispatchAt"] = prior["lastDispatchAt"]
        except (OSError, ValueError):
            pass
    async def cycle(*_):
        async with httpx.AsyncClient(timeout=25) as client:
            response = await client.get("https://paddock-brief-api.vercel.app/api/v1/events/featured")
            response.raise_for_status()
        await dispatch_cycle(response.json(), datetime.now(UTC), metadata, lambda *a: gh_json(gh, *a), allow_dispatch=not args.check_only)
        return 0  # Dispatch success never means that snapshots were saved.
    state = await run_worker(stop, args.health_file, once=args.once, collect_fn=cycle, metadata=metadata)
    print(json.dumps({key: state.get(key) for key in ("status", "mode", "event", "session", "workflowStatus", "lastCycleStatus", "lastError")}))
    return int(state.get("lastCycleStatus") == "failed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--gh-path")
    parser.add_argument("--health-file", type=Path, default=Path("/tmp/paddock-github-worker/health.json"))
    args = parser.parse_args()
    args.health_file.parent.mkdir(parents=True, exist_ok=True)
    with args.health_file.with_suffix(".lock").open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            parser.exit(1, "Another live worker already owns this health file\n")
        raise SystemExit(asyncio.run(main(args)))
