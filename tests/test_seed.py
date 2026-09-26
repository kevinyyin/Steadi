from datetime import date

from checkin.seed import seed_dad
from checkin.store import Store


def test_simulated_dad_tells_the_story(tmp_path):
    today = date(2026, 9, 26)
    dad = seed_dad(Store(tmp_path), today)
    assert dad["name"] == "Simulated: Dad" and dad["simulated"]
    levels = [c["level"] for c in dad["checkins"]]
    assert levels == ["green", "green", "green", "amber", "amber", "green", "green", "green"]
    assert [f["id"] for f in dad["checkins"][3]["flags"]] == ["chair_stand"]
    assert dad["checkins"][-1]["date"].startswith("2026-09-26")
    assert all(c["simulated"] for c in dad["checkins"] + dad["exercise"])
    flag_day = dad["checkins"][3]["date"][:10]
    before = [e for e in dad["exercise"] if e["date"][:10] < flag_day]
    after = [e for e in dad["exercise"] if e["date"][:10] > flag_day]
    assert len(before) == 3 and len(after) >= 15
    assert after[0]["plan"]["sit_to_stand"]["sets"] == 3  # leans on chair stands, the weak area
    assert Store(tmp_path).get("sim-dad")["checkins"][-1]["level"] == "green"
