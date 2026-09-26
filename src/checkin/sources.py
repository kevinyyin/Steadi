"""Motion sources. Each one has:

    read() -> (n, 7) array of t (host clock, s), ax, ay, az (g), gx, gy, gz (deg/s), new since the last call
    act(kind, **kw) -> None   the simulator and CSV replay act out a step from now; hardware ignores it
    close() -> None
    kind: str, simulated: bool
"""

import json
import queue
import socket
import threading
import urllib.request

import numpy as np

from . import sim
from .store import read_recording

EMPTY = np.empty((0, 7))


class SimSource:
    kind = "sim"
    simulated = True

    def __init__(self, clock, params=None, seed=0):
        self.clock = clock
        self.p = params or sim.SimParams()
        self.rng = np.random.default_rng(seed)
        self.dev = sim.Device(self.p, self.rng)
        self.n = int(clock.now() * sim.FS)  # next sample index on the 100 Hz grid
        self.pitch = sim.SIT_PITCH
        self.script = None  # (first sample index, acc, gyro, pitch after)
        self.truth = {}  # activity kind -> true scores of its latest run

    def act(self, kind, **kw):
        acc, gyro, truth, after = sim.render(kind, self.p, self.rng, **kw)
        start = max(self.n, int(round(self.clock.now() * sim.FS)))
        self.script = (start, acc, gyro, after)
        self.truth[kind] = truth

    def read(self):
        end = int(self.clock.now() * sim.FS)
        if end <= self.n:
            return EMPTY
        idx = np.arange(self.n, end)
        self.n = end
        acc, gyro = sim.idle(len(idx), self.pitch)
        if self.script:
            start, sa, sg, after = self.script
            k = idx - start
            inside = (k >= 0) & (k < len(sa))
            acc[inside], gyro[inside] = sa[k[inside]], sg[k[inside]]
            past = k >= len(sa)
            if past.any():
                acc[past], gyro[past] = sim.idle(int(past.sum()), after)
                self.pitch, self.script = after, None
        acc, gyro = self.dev(acc, gyro)
        return np.column_stack([idx / sim.FS, acc, gyro])

    def close(self):
        pass


class CsvSource:
    """Replays a recording in real time. Each act() jumps to the next recorded run of that step."""

    kind = "csv"

    def __init__(self, clock, path):
        self.clock = clock
        rec = read_recording(path)
        self.data, self.simulated = rec.data, rec.simulated
        self.starts = sorted((t_go, sid) for sid, (t_go, _) in rec.steps.items())
        self.played = set()
        self.n = int(clock.now() * sim.FS)
        self.pos = 0  # recording row shown when not playing
        self.play = None  # (host sample index at the jump, recording row at the jump)

    def act(self, kind, **kw):
        for t_go, sid in self.starts:
            if sid.split("#")[0] == kind and sid not in self.played:
                self.played.add(sid)
                row = int(np.searchsorted(self.data[:, 0], t_go))
                self.play = (max(self.n, int(round(self.clock.now() * sim.FS))), row)
                return
        print(f"csv source: no unplayed {kind!r} step left in the recording; holding still")

    def read(self):
        end = int(self.clock.now() * sim.FS)
        if end <= self.n:
            return EMPTY
        idx = np.arange(self.n, end)
        self.n = end
        rows = np.full(len(idx), self.pos)
        if self.play:
            k0, r0 = self.play
            live = idx >= k0
            rows[live] = np.minimum(r0 + (idx[live] - k0), len(self.data) - 1)
        self.pos = int(rows[-1])
        return np.column_stack([idx / sim.FS, self.data[rows, 1:7]])

    def close(self):
        pass


class _ClockMap:
    """Maps a device clock to the host clock. Each packet's newest sample was taken just before it
    arrived, so the smallest (arrival - newest sample time) seen so far is the best offset."""

    def __init__(self):
        self.offset = None
        self.last = None

    def update(self, newest_device_t, arrived_host_t):
        if self.last is not None and newest_device_t < self.last - 1.0:
            self.offset = None  # the device restarted
        self.last = newest_device_t
        off = arrived_host_t - newest_device_t
        self.offset = off if self.offset is None else min(self.offset, off)

    def __call__(self, device_t):
        return device_t + self.offset


