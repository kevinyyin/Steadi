import asyncio
import base64
import importlib.util
import io
import json
import shutil
import subprocess
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from checkin import sim, steadi, voice
from checkin.base import VirtualBase
from checkin.clock import FakeClock
from checkin.controller import Controller
from checkin.seed import seed_dad
from checkin.server import create_app
from checkin.sources import SimSource
from checkin.store import Store

ROOT = Path(__file__).resolve().parents[1]
QUICK_PLAN = {"sit_to_stand": {"sets": 1, "reps": 5},
              "balance": {"stance": "feet_together", "holds": 0, "target_s": 20}}


def waiting_prompts(tmp_path, mode, plan=None):
    """Every prompt a session shows while it waits for the button."""
    clock = FakeClock(t=1000.0037)
    store = Store(tmp_path)
    person = store.create("P", {"age": 72, "sex": "female", "fallen": False, "unsteady": False, "worried": False})
    all_hold = {s: 60.0 for s in steadi.STANCES}
    ctl = Controller(SimSource(clock, sim.SimParams(hold_s=all_hold), seed=3), VirtualBase(), store, clock)
    seen = set()

    async def go():
        task = asyncio.ensure_future(ctl.run_session(person["id"], mode, plan))
        while not task.done():
            if any(s["status"] == "waiting" for s in ctl.state["steps"]):
                seen.add(ctl.state["prompt"])
                ctl.press()
            await asyncio.sleep(0)

    asyncio.run(go())
    return seen


@pytest.mark.parametrize("mode,plan", [
    ("checkin", None),
    ("exercise", None),  # the standard plan
    ("exercise", QUICK_PLAN),  # the page's quick exercise
    ("exercise", {"sit_to_stand": {"sets": 1, "reps": 10},
                  "balance": {"stance": "tandem", "holds": 1, "target_s": 20}}),
])
def test_every_spoken_prompt_has_a_phrase(tmp_path, mode, plan):
    prompts = waiting_prompts(tmp_path, mode, plan)
    assert prompts and prompts <= set(voice.phrases())


def test_screen_phrases_are_the_pages_own_words():
    source = (ROOT / "src/checkin/static/app.js").read_text() + (ROOT / "src/checkin/controller.py").read_text()
    for text in voice.SCREEN:
        assert text in source


def test_filenames_follow_the_wording_and_voice(monkeypatch):
    monkeypatch.delenv("CHECKIN_VOICE", raising=False)
    names = [voice.filename(t) for t in voice.phrases()]
    assert len(set(names)) == len(names)
    assert voice.filename("Hold still.") == voice.filename("Hold still.")
    assert voice.filename("Hold still.") != voice.filename("Hold still!")
    assert voice.filename("Hold still.", "eve") != voice.filename("Hold still.", "ara")
    assert voice.DEFAULT_VOICE == "carina"
    assert voice.filename("Hold still.") == voice.filename("Hold still.", "carina")
    assert voice.filename("Hold still.") != voice.filename("Hold still.", "eve")


def test_the_committed_manifest_matches_the_files():
    manifest = json.loads(voice.MANIFEST.read_text())
    phrases = set(voice.phrases())
    for text, name in manifest.items():
        assert text in phrases, "stale cue: run scripts/make_voice.py"
        assert name == voice.filename(text, voice.DEFAULT_VOICE) and (voice.AUDIO / name).exists()


