import importlib.util
import time
from datetime import date

import pytest
from fastapi.testclient import TestClient

from checkin.base import VirtualBase
from checkin.clock import FakeClock
from checkin.controller import Controller
from checkin.seed import seed_dad
from checkin.server import create_app
from checkin.sources import SimSource
from checkin.store import Store

TODAY = date(2026, 9, 26)
PROFILE = {"name": "Judge", "age": 34, "sex": "female", "fallen": False, "unsteady": False, "worried": True}


@pytest.fixture
def client(tmp_path):
    clock = FakeClock()  # the whole check-in runs in simulated time
    store = Store(tmp_path)
    seed_dad(store, TODAY)
    app = create_app(Controller(SimSource(clock, seed=1), VirtualBase(), store, clock), store, today=lambda: TODAY)
    with TestClient(app) as c:
        yield c


def run_to_done(client, timeout_s=60):
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        state = client.get("/api/state").json()
        if state["phase"] in ("done", "stopped"):
            return state
        if any(s["status"] == "waiting" for s in state["steps"]):
            client.post("/api/button")
    raise AssertionError("session did not finish")


def test_dashboard_files_are_revalidated_on_every_load(client):
    for path in ("/", "/static/app.js", "/static/vendor/chart.umd.min.js"):
        r = client.get(path)
        assert r.status_code == 200 and r.headers["cache-control"] == "no-cache", path
    etag = client.get("/static/app.js").headers["etag"]
    assert client.get("/static/app.js", headers={"If-None-Match": etag}).status_code == 304


def test_people_and_profiles(client):
    assert [p["id"] for p in client.get("/api/people").json()] == ["sim-dad"]
    r = client.post("/api/people", json=PROFILE)
    assert r.status_code == 201 and r.json()["id"] == "judge"
    r = client.put("/api/people/judge", json={**PROFILE, "age": 35})
    assert r.json()["profile"]["age"] == 35
    assert client.put("/api/people/judge", json={**PROFILE, "age": 7}).status_code == 422
    assert client.put("/api/people/sim-dad", json=PROFILE).status_code == 403
    assert client.get("/api/people/..%2Fsecrets/dashboard").status_code == 404


def test_checkin_over_the_api_from_button_to_dashboard(client):
    client.post("/api/people", json=PROFILE)
    assert client.post("/api/session", json={"person_id": "judge", "mode": "checkin"}).status_code == 202
    assert client.post("/api/session", json={"person_id": "judge", "mode": "checkin"}).status_code == 409
    state = run_to_done(client)
    assert state["phase"] == "done" and all(s["status"] == "done" for s in state["steps"])
    d = client.get("/api/people/judge/dashboard").json()
    latest = d["latest"]
    assert latest["simulated"] is True and latest["metrics"]["tug_s"] > 5
    assert latest["cutoffs"]["chair_label"] == "women 60–64 (the youngest STEADI group)"
    assert "key_questions" in [f["id"] for f in latest["flags"]] and d["alert"]["level"] in ("amber", "red")
    assert d["trends"]["dates"] == [latest["date"][:10]]


def test_quick_exercise_and_adherence(client):
    client.post("/api/people", json=PROFILE)
    plan = {"sit_to_stand": {"sets": 1, "reps": 5}, "balance": {"stance": "feet_together", "holds": 0,
                                                                "target_s": 20}}
    assert client.post("/api/session", json={"person_id": "judge", "mode": "exercise", "plan": plan}).status_code == 202
    run_to_done(client)
    d = client.get("/api/people/judge/dashboard").json()
    assert d["exercise"][-1]["sets"][0]["reps"] == 5
    assert d["adherence"]["weeks"][-1]["reps"] == 5


def test_bad_session_requests(client):
    client.post("/api/people", json={**PROFILE, "age": None})
    r = client.post("/api/session", json={"person_id": "judge", "mode": "checkin"})
    assert r.status_code == 400 and "age and sex" in r.json()["detail"]
    assert client.post("/api/session", json={"person_id": "nobody", "mode": "checkin"}).status_code == 404
    bad_plan = {"sit_to_stand": {"sets": 1, "reps": 500}, "balance": {"stance": "feet_together", "holds": 0,
                                                                      "target_s": 20}}
    r = client.post("/api/session", json={"person_id": "judge", "mode": "exercise", "plan": bad_plan})
    assert r.status_code == 422


def test_cancel_over_the_api(client):
    client.post("/api/people", json=PROFILE)
    client.post("/api/session", json={"person_id": "judge", "mode": "checkin"})
    while client.get("/api/state").json()["phase"] != "running":
        pass
    client.post("/api/stop", json={"reason": "cancel"})
    assert run_to_done(client)["phase"] == "stopped"
    assert client.get("/api/people/judge/dashboard").json()["latest"] is None


def test_simulated_dad_dashboard(client):
    d = client.get("/api/people/sim-dad/dashboard").json()
    assert d["person"]["simulated"] and d["level"] == "green"
    assert d["trends"]["levels"].count("amber") == 2 and d["adherence"]["last_7_days"] == 5
    # every chart point from simulated data can be labelled "Simulated"
    assert d["trends"]["simulated"] == [True] * 8
    assert all(w["simulated"] == (w["sessions"] > 0) for w in d["adherence"]["weeks"])


def test_websocket_sends_state_then_events(client):
    with client.websocket_connect("/ws") as ws:
        first = ws.receive_json()
        assert first["type"] == "state" and first["source"]["simulated"] is True
        assert ws.receive_json()["type"] == "state"  # the idle heartbeat


def test_uvicorn_can_serve_the_websocket():
    # TestClient doesn't need it, but the real server does: without it /ws fails and the page never updates
    assert importlib.util.find_spec("websockets"), "add the websockets package"


def test_index_page_is_served(client):
    r = client.get("/")
    assert r.status_code == 200 and "<html" in r.text.lower()


def test_summary_works_with_no_ai_key(client, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    s = client.get("/api/people/sim-dad/summary").json()
    assert s["family_by"] == "template" and s["simulated"]
    assert s["doctor"].startswith("Fall-risk screening summary")
    assert client.get("/api/people/nobody/summary").status_code == 404
