#!/usr/bin/env python3
"""Generate check-in instruction pictures with the xAI Grok Imagine API.

Reads the key from XAI_API_KEY. Writes src/checkin/static/img/<name>.<ext>,
using the extension that matches the bytes the API returned.

    python scripts/make_images.py
    python scripts/make_images.py tandem
"""

import argparse
import base64
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

API = "https://api.x.ai/v1/images/generations"
MODEL = "grok-imagine-image-2.0"
TIMEOUT_S = 180
STYLE = (
    "Simple flat illustration, older adult in comfortable clothes, side view, "
    "plain light background, clear body position, no text. Showing: "
)
FEET_STYLE = (
    "Simple flat illustration, close-up of an older adult's feet in comfortable shoes, "
    "viewed from above at a slight angle, standing on a plain white floor, no text, "
    "no other body parts beyond the lower legs. Showing: "
)
# Side view hides how the feet are placed, so these three are a close-up from above.
FEET = frozenset({"feet_together", "semi_tandem", "tandem"})
OUT = Path(__file__).resolve().parents[1] / "src" / "checkin" / "static" / "img"
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}

POSITIONS = {
    "tug": "standing up from an arm chair and walking toward a line taped on the floor",
    "chair_stand": "standing up from an armless chair with arms crossed on the chest",
    "feet_together": "both feet side by side, touching each other",
    "semi_tandem": (
        "one foot placed half a step ahead, so its heel sits beside the big toe of the other foot, "
        "both feet touching along the side"
    ),
    "tandem": (
        "one foot directly in front of the other in a straight line, "
        "the front foot's heel touching the back foot's toes"
    ),
    "sit_to_stand": (
        "halfway through standing up from a sturdy armless chair, hips just lifted off the seat, "
        "feet flat on the floor, leaning slightly forward, arms crossed on the chest"
    ),
    "hold": "standing with one hand resting on a kitchen counter for balance",
}


def image_ext(data: bytes) -> str:
    """Extension for the format these bytes actually are."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if data.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return ".gif"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    raise SystemExit("image bytes are not png, jpeg, gif, or webp")


def generate(prompt: str, key: str) -> bytes:
    body = json.dumps({
        "model": MODEL,
        "prompt": prompt,
        "response_format": "b64_json",
        "aspect_ratio": "4:3",
    }).encode()
    req = urllib.request.Request(
        API,
        data=body,
        method="POST",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            payload = json.load(resp)
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        raise SystemExit(f"image API {e.code}: {detail}") from e
    except urllib.error.URLError as e:
        raise SystemExit(f"image API request failed: {e.reason}") from e
    try:
        raw = payload["data"][0]["b64_json"]
    except (KeyError, IndexError, TypeError) as e:
        keys = list(payload) if isinstance(payload, dict) else type(payload).__name__
        raise SystemExit(f"image API response has no b64_json ({keys})") from e
    if not isinstance(raw, str) or not raw:
        raise SystemExit("image API response has no b64_json")
    if raw.startswith("data:"):
        raw = raw.split(",", 1)[-1]
    try:
        return base64.b64decode(raw, validate=True)
    except (ValueError, TypeError) as e:
        raise SystemExit(f"image API b64_json is not valid base64: {e}") from e


def save(name: str, data: bytes) -> Path:
    ext = image_ext(data)
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{name}{ext}"
    for old in OUT.glob(f"{name}.*"):
        if old.suffix.lower() in IMAGE_EXTS and old.resolve() != path.resolve():
            old.unlink()
    path.write_bytes(data)
    return path


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description="Generate check-in instruction pictures")
    ap.add_argument(
        "names",
        nargs="*",
        choices=sorted(POSITIONS),
        help="regenerate only these (default: every picture)",
    )
    args = ap.parse_args(argv)
    key = os.environ.get("XAI_API_KEY")
    if not key:
        raise SystemExit("XAI_API_KEY is not set")
    for name in args.names or list(POSITIONS):
        print(f"generating {name}...", flush=True)
        style = FEET_STYLE if name in FEET else STYLE
        path = save(name, generate(style + POSITIONS[name], key))
        print(path)


if __name__ == "__main__":
    main()
