"""Digital AI Coach -- one process, one page.

    uvicorn app:app --port 8000     ->  http://localhost:8000

Three jobs, deliberately split, because one model doing all three was the reason
nothing was reliable:

  conversation  gemini-3.8-live   voice in, voice out, barge-in. No video.
  form          gemini-3.8-flash  one frame every ~2.5s during a set, in parallel.
  reps          the browser       motion-cycle detection. Instant, no API, no drift.

Live never sees video and never counts. That keeps its turns short and stops it
stalling, and it is why small movements like shoulder rolls now register at all.
"""
import asyncio, base64, io, json, logging, os, pathlib, re, time, traceback, wave
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from google import genai
from google.genai import types

from coach import (build_system_prompt, tools, get_user_profile_context, SYSTEM,
                   form_prompt)
from database.db_manager import DBManager
from concierge.health_goals import HealthGoalsManager

db = DBManager()
goals_manager = HealthGoalsManager(db=db)

# Key comes from .env (gitignored) so it never lands in a shell profile or a commit.
_env = pathlib.Path(__file__).parent / ".env"
if _env.exists():
    for _line in _env.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))

api_key = os.environ.get("GEMINI_API_KEY", "")

# Exact model IDs from the problem statement.
LIVE  = os.environ.get("MODEL_LIVE",  "gemini-3.8-live")            # the coach
TTS   = os.environ.get("MODEL_TTS",   "gemini-3.8-flash-tts")       # avatar narration
FLASH = os.environ.get("MODEL_FLASH", "gemini-3.8-flash")           # plan + script
VOICE = os.environ.get("GEMINI_VOICE", "Puck")
LANG  = os.environ.get("GEMINI_LANG", "en-US")   # it drifted into Spanish without this
FORM_EVERY = float(os.environ.get("FORM_EVERY", "2.5"))   # seconds between form checks

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"),
                    format="%(asctime)s %(levelname)-5s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("coach")
for _noisy in ("httpx", "google_genai.models", "google_genai"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)


app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],)
SESSIONS = {"n": 0, "seq": 0}     # if this ever exceeds 1, you have two coaches talking

client = genai.Client(api_key=api_key or "DUMMY_KEY_FOR_INIT",
                      http_options={"api_version": "v1alpha"}) if api_key else None
STARTED = time.strftime("%H:%M:%S")
FORM_CFG = types.GenerateContentConfig(
    response_mime_type="application/json", temperature=0.3,
    max_output_tokens=900,          # 400 truncated the JSON mid-string
    automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True))


