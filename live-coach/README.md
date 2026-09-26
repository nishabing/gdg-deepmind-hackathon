# Live Trainer — PS2, Next-Gen Voice & Real-Time Audio

A coach that watches you through the camera, talks while you move, and — when your form
breaks — **stops you, takes over the screen, and demonstrates the correction**.

The interruption is the novel beat. Every other fitness demo overlays a red skeleton and
keeps going. This one cuts the camera, puts the avatar in front of you, shows the fix,
and hands the camera back.

## Run

    export GEMINI_API_KEY=...
    source .venv/bin/activate        # already created, deps installed
    uvicorn app:app --port 8000

Open **http://localhost:8000**. That's it — no npm, no build step, one process.

## Files

    app.py              FastAPI: serves the page, /live websocket, /demo_narration
    coach.py            system prompt + the 7 tools  <- person 1 & 3 tune this
    static/index.html   the entire UI: capture, playback, state machine
    .venv/              ready to go

## Models

| Model | Where |
|---|---|
| `gemini-3.8-live` | the coach — voice in, voice out, video in, barge-in |
| `gemini-3.8-flash-tts` | the avatar's demonstration narration |
| `gemini-3.8-flash` | workout plan + narration script |
| `gemini-3.1-flash-lite-image` | generated demonstration stills (person 2, optional) |

IDs are at the top of `app.py`.

## Why PS2, not PS1

PS2's bar: *"if your app works just as well typed into a chatbox, you aren't pushing the
stack."* You cannot type mid-squat. Say that to the judge.

## How it works, one paragraph

The browser streams 16k mic audio and a 512×384 JPEG every 700ms over one WebSocket.
Live sends back three things: speech, a **text transcript of that speech** (captions),
and **tool calls**. The tool calls are the control plane — `rep`, `form_ok`,
`demonstrate` — and they drive the UI directly. The model speaks through audio and acts
through tools, so the page never guesses intent from prose.

## Who builds what

- **You** — it runs. Get an audio round-trip first, then frames, then the takeover.
- **Person 1 — the plan.** `gemini-3.8-flash` from demographics. Fastest path: build the
  plan JSON and paste it into `SYSTEM` in `coach.py` at connect time. Don't make it a
  tool unless you have time.
- **Person 2 — the avatar.** Mounts in `#avatarSlot` in `index.html`. The contract
  exists: `/demo_narration` returns `{script, wav_b64}`. Sync the animation to that clip.

## Timeline

- **T+0:20** — say hello, hear a reply. Nothing else matters until this works.
- **T+0:50** — frames flowing, coach reacts to what it sees, captions rendering.
- **T+1:20** — `demonstrate` fires and the screen takes over. **This is the demo.**
- **T+1:45** — freeze. Record.

## The demo

Headphones — without them the coach hears itself through the speakers and interrupts
itself. Echo cancellation is on and it is not enough in a loud room.

1. "I've got ten minutes, let's do legs." Plan fills the rail.
2. Start moving. Reps tick, form chip goes green, coach encourages.
3. **Deliberately break form.** Camera cuts, avatar takes the screen, demonstrates,
   camera returns.
4. Talk over the coach mid-sentence: "can we skip to lunges?" It stops instantly.

End on 4. Ten seconds of barge-in is the clearest proof you're on the audio stack
rather than wrapping it.

## Space problem — settle this first

Squats need the laptop 6–8 feet back with your whole body in frame. Test your actual
demo spot before writing anything. If framing doesn't work, switch to **overhead press
or lateral raise** — elbow flare, back arch and momentum swing are all visible from the
waist up at desk distance. Same code, same beats, no floor space.

## Cut list, in order

1. `#heard` line ("you: …") — cosmetic
2. Plan rail → one current-exercise chip
3. `form_ok` / `form_error` chips → keep `demonstrate` only
4. Rep counting → drop it. Cheaper than a visibly wrong count.
