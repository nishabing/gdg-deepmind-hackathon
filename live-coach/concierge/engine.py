"""
The SDAC Runtime Loop Engine for Offline Personal Fitness Concierge (Gemma 4 Edge Agent).
Orchestrates: SENSE -> DECIDE -> ACT -> CHECK with deterministic retry recovery and SQLite state persistence.
"""

import json
from typing import Any, Dict, List, Optional
from concierge.models import (
    Action,
    AttachedResource,
    LiveToolCTA,
    LocalStateUpdate,
    NetworkStatus,
    RoutingDecision,
    SDACOutput,
    SensedDemographics,
    SessionStatus,
    Telemetry,
    ThoughtProcess,
    UserResponse
)
from concierge.sense import Sensor
from concierge.decide import Decider
from concierge.act import Actor
from concierge.check import Checker, AuditResult
from database.db_manager import DBManager


class SDACEngine:
    def __init__(self, db: Optional[DBManager] = None):
        self.db = db or DBManager()
        self.sensor = Sensor(self.db)
        self.decider = Decider()
        self.actor = Actor(self.db)
        self.checker = Checker()

    def run_sdac_cycle(
        self,
        user_input: str,
        telemetry: Optional[Telemetry] = None,
        user_id: str = "default_user",
        session_id: str = "default_sess"
    ) -> SDACOutput:
        """
        Executes one full Sense-Decide-Act-Check (SDAC) cycle.
        """
        # ==========================================
        # STEP 1: SENSE (Input & Context Ingestion)
        # ==========================================
        sensed, telemetry, stored_user = self.sensor.sense(
            user_input=user_input,
            telemetry=telemetry,
            user_id=user_id
        )

        medical_clearance_flags = stored_user.get("medical_clearance_flags", [])

        # ==========================================
        # STEP 2: DECIDE (Strategy & Boundary Checks)
        # ==========================================
        # A. Instant Stop: Acute Red Flags Tripwire
        red_flag = self.decider.check_acute_red_flags(user_input)
        if red_flag:
            flag_desc, snippet = red_flag
            # Halt routine generation immediately. Commit state as STATUS_LOCKED_MEDICAL.
            self.db.upsert_user(
                user_id=user_id,
                session_status=SessionStatus.STATUS_LOCKED_MEDICAL.value
            )

            thought = ThoughtProcess(
                sensed_demographics=sensed,
                routing_decision="ACUTE_MEDICAL_EMERGENCY_HALT",
                safety_audit_passed=False,
                recovery_attempts=0,
                audit_notes=f"CRITICAL RED FLAG DETECTED: {flag_desc} ('{snippet}'). Instant triage halt triggered."
            )

            action = Action(
                tool_call="emergency_halt_protocol",
                parameters={"contraindication": flag_desc, "trigger": snippet},
                tool_result={"status": "HALTED", "reason": flag_desc}
            )

            local_state = LocalStateUpdate(
                session_status=SessionStatus.STATUS_LOCKED_MEDICAL.value,
                live_tool_intent_cached=False
            )

            emergency_message = (
                "🚨 **CLINICAL EMERGENCY TRIAGE PROTOCOL INITIATED**\n\n"
                f"**Immediate Safety Halt Triggered:** {flag_desc}.\n\n"
                "All routine generation and exercise recommendations have been immediately halted and locked (`STATUS_LOCKED_MEDICAL`).\n\n"
                "**Standard Offline Clinical Disclaimer & Action Protocol:**\n"
                "1. **Discontinue all physical exertion immediately.** Sit or recline in a comfortable, supported position.\n"
                "2. If experiencing acute chest discomfort, radiating pain, sudden numbness, or severe shortness of breath, "
                "**call local emergency medical services (911 / 112 or your regional emergency line) or have someone transport you to the nearest emergency department immediately.**\n"
                "3. Do not resume exercise until you have obtained formal in-person clinical clearance from a licensed medical physician."
            )

            user_resp = UserResponse(
                message=emergency_message,
                attached_resources=[],
                live_tool_cta=LiveToolCTA(
                    available=False,
                    notice="Live tool unavailable: System locked under emergency medical triage protocol."
                )
            )

            output = SDACOutput(
                thought_process=thought,
                action=action,
                local_state_update=local_state,
                user_response=user_resp
            )

            # Record audit log
            self.db.record_audit_log(
                session_id=session_id,
                user_id=user_id,
                input_text=user_input,
                network_status=telemetry.network_status.value,
                memory_headroom=telemetry.device_memory_headroom.value,
                sensed_demographics=sensed.model_dump(),
                routing_decision=thought.routing_decision,
                action_tool_call=action.tool_call,
                action_parameters=action.parameters,
                audit_passed=False,
                audit_failure_reasons=[f"Acute red flag: {flag_desc}"],
                recovery_attempts=0,
                final_state=SessionStatus.STATUS_LOCKED_MEDICAL.value,
                output_payload=output.model_dump()
            )

            return output

        # Intent Routing Decision
        routing_decision, decision_notes = self.decider.decide_routing(
            user_input=user_input,
            sensed=sensed,
            telemetry=telemetry
        )

        # ========================================================
        # STEP 3 & 4: ACT & CHECK with Deterministic Recovery Loop
        # ========================================================
        retry_budget = 2
        recovery_attempts = 0
        extra_exclusions: List[str] = []
        action: Optional[Action] = None
        audit_result: Optional[AuditResult] = None
        audit_history: List[str] = []

        while True:
            # STEP 3: ACT (Local Function Call & Resource Assembly)
            action = self.actor.prepare_and_execute_action(
                routing_decision=routing_decision,
                sensed=sensed,
                telemetry=telemetry,
                user_input=user_input,
                user_id=user_id,
                extra_exclusions=extra_exclusions
            )

            # STEP 4: CHECK (Deterministic Audit)
            audit_result = self.checker.audit(
                routing_decision=routing_decision,
                action=action,
                sensed=sensed,
                telemetry=telemetry,
                medical_clearance_flags=medical_clearance_flags
            )

            if audit_result.passed:
                break

            # Recovery Action: check failed
            audit_history.extend(audit_result.failure_reasons)
            if retry_budget > 0:
                retry_budget -= 1
                recovery_attempts += 1
                # Learn new exclusion tags from audit failure to feed into next ACT attempt
                for exc in audit_result.suggested_exclusions:
                    if exc not in extra_exclusions:
                        extra_exclusions.append(exc)
            else:
                # Retry budget exhausted -> Trigger Human Handoff
                break

        # Check final status
        safety_passed = audit_result.passed if audit_result else False

        if not safety_passed:
            # Human Handoff Escalation
            session_status = SessionStatus.STATUS_ESCALATED_HUMAN_REVIEW.value
            self.db.upsert_user(
                user_id=user_id,
                age_band=sensed.age_band,
                fitness_tier=sensed.fitness_tier,
                target_duration_min=sensed.target_duration_min,
                orthopedic_flags=sensed.orthopedic_flags,
                available_equipment=sensed.available_equipment,
                session_status=session_status
            )

            thought = ThoughtProcess(
                sensed_demographics=sensed,
                routing_decision=routing_decision.value,
                safety_audit_passed=False,
                recovery_attempts=recovery_attempts,
                audit_notes=f"Audit failed after {recovery_attempts} retries: {'; '.join(audit_history)}. Escalated to Human Review."
            )

            user_resp = UserResponse(
                message=(
                    "⚠️ **SAFETY AUDIT ESCALATION - HUMAN HANDOFF REQUIRED**\n\n"
                    "Our deterministic safety audit detected movement constraints or contraindications "
                    "that could not be safely resolved by on-device automated routines without specialized clinical oversight.\n\n"
                    f"**Audit Findings:**\n- " + "\n- ".join(set(audit_history)) + "\n\n"
                    "Your session status has been updated to `STATUS_ESCALATED_HUMAN_REVIEW`. "
                    "Please consult a certified physiotherapist or exercise specialist for customized clearance."
                ),
                attached_resources=[],
                live_tool_cta=LiveToolCTA(
                    available=False,
                    notice="Automated sessions paused pending clinical human review."
                )
            )

            output = SDACOutput(
                thought_process=thought,
                action=action, # type: ignore
                local_state_update=LocalStateUpdate(
                    session_status=session_status,
                    live_tool_intent_cached=False,
                    updated_demographics=sensed.model_dump()
                ),
                user_response=user_resp
            )

            self.db.record_audit_log(
                session_id=session_id,
                user_id=user_id,
                input_text=user_input,
                network_status=telemetry.network_status.value,
                memory_headroom=telemetry.device_memory_headroom.value,
                sensed_demographics=sensed.model_dump(),
                routing_decision=routing_decision.value,
                action_tool_call=action.tool_call, # type: ignore
                action_parameters=action.parameters, # type: ignore
                audit_passed=False,
                audit_failure_reasons=audit_history,
                recovery_attempts=recovery_attempts,
                final_state=session_status,
                output_payload=output.model_dump()
            )
            return output

        # Build successful response based on routing decision
        session_status = SessionStatus.READY.value
        live_tool_intent_cached = False
        attached_resources: List[AttachedResource] = []

        if routing_decision == RoutingDecision.ONLINE_LIVE_TOOL_HANDOFF:
            if telemetry.network_status == NetworkStatus.OFFLINE:
                session_status = SessionStatus.QUEUED_FOR_ONLINE.value
                live_tool_intent_cached = True

                # Static alignment cues & offline guide fallback
                guides = self.db.get_local_resource_guides("squat")
                if guides:
                    g = guides[0]
                    attached_resources.append(AttachedResource(
                        id=g["id"],
                        title=g["title"],
                        offline_path=g["offline_path"]
                    ))

                message = (
                    "I've saved your custom mobility plan offline. Real-time form analysis and live rep feedback "
                    "require our Live Workout Companion. Connect to the internet to launch your queued session.\n\n"
                    "In the meantime, I have attached our offline **Static Squat Form Alignment Guide** to review essential tripod foot balance and joint stacking."
                )

                live_cta = LiveToolCTA(
                    available=False,
                    notice="Real-time posture and sensor tracking available via Live Workout Tool once online."
                )
            else:
                # Online mode: emit deep-link execution token
                tool_res = action.tool_result or {} # type: ignore
                token = tool_res.get("handoff_token", "livetool://handoff?token=ready")
                message = (
                    "Your physical profile and movement targets have been packaged for the Live Workout Companion. "
                    "Launching real-time camera tracking and sensor sync now."
                )
                live_cta = LiveToolCTA(
                    available=True,
                    notice="Live Workout Companion ready for camera tracking and sensor sync.",
                    handoff_token=token
                )

        elif routing_decision == RoutingDecision.OFFLINE_RESOURCE_CURATION:
            guides = action.tool_result or [] # type: ignore
            if guides:
                for g in guides[:2]:
                    attached_resources.append(AttachedResource(
                        id=g["id"],
                        title=g["title"],
                        offline_path=g["offline_path"]
                    ))
                g_titles = ", ".join(f"**{g.title}**" for g in attached_resources)
                message = (
                    f"Here is your curated offline resource: {g_titles}. "
                    "These reference guides are stored locally on your device for immediate, zero-latency access."
                )
            else:
                message = "I've reviewed your request and curated our offline biomechanics references for safe movement execution."

            live_cta = LiveToolCTA(
                available=False,
                notice="Real-time posture and sensor tracking available via Live Workout Tool once online."
            )

        else: # OFFLINE_RECOMMENDATION
            routines = action.tool_result or [] # type: ignore
            if routines:
                chosen_routine = routines[0]
                exercises = chosen_routine.get("exercises", [])
                ex_text_list = []
                for idx, ex in enumerate(exercises, 1):
                    ex_text_list.append(f"{idx}. **{ex['name']}** — {ex['default_reps_or_time']}\n   *{ex['description']}*")
                ex_block = "\n".join(ex_text_list)

                # Attach related guide if available
                focus = chosen_routine.get("focus", "")
                if "knee" in focus or "knee_pain" in sensed.orthopedic_flags:
                    knee_guides = self.db.get_local_resource_guides("knee")
                    if knee_guides:
                        attached_resources.append(AttachedResource(
                            id=knee_guides[0]["id"],
                            title=knee_guides[0]["title"],
                            offline_path=knee_guides[0]["offline_path"]
                        ))
                else:
                    lumbar_guides = self.db.get_local_resource_guides("lumbar")
                    if lumbar_guides:
                        attached_resources.append(AttachedResource(
                            id=lumbar_guides[0]["id"],
                            title=lumbar_guides[0]["title"],
                            offline_path=lumbar_guides[0]["offline_path"]
                        ))

                message = (
                    f"### 📋 {chosen_routine['title']}\n"
                    f"**Focus:** `{chosen_routine['focus']}` | **Intensity:** `{chosen_routine['intensity_tier']}` | **Duration:** `{chosen_routine['duration_min']} min`\n\n"
                    f"{chosen_routine['description']}\n\n"
                    f"**Recommended Exercises:**\n{ex_block}\n\n"
                    f"💡 *Safety Note:* {chosen_routine.get('disclaimer', 'Move within a pain-free range of motion.')}"
                )
            else:
                message = "A safe restorative movement routine has been prepared offline according to your physical readiness profile."

            live_cta = LiveToolCTA(
                available=False,
                notice="Real-time posture and sensor tracking available via Live Workout Tool once online."
            )

        # Update user profile and state in SQLite
        self.db.upsert_user(
            user_id=user_id,
            age_band=sensed.age_band,
            fitness_tier=sensed.fitness_tier,
            target_duration_min=sensed.target_duration_min,
            orthopedic_flags=sensed.orthopedic_flags,
            available_equipment=sensed.available_equipment,
            session_status=session_status,
            live_tool_intent_cached=live_tool_intent_cached
        )

        thought = ThoughtProcess(
            sensed_demographics=sensed,
            routing_decision=routing_decision.value,
            safety_audit_passed=True,
            recovery_attempts=recovery_attempts,
            audit_notes="Deterministic safety audit passed. All contraindication tripwires cleared."
        )

        local_state = LocalStateUpdate(
            session_status=session_status,
            live_tool_intent_cached=live_tool_intent_cached,
            updated_demographics=sensed.model_dump()
        )

        user_resp = UserResponse(
            message=message,
            attached_resources=attached_resources,
            live_tool_cta=live_cta
        )

        output = SDACOutput(
            thought_process=thought,
            action=action, # type: ignore
            local_state_update=local_state,
            user_response=user_resp
        )

        # Log audit entry in SQLite
        self.db.record_audit_log(
            session_id=session_id,
            user_id=user_id,
            input_text=user_input,
            network_status=telemetry.network_status.value,
            memory_headroom=telemetry.device_memory_headroom.value,
            sensed_demographics=sensed.model_dump(),
            routing_decision=routing_decision.value,
            action_tool_call=action.tool_call, # type: ignore
            action_parameters=action.parameters, # type: ignore
            audit_passed=True,
            audit_failure_reasons=[],
            recovery_attempts=recovery_attempts,
            final_state=session_status,
            output_payload=output.model_dump()
        )

        return output
