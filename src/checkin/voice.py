"""Spoken cues and summaries in a Grok voice (xAI text to speech).

Every fixed phrase the check-in and exercise screens say is made once by scripts/make_voice.py and saved
under static/audio/, with index.json mapping each phrase's exact text to its file, so the tablet plays
them with no internet. The page falls back to the browser's own voice for any text without a file.
The family summary changes, so it's spoken on request and cached under the data folder.
Settings: XAI_API_KEY, CHECKIN_VOICE (voice id).
"""

import base64
import binascii
import hashlib
import json
import os
import urllib.request
from pathlib import Path

from . import ai, steadi
from .controller import CHECKIN_STEPS, READY, hold_prompt, sit_to_stand_prompt

TTS_URL = "https://api.x.ai/v1/tts"
# carina: xAI's wellness voice. Soft and soothing, and still easy to follow on a short instruction.
# eve (the API default) is energetic and reads as more synthetic on these cues.
DEFAULT_VOICE = "carina"
SPEED = 0.9  # a little slower than normal, for older listeners
BIT_RATE = 64000  # speech at 64 kbps keeps the committed files small
TIMEOUT_S = 30
AUDIO = Path(__file__).parent / "static" / "audio"
MANIFEST = AUDIO / "index.json"

# Said by the page itself (static/app.js) or the controller at the end of a session.
SCREEN = [
    "Done. Rest a moment.",
    "You finished. Thank you.",
    "Exercise done. Nice work.",
    "Session cancelled. Nothing was saved.",
    "Something went wrong; nothing was saved.",
]
# Exercise plans: 5 reps is the page's quick demo, 8 to MAX_REPS the planned sets.
EXERCISE_REPS = (5, *range(steadi.EXERCISE_REPS, steadi.MAX_REPS + 1))


def voice_id():
    return os.environ.get("CHECKIN_VOICE", DEFAULT_VOICE)


def phrases():
    """Every fixed text the screens speak, exactly as the page receives it."""
    out = [prompt + READY for _, _, prompt in CHECKIN_STEPS]
    out += [sit_to_stand_prompt(n) + READY for n in EXERCISE_REPS]
    out += [hold_prompt(s, steadi.EXERCISE_HOLD_S) + READY for s in steadi.STANCES]
    return out + SCREEN


def filename(text, voice=None):
    """Named by a hash of the voice, speed, and text, so a file never plays after its wording changes."""
    key = f"{voice or voice_id()}|{SPEED}|{text}"
    return hashlib.sha256(key.encode()).hexdigest()[:16] + ".mp3"


def load_manifest(path=MANIFEST):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return {}


def tts(text, key=None, voice=None):
    """MP3 bytes, or None with no API key or Grok switched off. Raises on network or API errors."""
    if key is None and not ai.ai_enabled():  # the server follows the Grok switch; make_voice.py passes its key
        return None
    key = key or os.environ.get("XAI_API_KEY")
    if not key:
        return None
    body = {
        "text": text,
        "voice_id": voice or voice_id(),
        "language": "en",
        "speed": SPEED,
        "output_format": {"codec": "mp3", "sample_rate": 24000, "bit_rate": BIT_RATE},
    }
    req = urllib.request.Request(
        TTS_URL, json.dumps(body).encode(), {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
        data, kind = r.read(), r.headers.get("Content-Type", "")
    if kind.startswith("audio/"):
        return data
    raw = json.loads(data).get("audio")  # JSON with base64 audio
    if not isinstance(raw, str) or not raw:
        raise ValueError("TTS response has no audio")
    try:
        return base64.b64decode(raw.split(",", 1)[-1], validate=True)
    except binascii.Error as e:
        raise ValueError(f"TTS audio is not valid base64: {e}") from e


def spoken(text, cache_dir, synth=None):
    """A file with `text` spoken: a pre-made one, else one cached in cache_dir, else made now (and cached).
    None with no API key. Raises on network or API errors."""
    synth = synth or tts
    made = load_manifest().get(text)
    if made and (AUDIO / made).exists():
        return AUDIO / made
    path = Path(cache_dir) / filename(text)
    if path.exists():
        return path
    data = synth(text)
    if data is None:
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_bytes(data)
    tmp.replace(path)
    return path
