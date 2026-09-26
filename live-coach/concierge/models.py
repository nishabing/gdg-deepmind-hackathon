"""
Data models and schemas for the SDAC runtime loop.
Strictly adheres to the Gemma 4 Edge Agent Output Schema.
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class AgeBand(str, Enum):
    YOUTH = "youth"
    YOUNG_ADULT = "young_adult"
    ADULT = "adult"
    SENIOR = "senior"


class FitnessTier(str, Enum):
    SEDENTARY = "sedentary"
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class NetworkStatus(str, Enum):
    OFFLINE = "OFFLINE"
    ONLINE = "ONLINE"
    UNSTABLE = "UNSTABLE"


class DeviceMemoryHeadroom(str, Enum):
    NOMINAL = "NOMINAL"
    CONSTRAINED = "CONSTRAINED"


class RoutingDecision(str, Enum):
    OFFLINE_RECOMMENDATION = "OFFLINE_RECOMMENDATION"
    OFFLINE_RESOURCE_CURATION = "OFFLINE_RESOURCE_CURATION"
    ONLINE_LIVE_TOOL_HANDOFF = "ONLINE_LIVE_TOOL_HANDOFF"


class SessionStatus(str, Enum):
    IDLE = "IDLE"
    READY = "READY"
    STATUS_LOCKED_MEDICAL = "STATUS_LOCKED_MEDICAL"
    STATUS_ESCALATED_HUMAN_REVIEW = "STATUS_ESCALATED_HUMAN_REVIEW"
    QUEUED_FOR_ONLINE = "QUEUED_FOR_ONLINE"


class Telemetry(BaseModel):
    network_status: NetworkStatus = NetworkStatus.OFFLINE
    device_memory_headroom: DeviceMemoryHeadroom = DeviceMemoryHeadroom.NOMINAL


class SensedDemographics(BaseModel):
    age_band: str = "adult"
    fitness_tier: str = "beginner"
    target_duration_min: int = 15
    orthopedic_flags: List[str] = Field(default_factory=list)
    available_equipment: List[str] = Field(default_factory=lambda: ["bodyweight"])
    missing_fields: List[str] = Field(default_factory=list)


class ThoughtProcess(BaseModel):
    sensed_demographics: SensedDemographics
    routing_decision: str
    safety_audit_passed: bool = True
    recovery_attempts: int = 0
    audit_notes: Optional[str] = None


class Action(BaseModel):
    tool_call: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    tool_result: Optional[Any] = None


class LocalStateUpdate(BaseModel):
    session_status: str = "READY"
    live_tool_intent_cached: bool = False
    updated_demographics: Optional[Dict[str, Any]] = None


class AttachedResource(BaseModel):
    id: str
    title: str
    offline_path: str


class LiveToolCTA(BaseModel):
    available: bool = False
    notice: str = ""
    handoff_token: Optional[str] = None


class UserResponse(BaseModel):
    message: str
    attached_resources: List[AttachedResource] = Field(default_factory=list)
    live_tool_cta: LiveToolCTA


class SDACOutput(BaseModel):
    thought_process: ThoughtProcess
    action: Action
    local_state_update: LocalStateUpdate
    user_response: UserResponse
