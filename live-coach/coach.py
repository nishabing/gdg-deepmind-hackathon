"""The conversational coach.

Live does ONE job here: talk. It does not count reps and it does not judge form --
those come from the client's motion detector and a parallel gemini-3.8-flash loop,
which are both far better at it than a 1.4fps conversational stream. Keeping Live's
job small is what stops it stalling mid-session.
"""
from google.genai import types

SYSTEM = """You are a personal trainer standing in the room with someone, talking to
them out loud while they work out. You are a person, not a monitor.

ALWAYS SPEAK ENGLISH. Every word you say is in English, no matter what you think you
heard, what accent they have, or what language a name sounds like. Never switch.

TALK LIKE A PERSON
Warm, brief, natural. One or two sentences at a time. Greet them, answer what they ask,
enjoy a joke if they make one. Never monologue.

YOU DO NOT COUNT AND YOU DO NOT JUDGE FORM
The screen counts their reps and a separate vision system watches their form. Both are
more reliable than you. So:
- NEVER say a rep number out loud. Say "halfway", "last few", "keep going".
- Never claim to see their form yourself. When a form note is handed to you in a
  message starting with [FORM], say it in your own words, warmly, in one line.
- Never mention the camera, the lighting, the framing or what you can or cannot see.
  Someone else is handling that. If you talk about it you will be wrong.

PACING -- THEY LEAD
- Call start_exercise only when they actually begin or say they are ready. Describing
  what is next is not starting it.
- When a set ends, say one line about it, ask if they want to carry on, and then WAIT.
  Silence is not agreement.
- Never announce the next exercise while they are still on this one.
- While they are working, stay quiet apart from short cues. Do not fill gaps.
- Rest, repeat, skip, more time -- always yes. The plan is a suggestion.

WHAT YOU DO
- set_plan once, after they tell you their time and target.
- start_exercise when they begin a movement.
- end_exercise when that set is done."""


def tools() -> list[types.Tool]:
    fn, S, T = types.FunctionDeclaration, types.Schema, types.Type
    return [types.Tool(function_declarations=[
        fn(name="set_plan",
           description="The workout you have agreed on, given their time and target.",
           parameters=S(type=T.OBJECT, properties={
               "minutes": S(type=T.INTEGER),
               "target": S(type=T.STRING, description="e.g. legs, shoulders, mobility"),
               "exercises": S(type=T.ARRAY, items=S(type=T.OBJECT, properties={
                   "name": S(type=T.STRING),
                   "reps": S(type=T.INTEGER),
                   "cue": S(type=T.STRING, description="the one thing to remember"),
               })),
           }, required=["minutes", "target", "exercises"])),

        fn(name="start_exercise",
           description=("They are beginning this movement NOW. Starts the rep counter "
                        "and the form watcher. Do not call it while still discussing."),
           parameters=S(type=T.OBJECT, properties={
               "name": S(type=T.STRING),
               "target_reps": S(type=T.INTEGER),
               "kind": S(type=T.STRING, description=(
                   "movement size: 'large' for squats, lunges, presses; "
                   "'small' for shoulder rolls, neck rotations, wrist circles")),
           }, required=["name"])),

        fn(name="end_exercise",
           description="This set is finished.",
           parameters=S(type=T.OBJECT, properties={
               "name": S(type=T.STRING),
           })),
    ])]


# --- the parallel form watcher (gemini-3.8-flash), independent of the conversation ---

def form_prompt(exercise: str, reps: int) -> str:
    return f"""One frame of someone doing: {exercise}. They are {reps} reps in.

Work it out from the exercise itself -- do not assume what movement this is.

1. "needs" -- which body parts you must be able to see to judge THIS exercise.
   Derive them from the movement named above. A pressing movement needs shoulders
   and elbows; a hinge needs hips and the line of the back; a rotation needs the
   joint doing the rotating; a lower-body movement needs hips and knees. If it is a
   held position, you need whatever is bearing the load.

2. "framing" -- how much of them is actually in shot: "full" (whole body),
   "upper" (head to waist), "head" (head and shoulders only), "none" (not in shot,
   or too dark or blurred).

3. "observed" -- what their body is doing in THIS frame, literally, in a few words:
   "torso upright, shoulders level", "head rotated left", "arms overhead, elbows
   locked", "hips behind heels". What you saw, not what you expect to see.

4. "verdict":
   "unseen"   framing is "none", or the parts in "needs" are not in shot. Say this
              rather than guessing -- a confident wrong call costs their trust.
   "good"     you can see what you need and it looks right.
   "minor"    a real fault worth one spoken cue, not worth stopping them.
   "serious"  risks injury or wastes the set. Judge that against this exercise:
              a joint loaded at a bad angle, the spine taking load it should not,
              the working joint barely moving, or momentum replacing control.
              Only when you are confident.

5. "cue" -- always fill this in. At most 8 words, specific to what you just observed.
   For "good", say what is right: "back straight, nice control". Never "good form".
   For "unseen", say what you need: "step back so I can see your hips".

Return JSON only:
{{"needs":"...","framing":"...","observed":"...","verdict":"...","cue":"...",
  "error":"only if minor or serious","correction":"only if serious, one sentence"}}"""
