import json

import pytest

from checkin import animals, summary

# 12 s of naming, as xAI returns it (words with start/end seconds, punctuation attached).
WALK = {
    "text": "Cat, dog, horse. Elephant, um, lion. Tiger, giraffe, dog again. Rabbits. Polar bear.",
    "duration": 12.0,
    "words": [{"text": w, "start": s, "end": s + 0.4} for w, s in [
        ("Cat,", 0.2), ("dog,", 1.0), ("horse.", 1.9), ("Elephant,", 3.0), ("lion.", 4.6), ("Tiger,", 5.5),
        ("giraffe,", 6.4), ("dog", 7.5), ("again.", 7.9), ("Rabbits.", 9.1), ("Polar", 10.5), ("bear.", 10.9)]],
}


def test_counts_distinct_animals_repeats_and_per_10s():
    c = animals.count(WALK)
    assert c["list"] == ["cat", "dog", "horse", "elephant", "lion", "tiger", "giraffe", "rabbit", "polar bear"]
    assert (c["named"], c["repeats"]) == (9, 1)
    assert c["per_10s"] == [8, 1] and c["seconds"] == 12.0


def test_plurals_and_text_without_timestamps():
    c = animals.count({"text": "Mice, geese, foxes, butterflies, bear, polar bears, the chair"})
    assert c["list"] == ["mouse", "goose", "fox", "butterfly", "bear", "polar bear"]
    assert c["per_10s"] is None  # no word times: the rate isn't claimed


def test_nothing_said_is_zero_not_an_error():
    assert animals.count({"text": "", "words": [], "duration": 11.0}) == {
        "status": "counted", "named": 0, "repeats": 0, "list": [], "per_10s": [0, 0], "seconds": 11.0}


def test_keyterms_fit_the_api_limits():
    assert len(animals.KEYTERMS) == 100 and all(len(k) <= 50 for k in animals.KEYTERMS)
    assert len(animals.KNOWN) == len(animals.ANIMALS)  # no duplicates in the word list


def test_stt_request_is_multipart_with_the_file_last(monkeypatch):
    sent = {}

    class Reply:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return json.dumps(WALK).encode()

    def urlopen(req, timeout):
        sent.update(url=req.full_url, headers=dict(req.header_items()), body=req.data, timeout=timeout)
        return Reply()

    monkeypatch.setenv("XAI_API_KEY", "test-key")
    monkeypatch.setattr(animals.urllib.request, "urlopen", urlopen)
    assert animals.stt(b"AUDIO", "audio/webm;codecs=opus", keyterms=["cat", "dog"]) == WALK
    assert sent["url"] == "https://api.x.ai/v1/stt" and sent["headers"]["Authorization"] == "Bearer test-key"
    body = sent["body"]
    assert body.count(b'name="keyterm"') == 2 and b'name="model"\r\n\r\ngrok-voice-transcribe-2.0' in body
    assert body.index(b'name="file"; filename="walk.webm"') > body.rindex(b'name="keyterm"')
    assert b"\r\n\r\nAUDIO\r\n" in body


def test_no_key_means_no_call(monkeypatch):
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    assert not animals.available()
    assert animals.stt(b"AUDIO", "audio/webm") is None
    assert animals.count_audio(b"AUDIO", "audio/webm") == {"status": "not_counted", "reason": "no XAI_API_KEY"}


def test_offline_or_empty_audio_is_not_counted():
    def offline(data, mime):
        raise OSError("no network")

    assert animals.count_audio(b"AUDIO", "audio/webm", offline)["status"] == "not_counted"
    assert animals.count_audio(b"", "audio/webm", offline)["reason"] == "no audio"
    assert animals.count_audio(b"x" * (animals.MAX_BYTES + 1), "audio/webm", offline)["status"] == "not_counted"
    ok = animals.count_audio(b"AUDIO", "audio/webm", lambda d, m: WALK)
    assert ok["named"] == 9 and ok["by"] == "grok"


def test_sample_clip_is_bundled():
    assert animals.SAMPLE.stat().st_size > 10_000


@pytest.mark.parametrize("step, line", [
    (None, "not counted."),
    ({"animals": {"status": "not_counted", "reason": "offline"}}, "not counted."),
    ({"animals": {**animals.count(WALK), "simulated": True}},
     "9 (1 repeat); new animals per 10 s: 8, 1, from a sample recording (SIMULATED)."),
])
def test_doctor_line(step, line):
    assert summary.animals_line(step) == line
