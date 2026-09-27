"""The one switch for every Grok call: the family summary, Ask Steady, speech to text, and any later AI feature.

Grok is on only with an XAI_API_KEY, without CHECKIN_AI=off, and while the dashboard's switch is on.
Anything that calls xAI checks ai_enabled() first and falls back to its offline version when it's False.
The dashboard switch lasts until the server restarts; CHECKIN_AI=off can't be switched back on from the page.
"""

import os

_switch = {"on": True}


def blocked_by():
    """Why Grok can't be turned on at all ("setting" or "no key"), or None."""
    if os.environ.get("CHECKIN_AI", "").strip().lower() in ("off", "0", "false", "no"):
        return "setting"
    if not os.environ.get("XAI_API_KEY"):
        return "no key"
    return None


def ai_enabled():
    """True when Grok calls are allowed right now."""
    return _switch["on"] and blocked_by() is None


def set_enabled(on):
    _switch["on"] = bool(on)


def status():
    """{"on", "available", "blocked_by"} for GET /api/ai."""
    blocked = blocked_by()
    return {"on": ai_enabled(), "available": blocked is None, "blocked_by": blocked}
