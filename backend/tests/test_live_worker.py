import asyncio
import json
from pathlib import Path
import pytest

from scripts.run_live_worker import run_worker, write_health
from scripts.run_live_worker import configure
from scripts.install_macos_live_worker import agent_config


def test_worker_retries_failures_and_returns_to_healthy_state(tmp_path) -> None:
    async def check():
        stop = asyncio.Event()
        calls = []
        async def collect(seconds, dry_run):
            assert (seconds, dry_run) == (14400, False)
            calls.append(1)
            if len(calls) == 1:
                raise RuntimeError("secret-value-must-not-appear")
            asyncio.get_running_loop().call_later(0.01, stop.set)
            return 3
        return await run_worker(stop, tmp_path / "health.json", retry_seconds=0.001, collect_fn=collect)
    result = asyncio.run(check())
    assert result["snapshotsSaved"] == 3
    assert result["consecutiveFailures"] == 0
    assert result["lastError"] is None
    assert result["lastSuccessfulCollectionAt"]
    assert "secret-value" not in (tmp_path / "health.json").read_text()


def test_stop_cancels_collector_and_runs_connection_cleanup(tmp_path) -> None:
    async def check():
        stop, started = asyncio.Event(), asyncio.Event()
        cleaned = []
        async def collect(*args):
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                cleaned.append(True)
        task = asyncio.create_task(run_worker(stop, tmp_path / "health.json", collect_fn=collect))
        await started.wait()
        stop.set()
        state = await asyncio.wait_for(task, 1)
        assert cleaned == [True]
        assert state["status"] == "stopped"
    asyncio.run(check())


def test_no_session_polls_without_busy_loop(tmp_path) -> None:
    async def check():
        stop = asyncio.Event()
        calls = []
        async def collect(*args):
            calls.append(1)
            asyncio.get_running_loop().call_later(0.01, stop.set)
            return 0
        result = await run_worker(stop, tmp_path / "health.json", poll_seconds=60, collect_fn=collect)
        assert calls == [1]
        assert result["lastCycleStatus"] == "ok"
        assert "lastSuccessfulCollectionAt" not in result
    asyncio.run(check())


def test_failed_once_reports_failure_without_leaking_response(tmp_path) -> None:
    async def collect(*args):
        raise ValueError("provider response containing a secret")
    result = asyncio.run(run_worker(asyncio.Event(), tmp_path / "health.json", once=True, collect_fn=collect))
    assert result["lastCycleStatus"] == "failed"
    assert result["lastError"] == "ValueError"
    assert "secret" not in json.dumps(result)


def test_health_is_private_and_atomically_replaceable(tmp_path) -> None:
    target = tmp_path / "state" / "health.json"
    write_health(target, {"status": "idle"})
    write_health(target, {"status": "collecting"})
    assert json.loads(target.read_text())["status"] == "collecting"
    assert target.stat().st_mode & 0o777 == 0o600
    assert list(target.parent.iterdir()) == [target]


def test_launch_agent_has_stable_paths_and_no_embedded_credentials() -> None:
    backend = Path("/workspace/paddock/backend")
    config = agent_config(backend, Path("/state"), Path("/logs"))
    assert config["WorkingDirectory"] == str(backend)
    assert config["RunAtLoad"] and config["KeepAlive"]
    assert config["ProgramArguments"][0] == str(backend / ".venv/bin/python")
    assert "EnvironmentVariables" not in config


@pytest.mark.parametrize("key", ["", "[SENSITIVE]"])
def test_missing_or_protected_writer_key_cannot_start_worker(tmp_path, monkeypatch, key) -> None:
    monkeypatch.delenv("SUPABASE_SECRET_KEY", raising=False)
    private = tmp_path / ".env.live-worker"
    private.write_text(f'SUPABASE_URL=https://example.supabase.co\nSUPABASE_SECRET_KEY="{key}"\n')
    with pytest.raises(RuntimeError, match="writer credentials"):
        configure(str(private))
