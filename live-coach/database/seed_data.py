"""
Seed data for the On-Device SQLite State Store.
Contains certified exercises, curated offline routines, and resource guide mappings.
"""

EXERCISES = [
    {
        "id": "ex_supine_90_90",
        "name": "Supine 90/90 Diaphragmatic Reset",
        "focus": "posterior_chain_mobility",
        "intensity_tier": "low",
        "tags": ["restorative", "low_impact", "knee_safe", "lumbar_safe", "senior_safe"],
        "equipment_required": ["mat", "chair"],
        "default_reps_or_time": "90 seconds",
        "description": "Decompress lumbar spine with calves supported on elevated surface, nasal diaphragmatic breathing."
    },
    {
        "id": "ex_cat_camel",
        "name": "Quadruped Cat-Camel (Gentle Range)",
        "focus": "posterior_chain_mobility",
        "intensity_tier": "low",
        "tags": ["restorative", "low_impact", "knee_safe", "senior_safe"],
        "equipment_required": ["mat"],
        "default_reps_or_time": "10 smooth cycles",
        "description": "Slow spinal articulation through pain-free flexion and extension on all fours."
    },
    {
        "id": "ex_glute_bridge_iso",
        "name": "Isometric Glute Bridge",
        "focus": "posterior_chain_mobility",
        "intensity_tier": "low",
        "tags": ["low_impact", "knee_safe", "senior_safe", "posterior_chain"],
        "equipment_required": ["mat"],
        "default_reps_or_time": "3 sets x 30s hold",
        "description": "Drive through heels to lift pelvis into hip extension without lumbar hyperextension."
    },
    {
        "id": "ex_tke_band",
        "name": "Terminal Knee Extension (TKE)",
        "focus": "knee_rehab",
        "intensity_tier": "low",
        "tags": ["knee_safe", "low_impact", "senior_safe", "quad_rehab"],
        "equipment_required": ["resistance_band"],
        "default_reps_or_time": "3 sets x 15 reps",
        "description": "Active terminal extension engaging VMO without axial loading or deep joint flexion."
    },
    {
        "id": "ex_spanish_squat_iso",
        "name": "Spanish Squat Isometric Hold (60 deg)",
        "focus": "knee_rehab",
        "intensity_tier": "low",
        "tags": ["knee_safe", "low_impact", "senior_safe", "isometric"],
        "equipment_required": ["wall"],
        "default_reps_or_time": "4 sets x 30s hold",
        "description": "Shallow isometric knee flexion relieving patellar tendon pain."
    },
    {
        "id": "ex_seated_chair_squat",
        "name": "Chair Sit-to-Stand (Controlled)",
        "focus": "knee_rehab",
        "intensity_tier": "low",
        "tags": ["senior_safe", "low_impact", "functional", "knee_safe"],
        "equipment_required": ["chair"],
        "default_reps_or_time": "3 sets x 10 reps",
        "description": "Controlled hip hinge to seated position on a sturdy chair, eliminating uncontrolled deep flexion."
    },
    {
        "id": "ex_bird_dog",
        "name": "Bird Dog Cross-Body Reach",
        "focus": "core_stability",
        "intensity_tier": "low",
        "tags": ["lumbar_safe", "low_impact", "senior_safe", "core"],
        "equipment_required": ["mat"],
        "default_reps_or_time": "3 sets x 8 reps per side",
        "description": "Contralateral arm and leg extension maintaining rigid neutral pelvis and lumbar stability."
    },
    {
        "id": "ex_side_lying_clam",
        "name": "Side-Lying Clamshell",
        "focus": "posterior_chain_mobility",
        "intensity_tier": "low",
        "tags": ["low_impact", "knee_safe", "senior_safe", "hip_abduction"],
        "equipment_required": ["mat"],
        "default_reps_or_time": "3 sets x 12 reps per side",
        "description": "Isolate gluteus medius with knees bent, rotating upper knee upward while keeping ankles together."
    },
    {
        "id": "ex_wall_slides",
        "name": "Wall Scapular Slides",
        "focus": "upper_body_mobility",
        "intensity_tier": "low",
        "tags": ["shoulder_safe", "low_impact", "senior_safe", "posture"],
        "equipment_required": ["wall"],
        "default_reps_or_time": "3 sets x 10 reps",
        "description": "Forearms against wall, sliding upward into shallow 'W' to 'Y' without shrugging traps."
    },
    {
        "id": "ex_banded_face_pull",
        "name": "Banded Face Pull with External Rotation",
        "focus": "upper_body_mobility",
        "intensity_tier": "low",
        "tags": ["shoulder_safe", "low_impact", "posture"],
        "equipment_required": ["resistance_band"],
        "default_reps_or_time": "3 sets x 15 reps",
        "description": "Horizontal pull toward bridge of nose with external rotation, strengthening rear delts and rotator cuff."
    },
    # High impact / Deep flexion / Heavy contraindication exercises for testing & advanced users
    {
        "id": "ex_jump_squats",
        "name": "Plyometric Jump Squats",
        "focus": "cardio_anaerobic",
        "intensity_tier": "high",
        "tags": ["high_impact", "deep_flexion", "anaerobic_circuit"],
        "equipment_required": ["bodyweight"],
        "default_reps_or_time": "4 sets x 45s max reps",
        "description": "Deep squat with explosive vertical leap, landing under eccentric load."
    },
    {
        "id": "ex_burpees",
        "name": "Full Chest-to-Floor Burpees",
        "focus": "cardio_anaerobic",
        "intensity_tier": "high",
        "tags": ["high_impact", "anaerobic_circuit", "deep_flexion"],
        "equipment_required": ["bodyweight"],
        "default_reps_or_time": "5 sets x 10 reps",
        "description": "Rapid drop to floor pushup followed by snap back into maximum vertical jump."
    },
    {
        "id": "ex_barbell_squat",
        "name": "Deep Barbell Back Squat",
        "focus": "full_body_strength",
        "intensity_tier": "high",
        "tags": ["axial_loading", "deep_flexion", "heavy_spinal_flexion"],
        "equipment_required": ["barbell"],
        "default_reps_or_time": "4 sets x 8 reps",
        "description": "Full depth squat with barbell loaded across upper traps."
    },
    {
        "id": "ex_hiit_sprint_intervals",
        "name": "Tabata Sprint Burpee Circuit",
        "focus": "cardio_anaerobic",
        "intensity_tier": "high",
        "tags": ["anaerobic_circuit", "high_intensity", "high_impact"],
        "equipment_required": ["bodyweight"],
        "default_reps_or_time": "8 rounds x 20s work / 10s rest",
        "description": "Maximal heart rate anaerobic circuit targeting VO2 max."
    }
]

