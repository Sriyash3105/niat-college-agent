"""Text-to-speech using Microsoft Edge neural voices (edge-tts, no API key required)."""

import asyncio
import uuid
from pathlib import Path

import edge_tts

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

# Native-language neural voices; run `uv run edge-tts --list-voices` to see alternatives.
VOICES = {
    "Telugu": "te-IN-MohanNeural",
    "Hindi": "hi-IN-MadhurNeural",
    "Tamil": "ta-IN-ValluvarNeural",
    "English": "en-IN-PrabhatNeural",
}


def synthesize_speech(text: str, language: str = "English") -> str:
    """Convert text to an MP3 in static/ and return the file name."""
    STATIC_DIR.mkdir(exist_ok=True)
    filename = f"voice_{uuid.uuid4().hex}.mp3"
    voice = VOICES.get(language, VOICES["English"])

    communicate = edge_tts.Communicate(text, voice)
    asyncio.run(communicate.save(str(STATIC_DIR / filename)))

    return filename
