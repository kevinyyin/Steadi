"""Synthesize the showreel soundtrack: 120 BPM, 42 bars (84 s), with Steadi's own beeps on the frames they appear.

    uv run --no-project --with numpy --with scipy python scripts/make_music.py

Writes public/music.wav. Frame numbers below are global frames of the Showreel composition (30 fps);
scene starts are listed in SCENES and match src/Showreel.tsx.
"""

import wave
from pathlib import Path

import numpy as np
from scipy.signal import butter, fftconvolve, sosfilt

SR = 44100
FPS = 30
BEAT = 0.5  # seconds at 120 BPM
BAR = 2.0
BARS = 42
N = int(SR * BARS * BAR)
rng = np.random.default_rng(7)

SCENES = {  # global start frame of each scene
    "cold": 0, "hook": 180, "logo": 420, "loop": 600, "hardware": 780, "tug": 1020, "dual": 1200,
    "chair": 1320, "balance": 1500, "levels": 1680, "coach": 1800, "dash": 1980, "grok": 2220, "outro": 2340,
}

music = np.zeros((2, N))  # ducked by the kick
drums = np.zeros((2, N))
fx = np.zeros((2, N))
send = np.zeros((2, N))  # reverb send


def sec(frame):
    return frame / FPS


def add(bus, sig, at, gain=1.0, pan=0.0, rev=0.0):
    """Mix a mono or stereo signal into a bus at `at` seconds (equal-power pan, optional reverb send)."""
    i = int(round(at * SR))
    if i >= N or i < 0:
        return
    sig = np.atleast_2d(sig)
    if sig.shape[0] == 1:
        sig = np.vstack([sig[0] * np.sqrt(1 - pan), sig[0] * np.sqrt(1 + pan)])
    j = min(N, i + sig.shape[1])
    bus[:, i:j] += sig[:, : j - i] * gain
    if rev:
        send[:, i:j] += sig[:, : j - i] * gain * rev


def t_(dur):
    return np.arange(int(dur * SR)) / SR


def lp(x, hz, order=2):
    return sosfilt(butter(order, hz, "low", fs=SR, output="sos"), x)


def hp(x, hz, order=2):
    return sosfilt(butter(order, hz, "high", fs=SR, output="sos"), x)


def bp(x, lo, hi, order=2):
    return sosfilt(butter(order, [lo, hi], "band", fs=SR, output="sos"), x)


def env(t, a=0.005, r=0.05, dur=None):
    dur = dur if dur is not None else t[-1]
    return np.clip(t / a, 0, 1) * np.clip((dur - t) / r, 0, 1)


def saw(f, t):
    return 2 * ((t * f) % 1.0) - 1


# ---- instruments ------------------------------------------------------------------------------------------------


def kick(gain=1.0):
    t = t_(0.5)
    f = 44 + 120 * np.exp(-t * 30)
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 6.5)
    click = hp(rng.standard_normal(len(t)), 2000) * np.exp(-t * 400) * 0.35
    return np.tanh((body + click) * 1.6) * gain


def clap():
    t = t_(0.35)
    n = bp(rng.standard_normal(len(t)), 900, 3200)
    e = sum(np.exp(-np.clip(t - d, 0, None) * 120) * (t >= d) for d in (0, 0.011, 0.022)) + 0.5 * np.exp(-t * 16)
    return n * e * 0.8


def hat(open_=False):
    t = t_(0.28 if open_ else 0.06)
    return hp(rng.standard_normal(len(t)), 7000) * np.exp(-t * (16 if open_ else 95))


def bass(f, dur):
    t = t_(dur)
    x = lp(saw(f, t) + 0.6 * np.sin(2 * np.pi * f * t), 520) + 0.5 * np.sin(2 * np.pi * f * t)
    return x * env(t, 0.004, 0.04)


def pad(freqs, dur):
    t = t_(dur)
    out = np.zeros((2, len(t)))
    for f in freqs:
        for side, cents in ((0, -8), (1, 8)):
            out[side] += saw(f * 2 ** (cents / 1200), t) + 0.5 * saw(f * 2 ** (-cents / 2400) / 2, t)
    out = np.vstack([lp(out[0], 1400, 4), lp(out[1], 1400, 4)]) / (len(freqs) * 2)
    return out * env(t, 0.35, 0.6)


def pluck(f, dur=0.3):
    t = t_(dur)
    return lp(saw(f, t), 2400) * np.exp(-t * 11) * env(t, 0.002, 0.03)


