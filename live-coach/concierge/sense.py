"""
Step 1: SENSE (Input & Context Ingestion)
Parses unstructured conversational input, device telemetry, and SQLite user profiles.
"""

import re
from typing import Any, Dict, List, Optional, Tuple
from concierge.models import AgeBand, FitnessTier, SensedDemographics, Telemetry, NetworkStatus, DeviceMemoryHeadroom
from database.db_manager import DBManager


class Sensor:
    def __init__(self, db: DBManager):
        self.db = db

    def sense(
        self,
        user_input: str,
        telemetry: Optional[Telemetry] = None,
        user_id: str = "default_user"
    ) -> Tuple[SensedDemographics, Telemetry, Dict[str, Any]]:
        """
        Ingest user input, merge with existing SQLite profile, and synthesize
        demographic context and hardware telemetry.
        """
        if telemetry is None:
            telemetry = Telemetry(
                network_status=NetworkStatus.OFFLINE,
                device_memory_headroom=DeviceMemoryHeadroom.NOMINAL
            )

        # Retrieve stored profile
        stored_user = self.db.get_user(user_id) or {}
        stored_age = stored_user.get("age_band", "adult")
        stored_tier = stored_user.get("fitness_tier", "intermediate")
        stored_dur = stored_user.get("target_duration_min", 15)
        stored_flags = set(stored_user.get("orthopedic_flags", []))
        stored_equip = set(stored_user.get("available_equipment", ["bodyweight"]))

        text_lower = user_input.lower()

        # 1. Sense Age Band
        detected_age = stored_age
        if any(w in text_lower for w in ["senior", "elderly", "65+", "70 year", "retired", "grandparent"]):
            detected_age = AgeBand.SENIOR.value
        elif any(w in text_lower for w in ["teen", "youth", "child", "under 18", "adolescent"]):
            detected_age = AgeBand.YOUTH.value
        elif any(w in text_lower for w in ["college", "young adult", "in my 20s", "twenties"]):
            detected_age = AgeBand.YOUNG_ADULT.value
        elif any(w in text_lower for w in ["adult", "in my 30s", "in my 40s", "in my 50s", "middle aged"]):
            detected_age = AgeBand.ADULT.value

        # 2. Sense Fitness Tier
        detected_tier = stored_tier
        if any(w in text_lower for w in ["sedentary", "desk job", "couch", "never worked out", "inactive"]):
            detected_tier = FitnessTier.SEDENTARY.value
        elif any(w in text_lower for w in ["beginner", "just starting", "new to exercise", "novice"]):
            detected_tier = FitnessTier.BEGINNER.value
        elif any(w in text_lower for w in ["intermediate", "moderate", "work out regularly", "few times a week"]):
            detected_tier = FitnessTier.INTERMEDIATE.value
        elif any(w in text_lower for w in ["advanced", "athlete", "competitive", "crossfit", "marathon"]):
            detected_tier = FitnessTier.ADVANCED.value

        # 3. Sense Target Duration
        detected_dur = stored_dur
        dur_match = re.search(r"(\d+)\s*(?:min|minute|minutes)", text_lower)
        if dur_match:
            try:
                detected_dur = int(dur_match.group(1))
            except ValueError:
                pass

        # 4. Sense Orthopedic Flags
        if any(w in text_lower for w in ["knee pain", "bad knee", "patellar", "tendonitis in knee", "knee stiffness", "hurts my knees"]):
            stored_flags.add("knee_pain")
        if any(w in text_lower for w in ["lumbar", "lower back", "back stiffness", "back pain", "spine pain", "stiff back"]):
            stored_flags.add("lumbar_stiffness")
        if any(w in text_lower for w in ["shoulder impingement", "shoulder pain", "rotator cuff", "sore shoulder"]):
            stored_flags.add("shoulder_impingement")
        if any(w in text_lower for w in ["wrist pain", "weak wrists", "carpal tunnel"]):
            stored_flags.add("wrist_instability")

        # 5. Sense Available Equipment
        if any(w in text_lower for w in ["dumbbells", "weights", "free weights"]):
            stored_equip.add("dumbbells")
        if any(w in text_lower for w in ["band", "resistance band", "elastic band"]):
            stored_equip.add("resistance_band")
        if any(w in text_lower for w in ["barbell", "bench"]):
            stored_equip.add("barbell")
        if any(w in text_lower for w in ["kettlebell"]):
            stored_equip.add("kettlebell")
        if any(w in text_lower for w in ["mat", "yoga mat"]):
            stored_equip.add("mat")
        if any(w in text_lower for w in ["chair"]):
            stored_equip.add("chair")
        if any(w in text_lower for w in ["no equipment", "bodyweight only"]):
            stored_equip = {"bodyweight"}

        # Identify missing fields for conversational clarification if necessary
        missing_fields = []
        if not stored_user.get("fitness_tier") and detected_tier == "beginner":
            # Just an indicator if user hasn't specified
            pass

        sensed = SensedDemographics(
            age_band=detected_age,
            fitness_tier=detected_tier,
            target_duration_min=detected_dur,
            orthopedic_flags=sorted(list(stored_flags)),
            available_equipment=sorted(list(stored_equip)),
            missing_fields=missing_fields
        )

        return sensed, telemetry, stored_user
