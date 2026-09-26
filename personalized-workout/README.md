# Offline Personal Fitness Concierge & Resource Router (Gemma 4 Edge Agent)
## Profile & Progress Hub • Voice-Enabled Health Goals • Live Companion

An autonomous, on-device Personal Fitness Concierge running 100% locally via Gemma 4 (E2B / E4B). The agent operates within a continuous, deterministic **Sense-Decide-Act-Check (SDAC)** runtime loop backed by clinical validation tripwires and an on-device SQLite state store.

---

## 1. System Overview & UI Mockup Architecture

Based on the system design mock, this project delivers the core **Profile & Progress Hub** and the connected **Gemma 4 Edge Concierge**:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        TITLE OF THE APP (PULSE EDGE)                   │
│                                                                        │
│   ┌────────────────────────┐  ┌───────────────────────────────────┐    │
│   │ < DIGITAL COACH >      │  │ CAMERA FEED        [END Override] │    │
│   │ Avatar Demonstration   │  │                                   │    │
│   │ Subtitles here...      │  │ Pose & Rep Tracking Active        │    │
│   └────────────────────────┘  │ [Timer] [Mute] [Camera ON/OFF]    │    │
│                               └───────────────────────────────────┘    │
│   ┌────────────────────────┐  ┌───────────────────────────────────┐    │
│   │ WORKOUT PROGRESS BAR   │  │ WORKOUT SUMMARY                   │    │
│   │ (Day 0) ──> (Day 1)★──>│  │ Reps, Total Time, Accuracy        │    │
│   │ *Highlight Current Day │  └───────────────────────────────────┘    │
│   └────────────────────────┘  ┌───────────────────────────────────┐    │
│   ┌────────────────────────┐  │ [👤 PROFILE BUTTON] (Top Corner)  │    │
│   │ "TELL US YOUR GOALS"   │  │ ──> Health Goals (Voice Input)    │    │
│   │ 🎙️ Voice Input Enabled │  │ ──> Healthcare Recommendations    │    │
│   │ Active Health Goals    │  │ ──> Workout Count Progress        │    │
│   └────────────────────────┘  └───────────────────────────────────┘    │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Core Capabilities Built

### 1. Profile & Progress Hub (Top Corner Profile Page)
- Accessible from the top corner profile button with user avatar, current day badge, and total workout count.
- **Workout Count Progress**: Tracks total completed workouts, active streak, and day progression.
- **Day Progression Timeline (Directly from Mock Image)**:
  - Horizontal timeline track: `(Day 0) ──> (Day 1)★ ──> (Day 2) ──> (Day 3)...`
  - **Highlights the current active day** with a pulsing neon badge and elevation.
  - Interactive **"Log Today's Workout Complete"** action that advances the user from `Day 0` to `Day 1` to `Day 2` with persistent SQLite logging.

### 2. Voice-Enabled Health Goals Tracking ("Tell Us Your Goals")
- **Web Speech API (`SpeechRecognition`) integration**: Real-time microphone listening with animated recording pulse. Users can speak their fitness goals hands-free.
- Automatically extracts structured **Health Goals** (e.g., knee rehab, lumbar decompression, senior mobility, desk posture, cardio stamina).
- Goals are tracked, persisted in SQLite, and can be updated anytime.

### 3. Healthcare Recommendations
- Generates tailored clinical recommendations and contraindication guidelines based on the user's specific health goals and orthopedic status:
  - Patellofemoral protocols (limiting deep flexion, TKEs, Spanish squat isometrics).
  - Lumbar spine decompression protocols (neutral pelvis, supine 90/90 breathing, glute medius activation).
  - Senior balance and cardiac pacing guidelines.

### 4. Curated Recommended Routines
- Selects certified offline routines matching the user's health goals with zero hallucinations.
- Automatically audits exercises against contraindication tags (`deep_flexion`, `high_impact`, `axial_loading`).