def beep(f=1600, dur=0.09):
    """The base station's passive buzzer: a square wave."""
    t = t_(dur)
    return lp(np.sign(np.sin(2 * np.pi * f * t)), 6000) * env(t, 0.003, 0.012) * 0.5


def chime(f=1320, dur=1.4):
    t = t_(dur)
    x = sum(a * np.sin(2 * np.pi * f * m * t) * np.exp(-t * d) for m, a, d in ((1, 1, 3), (2.76, 0.35, 6), (5.4, 0.15, 10)))
    return x * env(t, 0.002, 0.2)


def blip(f=1760, dur=0.12):
    t = t_(dur)
    return np.sin(2 * np.pi * f * t) * np.exp(-t * 30) * env(t, 0.002, 0.02)


def impact(dur=2.2):
    t = t_(dur)
    boom = np.sin(2 * np.pi * np.cumsum(38 + 50 * np.exp(-t * 8)) / SR) * np.exp(-t * 2.2)
    crash = lp(rng.standard_normal(len(t)), 5000) * np.exp(-t * 5) * 0.45
    return np.tanh((boom + crash) * 1.4)


def riser(dur):
    t = t_(dur)
    u = t / dur
    noise = rng.standard_normal(len(t))
    out = np.zeros(len(t))
    blk = 2048
    for s in range(0, len(t), blk):  # sweep a band up through the noise
        c = 300 + 6000 * u[min(s, len(t) - 1)] ** 2
        out[s : s + blk] = bp(noise[s : s + blk + 512], c * 0.7, min(c * 1.4, SR / 2 - 100))[: len(out[s : s + blk])]
    tone = np.sin(2 * np.pi * np.cumsum(180 + 900 * u**2) / SR) * 0.25
    return (out + tone) * u**2.2


def whoosh(dur=0.5, reverse=False):
    t = t_(dur)
    u = t / dur
    x = bp(rng.standard_normal(len(t)), 500, 4000) * np.sin(np.pi * u) ** 2
    return x[::-1] if reverse else x


def click():
    t = t_(0.012)
    return hp(rng.standard_normal(len(t)), 3000) * np.exp(-t * 500) * 0.6


# ---- arrangement ------------------------------------------------------------------------------------------------

A, Fm, Cm, G = 0, 1, 2, 3
CHORDS = {  # pad voicing, bass root, arp tones
    A: ([220.0, 261.63, 329.63], 55.0, [440, 523.25, 659.25, 880]),
    Fm: ([174.61, 220.0, 261.63], 43.65, [349.23, 440, 523.25, 698.46]),
    Cm: ([261.63, 329.63, 392.0], 65.41, [523.25, 659.25, 784, 1046.5]),
    G: ([196.0, 246.94, 293.66], 49.0, [392, 493.88, 587.33, 783.99]),
}
PROG = [A, Fm, Cm, G]

INTRO, HOOK, GROOVE, BREAK, OUTRO = range(5)


def section(b):
    if b <= 2:
        return INTRO
    if b <= 6:
        return HOOK
    if b in (28, 29):
        return BREAK
    if b >= 39:
        return OUTRO
    return GROOVE


kicks = []
for b in range(BARS):
    t0 = b * BAR
    s = section(b)
    chord = PROG[b % 4]
    voicing, root, arp = CHORDS[chord]
    if s != OUTRO:
        add(music, pad(voicing, BAR + 0.5), t0, gain={INTRO: 0.22, HOOK: 0.2}.get(s, 0.3), rev=0.4)
    if s == HOOK:
        add(music, bass(root, BAR - 0.05), t0, gain=0.38)
        for beat in (0, 2):
            add(drums, kick(0.75), t0 + beat * BEAT)
            kicks.append(t0 + beat * BEAT)
        if b < 6:
            add(drums, clap(), t0 + 2 * BEAT, gain=0.5, rev=0.3)
        for e in range(8):
            add(drums, hat(), t0 + e * BEAT / 2, gain=0.13 if e % 2 else 0.07, pan=0.3)
    if s == INTRO and b == 2:
        for e in range(8):
            add(drums, hat(), t0 + e * BEAT / 2, gain=0.12 if e % 2 else 0.06, pan=0.3)
    if s == GROOVE:
        for beat in range(4):
            add(drums, kick(), t0 + beat * BEAT)
            kicks.append(t0 + beat * BEAT)
            add(music, bass(root * (2 if beat == 3 else 1), 0.2), t0 + beat * BEAT + BEAT / 2, gain=0.6)
        for beat in (1, 3):
            add(drums, clap(), t0 + beat * BEAT, gain=0.55, rev=0.25)
        for sx in range(16):
            v = (0.2, 0.08, 0.26, 0.08)[sx % 4]
            add(drums, hat(open_=(sx % 8 == 6 and b % 2 == 1)), t0 + sx * BEAT / 4, gain=v, pan=0.35 if sx % 2 else -0.2)
        if b >= 13:  # 16th-note arp from the hardware scene on
            for sx in range(16):
                f = arp[(sx * 3) % 4] * (2 if sx % 8 == 7 else 1)
                add(music, pluck(f), t0 + sx * BEAT / 4, gain=0.1 if b < 30 else 0.13, pan=-0.4 if sx % 2 else 0.4, rev=0.35)

