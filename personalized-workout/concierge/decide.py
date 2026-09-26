"""
Step 2: DECIDE (Strategy & Routing Classification)
Routes intent to OFFLINE_RECOMMENDATION, OFFLINE_RESOURCE_CURATION, or ONLINE_LIVE_TOOL_HANDOFF.
Enforces Acute Red Flag tripwires (Instant Stop) with immediate medical triage lockdown.
"""

import re
from typing import Dict, Optional, Tuple
from concierge.models import RoutingDecision, SensedDemographics, SessionStatus, Telemetry


ACUTE_RED_FLAGS = [
    (r"\b(?:radiating\s+)?chest\s+pain\b", "Chest pain or radiating thoracic discomfort"),
    (r"\b(?:dizzy|dizziness|lightheaded|lightheadedness|fainting|vertigo|blacking out)\b", "Dizziness or near-syncope"),
    (r"\b(?:shortness\s+of\s+breath|difficulty\s+breathing|breathless|dyspnea)\b", "Acute shortness of breath"),
    (r"\b(?:sudden\s+numbness|tingling\s+in\s+arm|numb\s+arm|loss\s+of\s+sensation)\b", "Sudden numbness or neurological deficit"),
    (r"\b(?:surgery|operation|post-op|post-operative)\b.*?\b(?:[1-6]\s*weeks?|recent)\b", "Post-operative recovery under 6 weeks"),
    (r"\b(?:recent\s+surgery|just\s+had\s+surgery)\b", "Recent surgery within acute healing phase")
]

ONLINE_LIVE_KEYWORDS = [
    "live", "real-time", "real time", "camera", "form tracking", "cadence",
    "sensor", "rep count", "rep counting", "track my heart rate", "heart rate zones",
    "coach me in real time", "check my squat form live", "live form", "watch my form"
]

RESOURCE_KEYWORDS = [
    "guide", "reference", "how to do", "proper form", "stretching protocol",
    "decompression", "educational", "read", "anatomy", "posture alignment",
    "tutorial", "show me form"
]


class Decider:
    def check_acute_red_flags(self, user_input: str) -> Optional[Tuple[str, str]]:
        """
        Scans input for acute clinical contraindications requiring immediate halt.
        Returns (flag_description, matching_snippet) if detected.
        """
        text_lower = user_input.lower()
        for pattern, desc in ACUTE_RED_FLAGS:
            match = re.search(pattern, text_lower)
            if match:
                return desc, match.group(0)
        return None

    def decide_routing(
        self,
        user_input: str,
        sensed: SensedDemographics,
        telemetry: Telemetry
    ) -> Tuple[RoutingDecision, Dict[str, str]]:
        """
        Classifies intent into one of the three runtime branches.
        """
        text_lower = user_input.lower()
        notes = {}

        # 1. Check for Live Tool intent
        is_live_request = any(k in text_lower for k in ONLINE_LIVE_KEYWORDS)
        if is_live_request:
            notes["intent_detected"] = "User explicitly requested live, camera, or sensor real-time coaching."
            return RoutingDecision.ONLINE_LIVE_TOOL_HANDOFF, notes

        # 2. Check for Resource Curation intent
        is_resource_request = any(k in text_lower for k in RESOURCE_KEYWORDS)
        if is_resource_request and not any(w in text_lower for w in ["routine", "workout plan", "give me a routine"]):
            notes["intent_detected"] = "User requested educational resource, form reference, or decompression guide."
            return RoutingDecision.OFFLINE_RESOURCE_CURATION, notes

        # 3. Default to Offline Recommendation (Safe Routine / Plan)
        notes["intent_detected"] = "User seeks safe, offline routine or restorative movements matching physical profile."
        return RoutingDecision.OFFLINE_RECOMMENDATION, notes
