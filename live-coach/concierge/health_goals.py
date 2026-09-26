"""
Health Goals & Healthcare Recommendations Engine.
Processes user goals (via voice speech-to-text or typed input), synthesizes structured
Health Goals, generates clinical Healthcare Recommendations, and curates recommended routines.
"""

import re
from typing import Any, Dict, List, Optional
from database.db_manager import DBManager


class HealthGoalsManager:
    def __init__(self, db: Optional[DBManager] = None):
        self.db = db or DBManager()

    def process_and_update_goals(
        self,
        raw_goals_input: str,
        user_id: str = "default_user"
    ) -> Dict[str, Any]:
        """
        Takes raw spoken or typed input, extracts Health Goals, derives clinical
        Healthcare Recommendations, identifies matching routines, and persists them.
        """
        text_lower = raw_goals_input.lower()
        extracted_goals: List[str] = []
        orthopedic_flags: List[str] = []
        healthcare_recs: List[str] = []

        # 1. Pattern analysis for Health Goals
        # Knee health
        if any(w in text_lower for w in ["knee", "patellar", "tendonitis"]):
            extracted_goals.append("Rehabilitate knee joints and strengthen stabilizing quadriceps (VMO)")
            orthopedic_flags.append("knee_pain")
            healthcare_recs.extend([
                "Patellofemoral Protocol: Limit active knee flexion to 60° and eliminate plyometric jumping.",
                "Incorporate terminal knee extensions (TKE) and Spanish squat isometric holds for tendon relief.",
                "Ensure proper footwear with adequate arch support to prevent medial knee collapse (valgus)."
            ])

        # Back / Spine / Lumbar
        if any(w in text_lower for w in ["back", "lumbar", "spine", "stiffness", "sciatica"]):
            extracted_goals.append("Alleviate lower back stiffness and decompress lumbar spine")
            orthopedic_flags.append("lumbar_stiffness")
            healthcare_recs.extend([
                "Lumbar Neutrality: Avoid axial spinal loading (heavy barbell squats) and unassisted end-range flexion.",
                "Perform diaphragmatic breathing in supine 90/90 position daily to reset pelvic tension.",
                "Strengthen gluteus medius and transverse abdominis to provide active muscular lumbar bracing."
            ])

        # Posture / Shoulder
        if any(w in text_lower for w in ["posture", "shoulder", "neck", "desk", "hunched"]):
            extracted_goals.append("Correct desk posture and improve thoracic spine extension")
            if "shoulder" in text_lower:
                orthopedic_flags.append("shoulder_impingement")
            healthcare_recs.extend([
                "Ergonomic Protocol: Take a 60-second thoracic extension break for every 45 minutes of seated work.",
                "Prioritize horizontal pulling and rear deltoid activation over repetitive overhead pressing.",
                "Engage deep neck flexors and retract scapulae to counteract forward head posture."
            ])

        # Senior / Joint Longevity
        if any(w in text_lower for w in ["senior", "balance", "mobility", "longevity", "gentle"]):
            extracted_goals.append("Preserve joint mobility, dynamic balance, and functional independence")
            healthcare_recs.extend([
                "Senior Balance Protocol: Always perform standing balance drills within arm's reach of a wall or sturdy chair.",
                "Avoid rapid postural shifts (orthostatic hypotension precaution) when transitioning from floor to standing.",
                "Maintain low-impact steady state movement to support cardiovascular health without joint strain."
            ])

        # Cardio / Stamina / Endurance
        if any(w in text_lower for w in ["cardio", "stamina", "endurance", "lose weight", "fat loss", "weight loss"]):
            extracted_goals.append("Enhance aerobic endurance, metabolic health, and daily energy levels")
            healthcare_recs.extend([
                "Cardiac Pacing: Maintain a conversational heart rate (Zone 2) for sustainable fat oxidation.",
                "Hydration Guideline: Consume 250-500ml of water 30 minutes prior to aerobic sessions.",
                "Alternate high and low volume training days to promote central nervous system recovery."
            ])

        # Strength / Muscle
        if any(w in text_lower for w in ["strength", "muscle", "tone", "stronger"]):
            extracted_goals.append("Build total-body muscular endurance and joint stability")
            healthcare_recs.extend([
                "Progressive Overload Principle: Emphasize eccentric tempo control (3-second lowering) over sheer speed.",
                "Allow minimum 48 hours recovery between sessions training the same muscular group.",
                "Warm up with non-load-bearing dynamic stretches before applying resistance."
            ])

        # Default fallback if input was generic
        if not extracted_goals:
            extracted_goals.append(f"Achieve personalized fitness goal: '{raw_goals_input.strip()}'")
            healthcare_recs.extend([
                "General Clinical Protocol: Maintain a pain-free range of motion throughout all movements.",
                "Consistent Routine: Prioritize 15 minutes of daily structured movement over sporadic long sessions.",
                "Restorative Sleep: Aim for 7-9 hours of sleep to facilitate muscular tissue regeneration."
            ])

        # Get existing user profile to merge flags
        existing_user = self.db.get_user(user_id) or {}
        existing_flags = set(existing_user.get("orthopedic_flags", []))
        for f in orthopedic_flags:
            existing_flags.add(f)

        # Update in SQLite
        updated_user = self.db.upsert_user(
            user_id=user_id,
            orthopedic_flags=sorted(list(existing_flags)),
            health_goals=extracted_goals,
            healthcare_recommendations=healthcare_recs
        )

        # Use the same goal-, constraint-, and history-aware selector as the profile API.
        recommended_routines = self.db.get_recommended_routines(user_id)

        return {
            "health_goals": extracted_goals,
            "healthcare_recommendations": healthcare_recs,
            "recommended_routines": recommended_routines,
            "orthopedic_flags": sorted(list(existing_flags)),
            "user_profile": updated_user
        }
