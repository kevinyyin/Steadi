"""People (profile, check-ins, exercise logs) as JSON files, and raw recordings as CSV."""

import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np

ID_RE = re.compile(r"[a-z0-9][a-z0-9-]{0,63}")
COLUMNS = ["t", "ax", "ay", "az", "gx", "gy", "gz", "step"]


class Store:
    def __init__(self, root):
        self.root = Path(root)
        (self.root / "people").mkdir(parents=True, exist_ok=True)
        (self.root / "recordings").mkdir(parents=True, exist_ok=True)

    def _path(self, pid):
        if not ID_RE.fullmatch(pid or ""):
            raise KeyError(pid)
        return self.root / "people" / f"{pid}.json"

    def people(self):
        docs = [json.loads(p.read_text()) for p in (self.root / "people").glob("*.json")]
        out = [{"id": d["id"], "name": d["name"], "simulated": d["simulated"]} for d in docs]
        return sorted(out, key=lambda p: (p["name"].lower(), p["id"]))

    def get(self, pid):
        path = self._path(pid)
        if not path.exists():
            raise KeyError(pid)
        return json.loads(path.read_text())

    def save(self, person):
        path = self._path(person["id"])
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(person, indent=1))
        tmp.replace(path)  # atomic: a crash mid-write never leaves half a file

    def create(self, name, profile, simulated=False, pid=None):
        base = pid or re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:50] or "person"
        pid, n = base, 1
        while self._path(pid).exists():
            n += 1
            pid = f"{base}-{n}"
        person = {"id": pid, "name": name, "simulated": simulated, "profile": profile, "checkins": [],
                  "exercise": []}
        self.save(person)
        return person

    def recording_path(self, session_id):
        return self.root / "recordings" / f"{session_id}.csv"


@dataclass
class Recording:
    data: np.ndarray  # (n, 7): t, ax, ay, az (g), gx, gy, gz (deg/s)
    steps: dict  # step id -> (t_go, t_end)
    simulated: bool


def write_recording(path, data, tags, source, simulated):
    """`tags`: list of (step id, t_go, t_end). The header keeps each step's exact "Go" and end times;
    the `step` column marks the same windows for anyone plotting the file."""
    path = Path(path)
    with path.open("w", newline="") as f:
        f.write(f"# source={source} simulated={int(simulated)}\n")
        for sid, a, b in tags:
            f.write(f"# step {sid} {a:.3f} {b:.3f}\n")
        w = csv.writer(f)
        w.writerow(COLUMNS)
        for row in data:
            step = next((sid for sid, a, b in tags if a <= row[0] <= b), "")
            w.writerow([f"{row[0]:.3f}", *(f"{v:.4f}" for v in row[1:7]), step])


def read_recording(path):
    lines = Path(path).read_text().splitlines()
    head = [ln[1:].split() for ln in lines if ln.startswith("#")]
    simulated = any("simulated=1" in parts for parts in head)
    steps = {p[1]: (float(p[2]), float(p[3])) for p in head if len(p) == 4 and p[0] == "step"}
    rows = list(csv.DictReader(ln for ln in lines if not ln.startswith("#")))
    if not rows or set(COLUMNS[:7]) - set(rows[0]):
        raise ValueError(f"{path}: expected columns {','.join(COLUMNS)}")
    data = np.array([[float(r[c]) for c in COLUMNS[:7]] for r in rows])
    return Recording(data, steps, simulated)
