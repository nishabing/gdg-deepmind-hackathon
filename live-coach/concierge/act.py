"""
Step 3: ACT (Local Function Call & Resource Assembly)
Executes deterministic local SQLite tool calls. No hallucinated exercises or medical claims.
Tools:
- query_local_routines(target_focus, intensity_tier, excluded_tags)
- get_local_resource_guides(movement_id)
- queue_live_tool_session(payload)
"""

from typing import Any, Dict, List, Optional
from concierge.models import Action, RoutingDecision, SensedDemographics, Telemetry
from database.db_manager import DBManager


class Actor:
    def __init__(self, db: DBManager):
        self.db = db

    def prepare_and_execute_action(
        self,
        routing_decision: RoutingDecision,
        sensed: SensedDemographics,
        telemetry: Telemetry,
        user_input: str,
        user_id: str = "default_user",
        extra_exclusions: Optional[List[str]] = None
    ) -> Action:
        """
        Derives tool call parameters deterministically from sensed demographics and executes
        the local function against SQLite.
        """
        extra_exclusions = extra_exclusions or []

        # Branch 1: ONLINE_LIVE_TOOL_HANDOFF
        if routing_decision == RoutingDecision.ONLINE_LIVE_TOOL_HANDOFF:
            payload = {
                "user_id": user_id,
                "sensed_demographics": sensed.model_dump(),
                "telemetry": telemetry.model_dump(),
                "requested_intent": user_input,
                "recommended_focus": "squat_form_tracking" if "squat" in user_input.lower() else "cadence_and_sensor_sync"
            }
            tool_call = "queue_live_tool_session"
            parameters = {"payload": payload}
            tool_result = self.db.queue_live_tool_session(user_id=user_id, payload=payload)
            return Action(
                tool_call=tool_call,
                parameters=parameters,
                tool_result=tool_result
            )

        # Branch 2: OFFLINE_RESOURCE_CURATION
        if routing_decision == RoutingDecision.OFFLINE_RESOURCE_CURATION:
            movement_id = "squat"
            text_lower = user_input.lower()
            if "back" in text_lower or "lumbar" in text_lower or "decompression" in text_lower:
                movement_id = "lumbar_decompression"
            elif "knee" in text_lower or "patellar" in text_lower:
                movement_id = "knee_mobility"
            elif "shoulder" in text_lower or "rotator" in text_lower:
                movement_id = "shoulder_protection"
            elif "thoracic" in text_lower or "posture" in text_lower:
                movement_id = "thoracic_release"

            tool_call = "get_local_resource_guides"
            parameters = {"movement_id": movement_id}
            tool_result = self.db.get_local_resource_guides(movement_id_or_keyword=movement_id)
            return Action(
                tool_call=tool_call,
                parameters=parameters,
                tool_result=tool_result
            )

        # Branch 3: OFFLINE_RECOMMENDATION
        # Derive focus from input & orthopedic flags
        focus = "posterior_chain_mobility"
        text_lower = user_input.lower()
        if "knee" in sensed.orthopedic_flags or "knee" in text_lower:
            focus = "knee_rehab"
        elif "shoulder" in sensed.orthopedic_flags or "shoulder" in text_lower:
            focus = "upper_body_mobility"
        elif "hiit" in text_lower or "cardio" in text_lower:
            focus = "cardio_anaerobic"
        elif sensed.age_band == "senior":
            focus = "posterior_chain_mobility"

        # Determine intensity tier
        intensity_tier = "low"
        if sensed.fitness_tier in ["intermediate", "advanced"] and sensed.age_band != "senior":
            if "hiit" in text_lower or "cardio" in text_lower:
                intensity_tier = "high"
            elif "moderate" in text_lower:
                intensity_tier = "moderate"
            else:
                intensity_tier = "low"

        # Build baseline excluded tags
        exclude_tags = set(extra_exclusions)
        if "knee_pain" in sensed.orthopedic_flags:
            exclude_tags.update(["deep_flexion", "high_impact"])
        if "lumbar_stiffness" in sensed.orthopedic_flags:
            exclude_tags.update(["axial_loading", "heavy_spinal_flexion"])
        if "shoulder_impingement" in sensed.orthopedic_flags:
            exclude_tags.update(["overhead_pressing"])
        if sensed.age_band == "senior":
            exclude_tags.update(["anaerobic_circuit", "high_intensity"])

        tool_call = "query_local_routines"
        parameters = {
            "focus": focus,
            "intensity_tier": intensity_tier,
            "exclude_tags": sorted(list(exclude_tags))
        }

        tool_result = self.db.query_local_routines(
            focus=focus,
            intensity_tier=intensity_tier,
            exclude_tags=parameters["exclude_tags"]
        )

        # Fallback query if no routine matched strict criteria
        if not tool_result:
            tool_result = self.db.query_local_routines(
                focus="posterior_chain_mobility",
                intensity_tier="low",
                exclude_tags=parameters["exclude_tags"]
            )
            parameters["fallback_applied"] = True

        return Action(
            tool_call=tool_call,
            parameters=parameters,
            tool_result=tool_result
        )