def parse_form(text: str) -> dict:
    """Salvage a truncated response rather than throwing the whole check away."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    out = {}
    for key in ("needs", "framing", "observed", "verdict", "cue", "error", "correction"):
        m = re.search(rf'"{key}"\s*:\s*"([^"]*)', text or "")
        if m:
            out[key] = m.group(1)
    return out


def get_live_config(user_id: str = "default_user") -> types.LiveConnectConfig:
    sys_text = build_system_prompt(user_id=user_id)
    return types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        system_instruction=types.Content(parts=[types.Part(text=sys_text)]),
        tools=tools(),
        speech_config=types.SpeechConfig(
            language_code=LANG,
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=VOICE))),
        # Left at defaults on purpose: START_SENSITIVITY_LOW stopped the model
        # registering speech at all, and language_codes on the INPUT transcription
        # is unverified against this model. English is pinned above and in the prompt.
        output_audio_transcription=types.AudioTranscriptionConfig(),
        input_audio_transcription=types.AudioTranscriptionConfig(),
    )


CONFIG = get_live_config("default_user")


@app.get("/")
async def index():
    return FileResponse("static/index.html")


@app.get("/profile")
async def profile_page():
    return FileResponse("static/profile.html")


class HealthGoalRequest(BaseModel):
    input_text: str
    user_id: str = "default_user"


class CompleteWorkoutRequest(BaseModel):
    user_id: str = "default_user"
    routine_id: str | None = None
    routine_title: str | None = None
    duration_min: int = 15
    reps: int = 40
    notes: str = ""


@app.get("/api/profile/{user_id}")
async def get_profile(user_id: str = "default_user"):
    user = db.get_user(user_id) or {}
    progress = db.get_user_progress(user_id)
    recommended_routines = db.get_recommended_routines(user_id)
    return {
        "user": user,
        "progress": progress,
        "health_goals": user.get("health_goals", []),
        "healthcare_recommendations": user.get("healthcare_recommendations", []),
        "recommended_routines": recommended_routines
    }


@app.post("/api/profile/{user_id}/goals")
async def update_goals(user_id: str, req: HealthGoalRequest):
    result = goals_manager.process_and_update_goals(raw_goals_input=req.input_text, user_id=user_id)
    result["progress"] = db.get_user_progress(user_id)
    return result


@app.post("/api/profile/{user_id}/workout/complete")
async def complete_workout(user_id: str, req: CompleteWorkoutRequest):
    result = db.log_completed_workout(
        user_id=user_id,
        routine_id=req.routine_id,
        routine_title=req.routine_title or "Live AI Trainer Session",
        duration_min=req.duration_min,
        reps_completed=req.reps,
        notes=req.notes
    )
    result["progress"] = db.get_user_progress(user_id)
    return result


@app.post("/api/profile/{user_id}/reset")
async def reset_profile(user_id: str = "default_user"):
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM workout_logs WHERE user_id = ?", (user_id,))
        cursor.execute("DELETE FROM live_tool_queue")
        cursor.execute("DELETE FROM sdac_audit_logs")
        cursor.execute("""
            UPDATE users 
            SET workout_count = 0, current_day = 0, streak_days = 0,
                health_goals = '[]', healthcare_recommendations = '[]',
                orthopedic_flags = '[]', target_duration_min = 15
            WHERE id = ?
        """, (user_id,))
        conn.commit()
    return {"status": "cleared", "user_id": user_id}


@app.get("/api/linked_profile")
async def linked_profile(user_id: str = "default_user"):
    """Returns the linked health goals and constraints from the Profile Hub."""
    context = get_user_profile_context(user_id)
    return {"linked": bool(context), "context": context}


@app.websocket("/live")
async def live(ws: WebSocket):
    await ws.accept()
    if not client:
        await ws.send_json({
            "t": "error",
            "d": "GEMINI_API_KEY is not set in live-coach/.env. Please add your key to launch Gemini 3.8 Live."
        })
        await ws.close()
        return

    SESSIONS["seq"] += 1
    SESSIONS["n"] += 1
    sid = SESSIONS["seq"]
    if SESSIONS["n"] > 1:
        log.warning("!! %d LIVE SESSIONS OPEN -- two coaches will talk over each "
                    "other. The page opened a second socket.", SESSIONS["n"])
    st = {"exercise": None, "kind": "large", "reps": 0, "frame": None,
          "active": False, "last_serious": 0.0, "demonstrating": False,
          "paused": False, "last_cue": "", "framing_warned": False,
          "framing": None}
    counters = {"audio": 0, "frames": 0}

    user_id = ws.query_params.get("user_id", "default_user")
    live_cfg = get_live_config(user_id)

    try:
        async with client.aio.live.connect(model=LIVE, config=live_cfg) as session:
            log.info("live open  #%d  live=%s flash=%s voice=%r  (open sessions: %d)",
                     sid, LIVE, FLASH, VOICE, SESSIONS["n"])
            await ws.send_json({"t": "ready", "sid": sid, "open": SESSIONS["n"]})

            async def say(text: str):
                """Hand the coach something to say, in its own voice."""
                await session.send_client_content(
                    turns=types.Content(role="user", parts=[types.Part(text=text)]))

            # ---------- browser -> here ----------
            async def up():
                while True:
                    m = json.loads(await ws.receive_text())
                    t = m["t"]
                    if t == "audio":
                        await session.send_realtime_input(audio=types.Blob(
                            data=base64.b64decode(m["d"]),
                            mime_type="audio/pcm;rate=16000"))
                        counters["audio"] += 1
                        if counters["audio"] % 80 == 0:
                            log.info("UP audio %d chunks", counters["audio"])
                    elif t == "frame":
                        # Held for the form watcher. Never forwarded to Live.
                        st["frame"] = base64.b64decode(m["d"])
                        counters["frames"] += 1
                        if counters["frames"] % 25 == 0:
                            log.info("UP video %d frames (for form watcher)",
                                     counters["frames"])
                    elif t == "rep":
                        st["reps"] = m.get("n", st["reps"] + 1)
                        log.info("REP %d  (%s)", st["reps"], st["exercise"])
                    elif t == "log":
                        log.info("CLIENT %s", m.get("d", ""))
                    elif t == "pause":
                        # Camera or mic off is a pause, not a hint. Stop the form
                        # watcher and tell the coach to wait rather than coach on.
                        st["paused"] = bool(m.get("on"))
                        st["frame"] = None          # never judge a stale frame
                        log.info("PAUSE %s (%s)", st["paused"], m.get("why"))
                        if st["paused"]:
                            await say(
                                f"[The session is PAUSED -- they turned their "
                                f"{m.get('why','camera')} off. Rep counting and form "
                                f"tracking have stopped. Say one short line to "
                                f"acknowledge, do NOT tell them to continue, then stay "
                                f"quiet and wait until you are told it resumed.]")
                        else:
                            await say("[They are back. Session resumed. One short "
                                      "line, then carry on.]")
                    elif t == "resume":
                        st["demonstrating"] = False
                    elif t == "say":
                        await say(m["d"])

            # ---------- parallel form watcher (gemini-3.8-flash) ----------
            async def watch_form():
                while True:
                    await asyncio.sleep(FORM_EVERY)
                    if st["paused"] or st["demonstrating"]:
                        continue
                    if not (st["active"] and st["frame"]):
                        continue
                    try:
                        r = await client.aio.models.generate_content(
                            model=FLASH, config=FORM_CFG,
                            contents=[types.Part(text=form_prompt(st["exercise"], st["reps"])),
                                      types.Part(inline_data=types.Blob(
                                          data=st["frame"], mime_type="image/jpeg"))])
                        v = parse_form(r.text or "")
                        if not v.get("verdict"):
                            log.warning("form check unusable: %r", (r.text or "")[:120])
                            continue
                    except Exception as e:
                        log.warning("form check failed: %s", str(e)[:120])
                        continue

                    verdict = v.get("verdict", "good")
                    cue = (v.get("cue") or "").strip()
                    log.info("FORM %-7s framing=%-5s saw=%r -> %r", verdict,
                             v.get("framing", "?"), v.get("observed", "")[:48], cue)
                    await ws.send_json({"t": "form", **v})

                    # Tell the coach what is visible whenever it changes, so it can
                    # choose movements that fit the shot instead of nagging them to move.
                    fr = v.get("framing")
                    if fr and fr != st["framing"]:
                        st["framing"] = fr
                        await ws.send_json({"t": "framing", "framing": fr})
                        await say(f"[FRAMING] {fr}")

                    if verdict == "unseen":
                        # Once per session, not every 2.5 seconds.
                        if not st["framing_warned"]:
                            st["framing_warned"] = True
                            await say(
                                f"[FRAMING] You cannot see what this exercise needs "
                                f"({cue or 'out of frame'}). Offer them the closest "
                                f"movement you CAN see at '{fr}' framing, or to step "
                                f"back. One friendly line, then move on.")
                        continue

                    if verdict == "serious" and time.time() - st["last_serious"] > 20:
                        # THE BEAT: stop them, take the screen, demonstrate.
                        st["last_serious"] = time.time()
                        st["demonstrating"] = True
                        await ws.send_json({"t": "demonstrate",
                                            "exercise": st["exercise"],
                                            "error": v.get("error", ""),
                                            "correction": v.get("correction", "")})
                        await say(
                            "[You have just stopped them and taken over the screen to "
                            "demonstrate. Say it like a coach showing the movement: name "
                            "the error, show the fix, one cue. Three short sentences.]\n"
                            f"Exercise: {st['exercise']}\n"
                            f"Error: {v.get('error','')}\n"
                            f"Fix: {v.get('correction','')}")
                    elif verdict == "minor" and cue and cue != st["last_cue"]:
                        # Don't repeat yourself every 2.5s -- that is nagging.
                        st["last_cue"] = cue
                        await say(f"[FORM] {cue}")

            # ---------- here -> browser ----------
            async def down():
                while True:
                    async for r in session.receive():
                        if r.data:
                            await ws.send_json({"t": "audio",
                                                "d": base64.b64encode(r.data).decode()})
                        sc = r.server_content
                        if sc:
                            if sc.output_transcription and sc.output_transcription.text:
                                await ws.send_json({"t": "caption",
                                                    "d": sc.output_transcription.text})
                            if sc.input_transcription and sc.input_transcription.text:
                                log.info("HEARD %r", sc.input_transcription.text)
                                await ws.send_json({"t": "heard",
                                                    "d": sc.input_transcription.text})
                            if sc.interrupted:
                                log.info("barge-in")
                                await ws.send_json({"t": "interrupted"})
                            if sc.turn_complete:
                                await ws.send_json({"t": "turn_complete"})
                        if r.tool_call:
                            out = []
                            for fc in r.tool_call.function_calls:
                                a = dict(fc.args or {})
                                log.info("TOOL %s %s", fc.name, json.dumps(a)[:140])
                                if fc.name == "start_exercise":
                                    st.update(exercise=a.get("name"), reps=0, active=True,
                                              kind=a.get("kind", "large"))
                                elif fc.name == "end_exercise":
                                    # It must be able to quote them. Room noise cannot
                                    # be quoted, so it cannot end a set any more.
                                    said = (a.get("said") or "").strip()
                                    if not said:
                                        log.warning("end_exercise IGNORED — no quote")
                                        out.append(types.FunctionResponse(
                                            id=fc.id, name=fc.name,
                                            response={"ok": False, "error":
                                                      "Quote what they said, or keep going."}))
                                        continue
                                    log.info("end_exercise on: %r", said)
                                    st["active"] = False
                                await ws.send_json({"t": "tool", "name": fc.name, "args": a})
                                out.append(types.FunctionResponse(
                                    id=fc.id, name=fc.name, response={"ok": True}))
                            # Must answer or the model stalls waiting on us.
                            await session.send_tool_response(function_responses=out)

            tasks = [asyncio.create_task(f()) for f in (up, down, watch_form)]
            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_EXCEPTION)
            for t in pending:
                t.cancel()
            for t in done:
                if t.exception():
                    raise t.exception()

    except WebSocketDisconnect:
        log.info("client disconnected (#%d)", sid)
    except Exception:
        traceback.print_exc()
        try:
            await ws.send_json({"t": "error", "d": traceback.format_exc()[-400:]})
        except Exception:
            pass
    finally:
        SESSIONS["n"] = max(0, SESSIONS["n"] - 1)
        log.info("session #%d closed (open: %d)", sid, SESSIONS["n"])


class DemoIn(BaseModel):
    exercise: str
    error: str
    correction: str


def _wav(pcm: bytes, rate: int = 24000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate); w.writeframes(pcm)
    return buf.getvalue()


@app.post("/demo_narration")
async def demo_narration(d: DemoIn):
    """Kept for reference. Unused by default: the TTS model does not share Live's voice
    roster, so routing narration here made the coach change voice mid-session."""
    a = await client.aio.models.generate_content(
        model=TTS, contents=f"Say like a coach helping: {d.correction}",
        config=types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=VOICE)))))
    pcm = a.candidates[0].content.parts[0].inline_data.data
    return {"wav_b64": base64.b64encode(_wav(pcm)).decode()}


@app.get("/api/coach_voice")
async def coach_voice(text: str = "Hello! What are your goals today? I'm listening."):
    """Generate audio matching the coach's voice (TTS Puck / 24kHz)."""
    if not client:
        return {"ok": False, "reason": "no_client"}
    try:
        a = await client.aio.models.generate_content(
            model=TTS, contents=f"Say warmly and briefly like an athletic digital fitness coach: {text}",
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=VOICE)))))
        pcm = a.candidates[0].content.parts[0].inline_data.data
        return {"ok": True, "wav_b64": base64.b64encode(_wav(pcm, 24000)).decode()}
    except Exception as e:
        log.warning("coach_voice error: %s", e)
        return {"ok": False, "reason": str(e)}


@app.get("/health")
async def health():
    # started_at tells you whether the process actually picked up your last edit.
    return {"ok": True, "live": LIVE, "flash": FLASH, "form_every": FORM_EVERY,
            "voice": VOICE, "lang": LANG, "started_at": STARTED,
            "vad": "defaults", "sessions_open": SESSIONS["n"]}


if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "8080"))
    log.info(f"Starting server on 0.0.0.0:{port}")
    uvicorn.run("app:app", host="0.0.0.0", port=port, log_level="info")
