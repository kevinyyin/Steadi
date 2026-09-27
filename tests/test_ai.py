import pytest

from checkin import ai


@pytest.fixture(autouse=True)
def switch_on():
    ai.set_enabled(True)
    yield
    ai.set_enabled(True)


def test_off_without_a_key(monkeypatch):
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    monkeypatch.delenv("CHECKIN_AI", raising=False)
    assert not ai.ai_enabled()
    assert ai.status() == {"on": False, "available": False, "blocked_by": "no key"}


def test_setting_off_wins_over_the_switch(monkeypatch):
    monkeypatch.setenv("XAI_API_KEY", "test-key")
    monkeypatch.setenv("CHECKIN_AI", "off")
    ai.set_enabled(True)
    assert ai.status() == {"on": False, "available": False, "blocked_by": "setting"}


def test_the_switch(monkeypatch):
    monkeypatch.setenv("XAI_API_KEY", "test-key")
    monkeypatch.delenv("CHECKIN_AI", raising=False)
    assert ai.ai_enabled()
    ai.set_enabled(False)
    assert ai.status() == {"on": False, "available": True, "blocked_by": None}
