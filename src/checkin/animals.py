"""Counting the animals named during the dual-task walk: Grok speech to text, then a local word list.

Our measure, not a STEADI test. The walk time and dual-task cost never depend on it: with Grok off, no
microphone, or no internet the walk's result says "Animals: not counted". One call per walk; the audio is
sent to xAI and never written to disk here. Settings: XAI_API_KEY, CHECKIN_STT_MODEL, CHECKIN_AI (see ai.py).
The dashboard's Grok switch stops the call.
"""

import json
import math
import os
import re
import urllib.request
import uuid
from pathlib import Path

from . import ai

STT_URL = "https://api.x.ai/v1/stt"
DEFAULT_MODEL = "grok-voice-transcribe-2.0"
TIMEOUT_S = 30
MAX_BYTES = 2_000_000  # the 60 s walk limit of compressed speech is well under 1 MB
SAMPLE = Path(__file__).parent / "static" / "sample" / "animals-walk.mp3"  # Simulated: a synthetic voice
WINDOW_S = 10.0

# Commonest first: the first KEYTERMS_MAX are sent as `keyterm` hints (xAI allows 100, each up to 50 chars).
ANIMALS = """
cat dog horse cow pig sheep goat chicken duck rabbit mouse rat lion tiger bear elephant giraffe zebra
monkey gorilla chimpanzee kangaroo koala panda wolf fox deer moose elk camel hippo hippopotamus rhino
rhinoceros crocodile alligator snake lizard turtle tortoise frog toad fish shark whale dolphin seal
walrus octopus squid crab lobster shrimp jellyfish starfish penguin owl eagle hawk falcon parrot pigeon
dove crow raven robin sparrow swan goose turkey peacock flamingo ostrich emu bat squirrel chipmunk
hamster gerbil hedgehog raccoon skunk beaver otter badger mole donkey mule ox buffalo bison yak llama
alpaca leopard cheetah jaguar panther cougar lynx bobcat hyena jackal coyote meerkat mongoose
polar_bear guinea_pig sea_lion killer_whale
ant bee wasp hornet butterfly moth fly mosquito beetle ladybug ladybird spider scorpion snail slug worm
caterpillar grasshopper cricket dragonfly termite flea tick
antelope gazelle impala wildebeest warthog baboon lemur sloth armadillo anteater aardvark porcupine
opossum possum weasel ferret mink stoat marten wolverine platypus wombat dingo tapir okapi orangutan
gibbon hare lamb calf pony kitten puppy piglet foal bull stallion mare rooster hen
salmon trout tuna cod goldfish carp eel stingray swordfish seahorse clam oyster mussel manatee narwhal
orca porpoise pelican stork heron crane seagull gull puffin albatross vulture condor kiwi toucan
woodpecker hummingbird canary finch magpie jay cardinal bluejay blackbird starling quail pheasant
partridge chameleon iguana gecko python cobra viper rattlesnake newt salamander dinosaur
grizzly_bear black_bear brown_bear mountain_lion sea_turtle blue_whale bald_eagle red_panda giant_panda
honey_badger prairie_dog hermit_crab
""".split()
ANIMALS = [a.replace("_", " ") for a in ANIMALS]
KNOWN = set(ANIMALS)
KEYTERMS_MAX = 100
KEYTERMS = ANIMALS[:KEYTERMS_MAX]
IRREGULAR = {"mice": "mouse", "geese": "goose", "wolves": "wolf", "calves": "calf", "oxen": "ox",
             "octopi": "octopus", "octopuses": "octopus", "hippos": "hippo", "rhinos": "rhino",
             "ponies": "pony", "puppies": "puppy", "butterflies": "butterfly", "flies": "fly",
             "ladybugs": "ladybug", "donkeys": "donkey", "monkeys": "monkey", "turkeys": "turkey"}
WORD = re.compile(r"[a-z]+")


def available():
    """True while Grok calls are allowed; the page only offers the animal count then."""
    return ai.ai_enabled()


