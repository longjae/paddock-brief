"""Supervise live timing independently of a browser or hosted cron runner."""

from __future__ import annotations

import argparse
import asyncio
import fcntl
import json
import logging
import os
import signal
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings, get_settings
from scripts.collect_live_timing import collect

LOGGER = logging.getLogger(__name__)


def write_health(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            json.dump({**state, "heartbeatAt": datetime.now(UTC).isoformat()}, stream)
            stream.flush()
            os.fsync(stream.fileno())
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


async def run_worker(
    stop: asyncio.Event,
    health_path: Path,
    *,
    poll_seconds: float = 60,
    retry_seconds: float = 5,
    heartbeat_seconds: float = 15,
    once: bool = False,
    collect_fn=collect,
) -> dict[str, Any]:
    state: dict[str, Any] = {"status": "starting", "startedAt": datetime.now(UTC).isoformat(), "snapshotsSaved": 0, "consecutiveFailures": 0, "lastError": None}

    async def heartbeat() -> None:
        while True:
            write_health(health_path, state)
            await asyncio.sleep(heartbeat_seconds)

    async def wait_or_stop(seconds: float) -> None:
        try:
            await asyncio.wait_for(stop.wait(), timeout=seconds)
        except TimeoutError:
            pass

    beat = asyncio.create_task(heartbeat())
    try:
        while not stop.is_set():
            state.update(status="collecting", lastCycleAt=datetime.now(UTC).isoformat())
            write_health(health_path, state)
            task = asyncio.create_task(collect_fn(14400, False))
            stopping = asyncio.create_task(stop.wait())
            delay = poll_seconds
            try:
                done, _ = await asyncio.wait({task, stopping}, return_when=asyncio.FIRST_COMPLETED)
                if stopping in done:
                    break
                count = await task
                state.update(status="idle", lastCycleStatus="ok", consecutiveFailures=0, lastError=None)
                state["snapshotsSaved"] += count
                if count:
                    state["lastSuccessfulCollectionAt"] = datetime.now(UTC).isoformat()
                    delay = 5
            except Exception as error:
                state["consecutiveFailures"] += 1
                # Never copy provider response bodies, credentials, or URLs into health data.
                state.update(status="retrying", lastCycleStatus="failed", lastError=type(error).__name__)
                delay = min(300, retry_seconds * 2 ** min(state["consecutiveFailures"] - 1, 6))
                LOGGER.warning("Collector cycle failed (%s); retrying in %ss", type(error).__name__, delay)
            finally:
                for pending in (task, stopping):
                    if not pending.done():
                        pending.cancel()
                await asyncio.gather(task, stopping, return_exceptions=True)
            write_health(health_path, state)
            if once:
                break
            await wait_or_stop(delay)
    finally:
        beat.cancel()
        await asyncio.gather(beat, return_exceptions=True)
        state["status"] = "stopped"
        write_health(health_path, state)
    return state


def configure(env_file: str | None) -> None:
    settings = Settings(_env_file=env_file or ".env", app_use_sample_data=False, live_timing_enabled=True)
    if not settings.supabase_url or not settings.supabase_secret_key or settings.supabase_secret_key == "[SENSITIVE]":
        raise RuntimeError("Live worker requires Supabase writer credentials in its private env file")
    os.environ.update(SUPABASE_URL=settings.supabase_url, SUPABASE_SECRET_KEY=settings.supabase_secret_key, APP_USE_SAMPLE_DATA="false", LIVE_TIMING_ENABLED="true")
    get_settings.cache_clear()


async def main(args: argparse.Namespace) -> int:
    configure(args.env_file)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for name in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(name, stop.set)
    state = await run_worker(stop, args.health_file, once=args.once)
    return 1 if state.get("lastCycleStatus") == "failed" else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", default=os.environ.get("LIVE_WORKER_ENV_FILE"))
    parser.add_argument("--health-file", type=Path, default=Path(os.environ.get("LIVE_WORKER_HEALTH_FILE", "/tmp/paddock-live-worker/health.json")))
    parser.add_argument("--once", action="store_true", help="Check one collection cycle and exit")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args.health_file.parent.mkdir(parents=True, exist_ok=True)
    with args.health_file.with_suffix(".lock").open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            parser.exit(1, "Another live worker already owns this health file\n")
        raise SystemExit(asyncio.run(main(args)))
