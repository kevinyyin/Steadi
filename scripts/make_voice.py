#!/usr/bin/env python3
"""Speak every check-in and exercise cue with xAI Grok text to speech, saved as local files.

Reads the key from XAI_API_KEY (voice from CHECKIN_VOICE, default carina). Writes
src/checkin/static/audio/<hash>.mp3 and index.json (exact text -> file). A cue whose file already
exists is skipped, so running it again only pays for new or reworded cues; files no cue uses are removed.

    uv run python scripts/make_voice.py --dry-run   # what it would make, and the cost
    uv run python scripts/make_voice.py
"""

import argparse
import json
import os
import sys
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from checkin import voice  # noqa: E402

USD_PER_CHAR = 15 / 1_000_000  # docs.x.ai, Sep 2026


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description="Generate the spoken check-in cues")
    ap.add_argument("--dry-run", action="store_true", help="list what would be made and its cost, make nothing")
    args = ap.parse_args(argv)
    out = voice.AUDIO
    names = {text: voice.filename(text) for text in voice.phrases()}
    todo = [text for text, name in names.items() if not (out / name).exists()]
    chars = sum(len(t) for t in todo)
    print(f"{len(names)} cues, {len(todo)} to make: {chars} characters, about ${chars * USD_PER_CHAR:.3f}")
    if args.dry_run:
        for text in todo:
            print(f"  {names[text]}  {text}")
        return
    key = os.environ.get("XAI_API_KEY")
    if todo and not key:
        raise SystemExit("XAI_API_KEY is not set")
    out.mkdir(parents=True, exist_ok=True)
    for text in todo:
        print(f"speaking {names[text]}: {text[:60]}...", flush=True)
        try:
            data = voice.tts(text, key)
        except urllib.error.HTTPError as e:
            raise SystemExit(f"TTS API {e.code}: {e.read().decode('utf-8', 'replace')}") from e
        except (urllib.error.URLError, ValueError) as e:
            raise SystemExit(f"TTS request failed: {e}") from e
        (out / names[text]).write_bytes(data)
    for old in out.glob("*.mp3"):
        if old.name not in names.values():
            print(f"removing unused {old.name}")
            old.unlink()
    manifest = {text: name for text, name in names.items() if (out / name).exists()}
    voice.MANIFEST.write_text(json.dumps(manifest, indent=1) + "\n")
    print(voice.MANIFEST)


if __name__ == "__main__":
    main()
