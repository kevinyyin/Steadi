import json
import re
from datetime import date, datetime, timedelta

import pytest

from checkin import steadi


def person(age=78, sex="male", **answers):
    profile = {"age": age, "sex": sex, "fallen": False, "unsteady": False, "worried": False, **answers}
    return {"id": "p", "name": "Pat", "simulated": False, "profile": profile, "checkins": [], "exercise": []}


def metrics(tug=10.0, dual=12.0, stands=13, tandem=10.0, feet=10.0, semi=10.0):
    return steadi.metrics_from_steps({
        "tug": {"tug_s": tug}, "dual_tug": {"tug_s": dual}, "chair_stand": {"stands": stands},
        "balance_feet_together": {"hold_s": feet, "sway": 0.1},
        "balance_semi_tandem": {"hold_s": semi, "sway": 0.2},
        "balance_tandem": {"hold_s": tandem, "sway": 0.3},
    })


@pytest.mark.parametrize("age, sex, cutoff, label", [
    (60, "male", 14, "men 60–64"), (64, "male", 14, "men 60–64"), (65, "male", 12, "men 65–69"),
    (78, "male", 11, "men 75–79"), (94, "male", 7, "men 90–94"), (62, "female", 12, "women 60–64"),
    (72, "female", 10, "women 70–74"), (91, "female", 4, "women 90–94"),
])
def test_chair_norms_match_the_steadi_table(age, sex, cutoff, label):
    assert steadi.chair_norm(age, sex) == (cutoff, label)


def test_ages_outside_the_table_use_the_nearest_group_and_say_so():
    assert steadi.chair_norm(25, "female") == (12, "women 60–64 (the youngest STEADI group)")
    assert steadi.chair_norm(97, "male") == (7, "men 90–94 (the oldest STEADI group)")


def test_cutoffs_are_inclusive_where_steadi_says():
    ids = lambda m: [f["id"] for f in steadi.flags_for(person()["profile"], m)]  # noqa: E731
    assert ids(metrics(tug=11.99)) == [] and ids(metrics(tug=12.0)) == ["tug"]
    assert ids(metrics(stands=11)) == [] and ids(metrics(stands=10)) == ["chair_stand"]
    assert ids(metrics(tandem=10.0)) == [] and ids(metrics(tandem=9.9)) == ["balance"]


def test_any_yes_to_the_key_questions_is_one_flag_naming_the_answers():
    flags = steadi.flags_for(person(fallen=True, worried=True)["profile"], metrics())
    assert [f["id"] for f in flags] == ["key_questions"]
    assert "fallen in the past year" in flags[0]["text"] and "worries about falling" in flags[0]["text"]


def test_dual_task_cost_and_stopping_at_the_first_failed_stance():
    m = steadi.metrics_from_steps({"tug": {"tug_s": 10.0}, "dual_tug": {"tug_s": 12.5},
                                   "balance_feet_together": {"hold_s": 10.0, "sway": 0.1},
                                   "balance_semi_tandem": {"hold_s": 4.2, "sway": 0.4}})
    assert m["dual_task_cost_pct"] == 25.0 and m["chair_stands"] is None
    assert (m["semi_tandem_s"], m["tandem_s"]) == (4.2, 0.0)  # tandem not attempted: STEADI counts it as failed


def test_a_sensor_error_never_becomes_a_zero():
    m = steadi.metrics_from_steps({"tug": {"error": "no sensor data"}, "chair_stand": {"error": "x"},
                                   "balance_feet_together": {"error": "x"}})
    assert m["tug_s"] is None and m["chair_stands"] is None and m["tandem_s"] is None
    assert steadi.flags_for(person()["profile"], m) == []


def test_levels():
    assert steadi.level_for([], []) == "green"
    assert steadi.level_for([{"id": "tug"}], []) == "amber"
    assert steadi.level_for([], [{"id": "tug_s"}]) == "amber"
    assert steadi.level_for([{"id": "tug"}, {"id": "balance"}], []) == "red"


def add(p, m, day):
    rec = steadi.evaluate(p, m, datetime(2026, 9, 1) + timedelta(weeks=day))
    p["checkins"].append(rec)
    return rec


def test_change_from_baseline_needs_two_earlier_check_ins():
    p = person()
    assert add(p, metrics(stands=13), 0)["changes"]["chair_stands"] is None
    assert add(p, metrics(stands=13), 1)["changes"]["chair_stands"] is None
    ch = add(p, metrics(stands=12), 2)["changes"]["chair_stands"]
    assert ch == {"baseline": 13, "change": -1, "worse": False}


def test_sustained_decline_needs_two_worse_check_ins_in_a_row():
    p = person(age=62, sex="female")  # norm 12: 13 → 11 would flag, so stay above it
    for i, stands in enumerate([17, 17, 17]):
        add(p, metrics(stands=stands), i)
    first = add(p, metrics(stands=14), 3)
    assert first["changes"]["chair_stands"]["worse"] and first["declines"] == [] and first["level"] == "green"
    second = add(p, metrics(stands=14), 4)
    assert [d["id"] for d in second["declines"]] == ["chair_stands"] and second["level"] == "amber"
    assert "change from baseline" not in second["alert"]["title"]  # plain title; the items carry the detail


