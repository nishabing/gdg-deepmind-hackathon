"""
Database manager for on-device SQLite state store.
Handles schema initialization, seeding, atomic transactions, and querying.
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
        """Initialize SQLite tables and seed initial data if not present."""
        with open(SCHEMA_PATH, "r") as f:
            schema_sql = f.read()

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.executescript(schema_sql)

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

            # Check if routines table is populated
            cursor.execute("SELECT COUNT(*) FROM routines")
            if cursor.fetchone()[0] == 0:
                for r in ROUTINES:
                    cursor.execute(
                        """
                        INSERT INTO routines (id, title, focus, intensity_tier, duration_min, tags, exercise_ids, description, disclaimer)
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
                cursor.execute(
                    """
                    INSERT INTO users (id, age_band, fitness_tier, target_duration_min, orthopedic_flags, available_equipment, session_status)
                    VALUES ('default_user', 'adult', 'intermediate', 15, '[]', '["bodyweight"]', 'READY')
                    """
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
                "orthopedic_flags": json.loads(row["orthopedic_flags"]),
                "available_equipment": json.loads(row["available_equipment"]),
                "medical_clearance_flags": json.loads(row["medical_clearance_flags"]),
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
        live_tool_intent_cached: Optional[bool] = None
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
            with self.get_connection() as conn:
                conn.cursor().execute(
                    """
                    INSERT INTO users (id, age_band, fitness_tier, target_duration_min, orthopedic_flags, available_equipment, medical_clearance_flags, session_status, live_tool_intent_cached)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        user_id, age_band, fitness_tier, target_duration_min,
                        json.dumps(orthopedic_flags), json.dumps(available_equipment),
                        json.dumps(medical_clearance_flags), session_status, int(live_tool_intent_cached)
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

            with self.get_connection() as conn:
                conn.cursor().execute(
                    """
                    UPDATE users
                    SET age_band = ?, fitness_tier = ?, target_duration_min = ?,
                        orthopedic_flags = ?, available_equipment = ?, medical_clearance_flags = ?,
                        session_status = ?, live_tool_intent_cached = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (
                        new_age, new_tier, new_dur,
                        json.dumps(new_flags), json.dumps(new_equip),
                        json.dumps(new_med), new_status, int(new_intent),
                        user_id
                    )
                )
                conn.commit()

        return self.get_user(user_id) # type: ignore

    def query_local_routines(
        self,
        focus: Optional[str] = None,
        intensity_tier: Optional[str] = None,
        exclude_tags: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Query routines from local SQLite store, filtering by focus, intensity, and
        rigorously eliminating any routine whose exercises contain any excluded tag.
        """
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

            cursor.execute(query, params)
            rows = cursor.fetchall()
            results = []

            for row in rows:
                tags = json.loads(row["tags"])
                exercise_ids = json.loads(row["exercise_ids"])

                # Check routine-level excluded tags
                if any(ext in [t.lower() for t in tags] for ext in exclude_tags):
                    continue

                # Query associated exercises and inspect their individual tags
                ex_placeholders = ",".join("?" for _ in exercise_ids)
                if exercise_ids:
                    cursor.execute(f"SELECT * FROM exercises WHERE id IN ({ex_placeholders})", exercise_ids)
                    ex_rows = cursor.fetchall()
                else:
                    ex_rows = []

                # Verify contraindication exclusion against each exercise
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

    def get_local_resource_guides(self, movement_id_or_keyword: str) -> List[Dict[str, Any]]:
        """Query offline guides matching movement ID or keywords."""
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
        """Save a pending live workout session for online execution/handoff."""
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
            # Update user cached intent
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
