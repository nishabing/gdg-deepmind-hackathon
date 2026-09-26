"""Live Trainer — Linked with Personalized Workout Profile & Progress Hub.

Browser sends mic audio (16k PCM) + camera frames (JPEG, ~1.4/s) over one WebSocket.
Gemini Live sends back speech, a transcript of that speech, and tool calls. The tool
calls drive the UI state machine — the model speaks through audio and acts through
tools, so the page never has to guess intent from prose.
"""
import asyncio, base64, io, json, logging, os, pathlib, time, traceback, wave
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from google import genai
from google.genai import types

from coach import build_system_prompt, tools, get_user_profile_context
from database.db_manager import DBManager
from concierge.health_goals import HealthGoalsManager

db = DBManager()
goals_manager = HealthGoalsManager(db=db)

# Key comes from .env (gitignored) so it never lands in your shell profile or a commit.
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

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)-5s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("coach")

app = FastAPI(title="Live Trainer (Linked to Profile Hub)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

client = genai.Client(api_key=api_key or "DUMMY_KEY_FOR_INIT",
                      http_options={"api_version": "v1alpha"}) if api_key else None


def get_live_config(user_id: str = "default_user") -> types.LiveConnectConfig:
    sys_text = build_system_prompt(user_id=user_id)
    return types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        system_instruction=types.Content(parts=[types.Part(text=sys_text)]),
        tools=tools(),
        speech_config=types.SpeechConfig(voice_config=types.VoiceConfig(
            prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=VOICE))),
        # Captions, so the demo reads with the sound off.
        output_audio_transcription=types.AudioTranscriptionConfig(),
        input_audio_transcription=types.AudioTranscriptionConfig(),
    )


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
    flags = user.get("orthopedic_flags", [])
    focus = "knee_rehab" if "knee_pain" in flags else "posterior_chain_mobility"
    recommended_routines = db.query_local_routines(
        focus=focus,
        exclude_tags=["deep_flexion", "high_impact"] if "knee_pain" in flags else None
    )
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


@app.get("/api/linked_profile")
async def linked_profile(user_id: str = "default_user"):
    """Returns the linked health goals and constraints from the Profile Hub."""
    context = get_user_profile_context(user_id)
    return {"linked": bool(context), "context": context}


