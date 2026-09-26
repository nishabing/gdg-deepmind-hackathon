"""
FastAPI Backend Server for Offline Personal Fitness Concierge (Gemma 4 Edge Agent).
Serves SDAC execution API, telemetry controls, database inspection, and interactive UI.
Features:
- Profile & Progress Hub
- Voice-enabled Health Goals tracking
- Healthcare recommendations & routine curation
- Day 0 -> Day 1 -> Day 2 workout progression timeline
"""

import os
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from concierge.engine import SDACEngine
from concierge.health_goals import HealthGoalsManager
from concierge.models import NetworkStatus, DeviceMemoryHeadroom, Telemetry, SDACOutput
from database.db_manager import DBManager

app = FastAPI(
    title="Gemma 4 Edge Agent - Fitness Concierge",
    description="Offline Personal Fitness Concierge & Resource Router running via Sense-Decide-Act-Check (SDAC) loop",
    version="1.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Instantiate singletons
db = DBManager()
engine = SDACEngine(db=db)
goals_manager = HealthGoalsManager(db=db)

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
GUIDES_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "assets", "guides"))


class ChatRequest(BaseModel):
    message: str
    network_status: str = "OFFLINE"
    device_memory_headroom: str = "NOMINAL"
    user_id: str = "default_user"
    session_id: Optional[str] = "sess_web_001"


class UserProfileUpdate(BaseModel):
    age_band: Optional[str] = None
    fitness_tier: Optional[str] = None
    target_duration_min: Optional[int] = None
    orthopedic_flags: Optional[List[str]] = None
    available_equipment: Optional[List[str]] = None
    medical_clearance_flags: Optional[List[str]] = None
    session_status: Optional[str] = None
    health_goals: Optional[List[str]] = None


class HealthGoalRequest(BaseModel):
    input_text: str
    user_id: str = "default_user"


class CompleteWorkoutRequest(BaseModel):
    user_id: str = "default_user"
    routine_id: Optional[str] = None
    routine_title: Optional[str] = None
    duration_min: int = 15
    reps: int = 40
    notes: str = ""


@app.post("/api/chat", response_model=SDACOutput)
def chat_endpoint(req: ChatRequest):
    """Executes a full SDAC cycle for the incoming conversational turn."""
    try:
        net_status = NetworkStatus(req.network_status.upper())
    except ValueError:
        net_status = NetworkStatus.OFFLINE

    try:
        mem_status = DeviceMemoryHeadroom(req.device_memory_headroom.upper())
    except ValueError:
        mem_status = DeviceMemoryHeadroom.NOMINAL

    telemetry = Telemetry(
        network_status=net_status,
        device_memory_headroom=mem_status
    )

    session_id = req.session_id or "sess_web"
    output = engine.run_sdac_cycle(
        user_input=req.message,
        telemetry=telemetry,
        user_id=req.user_id,
        session_id=session_id
    )
    return output


@app.get("/api/user/{user_id}")
def get_user_endpoint(user_id: str = "default_user"):
    user = db.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@app.post("/api/user/{user_id}")
def update_user_endpoint(user_id: str, profile: UserProfileUpdate):
    updated = db.upsert_user(
        user_id=user_id,
        age_band=profile.age_band,
        fitness_tier=profile.fitness_tier,
        target_duration_min=profile.target_duration_min,
        orthopedic_flags=profile.orthopedic_flags,
        available_equipment=profile.available_equipment,
        medical_clearance_flags=profile.medical_clearance_flags,
        session_status=profile.session_status,
        health_goals=profile.health_goals
    )
    return updated


@app.post("/api/user/{user_id}/reset")
def reset_user_endpoint(user_id: str = "default_user"):
    updated = db.upsert_user(
        user_id=user_id,
        age_band="adult",
        fitness_tier="intermediate",
        target_duration_min=15,
        orthopedic_flags=[],
        available_equipment=["bodyweight"],
        medical_clearance_flags=[],
        session_status="READY",
        live_tool_intent_cached=False,
        health_goals=[
            "Relieve lower back stiffness and decompress spine",
            "Build functional hip and posterior chain mobility",
            "Maintain a consistent 15-minute daily movement routine"
        ],
        workout_count=0,
        current_day=0,
        streak_days=0,
        healthcare_recommendations=[
            "Maintain neutral spine alignment during all hip hinge patterns",
            "Avoid axial compressive spinal loading until mobility improves",
            "Take 60-second restorative nasal breathing pauses between sets"
        ]
    )
    return updated


# =========================================================================
# PROFILE & PROGRESS HUB ENDPOINTS (Voice Goals, Recommendations, Progress)
# =========================================================================

@app.get("/api/profile/{user_id}")
def get_full_profile_endpoint(user_id: str = "default_user"):
    user = db.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    progress = db.get_user_progress(user_id)

    # Curate recommended routines matching current profile & goals
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
def update_health_goals_endpoint(user_id: str, req: HealthGoalRequest):
    """Processes spoken voice input or typed goals, returns updated recommendations & routines."""
    result = goals_manager.process_and_update_goals(raw_goals_input=req.input_text, user_id=user_id)
    progress = db.get_user_progress(user_id)
    result["progress"] = progress
    return result


@app.get("/api/profile/{user_id}/progress")
def get_progress_endpoint(user_id: str = "default_user"):
    return db.get_user_progress(user_id)


@app.post("/api/profile/{user_id}/workout/complete")
def complete_workout_endpoint(user_id: str, req: CompleteWorkoutRequest):
    """Logs completed workout, increments workout_count, and advances current progression day."""
    result = db.log_completed_workout(
        user_id=user_id,
        routine_id=req.routine_id,
        routine_title=req.routine_title,
        duration_min=req.duration_min,
        reps_completed=req.reps,
        notes=req.notes
    )
    progress = db.get_user_progress(user_id)
    result["progress"] = progress
    return result


@app.get("/api/routines")
def list_routines_endpoint(focus: Optional[str] = None, intensity: Optional[str] = None):
    return db.query_local_routines(focus=focus, intensity_tier=intensity)


@app.get("/api/guides")
def list_guides_endpoint(keyword: str = ""):
    return db.get_local_resource_guides(keyword)


@app.get("/api/guide/view/{guide_id}")
def view_guide_content(guide_id: str):
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM resource_guides WHERE id = ?", (guide_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Guide not found")

        rel_path = row["offline_path"]
        abs_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", rel_path))
        if not os.path.exists(abs_path):
            raise HTTPException(status_code=404, detail="Offline asset file missing")

        with open(abs_path, "r", encoding="utf-8") as f:
            content = f.read()

        return {
            "id": row["id"],
            "title": row["title"],
            "offline_path": rel_path,
            "content": content
        }


@app.get("/api/live_queue")
def list_live_queue_endpoint():
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM live_tool_queue ORDER BY queued_at DESC LIMIT 20")
        rows = cursor.fetchall()
        return [dict(r) for r in rows]


@app.get("/api/audit_logs")
def list_audit_logs_endpoint(limit: int = 25):
    return db.list_audit_logs(limit=limit)


# Mount static frontend
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def serve_index():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return HTMLResponse("<h3>Gemma 4 Edge Agent Fitness Concierge is running.</h3>")
