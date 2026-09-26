import socket

import numpy as np
import pytest

from checkin import sim
from checkin.clock import FakeClock
from checkin.signals import tug_end
from checkin.sources import CsvSource, PhyphoxSource, SimSource, UdpSource, open_source
from checkin.store import write_recording


def test_sim_source_streams_100_hz_and_acts_on_cue():
    clock = FakeClock()
    src = SimSource(clock, seed=1)
    clock.t += 2.0
    before = src.read()
    assert len(before) == 200 and np.allclose(np.diff(before[:, 0]), 0.01)
    t_go = clock.t
    src.act("tug")
    clock.t += 20.0
    d = np.vstack([before, src.read()])
    assert np.all(np.diff(d[:, 0]) > 0)
    end = tug_end(d[:, 0], d[:, 1:4], d[:, 4:7], t_go)
    assert abs(end - t_go - src.truth["tug"]["tug_s"]) < 0.5


def test_csv_source_replays_each_step_when_cued(tmp_path):
    t, acc, gyro, truth = sim.simulate("tug", seed=2)
    path = tmp_path / "rec.csv"
    write_recording(path, np.column_stack([t + 50.0, acc, gyro]), [("tug", 50.0, 50.0 + t[-1])], "sim", True)
    clock = FakeClock()
    src = CsvSource(clock, path)
    assert src.simulated
    clock.t += 1.0
    idle = src.read()
    t_go = clock.t
    src.act("tug")
    clock.t += 20.0
    d = np.vstack([idle, src.read()])
    assert abs(tug_end(d[:, 0], d[:, 1:4], d[:, 4:7], t_go) - t_go - truth["tug_s"]) < 0.5
    src.act("tug")  # nothing left to play: holds still instead of crashing
    clock.t += 1.0
    assert len(src.read()) == 100


def test_udp_source_parses_lines_counts_drops_and_maps_the_clock():
    clock = FakeClock(t=500.0)
    src = UdpSource(clock, port=0, host="127.0.0.1")
    port = src.sock.getsockname()[1]
    tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    tx.sendto(b"1,1000,0.0,0.0,1.0,0.5,0.0,0.0\n2,1010,0.0,0.0,1.01,0.5,0.0,0.0\n", ("127.0.0.1", port))
    tx.sendto(b"garbage\n5,1040,0.1,0.0,1.0,0.5,0.0,0.0\n", ("127.0.0.1", port))
    rows = np.empty((0, 7))
    for _ in range(100):
        rows = np.vstack([rows, src.read()])
        if len(rows) == 3:
            break
    tx.close()
    src.close()
    assert len(rows) == 3 and src.dropped == 2
    assert rows[:, 0] == pytest.approx([499.96, 499.97, 500.0])  # spacing kept; newest sample = arrival
    assert rows[1, 3] == pytest.approx(1.01)


def phyphox_reply(t0, n, gyro=True):
    t = [t0 + i * 0.01 for i in range(1, n + 1)]
    buf = {"acc_time": t, "accX": [0.0] * n, "accY": [0.0] * n, "accZ": [9.81] * n}
    if gyro:
        buf |= {"gyr_time": t, "gyrX": [0.1] * n, "gyrY": [0.0] * n, "gyrZ": [0.0] * n}
    return {"buffer": {k: {"size": 0, "updateMode": "partial", "buffer": v} for k, v in buf.items()},
            "status": {"measuring": True}}


def test_phyphox_source_converts_units_and_asks_only_for_new_data():
    urls = []
    replies = [phyphox_reply(0.0, 5), phyphox_reply(0.05, 3)]
    clock = FakeClock()
    src = PhyphoxSource(clock, "http://phone:8080/", fetch=lambda u: urls.append(u) or replies.pop(0),
                        start_thread=False)
    src.poll()
    src.poll()
    rows = src.read()
    assert len(rows) == 8 and rows[0, 3] == pytest.approx(1.0) and rows[0, 4] == pytest.approx(5.7296, abs=1e-3)
    assert urls[0].startswith("http://phone:8080/get?accX=0.0|acc_time") and "acc_time=0.05" in urls[1]


def test_phyphox_accelerometer_only_experiment_gives_zero_gyro():
    src = PhyphoxSource(FakeClock(), "http://phone:8080", fetch=lambda u: phyphox_reply(0.0, 4, gyro=False),
                        start_thread=False)
    src.poll()
    assert np.all(src.read()[:, 4:7] == 0.0)


@pytest.mark.parametrize("spec", ["bluetooth", "phyphox"])
def test_open_source_rejects_bad_specs(spec):
    with pytest.raises(ValueError):
        open_source(spec, FakeClock())
