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
import asyncio, base64, io, json, logging, os, pathlib, time, traceback, wave
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from google import genai
from google.genai import types

from coach import SYSTEM, tools, form_prompt

# Key comes from .env (gitignored) so it never lands in a shell profile or a commit.
_env = pathlib.Path(__file__).parent / ".env"
if _env.exists():
    for _line in _env.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))
if not os.environ.get("GEMINI_API_KEY"):
    raise SystemExit("\nNo GEMINI_API_KEY.\n  put it in .env  ->  GEMINI_API_KEY=...\n")

LIVE  = os.environ.get("MODEL_LIVE",  "gemini-3.8-live")
FLASH = os.environ.get("MODEL_FLASH", "gemini-3.8-flash")
TTS   = os.environ.get("MODEL_TTS",   "gemini-3.8-flash-tts")
VOICE = os.environ.get("GEMINI_VOICE", "Puck")
FORM_EVERY = float(os.environ.get("FORM_EVERY", "2.5"))   # seconds between form checks

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"),
                    format="%(asctime)s %(levelname)-5s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("coach")

app = FastAPI()
SESSIONS = {"n": 0, "seq": 0}     # if this ever exceeds 1, you have two coaches talking
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"],
                      http_options={"api_version": "v1alpha"})

CONFIG = types.LiveConnectConfig(
    response_modalities=["AUDIO"],
    system_instruction=types.Content(parts=[types.Part(text=SYSTEM)]),
    tools=tools(),
    speech_config=types.SpeechConfig(voice_config=types.VoiceConfig(
        prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=VOICE))),
    output_audio_transcription=types.AudioTranscriptionConfig(),
    input_audio_transcription=types.AudioTranscriptionConfig(),
)
FORM_CFG = types.GenerateContentConfig(
    response_mime_type="application/json", temperature=0.2, max_output_tokens=300)


@app.get("/")
async def index():
    return FileResponse("static/index.html")


@app.websocket("/live")
async def live(ws: WebSocket):
    await ws.accept()
    SESSIONS["seq"] += 1
    SESSIONS["n"] += 1
    sid = SESSIONS["seq"]
    if SESSIONS["n"] > 1:
        log.warning("!! %d LIVE SESSIONS OPEN -- two coaches will talk over each "
                    "other. The page opened a second socket.", SESSIONS["n"])
    st = {"exercise": None, "kind": "large", "reps": 0, "frame": None,
          "active": False, "last_serious": 0.0, "demonstrating": False,
          "paused": False}
    counters = {"audio": 0, "frames": 0}

    try:
        async with client.aio.live.connect(model=LIVE, config=CONFIG) as session:
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
                        v = json.loads(r.text or "{}")
                    except Exception as e:
                        log.warning("form check failed: %s", str(e)[:120])
                        continue

                    verdict = v.get("verdict", "good")
                    log.info("FORM %-7s %s", verdict, v.get("cue", ""))
                    await ws.send_json({"t": "form", **v})

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
                    elif verdict == "minor" and v.get("cue"):
                        await say(f"[FORM] {v['cue']}")

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
        log.error("session failed\n%s", traceback.format_exc())
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


@app.get("/health")
async def health():
    return {"ok": True, "live": LIVE, "flash": FLASH, "form_every": FORM_EVERY}


app.mount("/static", StaticFiles(directory="static"), name="static")
