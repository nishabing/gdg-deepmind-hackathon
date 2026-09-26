-- SQLite Schema for Offline Personal Fitness Concierge & Resource Router

CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    age_band TEXT DEFAULT 'adult',
    fitness_tier TEXT DEFAULT 'beginner',
    target_duration_min INTEGER DEFAULT 15,
    orthopedic_flags TEXT DEFAULT '[]',
    available_equipment TEXT DEFAULT '["bodyweight"]',
    medical_clearance_flags TEXT DEFAULT '[]',
    health_goals TEXT DEFAULT '[]',
    workout_count INTEGER DEFAULT 0,
    current_day INTEGER DEFAULT 0,
    streak_days INTEGER DEFAULT 0,
    healthcare_recommendations TEXT DEFAULT '[]',
    session_status TEXT DEFAULT 'READY',
    live_tool_intent_cached INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS exercises (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    focus TEXT NOT NULL,
    intensity_tier TEXT NOT NULL,
    tags TEXT NOT NULL DEFAULT '[]',
    equipment_required TEXT NOT NULL DEFAULT '["bodyweight"]',
    default_reps_or_time TEXT NOT NULL,
    description TEXT
);

CREATE TABLE IF NOT EXISTS routines (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    focus TEXT NOT NULL,
    intensity_tier TEXT NOT NULL,
    duration_min INTEGER NOT NULL,
    tags TEXT NOT NULL DEFAULT '[]',
    exercise_ids TEXT NOT NULL DEFAULT '[]',
    description TEXT,
    disclaimer TEXT
);

CREATE TABLE IF NOT EXISTS resource_guides (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    movement_id TEXT NOT NULL,
    offline_path TEXT NOT NULL,
    summary TEXT,
    tags TEXT NOT NULL DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS live_tool_queue (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    queued_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT NOT NULL DEFAULT 'QUEUED',
    payload TEXT NOT NULL,
    handoff_token TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS workout_logs (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    routine_id TEXT,
    routine_title TEXT NOT NULL,
    day_number INTEGER NOT NULL,
    duration_min INTEGER NOT NULL,
    reps_completed INTEGER DEFAULT 0,
    notes TEXT,
    completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sdac_audit_logs (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    input_text TEXT,
    network_status TEXT,
    memory_headroom TEXT,
    sensed_demographics TEXT,
    routing_decision TEXT,
    action_tool_call TEXT,
    action_parameters TEXT,
    audit_passed INTEGER,
    audit_failure_reasons TEXT,
    recovery_attempts INTEGER,
    final_state TEXT,
    output_payload TEXT
);