ROUTINES = [
    {
        "id": "routine_posterior_chain_mobility",
        "title": "Low-Impact Posterior Chain & Decompression Flow",
        "focus": "posterior_chain_mobility",
        "intensity_tier": "low",
        "duration_min": 10,
        "tags": ["restorative", "knee_safe", "lumbar_safe", "senior_safe", "low_impact"],
        "exercise_ids": ["ex_supine_90_90", "ex_cat_camel", "ex_glute_bridge_iso", "ex_side_lying_clam"],
        "description": "A restorative, zero-axial-loading movement sequence designed to release lumbar stiffness and awaken glutes safely.",
        "disclaimer": "Perform in a slow, controlled manner. If radiating nerve sensations occur, stop immediately."
    },
    {
        "id": "routine_knee_safe_strength",
        "title": "Gentle Knee-Sparing Quadriceps & Hip Routine",
        "focus": "knee_rehab",
        "intensity_tier": "low",
        "duration_min": 15,
        "tags": ["knee_safe", "low_impact", "senior_safe", "quad_rehab"],
        "exercise_ids": ["ex_tke_band", "ex_spanish_squat_iso", "ex_seated_chair_squat", "ex_glute_bridge_iso"],
        "description": "Specifically formulated for individuals with patellar discomfort. Employs isometric holds and eliminates deep flexion.",
        "disclaimer": "Keep knee flexion under 60 degrees. Do not perform plyometrics."
    },
    {
        "id": "routine_senior_vitality",
        "title": "Senior Daily Balance & Joint Health Flow",
        "focus": "posterior_chain_mobility",
        "intensity_tier": "low",
        "duration_min": 15,
        "tags": ["senior_safe", "low_impact", "restorative", "balance"],
        "exercise_ids": ["ex_seated_chair_squat", "ex_bird_dog", "ex_wall_slides", "ex_supine_90_90"],
        "description": "Safe, gentle movements to preserve functional independence, balance, and spine mobility without cardiovascular strain.",
        "disclaimer": "Always keep a chair or wall nearby for balance support."
    },
    {
        "id": "routine_upper_body_mobility",
        "title": "Cervicothoracic & Rotator Cuff Health Sequence",
        "focus": "upper_body_mobility",
        "intensity_tier": "low",
        "duration_min": 12,
        "tags": ["shoulder_safe", "low_impact", "senior_safe", "posture"],
        "exercise_ids": ["ex_wall_slides", "ex_banded_face_pull", "ex_cat_camel"],
        "description": "Releases upper back and shoulder tension while reinforcing scapular stabilizer muscles.",
        "disclaimer": "Discontinue if shoulder pinching occurs."
    },
    {
        "id": "routine_spine_friendly_core",
        "title": "Spine-Friendly Core & Hip Stability",
        "focus": "posterior_chain_mobility",
        "intensity_tier": "low",
        "duration_min": 12,
        "tags": ["restorative", "lumbar_safe", "knee_safe", "low_impact"],
        "exercise_ids": ["ex_supine_90_90", "ex_bird_dog", "ex_glute_bridge_iso"],
        "description": "A supported breathing, trunk-control, and hip-extension sequence with no external load.",
        "disclaimer": "Use a comfortable range and stop if symptoms worsen."
    },
    {
        "id": "routine_gentle_mobility_reset",
        "title": "Gentle Mobility & Recovery Reset",
        "focus": "posterior_chain_mobility",
        "intensity_tier": "low",
        "duration_min": 10,
        "tags": ["restorative", "lumbar_safe", "knee_safe", "low_impact", "senior_safe"],
        "exercise_ids": ["ex_cat_camel", "ex_side_lying_clam", "ex_supine_90_90"],
        "description": "A short floor-based reset combining easy spinal movement, hip activation, and supported breathing.",
        "disclaimer": "Keep each movement pain-free and skip anything uncomfortable."
    },
    {
        "id": "routine_knee_control_foundation",
        "title": "Supported Knee Control & Hip Foundation",
        "focus": "knee_rehab",
        "intensity_tier": "low",
        "duration_min": 12,
        "tags": ["knee_safe", "low_impact", "quad_rehab"],
        "exercise_ids": ["ex_tke_band", "ex_seated_chair_squat", "ex_glute_bridge_iso"],
        "description": "A supported sequence for controlled knee extension, chair transfers, and hip strength.",
        "disclaimer": "Stay within a comfortable range; stop if you feel pain."
    },
    {
        "id": "routine_knee_isometric_reset",
        "title": "Low-Impact Knee Isometric Reset",
        "focus": "knee_rehab",
        "intensity_tier": "low",
        "duration_min": 10,
        "tags": ["knee_safe", "low_impact", "quad_rehab", "isometric"],
        "exercise_ids": ["ex_spanish_squat_iso", "ex_tke_band", "ex_side_lying_clam"],
        "description": "A low-impact option pairing supported isometric work with gentle hip activation.",
        "disclaimer": "Only use the isometric position if it is comfortable and within your clinician's guidance."
    },
    {
        "id": "routine_shoulder_posture_reset",
        "title": "Shoulder-Friendly Posture Reset",
        "focus": "upper_body_mobility",
        "intensity_tier": "low",
        "duration_min": 10,
        "tags": ["shoulder_safe", "low_impact", "posture"],
        "exercise_ids": ["ex_wall_slides", "ex_banded_face_pull", "ex_cat_camel"],
        "description": "A gentle upper-back and shoulder sequence focused on controlled scapular movement.",
        "disclaimer": "Skip any movement that causes pinching or discomfort."
    },
    {
        "id": "routine_hiit_anaerobic_blast",
        "title": "High-Intensity Anaerobic Plyo Circuit",
        "focus": "cardio_anaerobic",
        "intensity_tier": "high",
        "duration_min": 20,
        "tags": ["anaerobic_circuit", "high_intensity", "high_impact", "deep_flexion"],
        "exercise_ids": ["ex_hiit_sprint_intervals", "ex_jump_squats", "ex_burpees"],
        "description": "Maximal exertion circuit designed for experienced athletes with no joint or cardiac restrictions.",
        "disclaimer": "Requires prior medical clearance for high-intensity anaerobic conditioning."
    }
]

