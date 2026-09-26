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
    assert "flags increased fall risk" in summary.template(d)
    assert d["latest"]["alert"]["note"] == steadi.NOTE  # the doctor-facing alert keeps the STEADI note


def test_family_template_is_plain_words(dad):
    text = summary.template(dash(dad))  # shown on Home to the family and the person
    assert text.endswith(summary.FAMILY_NOTE)
    assert "fall-risk screening" in text
    assert not JARGON.search(text)


def test_ai_summary_used_when_it_passes_the_checks(dad):
    out = summary.summaries(dash(dad), ask=lambda s, u: "Timed Up and Go took 10.8 s, better than baseline.")
    assert out["family_by"] == "ai"
    assert out["family"] == "Simulated data. Timed Up and Go took 10.8 s, better than baseline."


@pytest.mark.parametrize(
    "reply",
    [
        "Timed Up and Go took 9.5 s.",  # a number that isn't in the data
        "These results predict a fall soon.",
        "He will likely fall without help.",
        "Keep going: exercise guarantees fewer falls.",
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


def test_openai_ask_without_a_key_makes_no_call(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert summary.openai_ask("system", "user") is None
