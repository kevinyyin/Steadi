import json

import numpy as np
import pytest

from checkin import sim
from checkin.cli import main
from checkin.store import write_recording


def test_replay_scores_a_recording(tmp_path, capsys):
    p = sim.SimParams(stand_cycle_s=3.0)
    t1, a1, g1, tug = sim.simulate("tug", p, seed=1)
    t2, a2, g2, chair = sim.simulate("chair_stand", p, seed=2)
    t2 = t2 + t1[-1] + 2.0
    data = np.vstack([np.column_stack([t1, a1, g1]), np.column_stack([t2, a2, g2])])
    go2 = t2[100]  # simulate() puts 1 s of stillness before "Go"
    path = tmp_path / "rec.csv"
    write_recording(path, data, [("tug", 0.0, t1[-1]), ("chair_stand", go2, go2 + 32.0)], "udp", False)
    main(["replay", str(path), "--age", "70", "--sex", "female"])
    out = json.loads(capsys.readouterr().out)
    assert abs(out["steps"]["tug"]["tug_s"] - tug["tug_s"]) < 0.5
    assert out["steps"]["chair_stand"]["stands"] == chair["stands"] == 10
    assert out["simulated"] is False and out["flags"] == []


def test_replay_explains_an_untagged_file(tmp_path):
    path = tmp_path / "raw.csv"
    write_recording(path, np.zeros((20, 7)), [], "udp", False)
    with pytest.raises(SystemExit, match="no step tags"):
        main(["replay", str(path)])


def test_seed_writes_the_simulated_history(tmp_path, capsys):
    main(["seed", "--data", str(tmp_path)])
    doc = json.loads((tmp_path / "people" / "sim-dad.json").read_text())
    assert doc["simulated"] and len(doc["checkins"]) == 8