def _singular(w):
    if w in KNOWN:
        return w
    if w in IRREGULAR:
        return IRREGULAR[w]
    for suffix, repl in (("ies", "y"), ("es", ""), ("s", "")):
        if w.endswith(suffix) and w[: -len(suffix)] + repl in KNOWN:
            return w[: -len(suffix)] + repl
    return None


def _tokens(transcript):
    """(word, start seconds or None) in order, from the word timestamps or else the plain text."""
    words = transcript.get("words") or [{"text": transcript.get("text", ""), "start": None}]
    return [(tok, w.get("start")) for w in words for tok in WORD.findall(str(w.get("text", "")).lower())]


def count(transcript):
    """Animals in a transcript ({"text", "words", "duration"} as xAI returns it): distinct names in the
    order said, repeats, and new animals per 10 seconds. "Polar bear" and "bear" are different animals."""
    toks = _tokens(transcript)
    seen, repeats, firsts, i = [], 0, [], 0
    while i < len(toks):
        pair = i + 1 < len(toks) and _singular(toks[i + 1][0])
        if pair and f"{toks[i][0]} {pair}" in KNOWN:
            name, step = f"{toks[i][0]} {pair}", 2
        else:
            name, step = _singular(toks[i][0]), 1
        if name in seen:
            repeats += 1
        elif name:
            seen.append(name)
            firsts.append(toks[i][1])
        i += step
    duration = transcript.get("duration")
    per_10s = None
    if duration and all(t is not None for t in firsts):
        per_10s = [0] * max(1, math.ceil(duration / WINDOW_S))
        for t in firsts:
            per_10s[min(int(t // WINDOW_S), len(per_10s) - 1)] += 1
    return {"status": "counted", "named": len(seen), "repeats": repeats, "list": seen, "per_10s": per_10s,
            "seconds": duration}


EXT = {"audio/webm": "webm", "audio/ogg": "ogg", "audio/mp4": "m4a", "audio/mpeg": "mp3", "audio/wav": "wav"}


def _form(fields, data, mime):
    """multipart/form-data body; xAI needs `file` after every other field."""
    boundary = uuid.uuid4().hex
    out = b""
    for k, v in fields:
        out += f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
    name = f"walk.{EXT.get(mime.split(';')[0].strip(), 'webm')}"
    out += (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{name}"\r\n'
            f"Content-Type: {mime}\r\n\r\n").encode() + data + f"\r\n--{boundary}--\r\n".encode()
    return out, f"multipart/form-data; boundary={boundary}"


def stt(data, mime, keyterms=KEYTERMS):
    """Grok speech to text: {"text", "duration", "words": [{"text", "start", "end"}]}, or None when Grok is
    off (no key, CHECKIN_AI=off, or the dashboard switch). Raises on network or API errors."""
    if not ai.ai_enabled():
        return None
    key = os.environ.get("XAI_API_KEY")
    if not key:
        return None
    fields = [("model", os.environ.get("CHECKIN_STT_MODEL", DEFAULT_MODEL)), ("language", "en"),
              *(("keyterm", k) for k in keyterms)]
    body, ctype = _form(fields, data, mime)
    req = urllib.request.Request(STT_URL, body, {"Authorization": f"Bearer {key}", "Content-Type": ctype})
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
        return json.loads(r.read())


def count_audio(data, mime, transcribe=None):
    """The animal count for one walk's audio, or {"status": "not_counted", "reason"}. Never raises."""
    if not data:
        return {"status": "not_counted", "reason": "no audio"}
    if len(data) > MAX_BYTES:
        return {"status": "not_counted", "reason": "recording too long"}
    try:
        transcript = (transcribe or stt)(data, mime)
    except Exception as e:  # offline, bad key, rate limit, odd reply: the walk result stands without it
        return {"status": "not_counted", "reason": f"speech to text unavailable ({type(e).__name__})"}
    if transcript is None:
        reason = "no XAI_API_KEY" if not os.environ.get("XAI_API_KEY") else "Grok is off"
        return {"status": "not_counted", "reason": reason}
    return {**count(transcript), "by": "grok"}
