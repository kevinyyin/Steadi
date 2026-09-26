"""The "Simulated: Dad" story: chair stands slip, an amber flag appears, exercise starts, scores recover."""

from datetime import datetime, time, timedelta

from . import steadi

DAD_ID = "sim-dad"
# One row per weekly check-in: TUG s, dual-task TUG s, chair stands, tandem hold s. Age 78, male: norm is 11.
WEEKS = [
    (10.8, 12.6, 13, 10.0),
    (11.0, 12.9, 12, 10.0),
    (11.3, 13.4, 11, 10.0),
    (11.7, 14.0, 10, 10.0),  # below the STEADI average: amber, and the exercise plan starts
    (11.6, 13.8, 10, 10.0),
    (11.3, 13.3, 11, 10.0),
    (11.0, 12.9, 12, 10.0),
    (10.8, 12.6, 13, 10.0),
]
FLAG_WEEK = 3  # index of the first flagged week
HOLD_CAPABILITY = {"feet_together": 30.0, "semi_tandem": 24.0, "tandem": 12.0}  # seconds Dad can hold each


def _steps(tug, dual, stands, tandem):
    bal = lambda stance, hold, sway: {"stance": stance, "hold_s": hold, "broke": hold < 10, "sway": sway,  # noqa: E731
                                      "method": "sensor", "target_s": 10.0}
    return {
        "tug": {"tug_s": tug, "method": "sensor"},
        "dual_tug": {"tug_s": dual, "method": "sensor"},
        "chair_stand": {"stands": stands, "arms_used": False},
        "balance_feet_together": bal("feet_together", 10.0, 0.12),
        "balance_semi_tandem": bal("semi_tandem", 10.0, 0.19),
        "balance_tandem": bal("tandem", tandem, 0.28),
    }


def _exercise_log(person, when):
    plan = steadi.make_plan(person, when.date())
    sts, bal = plan["sit_to_stand"], plan["balance"]
    hold = min(bal["target_s"], HOLD_CAPABILITY[bal["stance"]])
    return {
        "id": f"sim-ex-{when:%Y%m%d}", "date": when.isoformat(timespec="seconds"), "source": "sim",
        "simulated": True, "recording": None, "plan": plan,
        "sets": [{"reps": sts["reps"], "target": sts["reps"]} for _ in range(sts["sets"])],
        "holds": [{"stance": bal["stance"], "hold_s": hold, "broke": hold < bal["target_s"], "sway": 0.2,
                   "method": "sensor", "target_s": bal["target_s"]} for _ in range(bal["holds"])],
    }


def seed_dad(store, today):
    """(Re)write the simulated history so its last check-in is `today`."""
    person = {
        "id": DAD_ID, "name": "Simulated: Dad", "simulated": True,
        "profile": {"age": 78, "sex": "male", "fallen": False, "unsteady": False, "worried": False},
        "checkins": [], "exercise": [],
    }
    first = today - timedelta(weeks=len(WEEKS) - 1)
    for i, row in enumerate(WEEKS):
        day = first + timedelta(weeks=i)
        steps = _steps(*row)
        record = steadi.evaluate(person, steadi.metrics_from_steps(steps), datetime.combine(day, time(10, 0)))
        record.update(id=f"sim-{day:%Y%m%d}", source="sim", simulated=True, steps=steps, recording=None)
        person["checkins"].append(record)
        offsets = [2] if i < FLAG_WEEK else [1, 2, 3, 5, 6]  # a pamphlet once a week, then most days
        for d in offsets:
            when = datetime.combine(day + timedelta(days=d), time(9, 30))
            if when.date() < today:
                person["exercise"].append(_exercise_log(person, when))
    store.save(person)
    return person