### 5. SDAC Runtime Loop & Edge Concierge
- **Sense-Decide-Act-Check (SDAC)** continuous loop.
- **Acute Red Flag Tripwires**: Instant stop on radiating chest pain, dizziness, shortness of breath, sudden numbness, or post-operative healing <6 weeks (`STATUS_LOCKED_MEDICAL`).
- **Offline Boundary Gate**: Defers real-time camera tracking when offline, provides static alignment cues, and queues sessions for online handoff.

---

## 3. Directory Structure

```
personalized-workout/
├── assets/
│   └── guides/                           # Offline Markdown resource guides
│       ├── lumbar_decompression.md
│       ├── squat_form_alignment.md
│       ├── knee_sparing_mobility.md
│       ├── rotator_cuff_activation.md
│       └── thoracic_spine_release.md
├── database/
│   ├── schema.sql                        # SQLite schema (users, routines, logs, etc.)
│   ├── seed_data.py                      # Certified movements and routines
│   └── db_manager.py                     # Thread-safe SQLite manager & progress tracker
├── concierge/
│   ├── models.py                         # Pydantic schemas (SDAC Output Schema)
│   ├── health_goals.py                   # Voice goals processor & healthcare recommender
│   ├── sense.py                          # Step 1: Input & Telemetry sensing
│   ├── decide.py                         # Step 2: Gemma 4 routing & red flag checks
│   ├── act.py                            # Step 3: Local SQLite function caller
│   ├── check.py                          # Step 4: Deterministic safety rules
│   ├── engine.py                         # SDAC Orchestrator & retry recovery loop
│   └── gemma_runtime.py                  # Gemma 4 Edge Agent runtime & system prompts
├── web/
│   ├── app.py                            # FastAPI backend with Profile & Progress API
│   └── static/
│       ├── index.html                    # Profile Hub, Concierge Chat & Sketch Mockup
│       ├── style.css                     # Responsive dark-tech styling
│       └── app.js                        # Voice recognition controller & progress renderer
├── tests/
│   ├── test_profile_and_goals.py         # Tests voice goals, recs, and Day progression
│   ├── test_red_flags.py                 # Tests acute medical triage lockdown
│   ├── test_tripwires.py                 # Tests Rule 1 contraindication exclusions
│   ├── test_age_gate.py                  # Tests Rule 2 senior heart rate / HIIT gate
│   ├── test_online_gate.py               # Tests Rule 3 offline deferral vs online token handoff
│   ├── test_recovery_loop.py             # Tests retry budget decrement & human handoff
│   └── test_sdac_engine.py               # End-to-end SDAC integration & schema adherence
├── run_cli.py                            # Terminal CLI runner with preset scenarios
├── run.sh                                # Execution helper script
└── requirements.txt                      # Project dependencies
```

---

## 4. Running the Application

### 1. Start the Interactive Web Application
```bash
cd /Users/nisha/gdg-deepmind-hackathon/personalized-workout
source .venv/bin/activate
python3 -m uvicorn web.app:app --host 127.0.0.1 --port 8000
```
Open **`http://127.0.0.1:8000`** in Chrome or Safari:
1. **Profile & Progress Hub**:
   - Tap the **🎙️ Microphone button** to speak your health goals (or click any of the quick voice presets).
   - Watch your **Active Health Goals**, **Healthcare Recommendations**, and **Recommended Routines** update in real-time.
   - Look at the **Workout Progress Timeline**: `(Day 0) ──> (Day 1)★ ──> (Day 2)`.
   - Click **"Log Today's Workout Complete"** to advance the progression day and increment your workout count!
2. **Gemma Edge Concierge**:
   - Chat with the Gemma 4 Edge Concierge and inspect the live SDAC pipeline and RFC 8259 JSON schema.
3. **Live Companion View**:
   - View the connected workout tool from the mock sketch with Digital Coach avatar, camera feed controls, timer, and workout summary.

### 2. Run the 18 Automated Unit Tests
```bash
source .venv/bin/activate
PYTHONPATH=. pytest -v
```

### 3. Run the CLI
```bash
source .venv/bin/activate
python3 run_cli.py --scenario knee
```