class UdpSource:
    """ESP32 belt: text datagrams of `seq,ms,ax,ay,az,gx,gy,gz` lines (firmware/PROTOCOL.md)."""

    kind = "udp"
    simulated = False

    def __init__(self, clock, port, host="0.0.0.0"):
        self.clock = clock
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((host, port))
        self.sock.setblocking(False)
        self.map = _ClockMap()
        self.last_seq = None
        self.dropped = 0

    def act(self, kind, **kw):
        pass

    def read(self):
        rows = []
        while True:
            try:
                data, _ = self.sock.recvfrom(65535)
            except (BlockingIOError, InterruptedError):
                break
            packet = []
            for line in data.decode("ascii", "ignore").splitlines():
                parts = line.strip().split(",")
                if len(parts) != 8:
                    continue
                try:
                    seq, ms = int(parts[0]), int(parts[1])
                    packet.append([ms / 1000.0, *(float(v) for v in parts[2:])])
                except ValueError:
                    continue
                if self.last_seq is not None and seq > self.last_seq + 1:
                    self.dropped += seq - self.last_seq - 1
                self.last_seq = seq
            if packet:
                self.map.update(packet[-1][0], self.clock.now())
                rows += packet
        if not rows:
            return EMPTY
        rows = np.array(rows)
        rows[:, 0] = self.map(rows[:, 0])
        return rows

    def close(self):
        self.sock.close()


def _get_json(url, timeout=1.0):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read())


class PhyphoxSource:
    """Phone running phyphox with remote access on (firmware/phyphox/belt-imu.phyphox, or the built-in
    "Acceleration with g" experiment for accelerometer only). Polls /get in a background thread."""

    kind = "phyphox"
    simulated = False
    BUFFERS = ("accX", "accY", "accZ", "acc_time", "gyrX", "gyrY", "gyrZ", "gyr_time")

    def __init__(self, clock, url, fetch=_get_json, poll_s=0.1, start_thread=True):
        self.clock = clock
        self.url = url.rstrip("/")
        self.fetch = fetch
        self.poll_s = poll_s
        self.map = _ClockMap()
        self.last_acc = self.last_gyr = 0.0
        self.q = queue.SimpleQueue()
        self.error = None
        self._stop = threading.Event()
        if start_thread:
            try:
                self.fetch(self.url + "/control?cmd=start")
            except OSError as e:
                self.error = str(e)
            threading.Thread(target=self._loop, daemon=True).start()

    def act(self, kind, **kw):
        pass

    def _loop(self):
        while not self._stop.wait(self.poll_s):
            try:
                self.poll()
                self.error = None
            except (OSError, ValueError, KeyError) as e:
                self.error = str(e)

    def poll(self):
        a, g = self.last_acc, self.last_gyr
        q = "&".join(
            [f"acc{c}={a!r}|acc_time" for c in "XYZ"]
            + [f"acc_time={a!r}"]
            + [f"gyr{c}={g!r}|gyr_time" for c in "XYZ"]
            + [f"gyr_time={g!r}"]
        )
        buf = self.fetch(f"{self.url}/get?{q}")["buffer"]
        get = lambda k: np.array(buf.get(k, {}).get("buffer") or [], dtype=float)  # noqa: E731
        at = get("acc_time")
        if len(at) == 0:
            return
        acc = np.column_stack([get(f"acc{c}")[: len(at)] for c in "XYZ"]) / sim.G
        gt = get("gyr_time")
        if len(gt):
            gyro = np.column_stack([np.interp(at, gt, get(f"gyr{c}")[: len(gt)]) for c in "XYZ"])
            gyro = np.degrees(gyro)
            self.last_gyr = float(gt[-1])
        else:
            gyro = np.zeros_like(acc)  # accelerometer-only experiment
        self.last_acc = float(at[-1])
        self.map.update(self.last_acc, self.clock.now())
        rows = np.column_stack([self.map(at), acc, gyro])
        self.q.put(rows[np.isfinite(rows).all(axis=1)])

    def read(self):
        parts = []
        while not self.q.empty():
            parts.append(self.q.get())
        return np.vstack(parts) if parts else EMPTY

    def close(self):
        self._stop.set()


def open_source(spec, clock, udp_port=4210, seed=0):
    """`sim`, `csv:<file>`, `udp`, or `phyphox:<http://phone-ip:8080>`."""
    kind, _, arg = spec.partition(":")
    if kind == "sim":
        return SimSource(clock, seed=seed)
    if kind == "csv":
        return CsvSource(clock, arg)
    if kind == "udp":
        return UdpSource(clock, udp_port)
    if kind == "phyphox" and arg:
        return PhyphoxSource(clock, arg)
    if kind == "phyphox":
        raise ValueError("phyphox needs the address phyphox shows under Remote access, e.g. phyphox:http://192.168.1.23:8080")
    raise ValueError(f"unknown source {spec!r}: use sim, csv:<file>, udp, or phyphox:<url>")
