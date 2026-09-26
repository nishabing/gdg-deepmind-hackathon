"""
Database manager for on-device SQLite state store.
Handles schema initialization, migrations, seeding, atomic transactions,
health goals tracking, and workout count progress.
"""

import json
import os
import sqlite3
import uuid
from typing import Any, Dict, List, Optional
from database.seed_data import EXERCISES, ROUTINES, RESOURCE_GUIDES

DEFAULT_DB_PATH = os.path.join(os.path.dirname(__file__), "concierge_state.db")
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")


class DBManager:
    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path
        self.init_db()

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self) -> None:
        """Initialize SQLite tables, run migrations, and seed initial data if not present."""
        with open(SCHEMA_PATH, "r") as f:
            schema_sql = f.read()

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.executescript(schema_sql)

            # Auto-migrate existing users table if columns are missing
            cursor.execute("PRAGMA table_info(users)")
            existing_cols = {row["name"] for row in cursor.fetchall()}

            if "health_goals" not in existing_cols:
                cursor.execute("ALTER TABLE users ADD COLUMN health_goals TEXT DEFAULT '[]'")
            if "workout_count" not in existing_cols:
                cursor.execute("ALTER TABLE users ADD COLUMN workout_count INTEGER DEFAULT 0")
            if "current_day" not in existing_cols:
                cursor.execute("ALTER TABLE users ADD COLUMN current_day INTEGER DEFAULT 0")
            if "streak_days" not in existing_cols:
                cursor.execute("ALTER TABLE users ADD COLUMN streak_days INTEGER DEFAULT 0")
            if "healthcare_recommendations" not in existing_cols:
                cursor.execute("ALTER TABLE users ADD COLUMN healthcare_recommendations TEXT DEFAULT '[]'")

            # Check if exercises table is populated
            cursor.execute("SELECT COUNT(*) FROM exercises")
            if cursor.fetchone()[0] == 0:
                for ex in EXERCISES:
                    cursor.execute(
                        """
                        INSERT INTO exercises (id, name, focus, intensity_tier, tags, equipment_required, default_reps_or_time, description)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            ex["id"],
                            ex["name"],
                            ex["focus"],
                            ex["intensity_tier"],
                            json.dumps(ex["tags"]),
                            json.dumps(ex["equipment_required"]),
                            ex["default_reps_or_time"],
                            ex["description"]
                        )
                    )

            # Add new curated routines on existing installations without overwriting edits.
            for r in ROUTINES:
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO routines (id, title, focus, intensity_tier, duration_min, tags, exercise_ids, description, disclaimer)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        r["id"],
                        r["title"],
                        r["focus"],
                        r["intensity_tier"],
                        r["duration_min"],
                        json.dumps(r["tags"]),
                        json.dumps(r["exercise_ids"]),
                        r["description"],
                        r["disclaimer"]
                    )
                )

            # Check if resource_guides table is populated
            cursor.execute("SELECT COUNT(*) FROM resource_guides")
            if cursor.fetchone()[0] == 0:
                for g in RESOURCE_GUIDES:
                    cursor.execute(
                        """
                        INSERT INTO resource_guides (id, title, movement_id, offline_path, summary, tags)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            g["id"],
                            g["title"],
                            g["movement_id"],
                            g["offline_path"],
                            g["summary"],
                            json.dumps(g["tags"])
                        )
                    )

            # Check if default user exists
            cursor.execute("SELECT COUNT(*) FROM users WHERE id = 'default_user'")
            if cursor.fetchone()[0] == 0:
                default_goals = json.dumps([
                    "Relieve lower back stiffness and decompress spine",
                    "Build functional hip and posterior chain mobility",
                    "Maintain a consistent 15-minute daily movement routine"
                ])
                default_recs = json.dumps([
                    "Maintain neutral spine alignment during all hip hinge patterns",
                    "Avoid axial compressive spinal loading until mobility improves",
                    "Take 60-second restorative nasal breathing pauses between sets"
                ])
                cursor.execute(
                    """
                    INSERT INTO users (
                        id, age_band, fitness_tier, target_duration_min,
                        orthopedic_flags, available_equipment, session_status,
                        health_goals, workout_count, current_day, streak_days, healthcare_recommendations
                    )
                    VALUES ('default_user', 'adult', 'intermediate', 15, '[]', '["bodyweight"]', 'READY', ?, 0, 0, 0, ?)
                    """,
                    (default_goals, default_recs)
                )

            conn.commit()

    def get_user(self, user_id: str = "default_user") -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return {
                "id": row["id"],
                "age_band": row["age_band"],
                "fitness_tier": row["fitness_tier"],
                "target_duration_min": row["target_duration_min"],
                "orthopedic_flags": json.loads(row["orthopedic_flags"] or '[]'),
                "available_equipment": json.loads(row["available_equipment"] or '["bodyweight"]'),
                "medical_clearance_flags": json.loads(row["medical_clearance_flags"] or '[]'),
                "health_goals": json.loads(row["health_goals"] or '[]'),
                "workout_count": row["workout_count"] or 0,
                "current_day": row["current_day"] or 0,
                "streak_days": row["streak_days"] or 0,
                "healthcare_recommendations": json.loads(row["healthcare_recommendations"] or '[]'),
                "session_status": row["session_status"],
                "live_tool_intent_cached": bool(row["live_tool_intent_cached"]),
                "updated_at": row["updated_at"]
            }

    def upsert_user(
        self,
        user_id: str = "default_user",
        age_band: Optional[str] = None,
        fitness_tier: Optional[str] = None,
        target_duration_min: Optional[int] = None,
        orthopedic_flags: Optional[List[str]] = None,
        available_equipment: Optional[List[str]] = None,
        medical_clearance_flags: Optional[List[str]] = None,
        session_status: Optional[str] = None,
        live_tool_intent_cached: Optional[bool] = None,
        health_goals: Optional[List[str]] = None,
        workout_count: Optional[int] = None,
        current_day: Optional[int] = None,
        streak_days: Optional[int] = None,
        healthcare_recommendations: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        existing = self.get_user(user_id)
        if not existing:
            age_band = age_band or "adult"
            fitness_tier = fitness_tier or "beginner"
            target_duration_min = target_duration_min or 15
            orthopedic_flags = orthopedic_flags or []
            available_equipment = available_equipment or ["bodyweight"]
            medical_clearance_flags = medical_clearance_flags or []
            session_status = session_status or "READY"
            live_tool_intent_cached = live_tool_intent_cached if live_tool_intent_cached is not None else False
            health_goals = health_goals or []
            workout_count = workout_count or 0
            current_day = current_day or 0
            streak_days = streak_days or 0
            healthcare_recommendations = healthcare_recommendations or []

            with self.get_connection() as conn:
                conn.cursor().execute(
                    """
                    INSERT INTO users (
                        id, age_band, fitness_tier, target_duration_min,
                        orthopedic_flags, available_equipment, medical_clearance_flags,
                        session_status, live_tool_intent_cached, health_goals,
                        workout_count, current_day, streak_days, healthcare_recommendations
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        user_id, age_band, fitness_tier, target_duration_min,
                        json.dumps(orthopedic_flags), json.dumps(available_equipment),
                        json.dumps(medical_clearance_flags), session_status, int(live_tool_intent_cached),
                        json.dumps(health_goals), workout_count, current_day, streak_days,
                        json.dumps(healthcare_recommendations)
                    )
                )
                conn.commit()
        else:
            new_age = age_band if age_band is not None else existing["age_band"]
            new_tier = fitness_tier if fitness_tier is not None else existing["fitness_tier"]
            new_dur = target_duration_min if target_duration_min is not None else existing["target_duration_min"]
            new_flags = orthopedic_flags if orthopedic_flags is not None else existing["orthopedic_flags"]
            new_equip = available_equipment if available_equipment is not None else existing["available_equipment"]
            new_med = medical_clearance_flags if medical_clearance_flags is not None else existing["medical_clearance_flags"]
            new_status = session_status if session_status is not None else existing["session_status"]
            new_intent = live_tool_intent_cached if live_tool_intent_cached is not None else existing["live_tool_intent_cached"]
            new_goals = health_goals if health_goals is not None else existing["health_goals"]
            new_count = workout_count if workout_count is not None else existing["workout_count"]
            new_day = current_day if current_day is not None else existing["current_day"]
            new_streak = streak_days if streak_days is not None else existing["streak_days"]
            new_recs = healthcare_recommendations if healthcare_recommendations is not None else existing["healthcare_recommendations"]

            with self.get_connection() as conn:
                conn.cursor().execute(
                    """
                    UPDATE users
                    SET age_band = ?, fitness_tier = ?, target_duration_min = ?,
                        orthopedic_flags = ?, available_equipment = ?, medical_clearance_flags = ?,
                        session_status = ?, live_tool_intent_cached = ?, health_goals = ?,
                        workout_count = ?, current_day = ?, streak_days = ?,
                        healthcare_recommendations = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (
                        new_age, new_tier, new_dur,
                        json.dumps(new_flags), json.dumps(new_equip),
                        json.dumps(new_med), new_status, int(new_intent),
                        json.dumps(new_goals), new_count, new_day, new_streak,
                        json.dumps(new_recs), user_id
                    )
                )
                conn.commit()

        return self.get_user(user_id) # type: ignore

    def log_completed_workout(
        self,
        user_id: str = "default_user",
        routine_id: Optional[str] = None,
        routine_title: Optional[str] = None,
        duration_min: int = 15,
        reps_completed: int = 40,
        notes: str = ""
    ) -> Dict[str, Any]:
        """Logs a completed workout session, increments count, and advances current progression day."""
        user = self.get_user(user_id) or {}
        new_count = (user.get("workout_count", 0)) + 1
        new_day = (user.get("current_day", 0)) + 1
        new_streak = (user.get("streak_days", 0)) + 1
        title = routine_title or "Custom Movement Session"

        log_id = f"wlog_{uuid.uuid4().hex[:8]}"
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO workout_logs (id, user_id, routine_id, routine_title, day_number, duration_min, reps_completed, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (log_id, user_id, routine_id, title, user.get("current_day", 0), duration_min, reps_completed, notes)
            )
            cursor.execute(
                """
                UPDATE users
                SET workout_count = ?, current_day = ?, streak_days = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (new_count, new_day, new_streak, user_id)
            )
            conn.commit()

        return {
            "log_id": log_id,
            "workout_count": new_count,
            "current_day": new_day,
            "streak_days": new_streak,
            "routine_title": title
        }

    def get_user_progress(self, user_id: str = "default_user") -> Dict[str, Any]:
        """
        Calculates workout count progress and generates the Day progression timeline:
        Day 0 -> Day 1 -> Day 2 ... with the current active day highlighted.
        """
        user = self.get_user(user_id) or {}
        current_day = user.get("current_day", 0)
        workout_count = user.get("workout_count", 0)
        streak_days = user.get("streak_days", 0)

        # Build timeline (from Day 0 up to max(current_day + 2, 5))
        total_timeline_days = max(current_day + 3, 6)
        timeline = []
        for d in range(total_timeline_days):
            if d < current_day:
                status = "completed"
            elif d == current_day:
                status = "active_today"
            else:
                status = "upcoming"
            timeline.append({
                "day_number": d,
                "label": f"Day {d}",
                "status": status,
                "is_current": (d == current_day)
            })

        # Fetch recent logs
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM workout_logs WHERE user_id = ? ORDER BY completed_at DESC LIMIT 10",
                (user_id,)
            )
            logs = [dict(r) for r in cursor.fetchall()]

        return {
            "user_id": user_id,
            "workout_count": workout_count,
            "current_day": current_day,
            "streak_days": streak_days,
            "timeline": timeline,
            "recent_workouts": logs
        }

    def query_local_routines(
        self,
        focus: Optional[str] = None,
        intensity_tier: Optional[str] = None,
        exclude_tags: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        exclude_tags = [t.lower() for t in (exclude_tags or [])]
        with self.get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM routines WHERE 1=1"
            params: List[Any] = []

            if focus:
                query += " AND (focus LIKE ? OR title LIKE ?)"
                params.extend([f"%{focus}%", f"%{focus}%"])
            if intensity_tier:
                query += " AND intensity_tier = ?"
                params.append(intensity_tier.lower())

            query += " ORDER BY id"
            cursor.execute(query, params)
            rows = cursor.fetchall()
            results = []

            for row in rows:
                tags = json.loads(row["tags"])
                exercise_ids = json.loads(row["exercise_ids"])

                if any(ext in [t.lower() for t in tags] for ext in exclude_tags):
                    continue

                ex_placeholders = ",".join("?" for _ in exercise_ids)
                if exercise_ids:
                    cursor.execute(f"SELECT * FROM exercises WHERE id IN ({ex_placeholders})", exercise_ids)
                    ex_rows = cursor.fetchall()
                else:
                    ex_rows = []

                has_contraindication = False
                exercise_list = []
                for ex in ex_rows:
                    ex_tags = [t.lower() for t in json.loads(ex["tags"])]
                    if any(ext in ex_tags for ext in exclude_tags):
                        has_contraindication = True
                        break
                    exercise_list.append({
                        "id": ex["id"],
                        "name": ex["name"],
                        "focus": ex["focus"],
                        "intensity_tier": ex["intensity_tier"],
                        "tags": json.loads(ex["tags"]),
                        "equipment_required": json.loads(ex["equipment_required"]),
                        "default_reps_or_time": ex["default_reps_or_time"],
                        "description": ex["description"]
                    })

                if has_contraindication:
                    continue

                results.append({
                    "id": row["id"],
                    "title": row["title"],
                    "focus": row["focus"],
                    "intensity_tier": row["intensity_tier"],
                    "duration_min": row["duration_min"],
                    "tags": tags,
                    "exercises": exercise_list,
                    "description": row["description"],
                    "disclaimer": row["disclaimer"]
                })

            return results

    def get_recommended_routines(self, user_id: str = "default_user", limit: int = 3) -> List[Dict[str, Any]]:
        """Return varied low-intensity routines matched to a user's saved goals and constraints."""
        user = self.get_user(user_id) or {}
        flags = set(user.get("orthopedic_flags", []))
        goals = " ".join(user.get("health_goals", [])).lower()

        if "knee_pain" in flags or any(term in goals for term in ("knee", "patellar")):
            focus = "knee_rehab"
        elif "shoulder_impingement" in flags or any(term in goals for term in ("shoulder", "posture", "neck")):
            focus = "upper_body_mobility"
        elif any(term in goals for term in ("cardio", "endurance", "stamina")):
            focus = "cardio_anaerobic"
        else:
            focus = "posterior_chain_mobility"

        excluded_tags = set()
        if "knee_pain" in flags:
            excluded_tags.update(("deep_flexion", "high_impact"))
        if "lumbar_stiffness" in flags:
            excluded_tags.update(("axial_loading", "heavy_spinal_flexion"))
        if "shoulder_impingement" in flags:
            excluded_tags.add("overhead_pressing")
        if user.get("age_band") == "senior":
            excluded_tags.update(("anaerobic_circuit", "high_intensity"))

        routines = self.query_local_routines(
            focus=focus,
            intensity_tier="low",
            exclude_tags=sorted(excluded_tags)
        )
        if not routines and focus != "posterior_chain_mobility":
            routines = self.query_local_routines(
                focus="posterior_chain_mobility",
                intensity_tier="low",
                exclude_tags=sorted(excluded_tags)
            )

        if not routines or limit <= 0:
            return []

        # Rotate the lead recommendation after completed sessions instead of showing
        # the same first database row every time the profile is opened.
        offset = user.get("workout_count", 0) % len(routines)
        routines = routines[offset:] + routines[:offset]
        return routines[:limit]

    def get_local_resource_guides(self, movement_id_or_keyword: str) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            kw = f"%{movement_id_or_keyword.lower()}%"
            cursor.execute(
                """
                SELECT * FROM resource_guides
                WHERE LOWER(movement_id) LIKE ?
                   OR LOWER(title) LIKE ?
                   OR LOWER(tags) LIKE ?
                """,
                (kw, kw, kw)
            )
            rows = cursor.fetchall()
            return [
                {
                    "id": r["id"],
                    "title": r["title"],
                    "movement_id": r["movement_id"],
                    "offline_path": r["offline_path"],
                    "summary": r["summary"],
                    "tags": json.loads(r["tags"])
                }
                for r in rows
            ]

    def queue_live_tool_session(self, user_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        session_id = f"live_sess_{uuid.uuid4().hex[:10]}"
        token = f"livetool://handoff?token={uuid.uuid4().hex}&sess={session_id}"
        with self.get_connection() as conn:
            conn.cursor().execute(
                """
                INSERT INTO live_tool_queue (id, user_id, status, payload, handoff_token)
                VALUES (?, ?, 'QUEUED', ?, ?)
                """,
                (session_id, user_id, json.dumps(payload), token)
            )
            conn.cursor().execute(
                "UPDATE users SET live_tool_intent_cached = 1 WHERE id = ?",
                (user_id,)
            )
            conn.commit()
        return {
            "session_id": session_id,
            "handoff_token": token,
            "status": "QUEUED"
        }

    def record_audit_log(
        self,
        session_id: str,
        user_id: str,
        input_text: str,
        network_status: str,
        memory_headroom: str,
        sensed_demographics: Dict[str, Any],
        routing_decision: str,
        action_tool_call: str,
        action_parameters: Dict[str, Any],
        audit_passed: bool,
        audit_failure_reasons: List[str],
        recovery_attempts: int,
        final_state: str,
        output_payload: Dict[str, Any]
    ) -> str:
        log_id = f"audit_{uuid.uuid4().hex[:8]}"
        with self.get_connection() as conn:
            conn.cursor().execute(
                """
                INSERT INTO sdac_audit_logs (
                    id, session_id, user_id, input_text, network_status, memory_headroom,
                    sensed_demographics, routing_decision, action_tool_call, action_parameters,
                    audit_passed, audit_failure_reasons, recovery_attempts, final_state, output_payload
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    log_id, session_id, user_id, input_text, network_status, memory_headroom,
                    json.dumps(sensed_demographics), routing_decision, action_tool_call,
                    json.dumps(action_parameters), int(audit_passed), json.dumps(audit_failure_reasons),
                    recovery_attempts, final_state, json.dumps(output_payload)
                )
            )
            conn.commit()
        return log_id

    def list_audit_logs(self, limit: int = 20) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM sdac_audit_logs ORDER BY timestamp DESC LIMIT ?", (limit,))
            rows = cursor.fetchall()
            return [
                {
                    "id": r["id"],
                    "session_id": r["session_id"],
                    "user_id": r["user_id"],
                    "timestamp": r["timestamp"],
                    "input_text": r["input_text"],
                    "network_status": r["network_status"],
                    "memory_headroom": r["memory_headroom"],
                    "sensed_demographics": json.loads(r["sensed_demographics"]),
                    "routing_decision": r["routing_decision"],
                    "action_tool_call": r["action_tool_call"],
                    "action_parameters": json.loads(r["action_parameters"]),
                    "audit_passed": bool(r["audit_passed"]),
                    "audit_failure_reasons": json.loads(r["audit_failure_reasons"]),
                    "recovery_attempts": r["recovery_attempts"],
                    "final_state": r["final_state"],
                    "output_payload": json.loads(r["output_payload"])
                }
                for r in rows
            ]
