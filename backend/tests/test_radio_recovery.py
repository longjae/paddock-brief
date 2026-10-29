import asyncio
import httpx
import pytest

from app.core.config import Settings
from app.services.live_timing import LiveTimingService


class RadioStore:
    def __init__(self):
        self.row = None
        self.operation = None
        self.payload = None
    def table(self, name): return self
    def select(self, columns):
        self.operation = "select"
        return self
    def eq(self, key, value): return self
    def limit(self, count): return self
    def upsert(self, payload, **kwargs):
        self.operation, self.payload = "upsert", payload
        return self
    def update(self, payload):
        self.operation, self.payload = "update", payload
        return self
    def execute(self):
        if self.operation == "upsert": self.row = dict(self.payload)
        if self.operation == "update": self.row.update(self.payload)
        return type("Result", (), {"data": [self.row] if self.row else []})()


def service_with_transport(monkeypatch, handler):
    import app.services.live_timing as module
    real_client = httpx.AsyncClient
    monkeypatch.setattr(module.httpx, "AsyncClient", lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs))
    service = LiveTimingService(Settings(app_use_sample_data=True, openai_api_key="test", supabase_secret_key="test"))
    service.radio_store = RadioStore()
    return service


def test_translation_failure_retries_text_only_preserving_two_speakers(monkeypatch) -> None:
    calls = []
    def respond(request):
        calls.append(request.url.path)
        if request.url.path.endswith(".mp3"): return httpx.Response(200, content=b"audio")
        if request.url.path.endswith("/audio/transcriptions"):
            assert b'name="chunking_strategy"\r\n\r\nauto' in request.content
            return httpx.Response(200, json={"text": "Box. Copy.", "segments": [
                {"start": 0, "end": 1, "speaker": "A", "text": "Box."},
                {"start": 1.5, "end": 2.5, "speaker": "B", "text": "Copy."},
            ]})
        if calls.count("/v1/responses") == 1: return httpx.Response(503)
        return httpx.Response(200, json={"output_text": "피트로. 확인."})
    service = service_with_transport(monkeypatch, respond)
    async def check():
        first = await service.transcribe_team_radio("TeamRadio/TEST.mp3", "2026/test/Race/")
        assert first["transcript"] == "Box. Copy." and first["translation"] is None
        second = await service.transcribe_team_radio("TeamRadio/TEST.mp3", "2026/test/Race/")
        assert second["translation"] == "피트로. 확인."
        assert [x["speaker"] for x in second["segments"]] == ["A", "B"]
    asyncio.run(check())
    assert calls.count("/v1/audio/transcriptions") == 1
    assert calls.count("/v1/responses") == 2


def test_silence_is_saved_unavailable_and_not_transcribed_again(monkeypatch) -> None:
    calls = []
    def respond(request):
        calls.append(request.url.path)
        if request.url.path.endswith(".mp3"): return httpx.Response(200, content=b"audio")
        return httpx.Response(200, json={"text": "  ", "segments": []})
    service = service_with_transport(monkeypatch, respond)
    async def check():
        for _ in range(2):
            result = await service.transcribe_team_radio("TeamRadio/TEST.mp3", "2026/test/Race/")
            assert result["status"] == "unavailable"
            assert not result["transcript"] and not result["segments"]
    asyncio.run(check())
    assert len(calls) == 2 and "/v1/responses" not in calls


def test_missing_audio_is_not_falsely_saved_as_silence(monkeypatch) -> None:
    service = service_with_transport(monkeypatch, lambda request: httpx.Response(404))
    async def check():
        with pytest.raises(httpx.HTTPStatusError):
            await service.transcribe_team_radio("TeamRadio/TEST.mp3", "2026/test/Race/")
    asyncio.run(check())
    assert service.radio_store.row is None


def test_repeated_translation_failure_never_downloads_saved_audio_again(monkeypatch) -> None:
    paths = []
    def respond(request):
        paths.append(request.url.path)
        return httpx.Response(503)
    service = service_with_transport(monkeypatch, respond)
    service.radio_store.row = {"transcript": "Box, box", "translation": None, "status": "ready", "segments": [{"start": 0, "end": 1, "speaker": "A", "text": "Box, box"}]}
    async def check():
        for _ in range(2):
            result = await service.transcribe_team_radio("TeamRadio/TEST.mp3", "2026/test/Race/")
            assert result["transcript"] == "Box, box" and result["translation"] is None
            assert len(result["segments"]) == 1
    asyncio.run(check())
    assert paths == ["/v1/responses", "/v1/responses"]
