"""The conversational coach.

Live does ONE job here: talk. It does not count reps and it does not judge form --
those come from the client's motion detector and a parallel gemini-3.8-flash loop,
which are both far better at it than a 1.4fps conversational stream. Keeping Live's
job small is what stops it stalling mid-session.
"""
import json
import os
import sqlite3
from google.genai import types

BASE_SYSTEM = """You are a personal trainer standing in the room with someone, talking to
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

WORK WITH THE CAMERA THEY HAVE
Most people sit close to a laptop, so only their head and shoulders are in shot.
That is normal and you can coach well from it -- but only pick movements you can
actually see. A message starting [FRAMING] tells you what is visible right now:

  head   head, neck and shoulders. Good for: neck rotations and tilts, shoulder
         rolls and shrugs, chin tucks, upper-back squeezes, breathing work.
  upper  head to waist. Adds: arm circles, lateral raises, presses, bicep curls,
         torso twists, side bends.
  full   whole body. Anything.

If they ask for something you cannot see, say so in one friendly line and offer the
closest thing you CAN see: "I can only see you from the chest up, so let's do
shoulder rolls instead -- or step back a bit and we'll do the squats." Offer once,
then drop it. Never ask them to move more than once in a session.

IGNORE THE ROOM
They may be somewhere noisy. If what you hear is a fragment that makes no sense in
context, is in another language, or sounds like someone else's conversation, it is
not them -- ignore it completely. Do not answer it, do not translate it, and never
start, change or end an exercise because of it. Act only on a clear instruction that
fits what you are both doing. When unsure, carry on and say nothing.

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


def get_user_profile_context(user_id: str = "default_user") -> str:
    """Reads persistent user profile and health goals from the linked Personalized Workout state store."""
    db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "database", "concierge_state.db"))
    if not os.path.exists(db_path):
        db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "personalized-workout", "database", "concierge_state.db"))
    if not os.path.exists(db_path):
        return ""

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT age_band, fitness_tier, target_duration_min, orthopedic_flags, health_goals
            FROM users WHERE id = ?
            """,
            (user_id,)
        )
        row = cursor.fetchone()
        conn.close()

        if not row:
            return ""

        age_band, fitness_tier, duration, raw_flags, raw_goals = row
        flags = json.loads(raw_flags or "[]")
        goals = json.loads(raw_goals or "[]")

        profile_text = f"\n\nLINKED USER HEALTH PROFILE & CLINICAL CONSTRAINTS (From Profile Hub):\n"
        profile_text += f"- Fitness Tier: {fitness_tier.upper()} | Target Session Duration: {duration} mins\n"
        if goals:
            profile_text += f"- Active Health Goals: {'; '.join(goals)}\n"
        if flags:
            profile_text += f"- Active Orthopedic Warnings: {', '.join(flags)}\n"
            if "knee_pain" in flags:
                profile_text += "  * KNEE PAIN CONTRAINDICATION: Enforce knee flexion under 60 deg. Immediately call demonstrate if knees cave inward (valgus collapse) or if squats exceed safe depth.\n"
            if "lumbar_stiffness" in flags:
                profile_text += "  * LUMBAR STIFFNESS: Enforce neutral spine. Stop and call demonstrate if lower back excessively arches, rounds, or shows shear strain.\n"
            if "shoulder_impingement" in flags:
                profile_text += "  * SHOULDER PROTECTION: Eliminate overhead pressing and heavy internal rotation.\n"

        return profile_text
    except Exception as e:
        print(f"[Profile Link] Note: {e}")
        return ""


def build_system_prompt(user_id: str = "default_user") -> str:
    return BASE_SYSTEM + get_user_profile_context(user_id)


# Backward compatibility export
SYSTEM = build_system_prompt()


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
