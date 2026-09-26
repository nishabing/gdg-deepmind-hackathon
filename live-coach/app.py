"""Live Trainer — one file, one process, one command.

    export GEMINI_API_KEY=...
    uvicorn app:app --port 8000     ->  open http://localhost:8000

Browser sends mic audio (16k PCM) + camera frames (JPEG, ~1.4/s) over one WebSocket.
Gemini Live sends back speech, a transcript of that speech, and tool calls. The tool
calls drive the UI state machine — the model speaks through audio and acts through
tools, so the page never has to guess intent from prose.
"""
import asyncio, base64, io, json, logging, os, pathlib, time, traceback, wave
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from google import genai
from google.genai import types

from coach import SYSTEM, tools

# Key comes from .env (gitignored) so it never lands in your shell profile or a commit.
_env = pathlib.Path(__file__).parent / ".env"
if _env.exists():
    for _line in _env.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))

if not os.environ.get("GEMINI_API_KEY"):
    raise SystemExit(
        "\nNo GEMINI_API_KEY.\n"
        "  cp .env.example .env   then paste your key into .env\n")

# Exact model IDs from the problem statement. Change them here, nowhere else.
LIVE  = os.environ.get("MODEL_LIVE",  "gemini-3.8-live")            # the coach
TTS   = os.environ.get("MODEL_TTS",   "gemini-3.8-flash-tts")       # avatar narration
FLASH = os.environ.get("MODEL_FLASH", "gemini-3.8-flash")           # plan + script
VOICE = os.environ.get("GEMINI_VOICE", "Puck")

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)-5s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("coach")

app = FastAPI()
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"],
                      http_options={"api_version": "v1alpha"})

CONFIG = types.LiveConnectConfig(
    response_modalities=["AUDIO"],
    system_instruction=types.Content(parts=[types.Part(text=SYSTEM)]),
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


@app.websocket("/live")
async def live(ws: WebSocket):
    await ws.accept()
    try:
        async with client.aio.live.connect(model=LIVE, config=CONFIG) as session:
            log.info("live session open  model=%s voice=%s", LIVE, VOICE)
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
                        if stats["audio"] % 50 == 0:
                            secs = stats["audio_bytes"] / 2 / 16000
                            log.info("UP audio  %d chunks  %.1fs of speech sent",
                                     stats["audio"], secs)
                    elif m["t"] == "frame":
                        raw = base64.b64decode(m["d"])
                        await session.send_realtime_input(video=types.Blob(
                            data=raw, mime_type="image/jpeg"))
                        frames += 1
                        stats["frames"] = frames
                        # If this stays at 0 the coach is reacting to your voice alone.
                        if frames % 20 == 0:
                            log.info("UP video  %d frames  last=%dB", frames, len(raw))
                    elif m["t"] == "text":
                        # Ground truth from the client's motion detector.
                        log.info("UP text   %s", m["d"])
                        await session.send_realtime_input(text=m["d"])
                    elif m["t"] == "resume":
                        log.info("UP resume (demonstration finished)")
                        await session.send_client_content(turns=types.Content(
                            role="user", parts=[types.Part(
                                text="[demonstration over, they are back on camera]")]))

            async def down():
                while True:
                    async for r in session.receive():
                        if r.data:
                            stats["replies"] += 1
                            if stats["replies"] % 40 == 1:
                                log.info("DOWN audio (coach speaking)")
                            await ws.send_json({"t": "audio",
                                                "d": base64.b64encode(r.data).decode()})
                        sc = r.server_content
                        if sc:
                            if sc.output_transcription and sc.output_transcription.text:
                                log.debug("DOWN says %r", sc.output_transcription.text)
                                await ws.send_json({"t": "caption",
                                                    "d": sc.output_transcription.text})
                            if sc.input_transcription and sc.input_transcription.text:
                                # THE LINE THAT MATTERS: if this never appears, your
                                # microphone audio is not reaching the model.
                                log.info("HEARD YOU %r", sc.input_transcription.text)
                                await ws.send_json({"t": "heard",
                                                    "d": sc.input_transcription.text})
                            if sc.interrupted:
                                await ws.send_json({"t": "interrupted"})
                            if sc.turn_complete:
                                await ws.send_json({"t": "turn_complete"})
                        if r.tool_call:
                            out = []
                            for fc in r.tool_call.function_calls:
                                log.info("TOOL  %s(%s)", fc.name,
                                         json.dumps(dict(fc.args or {}))[:160])
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
        log.info("client disconnected")
    except Exception:
        log.error("session failed\n%s", traceback.format_exc())
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
    """The avatar's demonstration voice. Scripted with Flash, spoken with Flash TTS —
    a fixed-length clip the avatar animation can sync against, which a streaming
    conversational turn cannot give you."""
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
    return {"ok": True, "live": LIVE, "tts": TTS, "flash": FLASH}


app.mount("/static", StaticFiles(directory="static"), name="static")
