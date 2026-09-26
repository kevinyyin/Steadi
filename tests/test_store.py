import numpy as np
import pytest

from checkin import sim
from checkin.store import Store, read_recording, write_recording


def test_people_round_trip_with_unique_ids(tmp_path):
    store = Store(tmp_path)
    a = store.create("Ana María", {"age": 70})
    b = store.create("Ana María", {"age": 71})
    assert (a["id"], b["id"]) == ("ana-mar-a", "ana-mar-a-2")
    a["checkins"].append({"level": "green"})
    store.save(a)
    assert store.get(a["id"])["checkins"] == [{"level": "green"}]
    assert [p["id"] for p in store.people()] == ["ana-mar-a", "ana-mar-a-2"]


@pytest.mark.parametrize("bad", ["../secrets", "a/b", "", "UPPER", "x" * 80])
def test_ids_cannot_escape_the_data_folder(tmp_path, bad):
    with pytest.raises(KeyError):
        Store(tmp_path).get(bad)


def test_recording_round_trip_keeps_step_windows(tmp_path):
    t, acc, gyro, _ = sim.simulate("tug", seed=1)
    data = np.column_stack([t, acc, gyro])
    path = tmp_path / "r.csv"
    write_recording(path, data, [("tug", 0.0037, 9.0)], "sim", True)
    rec = read_recording(path)
    assert rec.simulated and rec.steps == {"tug": (0.004, 9.0)}  # exact "Go", not the next sample
    assert np.allclose(rec.data, data, atol=1e-3)


def test_a_csv_without_our_columns_is_rejected(tmp_path):
    path = tmp_path / "phone.csv"
    path.write_text("Time (s),Acceleration x (m/s^2)\n0,1\n")
    with pytest.raises(ValueError, match="expected columns"):
        read_recording(path)
