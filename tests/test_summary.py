import re
from datetime import date

import pytest

from checkin import steadi, summary
from checkin.seed import DAD_ID, seed_dad
from checkin.store import Store

TODAY = date(2026, 9, 26)
JARGON = re.compile(r"STEADI|\bTUG\b|tandem|sway|baseline|dual-task", re.IGNORECASE)


@pytest.fixture
def dad(tmp_path):
    store = Store(tmp_path)
    seed_dad(store, TODAY)
    return store.get(DAD_ID)


def dash(person):
    return steadi.dashboard(person, TODAY)


def test_doctor_summary_is_exact_and_has_no_name(dad):
    text = summary.doctor(dash(dad))
    assert "SIMULATED DATA" in text
    assert "Timed Up and Go: 10.8 s (flags at 12 s or more" in text
    assert "Chair stands first 13, worst 10 (2026-08-29), latest 13" in text
    assert "does not diagnose" in text
    assert "Dad" not in text  # this text is what goes to the AI


def test_simulated_checkins_are_labelled_for_a_real_person(dad):
    dad["simulated"] = False  # a real person whose check-ins came from the simulator
    assert "SIMULATED DATA: some check-ins are simulated" in summary.doctor(dash(dad))  # printed and downloaded


def test_flagged_checkin_reaches_both_summaries(dad):
    dad["checkins"] = dad["checkins"][:4]  # ends at the chair-stand dip
    d = dash(dad)
    assert "flags increased fall risk: 10 chair stands" in summary.doctor(d)
    family = summary.template(d)
    assert "flags increased fall risk. Leg strength: 10 stand-ups from a chair in 30 seconds" in family
    assert not JARGON.search(family)
    assert d["latest"]["alert"]["note"] == steadi.NOTE  # the doctor-facing alert keeps the STEADI note


def test_a_decline_alone_says_what_changed_not_flags(dad):
    d = dash(dad)
    d["latest"].update(flags=[], declines=[{"id": "chair_stands"}], alert={"advice": "Mention it to the doctor."})
    family = summary.template(d)
    assert "showed a change from usual. Leg strength has been worse than usual two check-ins in a row." in family
    assert "flags increased fall risk" not in family


def test_family_template_is_plain_words(dad):
    text = summary.template(dash(dad))  # shown on Home to the family and the person
    assert text.endswith(summary.FAMILY_NOTE)
    assert "fall-risk screening" in text
    assert not JARGON.search(text)


def test_family_items_use_the_home_cards_words():
    latest = {
        "metrics": {"tug_s": 12.4, "chair_stands": 9, "tandem_s": 8.2},
        "cutoffs": {"tug_s": 12.0, "tandem_s": 10.0, "chair_label": "men 90–94 (the oldest STEADI group)"},
        "key_questions": {"fallen": True, "unsteady": False, "worried": True},
        "flags": [{"id": i} for i in ("key_questions", "tug", "chair_stand", "balance")],
        "declines": [{"id": "dual_task_cost_pct"}],
    }
    assert summary.family_items(latest) == [
        "Answered yes: has had a fall in the past year; worries about falling.",
        "Standing up and walking took 12.4 seconds; 12 seconds or longer is flagged.",
        "Leg strength: 9 stand-ups from a chair in 30 seconds, fewer than average for men 90–94.",
        "Balance: held one foot right in front of the other for 8.2 seconds; under 10 seconds is flagged.",
        "Walking while naming animals has been worse than usual two check-ins in a row.",
    ]


def test_a_balance_flag_names_the_stance_that_broke():
    latest = {"metrics": {"feet_together_s": 10.0, "semi_tandem_s": 4.2, "tandem_s": 0.0},
              "cutoffs": {"tandem_s": 10.0}, "flags": [{"id": "balance"}], "key_questions": {}}
    assert summary.family_items(latest) == [
        "Balance: held one foot a little ahead of the other for 4.2 seconds (the goal is 10), "
        "so the hardest position wasn't tried."]


def test_ai_summary_used_when_it_passes_the_checks(dad):
    out = summary.summaries(dash(dad), ask=lambda s, u: "Standing up and walking took 10.8 seconds, as usual.")
    assert out["family_by"] == "ai"
    assert out["family"] == "Simulated data. Standing up and walking took 10.8 seconds, as usual."


@pytest.mark.parametrize(
    "reply",
    [
        "Timed Up and Go took 9.5 s.",  # a number that isn't in the data
        "These results predict a fall soon.",
        "He will likely fall without help.",
        "Keep going: exercise guarantees fewer falls.",
        "Timed Up and Go took 10.8 s, better than baseline.",  # clinical words the family never sees
        "",
        None,  # no API key
    ],
)
def test_template_when_the_ai_reply_is_unusable(dad, reply):
    out = summary.summaries(dash(dad), ask=lambda s, u: reply)
    assert out["family_by"] == "template"
    assert out["family"].startswith("Simulated data. The check-in on Saturday, September 26 raised no flags.")


def test_template_when_offline(dad):
    def offline(system, user):
        raise OSError("no internet")

    assert summary.summaries(dash(dad), ask=offline)["family_by"] == "template"


def test_no_checkins_never_calls_the_ai(tmp_path):
    person = Store(tmp_path).create("Pat", {"age": 70, "sex": "female", "fallen": True})

    def fail(system, user):
        raise AssertionError("called")

    out = summary.summaries(dash(person), ask=fail)
    assert "No check-ins yet." in out["doctor"]
    assert "Key questions" not in out["doctor"]
    assert out["family"] == "No check-in yet."
    assert not out["simulated"]


def test_grok_ask_without_a_key_makes_no_call(monkeypatch):
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    assert summary.grok_ask("system", "user") is None