def test_alert_wording_never_overclaims():
    p = person(fallen=True)
    rec = add(p, metrics(tug=13.0, stands=8, tandem=3.0), 0)
    assert rec["level"] == "red" and len(rec["alert"]["items"]) == 4
    text = json.dumps(rec).lower()
    assert "flags increased fall risk" in text
    assert not re.search(r"diagnos|predict|prevent|guarantee", text)


def test_plan_leans_on_the_weakest_area():
    def plan_after(**kw):
        p = person()  # 78-year-old man: the STEADI line is 11 stands
        add(p, metrics(**kw), 0)
        plan = steadi.make_plan(p)
        return plan["sit_to_stand"]["sets"], plan["balance"]["holds"]

    assert steadi.make_plan(person())["why"] == "no check-in yet: the standard plan"
    assert plan_after(stands=9) == (3, 2)  # below the line
    assert plan_after(stands=12) == (3, 2)  # near it still counts as low
    assert plan_after(stands=13) == (2, 2)  # a full tandem hold is not a weak area
    assert plan_after(stands=16, tandem=6.0) == (2, 4)
    assert plan_after(stands=9, tandem=6.0) == (3, 4)


def test_balance_holds_progress_once_every_hold_hits_its_target():
    hold = lambda stance, s: {"stance": stance, "hold_s": s, "target_s": 20.0}  # noqa: E731
    assert steadi.next_stance([]) == "feet_together"
    assert steadi.next_stance([{"holds": [hold("feet_together", 20), hold("feet_together", 20)]}]) == "semi_tandem"
    assert steadi.next_stance([{"holds": [hold("semi_tandem", 20), hold("semi_tandem", 9)]}]) == "semi_tandem"
    assert steadi.next_stance([{"holds": [hold("tandem", 20)]}]) == "tandem"
    assert steadi.next_stance([{"holds": [hold("tandem", 20)]}, {"holds": []}]) == "tandem"


def test_adherence_counts_exercise_days_per_week():
    today = date(2026, 9, 26)  # a Saturday
    logs = [{"date": f"2026-09-{d:02d}T09:00:00", "sets": [{"reps": 8}], "holds": [{"hold_s": 20.0}]}
            for d in (21, 21, 22, 24, 26, 14)]
    a = steadi.adherence(logs, today, weeks=2)
    assert a["weeks"] == [
        {"week_start": "2026-09-14", "days": 1, "sessions": 1, "reps": 8, "hold_s": 20.0, "simulated": False},
        {"week_start": "2026-09-21", "days": 4, "sessions": 5, "reps": 40, "hold_s": 100.0, "simulated": False},
    ]
    assert a["last_7_days"] == 4 and a["target_days_per_week"] == 5


def test_dashboard_bundles_everything_the_page_shows():
    p = person()
    add(p, metrics(stands=9), 0)
    d = steadi.dashboard(p, date(2026, 9, 26))
    assert set(d) == {"person", "latest", "level", "alert", "trends", "plan", "adherence", "exercise"}
    assert d["trends"]["series"]["chair_stands"] == [9] and d["trends"]["cutoffs"]["chair_stands"] == 11


TODAY = date(2026, 9, 26)


def session(day, reps=8, target=8, stance="feet_together", hold=20.0):
    """One exercise log from September `day`: two sets and two supported holds."""
    return {"date": f"2026-09-{day:02d}T09:00:00", "sets": [{"reps": reps, "target": target}] * 2,
            "holds": [{"stance": stance, "hold_s": hold, "target_s": 20.0}] * 2}


def plan_for(*logs, p=None):
    p = p or person()
    p["exercise"] = list(logs)
    return steadi.make_plan(p, TODAY)


def test_reps_go_up_once_every_set_hits_its_target():
    reps = lambda *logs: plan_for(*logs)["sit_to_stand"]["reps"]  # noqa: E731
    assert reps(session(22), session(24), session(25)) == 9
    assert reps(session(22), session(24), session(25, reps=6)) == 8  # missed the target: same reps
    assert reps(session(22), session(24), session(25, reps=10, target=10)) == 10  # sets of 5–10 at most
    assert reps(session(22), session(24, reps=9, target=9), session(25, reps=5, target=5)) == 10  # a demo doesn't count


def test_a_slow_decline_adds_exercise_for_that_area():
    p = person(age=62, sex="female")  # STEADI line 12: 14 stands is not near it, so only the decline can add a set
    for i, stands in enumerate([17, 17, 17, 14, 14]):
        add(p, metrics(stands=stands), i)
    assert [d["id"] for d in p["checkins"][-1]["declines"]] == ["chair_stands"]
    plan = steadi.make_plan(p, TODAY)
    assert plan["sit_to_stand"]["sets"] == 3 and "slipped below their baseline" in plan["why"]


def test_missed_sessions_pause_progression():
    plan = plan_for(session(10), session(25))  # every target hit, but 1 exercise day in the last 7
    assert plan["sit_to_stand"]["reps"] == 8 and plan["balance"]["stance"] == "feet_together"
    assert "1 of 3 exercise days" in plan["why"]
    plan = plan_for(session(10), session(23), session(24), session(25))  # 3 days: move up
    assert plan["sit_to_stand"]["reps"] == 9 and plan["balance"]["stance"] == "semi_tandem"
    assert "exercise days" not in plan["why"]
