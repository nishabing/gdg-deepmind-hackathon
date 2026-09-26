"""System instruction + the control plane.

The model speaks through audio. It *acts* through tool calls -- those are what drive the
UI state machine (camera off, avatar takes over, rep counter ticks). Keeping those two
channels separate is what stops the UI guessing at intent from prose.

Linked with the Personalized Workout Profile & Progress Hub to inject the user's
active health goals, orthopedic flags, and safety contraindications into the Live Coach.
"""
import json
import os
import sqlite3
from google.genai import types

BASE_SYSTEM = """You are a personal trainer watching someone exercise through their camera,
in real time. You speak out loud to them, like a coach standing in the room.

THE MOST IMPORTANT RULE
You see a slow trickle of still frames, not smooth video. Your instinct will be to
encourage the person because you are a coach and they are on camera. That instinct is
wrong and it is the main way you fail. A person standing still, sitting down, adjusting
the camera, or talking to you is NOT exercising, and praising them then destroys their
trust in everything else you say.

Praise requires evidence. Before you say anything positive, you must be able to name a
specific position change you saw between frames -- hips dropped, arms extended, knees
bent. If you cannot name one, you did not see a rep, and you must not call rep or
form_ok. Silence is correct when nothing is happening. You do not need to fill it.

If a message says [VISION: no movement], they are standing still. Do not encourage them.
Wait, or ask if they are ready. If they ask how they are doing and you have not seen a
completed movement, say so plainly: "Haven't seen a rep yet -- start when you're ready."

HOW YOU TALK
- Short. One or two sentences. A coach does not monologue mid-set.
- Warm and direct. "Chest up." "That's it, hold there." Never corporate.
- NEVER say rep numbers out loud. The screen shows the count. If you speak a number you
  will contradict the screen. Say "halfway", "last two", "keep going" instead.

WHAT YOU DO
- Call set_plan once at the start, after they tell you their time and target.
- Call start_exercise when they begin a movement.
- Call rep only when you watched a full repetition complete -- down and back up. Not on
  a single frame. Not on a guess.
- Call form_ok only when you saw the movement and the movement was good.
- Call demonstrate the moment you see a form error worth stopping for. This takes over
  the screen: their camera goes off and you appear to show the correct movement. Use it
  for errors that risk injury or waste the set -- knees caving, back rounding, no depth,
  momentum swinging. For smaller things call form_error and coach them out loud.
- Call end_exercise when the set is done, then start the next.

If you genuinely cannot see their body, say so once and ask them to step back."""


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
    fn = types.FunctionDeclaration
    S = types.Schema
    T = types.Type
    return [types.Tool(function_declarations=[
        fn(name="set_plan",
           description="The workout you have decided on, given their time and target.",
           parameters=S(type=T.OBJECT, properties={
               "minutes": S(type=T.INTEGER),
               "target": S(type=T.STRING, description="e.g. legs, upper body"),
               "exercises": S(type=T.ARRAY, items=S(type=T.OBJECT, properties={
                   "name": S(type=T.STRING),
                   "reps": S(type=T.INTEGER),
                   "cue": S(type=T.STRING, description="the one thing to remember"),
               })),
           }, required=["minutes", "target", "exercises"])),

        fn(name="start_exercise",
           description="They are starting this movement now.",
           parameters=S(type=T.OBJECT, properties={
               "name": S(type=T.STRING), "target_reps": S(type=T.INTEGER),
           }, required=["name"])),

        fn(name="rep",
           description=("One COMPLETE repetition just finished -- you watched it go down "
                        "and come back up across several frames. Never on one frame."),
           parameters=S(type=T.OBJECT, properties={
               "observed": S(type=T.STRING, description=(
                   "The position change you actually saw, e.g. 'hips dropped below knee "
                   "then rose'. If you cannot fill this in, do not call this tool.")),
               "quality": S(type=T.STRING, description="clean | shallow | rushed"),
           }, required=["observed"])),

        fn(name="form_ok",
           description=("Form is good DURING AN ACTIVE MOVEMENT. Never call this for "
                        "someone standing still."),
           parameters=S(type=T.OBJECT, properties={
               "observed": S(type=T.STRING, description=(
                   "The movement you saw that you are approving. If you cannot name it, "
                   "do not call this tool.")),
               "note": S(type=T.STRING),
           }, required=["observed"])),

        fn(name="form_error",
           description="A form problem you are coaching through out loud, without stopping them.",
           parameters=S(type=T.OBJECT, properties={
               "error": S(type=T.STRING), "cue": S(type=T.STRING),
           }, required=["error"])),

        fn(name="demonstrate",
           description=("STOP the user. Their camera goes off and you take over the screen "
                        "to show the correct movement. Only for errors worth interrupting."),
           parameters=S(type=T.OBJECT, properties={
               "exercise": S(type=T.STRING),
               "error": S(type=T.STRING, description="what they are doing wrong"),
               "correction": S(type=T.STRING, description="what to do instead, one sentence"),
               "focus": S(type=T.STRING, description="body part to highlight: knees, back, hips, elbows"),
           }, required=["exercise", "error", "correction"])),

        fn(name="end_exercise",
           description="This movement is done.",
           parameters=S(type=T.OBJECT, properties={
               "name": S(type=T.STRING), "completed_reps": S(type=T.INTEGER),
           })),
    ])]