@app.websocket("/live")
async def live(ws: WebSocket):
    await ws.accept()
    user_id = ws.query_params.get("user_id", "default_user")

    if not client:
        await ws.send_json({"t": "ready"})
        profile_ctx = get_user_profile_context(user_id)
        msg_text = "Offline Mode Active (Add GEMINI_API_KEY to .env for Live Gemini Voice). "
        if profile_ctx and profile_ctx.get("goals"):
            msg_text += f"Tracking goals: {', '.join(profile_ctx['goals'][:2])}"
        await ws.send_json({"t": "caption", "d": msg_text})
        await ws.send_json({
            "t": "tool",
            "name": "start_exercise",
            "args": {"name": "Bodyweight Squats", "target_reps": 10}
        })
        try:
            rep_counter = 0
            while True:
                raw_text = await ws.receive_text()
                msg = json.loads(raw_text)
                if msg.get("t") == "text" and "movement resumed" in msg.get("d", ""):
                    rep_counter += 1
                    await ws.send_json({
                        "t": "tool",
                        "name": "rep_completed",
                        "args": {
                            "count": rep_counter,
                            "form_quality": "good",
                            "cue": "Keep steady cadence and chest upright!"
                        }
                    })
        except WebSocketDisconnect:
            log.info("offline session closed by client")
            return
        except Exception as e:
            log.warning("offline session exception: %s", e)
            return
    live_config = get_live_config(user_id)

    try:
        async with client.aio.live.connect(model=LIVE, config=live_config) as session:
            log.info("live session open  model=%s voice=%s user=%s", LIVE, VOICE, user_id)
            await ws.send_json({"t": "ready"})
            stats = {"audio": 0, "audio_bytes": 0, "frames": 0, "replies": 0}
            t_start = time.time()

            frames = 0

            async def up():
                nonlocal frames
                while True:
                    m = json.loads(await ws.receive_text())
                    if m["t"] == "audio":
                        pcm = base64.b64decode(m["d"])
                        await session.send_realtime_input(audio=types.Blob(
                            data=pcm, mime_type="audio/pcm;rate=16000"))
                        stats["audio"] += 1
                        stats["audio_bytes"] += len(pcm)
                    elif m["t"] == "frame":
                        raw = base64.b64decode(m["d"])
                        await session.send_realtime_input(video=types.Blob(
                            data=raw, mime_type="image/jpeg"))
                        frames += 1
                        stats["frames"] += 1
                        if frames % 20 == 0:
                            log.debug("frames sent: %d (last %dB)", frames, len(raw))
                    elif m["t"] == "text":
                        # Ground truth from the client's motion detector.
                        await session.send_realtime_input(text=m["d"])
                    elif m["t"] == "resume":
                        await session.send_client_content(turns=types.Content(
                            role="user", parts=[types.Part(
                                text="[demonstration over, they are back on camera]")]))

            async def down():
                while True:
                    async for r in session.receive():
                        if r.data:
                            stats["replies"] += 1
                            await ws.send_json({"t": "audio",
                                                "d": base64.b64encode(r.data).decode()})
                        sc = r.server_content
                        if sc:
                            if sc.output_transcription and sc.output_transcription.text:
                                await ws.send_json({"t": "caption",
                                                    "d": sc.output_transcription.text})
                            if sc.input_transcription and sc.input_transcription.text:
                                await ws.send_json({"t": "heard",
                                                    "d": sc.input_transcription.text})
                            if sc.interrupted:
                                await ws.send_json({"t": "interrupted"})
                            if sc.turn_complete:
                                await ws.send_json({"t": "turn_complete"})
                        if r.tool_call:
                            out = []
                            for fc in r.tool_call.function_calls:
                                log.info("tool call  name=%s args=%s", fc.name, dict(fc.args or {}))
                                await ws.send_json({"t": "tool", "name": fc.name,
                                                    "args": dict(fc.args or {})})
                                out.append(types.FunctionResponse(
                                    id=fc.id, name=fc.name, response={"ok": True}))
                            # Must answer or the model stalls waiting on us.
                            await session.send_tool_response(function_responses=out)

            a, b = asyncio.create_task(up()), asyncio.create_task(down())
            done, pending = await asyncio.wait({a, b}, return_when=asyncio.FIRST_EXCEPTION)
            for t in pending:
                t.cancel()
            for t in done:
                if t.exception():
                    raise t.exception()

    except WebSocketDisconnect:
        dur = time.time() - t_start
        log.info(
            "live session closed  dur=%.1fs frames=%d audio_chunks=%d "
            "(%.1f kB) replies=%d",
            dur, stats["frames"], stats["audio"],
            stats["audio_bytes"] / 1024, stats["replies"])
    except Exception:
        traceback.print_exc()
        try:
            await ws.send_json({"t": "error", "d": traceback.format_exc()[-400:]})
        except Exception:
            pass


class DemoIn(BaseModel):
    exercise: str
    error: str
    correction: str
    focus: str | None = None


def _wav(pcm: bytes, rate: int = 24000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
        w.writeframes(pcm)
    return buf.getvalue()


@app.post("/demo_narration")
async def demo_narration(d: DemoIn):
    """The avatar's demonstration voice. Scripted with Flash, spoken with Flash TTS."""
    if not client:
        return {"script": d.correction, "wav_b64": ""}

    s = await client.aio.models.generate_content(
        model=FLASH,
        contents=f"""Write what a trainer says while demonstrating correct form, after
stopping someone mid-set. Three short sentences, max 45 words. Name the error, show the
fix, give one cue. Spoken aloud: no lists, no numbers. Plain text only.

Exercise: {d.exercise}
Their error: {d.error}
The correction: {d.correction}""",
        config=types.GenerateContentConfig(temperature=0.6, max_output_tokens=200))
    script = (s.text or d.correction).strip()

    a = await client.aio.models.generate_content(
        model=TTS,
        contents=f"Say this like a coach who stopped you to help, calm and "
                 f"encouraging: {script}",
        config=types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=VOICE)))))
    pcm = a.candidates[0].content.parts[0].inline_data.data
    return {"script": script, "wav_b64": base64.b64encode(_wav(pcm)).decode()}


@app.get("/health")
async def health():
    return {
        "ok": True,
        "service": "live-coach",
        "has_key": bool(api_key),
        "live": LIVE,
        "tts": TTS,
        "flash": FLASH
    }


if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "8080"))
    log.info(f"Starting server on 0.0.0.0:{port}")
    uvicorn.run("app:app", host="0.0.0.0", port=port, log_level="info")

