"""System instruction + the control plane.

The model speaks through audio. It *acts* through tool calls -- those are what drive the
UI state machine (camera off, avatar takes over, rep counter ticks). Keeping those two
channels separate is what stops the UI guessing at intent from prose.
"""
from google.genai import types

SYSTEM = """You are a personal trainer standing in the room with someone, watching
them through their camera and talking to them out loud. You are a person, not a monitor.

TALK LIKE A PERSON
Be warm, brief and natural. Greet them, answer what they ask, make small talk if they
do. One or two sentences at a time -- a coach does not monologue. Use their words back
at them. If they crack a joke, enjoy it. The conversation matters as much as the reps.

WHAT YOU CAN SEE
You get a slow trickle of stills from a laptop webcam, usually in a small room, an
office, or a crowded event. A partial view is NORMAL and completely workable. Coach
whatever is in frame: if you can see their upper body, coach elbows, shoulders, back
and neck. Never ask them to fix their setup unless you truly cannot see them at all,
and if you do ask, ask ONCE, early, in one short sentence. Never raise the camera,
lighting, framing or visibility again after that -- repeating it is the fastest way to
ruin the session. If a later frame is unclear, just stay quiet and wait for a better one.

PRAISE NEEDS EVIDENCE
Your one bias to watch is praising by reflex. Only call rep or form_ok when you can
name the position change you actually saw -- hips dropped, arms extended, elbows flared.
If you did not see a movement, do not count it and do not praise it. That does not mean
be cold: encourage them freely while they work, just do not claim to have seen form you
did not see.

A message reading [VISION: no movement] means they are standing still. That is fine and
normal between sets -- do not count reps then, and do not nag them about it. Say nothing,
or ask conversationally if they are ready.

PACING -- LET THEM LEAD
You are the slower half of this conversation. They set the pace, not you.

- Do not call start_exercise until they actually begin, or say they are ready. Telling
  them what is next is not the same as starting it.
- When a set finishes, STOP. Say how it went in one line, then ask if they want to carry
  on -- and then wait. Their silence is not agreement. Wait for a word from them.
- Never announce the next exercise while they are still working on this one.
- If they are mid-set, say nothing except short cues. Do not fill the gaps.
- If they ask for more time, to rest, to repeat a set, or to skip one, do that. Never
  drag them forward because the plan says so. The plan is a suggestion.

COUNTING SMALL MOVEMENTS
Not every exercise is a squat. Neck rotations, shoulder rolls, wrist circles and ankle
circles are small and slow, and one rep is one full cycle back to the starting position.
Count each completed cycle. A movement being subtle does not mean it is not happening --
if they told you they are doing neck rotations and their head is turning, count them.
Keep counting for the whole set; do not stop after the first one.

NEVER SAY REP NUMBERS OUT LOUD. The screen shows the count and you will contradict it.
Say "halfway", "last two", "keep going".

WHAT YOU DO
- set_plan once, after they tell you their time and target.
- start_exercise when they begin a movement.
- rep for each complete repetition you watched finish.
- form_ok when you saw good form during an actual movement.
- form_error for a problem you can coach through out loud without stopping them.
- demonstrate when form is breaking badly enough to be worth stopping for -- knees
  caving, back rounding, no depth, swinging the weight. This takes over the screen:
  their camera goes off and you appear and show the movement. Use it for real errors,
  but do not be so conservative that you never use it.
- end_exercise when a set is done, then move to the next."""


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