def test_browser_fallback_prefers_a_natural_local_voice():
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    script = r"""
const fs = require("fs");
const src = fs.readFileSync("src/checkin/static/app.js", "utf8");
const start = src.indexOf("const HUMAN_VOICE");
const end = src.indexOf("function browserVoice");
if (start < 0 || end < 0) throw new Error("voice picker not found");
const pick = new Function(src.slice(start, end) + "\nreturn pickSpokenVoice;")();
const v = (name, local, lang = "en-US") => ({ name, voiceURI: name, localService: local, lang });
const chosen = (voices) => { const p = pick(voices); return p ? p.name : null; };
const cases = [
  [[v("Microsoft David Desktop", true), v("Microsoft Zira Desktop", true)], "Microsoft Zira Desktop"],
  [[v("eSpeak English", true), v("Samantha", true)], "Samantha"],
  [[v("Microsoft David Desktop", true), v("Google US English", false)], "Google US English"],
  [[], null],
];
for (const [voices, want] of cases) {
  const got = chosen(voices);
  if (got !== want) { console.error(JSON.stringify({ got, want })); process.exit(1); }
}
"""
    ran = subprocess.run([node, "-e", script], cwd=ROOT, capture_output=True, text=True)
    assert ran.returncode == 0, ran.stderr


def test_tts_is_skipped_without_a_key(monkeypatch):
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    assert voice.tts("Hello") is None


class FakeResponse(io.BytesIO):
    def __init__(self, data, kind):
        super().__init__(data)
        self.headers = {"Content-Type": kind}

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@pytest.mark.parametrize("data,kind", [
    (b"ID3raw", "audio/mpeg"),
    (json.dumps({"audio": base64.b64encode(b"ID3raw").decode(), "content_type": "audio/mpeg"}).encode(),
     "application/json"),
])
def test_tts_reads_raw_or_base64_audio(monkeypatch, data, kind):
    monkeypatch.delenv("CHECKIN_VOICE", raising=False)
    sent = {}

    def urlopen(req, timeout):
        sent.update(json.loads(req.data))
        return FakeResponse(data, kind)

    monkeypatch.setattr(voice.urllib.request, "urlopen", urlopen)
    assert voice.tts("Hello", key="k") == b"ID3raw"
    assert sent["voice_id"] == "carina" and sent["language"] == "en"
    assert sent["speed"] == voice.SPEED and sent["output_format"]["codec"] == "mp3"


def test_spoken_caches_so_each_text_is_paid_for_once(tmp_path):
    calls = []

    def synth(text):
        calls.append(text)
        return b"ID3" + text.encode()

    first = voice.spoken("A new summary.", tmp_path, synth)
    again = voice.spoken("A new summary.", tmp_path, synth)
    assert first == again and first.read_bytes() == b"ID3A new summary." and calls == ["A new summary."]
    assert voice.spoken("Another one.", tmp_path, lambda t: None) is None


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    clock = FakeClock()
    store = Store(tmp_path)
    seed_dad(store, date(2026, 9, 26))
    app = create_app(Controller(SimSource(clock, seed=1), VirtualBase(), store, clock), store,
                     today=lambda: date(2026, 9, 26))
    with TestClient(app) as c:
        yield c


def test_summary_audio_speaks_only_the_summary_served(client, monkeypatch):
    assert client.get("/api/people/sim-dad/summary/audio").status_code == 404  # no summary made yet
    family = client.get("/api/people/sim-dad/summary").json()["family"]
    assert client.get("/api/people/sim-dad/summary/audio").status_code == 404  # no key: the browser's voice reads it
    spoken = []
    monkeypatch.setattr(voice, "tts", lambda text: spoken.append(text) or b"ID3fake")
    r = client.get("/api/people/sim-dad/summary/audio")
    assert r.status_code == 200 and r.headers["content-type"] == "audio/mpeg" and r.content == b"ID3fake"
    assert spoken == [family]
    assert client.get("/api/people/sim-dad/summary/audio").content == b"ID3fake" and len(spoken) == 1  # cached


def test_summary_audio_offline_is_a_404_not_a_500(client, monkeypatch):
    client.get("/api/people/sim-dad/summary")

    def offline(text):
        raise OSError("no network")

    monkeypatch.setattr(voice, "tts", offline)
    assert client.get("/api/people/sim-dad/summary/audio").status_code == 404


def test_make_voice_dry_run_needs_no_key(monkeypatch, capsys):
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    spec = importlib.util.spec_from_file_location("make_voice", ROOT / "scripts" / "make_voice.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.main(["--dry-run"])
    assert "cues" in capsys.readouterr().out
