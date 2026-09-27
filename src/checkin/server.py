"""FastAPI app: the JSON + WebSocket API in docs/API.md, plus the static dashboard."""

import asyncio
import collections
import contextlib
import logging
import time
from datetime import date
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import ai, steadi, summary, voice
from .controller import Busy

log = logging.getLogger(__name__)
STATIC = Path(__file__).parent / "static"
# Revalidate the page and its files on every load (ETag keeps it cheap): a cached old app.js under a new
# index.html leaves the page broken until someone hard-refreshes the tablet.
NO_CACHE = {"Cache-Control": "no-cache"}


class Static(StaticFiles):
    def file_response(self, *args, **kwargs):
        response = super().file_response(*args, **kwargs)
        response.headers.update(NO_CACHE)
        return response


class ProfileIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    age: int | None = Field(None, ge=18, le=120)
    sex: Literal["male", "female"] | None = None
    fallen: bool = False
    unsteady: bool = False
    worried: bool = False


class SetsIn(BaseModel):
    sets: int = Field(ge=0, le=6)
    reps: int = Field(ge=1, le=20)


class HoldsIn(BaseModel):
    stance: Literal["feet_together", "semi_tandem", "tandem"]
    holds: int = Field(ge=0, le=6)
    target_s: float = Field(gt=0, le=60)


class PlanIn(BaseModel):
    sit_to_stand: SetsIn
    balance: HoldsIn


class SessionIn(BaseModel):
    person_id: str
    mode: Literal["checkin", "exercise"]
    plan: PlanIn | None = None  # exercise only; default is the person's plan


class StopIn(BaseModel):
    reason: Literal["arms_used", "cancel"]


class AskIn(BaseModel):
    question: str = Field(min_length=1, max_length=200)


class AiIn(BaseModel):
    on: bool


ASK_PER_MINUTE = 10  # the xAI budget is shared: a stuck key or a public page can't run it down


def create_app(controller, store, today=date.today, demo=False):
    clients: set[asyncio.Queue] = set()
    family: dict[str, str] = {}  # person id -> the family summary last served

    def broadcast(event):
        for q in list(clients):
            q.put_nowait(event)

    controller.on_event = broadcast
    controller.state["demo"] = demo  # the page hides Add a person and Edit profile

    @contextlib.asynccontextmanager
    async def lifespan(app):
        task = asyncio.create_task(controller.run())
        yield
        task.cancel()
        controller.source.close()
        controller.base.close()

    app = FastAPI(title="Fall-risk check-in", lifespan=lifespan)
    app.mount("/static", Static(directory=STATIC), name="static")

    def not_in_demo():
        if demo:
            raise HTTPException(403, "this is a demo: people can't be added or changed")

    def person_or_404(pid):
        try:
            return store.get(pid)
        except KeyError:
            raise HTTPException(404, f"no person {pid!r}") from None

    @app.get("/")
    def index():
        return FileResponse(STATIC / "index.html", headers=NO_CACHE)

    @app.get("/api/state")
    def state():
        return controller.state

    @app.get("/api/people")
    def people():
        return store.people()

    @app.post("/api/people", status_code=201)
    def create_person(body: ProfileIn):
        not_in_demo()
        profile = body.model_dump(exclude={"name"})
        return store.create(body.name, profile)

    @app.put("/api/people/{pid}")
    def update_person(pid: str, body: ProfileIn):
        not_in_demo()
        person = person_or_404(pid)
        if person["simulated"]:
            raise HTTPException(403, "the simulated person is read-only; reseed with `checkin seed`")
        person["name"] = body.name
        person["profile"] = body.model_dump(exclude={"name"})
        store.save(person)
        return person

    @app.get("/api/people/{pid}/dashboard")
    def dashboard(pid: str):
        return steadi.dashboard(person_or_404(pid), today())

    @app.get("/api/people/{pid}/summary")
    def person_summary(pid: str):
        s = summary.summaries(steadi.dashboard(person_or_404(pid), today()))
        family[pid] = s["family"]
        return s

    # Speaks only the summary this server last wrote, so nobody can spend the key on text of their own.
    @app.get("/api/people/{pid}/summary/audio")
    def summary_audio(pid: str):
        person_or_404(pid)
        if pid not in family:
            raise HTTPException(404, "make the summary first")
        try:
            path = voice.spoken(family[pid], store.root / "audio")
        except Exception as e:  # offline, bad key, rate limit: the page reads it with the browser's voice
            log.warning("AI voice unavailable: %s", e)
            path = None
        if path is None:
            raise HTTPException(404, "no AI voice available")
        return FileResponse(path, media_type="audio/mpeg")

    asked = collections.deque()  # times of recent Grok-bound questions
    answers = {}  # (person, latest check-in, question) -> reply, so a rehearsed question costs one call

    @app.post("/api/people/{pid}/ask")
    def ask(pid: str, body: AskIn):
        dash = steadi.dashboard(person_or_404(pid), today())
        if not ai.ai_enabled():
            raise HTTPException(503, "Grok is off")
        question = " ".join(body.question.split())
        key = (pid, (dash["latest"] or {}).get("id"), question.lower())
        if key in answers:
            return answers[key]
        now = time.monotonic()
        while asked and now - asked[0] > 60:
            asked.popleft()
        if len(asked) >= ASK_PER_MINUTE:
            raise HTTPException(429, "Too many questions in a minute. Try again shortly.")
        asked.append(now)
        out = summary.answer(dash, question)
        if out["by"] != "template":  # a failed call isn't cached, so it's tried again
            answers[key] = out
        return out

    @app.get("/api/ai")
    def ai_status():
        return ai.status()

    @app.put("/api/ai")
    async def set_ai(body: AiIn):  # async: broadcast() isn't thread-safe
        ai.set_enabled(body.on)
        out = ai.status()
        broadcast({"type": "ai", **out})
        return out

    @app.post("/api/session", status_code=202)
    def start_session(body: SessionIn):
        try:
            controller.start(body.person_id, body.mode, body.plan.model_dump() if body.plan else None)
        except Busy as e:
            raise HTTPException(409, str(e)) from None
        except KeyError:
            raise HTTPException(404, f"no person {body.person_id!r}") from None
        except ValueError as e:
            raise HTTPException(400, str(e)) from None
        return {"ok": True}

    @app.post("/api/button")
    def button():
        controller.press()
        return {"ok": True}

    @app.post("/api/stop")
    def stop(body: StopIn):
        controller.stop(body.reason)
        return {"ok": True}

    @app.websocket("/ws")
    async def ws(socket: WebSocket):
        await socket.accept()
        q = asyncio.Queue()
        clients.add(q)
        try:
            await socket.send_json({"type": "state", **controller.state})
            while True:
                await socket.send_json(await q.get())
        except (WebSocketDisconnect, RuntimeError):
            pass
        finally:
            clients.discard(q)

    return app
