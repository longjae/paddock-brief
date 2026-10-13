"""Save public team radio transcripts with the collector's server-only key."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import httpx
from supabase import create_client

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings
from app.services.live_timing import team_radio_audio_url

API_URL = "https://paddock-brief-api.vercel.app/api/v1"


def response_text(payload: dict) -> str:
    return str(payload.get("output_text") or next(
        (content.get("text") for output in payload.get("output", []) for content in output.get("content", []) if content.get("type") == "output_text"),
        "",
    )).strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--event-slug", default="")
    args = parser.parse_args()
    settings = Settings()
    if not (settings.supabase_url and settings.supabase_secret_key and settings.openai_api_key):
        print(json.dumps({"ok": False, "error": "Collector credentials are missing"}))
        return 2

    database = create_client(settings.supabase_url, settings.supabase_secret_key)
    headers = {"Authorization": f"Bearer {settings.openai_api_key}"}
    with httpx.Client(timeout=90, follow_redirects=True) as client:
        if args.event_slug:
            slug = args.event_slug
        else:
            featured = client.get(f"{API_URL}/events/featured")
            featured.raise_for_status()
            slug = featured.json()["slug"]
        state_response = client.get(f"{API_URL}/events/{slug}/race-state")
        state_response.raise_for_status()
        radios = state_response.json().get("teamRadio") or []
        outcomes = []
        for radio in radios:
            path = str(radio.get("Path") or "")
            session_path = str(radio.get("SessionPath") or "")
            try:
                audio_url = team_radio_audio_url(path, session_path)
                existing = database.table("team_radio_transcripts").select("transcript,translation").eq("session_path", session_path).eq("path", path).limit(1).execute().data
                if existing and existing[0].get("translation"):
                    outcomes.append({"path": path, "status": "existing"})
                    continue
                if existing:
                    transcript = existing[0]["transcript"]
                else:
                    audio = client.get(audio_url, headers={"User-Agent": settings.collector_user_agent})
                    audio.raise_for_status()
                    transcription = client.post(
                        "https://api.openai.com/v1/audio/transcriptions",
                        headers=headers,
                        data={"model": "gpt-4o-mini-transcribe", "response_format": "json"},
                        files={"file": (path.rsplit("/", 1)[-1], audio.content, "audio/mpeg")},
                    )
                    transcription.raise_for_status()
                    transcript = str(transcription.json().get("text") or "").strip()
                if not transcript:
                    outcomes.append({"path": path, "status": "no-speech"})
                    continue
                translation = None
                try:
                    translated = client.post(
                        "https://api.openai.com/v1/responses",
                        headers=headers,
                        json={"model": settings.openai_summary_model, "input": "다음 F1 팀 라디오를 자연스럽고 짧은 한국어로 번역하세요. 고유명사는 유지하고 번역문만 출력하세요.\n\n" + transcript},
                    )
                    translated.raise_for_status()
                    translation = response_text(translated.json()) or None
                except (httpx.HTTPError, ValueError):
                    pass
                database.table("team_radio_transcripts").upsert({"session_path": session_path, "path": path, "transcript": transcript, "translation": translation}, on_conflict="session_path,path").execute()
                outcomes.append({"path": path, "status": "saved", "translated": bool(translation)})
            except (httpx.HTTPError, ValueError, KeyError) as error:
                outcomes.append({"path": path, "status": "failed", "error": str(error)[:160]})
    print(json.dumps({"ok": not any(row["status"] == "failed" for row in outcomes), "event": slug, "radios": outcomes}, ensure_ascii=False))
    return 1 if any(row["status"] == "failed" for row in outcomes) else 0


if __name__ == "__main__":
    sys.exit(main())