# the hook's snare roll and riser into the drop (bar 7)
for i in range(4):
    add(drums, clap(), 6 * BAR + 2 * BEAT + i * BEAT / 4, gain=0.25 + i * 0.05)
for i in range(8):
    add(drums, clap(), 6 * BAR + 3 * BEAT + i * BEAT / 8, gain=0.3 + i * 0.04)
add(fx, riser(BAR), 6 * BAR, gain=0.5, rev=0.3)

# breakdown (Levels): stabs on the three panel slams, riser into Coach
for f in (1680, 1685, 1690):
    add(music, pad(CHORDS[A][0], 0.45) * 2.2, sec(f), gain=0.5, rev=0.5)
    add(drums, kick(0.8), sec(f))
add(fx, riser(BAR), 29 * BAR, gain=0.45, rev=0.3)
for i in range(8):
    add(drums, clap(), 29 * BAR + 3 * BEAT + i * BEAT / 8, gain=0.25 + i * 0.04)

# outro: Check. Coach. Share. then the last chord
for i, f in enumerate((2340, 2355, 2370)):
    add(fx, impact(1.2), sec(f), gain=0.5)
    add(drums, kick(), sec(f))
    add(music, pad([v * (1, 1.12246, 1.33484)[i] for v in CHORDS[A][0]], 0.5) * 2, sec(f), gain=0.45, rev=0.5)
for i in range(8):
    add(drums, clap(), sec(2385) + i * BEAT / 8, gain=0.25 + i * 0.03)
add(music, pad([110, 220, 261.63, 329.63, 493.88], 6.0) * 1.3, 40 * BAR, gain=0.5, rev=0.8)
add(fx, impact(3.0), 40 * BAR, gain=0.4)

# ---- cues, on the frames where they happen on screen --------------------------------------------------------------

S = SCENES
for f in (0, 15, 30, 45):  # cold open: LED blinks
    add(fx, blip(1760), sec(f), gain=0.35, rev=0.5)
add(fx, riser(sec(118 - 62)) * 0.5, sec(62), gain=0.25)  # the pen drawing the signal
add(fx, whoosh(0.3), sec(S["hook"]) - 0.15, gain=0.3)
for f in (180, 240, 300):  # stat slams
    add(fx, impact(1.4), sec(f), gain=0.45)
add(fx, chime(1318.5, 1.2), sec(S["hook"] + 214), gain=0.25, rev=0.5)  # "your home."
add(fx, impact(2.5), sec(S["logo"]), gain=0.6)  # the drop
add(fx, chime(1760, 1.6), sec(S["logo"] + 60), gain=0.3, rev=0.6)  # LED lands on the i
for i, f in enumerate((30, 45, 60, 75)):  # STEADI nodes light
    add(fx, blip((880, 1046.5, 1318.5, 1760)[i]), sec(S["loop"] + f), gain=0.3, rev=0.5)
add(fx, riser(sec(40)), sec(S["loop"] + 138), gain=0.4)  # zoom-through
add(fx, impact(1.2), sec(S["hardware"]), gain=0.35)
for f in (17, 32, 47):  # base station button presses
    add(fx, beep(1500, 0.11), sec(S["hardware"] + 118 + f), gain=0.35)
for f in (S["tug"], S["dual"], S["chair"], S["levels"], S["grok"], S["outro"]):  # shutter and wipe cuts
    add(fx, whoosh(0.45), sec(f) - 0.25, gain=0.35, pan=-0.2)
