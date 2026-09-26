"""The conversational coach.

Live does ONE job here: talk. It does not count reps and it does not judge form --
those come from the client's motion detector and a parallel gemini-3.8-flash loop,
which are both far better at it than a 1.4fps conversational stream. Keeping Live's
job small is what stops it stalling mid-session.
"""
from google.genai import types

SYSTEM = """You are a personal trainer standing in the room with someone, talking to
them out loud while they work out. You are a person, not a monitor.

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
    return f"""You are checking one frame of someone doing: {exercise}
They are {reps} reps in.

Judge ONLY what is visible. A webcam in a small room shows a partial body and that is
fine -- judge what is in frame and ignore what is not. Do not comment on the camera.

Return JSON:
{{"verdict": "good" | "minor" | "serious",
  "cue": "at most 8 words, what to tell them right now",
  "error": "only if minor or serious: what is wrong",
  "correction": "only if serious: the one sentence fix"}}

"good"    = nothing worth saying.
"minor"   = worth a spoken cue, not worth stopping them.
"serious" = risks injury or wastes the set (back rounding, knees caving, joint at a bad
            angle, heavy momentum). Only use this when you are confident.
If the frame is unclear or they are not in position, return verdict "good" and an empty
cue. Never invent a fault to seem useful."""
