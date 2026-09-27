import csv
import json

import numpy as np
import pytest

from checkin import sim, validate
from checkin.cli import main
from checkin.store import write_recording


def _checkin_recording(path, simulated=False):
    p = sim.SimParams(stand_cycle_s=3.0, hold_s={"feet_together": 60.0, "semi_tandem": 60.0, "tandem": 4.0})
    t1, a1, g1, tug = sim.simulate("tug", p, seed=1)
    t2, a2, g2, chair = sim.simulate("chair_stand", p, seed=2)
    t3, a3, g3, tandem = sim.simulate("balance_tandem", p, seed=3)
    t2 = t2 + t1[-1] + 2.0
    t3 = t3 + t2[-1] + 2.0
    go2, go3 = t2[100], t3[100]
    data = np.vstack([np.column_stack(x) for x in ((t1, a1, g1), (t2, a2, g2), (t3, a3, g3))])
    tags = [("tug", 0.0, t1[-1]), ("chair_stand", go2, go2 + 30.0), ("balance_tandem", go3, go3 + 10.0)]
    write_recording(path, data, tags, "udp", simulated)
    return {"tug": tug["tug_s"], "chair_stand": chair["stands"], "balance_tandem": tandem["hold_s"]}


def _truth(path, rows):
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, validate.FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in validate.FIELDS})


def test_agreement_stats():
    pairs = [{"step": "tug", "truth": t, "belt": b, "diff": b - t} for t, b in ((10, 10.5), (13, 12.5), (11, 12.6))]
    s = validate.agreement(pairs, 1.0, "time")
    assert s["n"] == 3 and s["within"] == 2
    assert s["bias"] == pytest.approx(0.533, abs=1e-3) and s["mae"] == pytest.approx(0.867, abs=1e-3)
    assert s["loa"][0] < s["bias"] < s["loa"][1]
    # 13 vs 12.5: both past the 12 s cutoff; 11 vs 12.6: the belt alone would flag
    assert s["cutoff"] == {"n": 3, "agree": 2, "what": "12 s TUG cutoff"}
    counts = validate.agreement([{"step": "chair_stand", "truth": 10, "belt": 10, "diff": 0},
                                 {"step": "chair_stand", "truth": 9, "belt": 11, "diff": 2}], 1, "count")
    assert counts["exact"] == 1 and counts["within"] == 1


def test_template_lists_every_step_once_without_belt_values(tmp_path):
    rec = tmp_path / "recordings"
    rec.mkdir()
    _checkin_recording(rec / "a.csv")
    out = tmp_path / "validation" / "ground_truth.csv"
    assert validate.write_template(rec, out) == 3
    assert validate.write_template(rec, out) == 0  # re-running keeps typed-in rows and adds nothing
    rows = list(csv.DictReader(out.read_text().splitlines()))
    assert [r["step"] for r in rows] == ["tug", "chair_stand", "balance_tandem"]
    assert all(r["truth"] == "" for r in rows) and set(rows[0]) == set(validate.FIELDS)


def test_validate_pairs_belt_with_truth_and_writes_the_report(tmp_path, capsys):
    rec = tmp_path / "recordings"
    rec.mkdir()
    true = _checkin_recording(rec / "a.csv")
    truth = tmp_path / "ground_truth.csv"
    _truth(truth, [{"recording": "a.csv", "step": "tug", "truth": round(true["tug"] + 0.2, 2), "person": "p1"},
                   {"recording": "a.csv", "step": "chair_stand", "truth": true["chair_stand"], "person": "p1"},
                   {"recording": "a.csv", "step": "balance_tandem", "truth": true["balance_tandem"]},
                   {"recording": "a.csv", "step": "balance_semi_tandem", "truth": 10}])  # never recorded
    out = tmp_path / "report"
    main(["validate", str(truth), "--recordings", str(rec), "--out", str(out)])
    printed = capsys.readouterr().out
    assert "Simulated" not in printed and "1 not scored" in printed
    doc = json.loads((out / "results.json").read_text())
    assert doc["simulated"] is False
    stats = doc["stats"]
    assert stats["tug"]["n"] == 1 and abs(stats["tug"]["bias"]) < 0.7
    assert stats["chair_stand"]["exact"] == 1
    assert stats["balance"]["n"] == 1 and stats["balance"]["not_scored"] == 1
    for slug in ("summary", "tug-scatter", "tug-bland-altman", "balance-scatter", "counts"):
        svg = (out / f"{slug}.svg").read_text()
        assert 'role="img"' in svg and "Simulated" not in svg
        assert (out / f"{slug}.png").read_bytes()[:4] == b"\x89PNG"
    page = (out / "report.html").read_text()
    assert "not a clinical validation" in page
    assert "http://" not in page.replace("http://www.w3.org/2000/svg", "")  # offline: no network assets
    assert "https://" not in page


def test_simulated_run_is_labelled_everywhere(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("checkin.cli.DATA", tmp_path)
    main(["validate", "--simulated", "--no-png"])
    printed = capsys.readouterr().out
    assert "Timed Up and Go (Simulated)" in printed
    out = tmp_path / "validation" / "simulated" / "report"
    assert json.loads((out / "results.json").read_text())["simulated"] is True
    for svg in out.glob("*.svg"):
        assert "Simulated" in svg.read_text(), svg.name
    assert "<strong>Simulated.</strong>" in (out / "report.html").read_text()
    assert not list(out.glob("*.png"))


def test_missing_truth_file_points_at_the_template(tmp_path):
    with pytest.raises(SystemExit, match="--template"):
        main(["validate", str(tmp_path / "none.csv")])