add(fx, beep(2000, 0.16), sec(S["tug"] + 15), gain=0.4)  # "Go"
add(fx, beep(2000, 0.08), sec(S["tug"] + 150), gain=0.3)  # sat down: two short tones
add(fx, beep(2600, 0.1), sec(S["tug"] + 150) + 0.1, gain=0.3)
for i in range(9):  # animals named
    add(fx, pluck((523.25, 587.33, 659.25, 783.99, 880, 1046.5, 1174.66, 1318.5, 1567.98)[i], 0.25), sec(S["dual"] + 14 + i * 8), gain=0.3, pan=(-0.5, 0.5)[i % 2], rev=0.3)
add(fx, whoosh(0.35, reverse=True), sec(S["dual"] + 92), gain=0.3)
add(fx, chime(1760, 0.8), sec(S["dual"] + 104), gain=0.2, rev=0.4)
for i in range(12):  # chair stands: a beep per stand, dotted eighths
    add(fx, beep(1600, 0.07), sec(S["chair"] + round(8 + i * 11.25)), gain=0.3)
add(fx, chime(1318.5, 1.0), sec(S["chair"] + 144), gain=0.25, rev=0.5)
add(fx, whoosh(0.25), sec(S["balance"]) - 0.12, gain=0.25)
for f in (64, 114, 164):  # holds complete
    add(fx, chime(1567.98, 0.8), sec(S["balance"] + f), gain=0.18, rev=0.5)
for d in (0, 0.14):  # sway warning
    add(fx, beep(2400, 0.07), sec(S["balance"] + 140) + d, gain=0.35)
add(fx, whoosh(0.6), sec(S["levels"] + 34), gain=0.3)
add(fx, whoosh(0.6, reverse=True), sec(S["levels"] + 100), gain=0.3)
add(fx, blip(1760), sec(S["levels"] + 118), gain=0.3, rev=0.5)
for i in range(8):  # coach reps
    add(fx, beep(1500, 0.07), sec(S["coach"] + 15 + i * 15), gain=0.28)
for i, f in enumerate((128, 135, 143, 150, 158)):  # exercise days
    add(fx, pluck((659.25, 783.99, 880, 1046.5, 1318.5)[i], 0.3), sec(S["coach"] + f), gain=0.35, rev=0.3)
add(fx, whoosh(0.9), sec(S["dash"]), gain=0.3)
add(fx, whoosh(0.8), sec(S["dash"] + 120), gain=0.25)
add(fx, click(), sec(S["dash"] + 180), gain=0.6)
add(fx, whoosh(0.4), sec(S["dash"] + 180), gain=0.2)
for f in range(14, 78, 2):  # typewriter
    add(fx, click(), sec(S["grok"] + f), gain=0.25 + 0.1 * rng.random(), pan=rng.uniform(-0.3, 0.3))
for f in (60, 70, 80, 90):  # guardrail checks
    add(fx, blip(1318.5, 0.1), sec(S["grok"] + f), gain=0.3, rev=0.3)
for f in (166, 172):  # the LED blinks out
    add(fx, blip(1760), sec(S["outro"] + f), gain=0.3, rev=0.6)

# ---- mix ----------------------------------------------------------------------------------------------------------

duck = np.ones(N)
for k in kicks:
    i = int(k * SR)
    t = t_(0.35)
    j = min(N, i + len(t))
    duck[i:j] = np.minimum(duck[i:j], 1 - 0.55 * np.exp(-t * 9)[: j - i])
music *= duck

ir_t = t_(1.6)
ir = rng.standard_normal((2, len(ir_t))) * np.exp(-ir_t * 3.2)
ir[:, : int(0.012 * SR)] = 0
wet = np.vstack([fftconvolve(send[c], ir[c])[:N] for c in range(2)]) * 0.012

master = music * 0.9 + drums * 0.75 + fx * 0.9 + wet
master = np.vstack([hp(master[c], 28) for c in range(2)])
master = np.tanh(master * 1.1)
master *= 0.89 / np.max(np.abs(master))
fade = np.clip((N - np.arange(N)) / (0.4 * SR), 0, 1)
master *= fade

out = Path(__file__).resolve().parent.parent / "public" / "music.wav"
pcm = (master.T * 32767).astype("<i2")
with wave.open(str(out), "wb") as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes(pcm.tobytes())
print(f"wrote {out} ({N / SR:.1f} s)")