RESOURCE_GUIDES = [
    {
        "id": "guide_lumbar_decompression_01",
        "title": "5-Minute Lower Back Decompression Guide",
        "movement_id": "lumbar_decompression",
        "offline_path": "assets/guides/lumbar_decompression.md",
        "summary": "Step-by-step diaphragmatic reset and pelvic unloaded stretches for lower back stiffness.",
        "tags": ["lumbar_stiffness", "decompression", "posterior_chain", "restorative"]
    },
    {
        "id": "guide_squat_form_01",
        "title": "Static Squat Form Alignment & Biomechanical Reference",
        "movement_id": "squat",
        "offline_path": "assets/guides/squat_form_alignment.md",
        "summary": "Offline biomechanics, tripod foot distribution, safe working depth, and hip hinge cues.",
        "tags": ["squat", "form_cues", "alignment", "biomechanics"]
    },
    {
        "id": "guide_knee_sparing_01",
        "title": "Knee-Sparing Lower Body Mobility Protocol",
        "movement_id": "knee_mobility",
        "offline_path": "assets/guides/knee_sparing_mobility.md",
        "summary": "Patellofemoral decompression, TKEs, and Spanish squat isometric holds avoiding deep flexion.",
        "tags": ["knee_pain", "patellar_tendonitis", "low_impact", "rehab"]
    },
    {
        "id": "guide_rotator_cuff_01",
        "title": "Rotator Cuff & Shoulder Protection Guide",
        "movement_id": "shoulder_protection",
        "offline_path": "assets/guides/rotator_cuff_activation.md",
        "summary": "Subacromial space preservation, sidelying external rotation, and prone scapular retractions.",
        "tags": ["shoulder_impingement", "rotator_cuff", "scapular_control"]
    },
    {
        "id": "guide_thoracic_spine_01",
        "title": "Thoracic Spine Release & Posture Alignment Guide",
        "movement_id": "thoracic_release",
        "offline_path": "assets/guides/thoracic_spine_release.md",
        "summary": "Quadruped thread the needle and open book lateral rotations for upper spine stiffness.",
        "tags": ["thoracic_mobility", "posture", "upper_back"]
    }
]
