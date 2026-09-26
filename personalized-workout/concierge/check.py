"""
Step 4: CHECK (Deterministic Audit & Error Recovery)
Applies strict deterministic Kotlin/Swift-style safety rules.
Evaluates contraindications, age/cardiac gates, and network boundaries before presenting to the user.
Manages retry budget and triggers Human Handoff if recovery is exhausted.
"""

from typing import Any, Dict, List, Optional, Tuple
from concierge.models import Action, NetworkStatus, RoutingDecision, SensedDemographics, Telemetry


class AuditResult:
    def __init__(self, passed: bool, failure_reasons: Optional[List[str]] = None, suggested_exclusions: Optional[List[str]] = None):
        self.passed = passed
        self.failure_reasons = failure_reasons or []
        self.suggested_exclusions = suggested_exclusions or []


class Checker:
    def audit(
        self,
        routing_decision: RoutingDecision,
        action: Action,
        sensed: SensedDemographics,
        telemetry: Telemetry,
        medical_clearance_flags: Optional[List[str]] = None
    ) -> AuditResult:
        """
        Executes deterministic rules against candidate action and database results.
        """
        failures = []
        suggested_exclusions = []
        medical_clearance_flags = medical_clearance_flags or []

        # --- Rule 3 (Online Boundary Gate) ---
        if routing_decision == RoutingDecision.ONLINE_LIVE_TOOL_HANDOFF:
            if telemetry.network_status == NetworkStatus.OFFLINE:
                # The rule requires that when offline, real-time tracking MUST be deferred with a local fallback
                # This is audited to verify action is queued and not attempting immediate live streaming
                if action.tool_call != "queue_live_tool_session":
                    failures.append("Rule 3 Violation: Offline state attempted immediate live connection without queueing.")
                # Online boundary is satisfied when properly queued with offline deferral
            return AuditResult(passed=len(failures) == 0, failure_reasons=failures, suggested_exclusions=suggested_exclusions)

        # Audit for routines returned in action.tool_result
        if action.tool_call == "query_local_routines":
            routines = action.tool_result or []
            if not routines:
                # No routines found is handled via fallback or human escalation
                return AuditResult(passed=False, failure_reasons=["No certified routines match safety filters."], suggested_exclusions=[])

            for routine in routines:
                exercises = routine.get("exercises", [])
                routine_tags = [t.lower() for t in routine.get("tags", [])]

                # --- Rule 1 (Contraindication Tripwire) ---
                # Knee pain: Zero exercises may contain deep_flexion or high_impact
                if "knee_pain" in sensed.orthopedic_flags:
                    for ex in exercises:
                        ex_tags = [t.lower() for t in ex.get("tags", [])]
                        if "deep_flexion" in ex_tags or "high_impact" in ex_tags:
                            failures.append(
                                f"Rule 1 Violation (Knee Pain): Exercise '{ex['name']}' contains forbidden tags: "
                                f"{[t for t in ['deep_flexion', 'high_impact'] if t in ex_tags]}."
                            )
                            suggested_exclusions.extend(["deep_flexion", "high_impact"])

                # Lumbar stiffness: Zero exercises may contain axial_loading or heavy_spinal_flexion
                if "lumbar_stiffness" in sensed.orthopedic_flags:
                    for ex in exercises:
                        ex_tags = [t.lower() for t in ex.get("tags", [])]
                        if "axial_loading" in ex_tags or "heavy_spinal_flexion" in ex_tags:
                            failures.append(
                                f"Rule 1 Violation (Lumbar Stiffness): Exercise '{ex['name']}' contains forbidden tags: "
                                f"{[t for t in ['axial_loading', 'heavy_spinal_flexion'] if t in ex_tags]}."
                            )
                            suggested_exclusions.extend(["axial_loading", "heavy_spinal_flexion"])

                # Shoulder impingement: Zero exercises may contain overhead_pressing
                if "shoulder_impingement" in sensed.orthopedic_flags:
                    for ex in exercises:
                        ex_tags = [t.lower() for t in ex.get("tags", [])]
                        if "overhead_pressing" in ex_tags:
                            failures.append(
                                f"Rule 1 Violation (Shoulder Impingement): Exercise '{ex['name']}' contains overhead_pressing."
                            )
                            suggested_exclusions.append("overhead_pressing")

                # --- Rule 2 (Age & Heart Rate Gate) ---
                # If senior, block high-intensity anaerobic circuits unless clearance flag is logged
                if sensed.age_band == "senior":
                    is_cleared = "anaerobic_cleared" in medical_clearance_flags
                    if not is_cleared:
                        if routine.get("intensity_tier") == "high" or "anaerobic_circuit" in routine_tags:
                            failures.append(
                                f"Rule 2 Violation (Senior Gate): Routine '{routine['title']}' is high-intensity anaerobic without clearance."
                            )
                            suggested_exclusions.extend(["anaerobic_circuit", "high_intensity"])
                        for ex in exercises:
                            ex_tags = [t.lower() for t in ex.get("tags", [])]
                            if "anaerobic_circuit" in ex_tags or ex.get("intensity_tier") == "high":
                                failures.append(
                                    f"Rule 2 Violation (Senior Gate): Exercise '{ex['name']}' is high-intensity anaerobic without clearance."
                                )
                                suggested_exclusions.extend(["anaerobic_circuit", "high_intensity"])

        passed = len(failures) == 0
        return AuditResult(
            passed=passed,
            failure_reasons=failures,
            suggested_exclusions=sorted(list(set(suggested_exclusions)))
        )
