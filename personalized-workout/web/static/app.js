/**
 * Personalized Fitness - Controller & Voice Health Goals Engine
 * Integrates Profile & Progress Hub, Web Speech API Voice Input,
 * Day-by-Day Progression Timeline, Healthcare Recommendations, and SDAC Loop.
 */

let currentNetworkStatus = "OFFLINE";
let currentMemoryHeadroom = "NOMINAL";
let currentUserId = "default_user";

// Speech Recognition instance
let speechRecognizer = null;
let isRecordingVoice = false;

// DOM Elements
const navTabs = document.querySelectorAll(".nav-tab");
const appViews = document.querySelectorAll(".app-view");
const topProfileBtn = document.getElementById("topProfileBtn");

// Profile & Goals DOM Elements
const micBtn = document.getElementById("micBtn");
const voiceStatusTitle = document.getElementById("voiceStatusTitle");
const voiceStatusSubtitle = document.getElementById("voiceStatusSubtitle");
const goalsInputText = document.getElementById("goalsInputText");
const saveGoalsBtn = document.getElementById("saveGoalsBtn");
const activeGoalsList = document.getElementById("activeGoalsList");
const healthcareRecsList = document.getElementById("healthcareRecsList");
const recommendedRoutinesList = document.getElementById("recommendedRoutinesList");
const completeWorkoutBtn = document.getElementById("completeWorkoutBtn");
const timelineTrack = document.getElementById("timelineTrack");
const totalWorkoutCount = document.getElementById("totalWorkoutCount");
const currentDayDisplay = document.getElementById("currentDayDisplay");
const streakDaysDisplay = document.getElementById("streakDaysDisplay");
const headerProgressBadge = document.getElementById("headerProgressBadge");
const workoutHistoryList = document.getElementById("workoutHistoryList");

// Concierge DOM Elements
const chatForm = document.getElementById("chatForm");
const userInput = document.getElementById("userInput");
const chatMessages = document.getElementById("chatMessages");
const sendBtn = document.getElementById("sendBtn");
const jsonViewer = document.getElementById("jsonViewer");

// Modal DOM Elements
const guideModal = document.getElementById("guideModal");
const modalCloseBtn = document.getElementById("modalCloseBtn");
const modalBackdrop = document.getElementById("modalBackdrop");
const modalTitle = document.getElementById("modalTitle");
const guideMarkdownContent = document.getElementById("guideMarkdownContent");

// Live View Controls
const liveTimerText = document.getElementById("liveTimerText");
const muteBtn = document.getElementById("muteBtn");
const camToggleBtn = document.getElementById("camToggleBtn");
const endWorkoutBtn = document.getElementById("endWorkoutBtn");
let liveTimerInterval = null;
let liveSeconds = 225; // 03:45

document.addEventListener("DOMContentLoaded", () => {
    setupNavigation();
    setupSpeechRecognition();
    setupGoalsAndProgress();
    setupTelemetryToggles();
    setupConcierge();
    setupLiveView();
    setupModal();

    // Initial data load
    loadFullProfile();
});

// ==========================================
// 1. Navigation & Views
// ==========================================
function setupNavigation() {
    navTabs.forEach(tab => {
        tab.addEventListener("click", () => {
            const targetView = tab.dataset.view;
            switchView(targetView);
        });
    });

    if (topProfileBtn) {
        topProfileBtn.addEventListener("click", () => {
            switchView("profile");
        });
    }
}

function switchView(viewName) {
    navTabs.forEach(t => {
        t.classList.toggle("active", t.dataset.view === viewName);
    });
    appViews.forEach(v => {
        v.classList.toggle("active", v.id === `view-${viewName}`);
    });

    if (viewName === "profile") {
        loadFullProfile();
    }
}

// ==========================================
// 2. Voice Input (Web Speech API)
// ==========================================
function setupSpeechRecognition() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

    if (!SpeechRecognition) {
        voiceStatusSubtitle.textContent = "Voice input supported via browser Speech API (Type your goals below)";
        return;
    }

    speechRecognizer = new SpeechRecognition();
    speechRecognizer.continuous = false;
    speechRecognizer.interimResults = true;
    speechRecognizer.lang = "en-US";

    speechRecognizer.onstart = () => {
        isRecordingVoice = true;
        micBtn.classList.add("listening");
        voiceStatusTitle.textContent = "Listening... Speak your health goals now";
        voiceStatusSubtitle.textContent = "Say things like: 'Rehab my knee and fix lower back stiffness with gentle routines'";
    };

    speechRecognizer.onresult = (event) => {
        let transcript = "";
        for (let i = event.resultIndex; i < event.results.length; i++) {
            transcript += event.results[i][0].transcript;
        }
        goalsInputText.value = transcript;
    };

    speechRecognizer.onerror = (event) => {
        console.warn("Speech recognition error:", event.error);
        stopVoiceRecording();
        voiceStatusTitle.textContent = "Voice input paused (tap mic or type)";
    };

    speechRecognizer.onend = () => {
        stopVoiceRecording();
    };

    micBtn.addEventListener("click", () => {
        if (!isRecordingVoice) {
            startVoiceRecording();
        } else {
            stopVoiceRecording();
        }
    });

    // Voice preset chips
    document.querySelectorAll(".voice-preset-btn").forEach(btn => {
        btn.addEventListener("click", () => {
            const goalText = btn.dataset.goal;
            goalsInputText.value = goalText;
            updateHealthGoals(goalText);
        });
    });
}

function startVoiceRecording() {
    if (!speechRecognizer) {
        alert("Speech Recognition not supported in this browser. Please type your goals into the box.");
        return;
    }
    try {
        speechRecognizer.start();
    } catch (e) {
        console.error(e);
    }
}

function stopVoiceRecording() {
    isRecordingVoice = false;
    micBtn.classList.remove("listening");
    voiceStatusTitle.textContent = "Tap microphone to speak goals";
    voiceStatusSubtitle.textContent = "Web Speech API • Real-time on-device voice processing";
    if (speechRecognizer) {
        try { speechRecognizer.stop(); } catch (e) {}
    }
}

// ==========================================
// 3. Profile, Health Goals & Progress Logic
// ==========================================
function setupGoalsAndProgress() {
    saveGoalsBtn.addEventListener("click", () => {
        const text = goalsInputText.value.trim();
        if (!text) {
            alert("Please enter or speak your health goals.");
            return;
        }
        updateHealthGoals(text);
    });

    completeWorkoutBtn.addEventListener("click", async () => {
        try {
            completeWorkoutBtn.disabled = true;
            completeWorkoutBtn.textContent = "Logging session...";

            const resp = await fetch(`/api/profile/${currentUserId}/workout/complete`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    user_id: currentUserId,
                    routine_title: "15-Min Daily Mobility & Joint Health",
                    duration_min: 15,
                    reps: 45,
                    notes: "Day progression target met."
                })
            });

            if (!resp.ok) throw new Error("Failed to complete workout");
            const data = await resp.json();

            // Refresh profile & show feedback
            await loadFullProfile();
            completeWorkoutBtn.textContent = `✓ Day ${data.current_day - 1} Completed!`;
            setTimeout(() => {
                completeWorkoutBtn.disabled = false;
                completeWorkoutBtn.innerHTML = `<span>✓ Log Today's Workout Complete</span>`;
            }, 1800);

        } catch (err) {
            alert("Error logging workout: " + err.message);
            completeWorkoutBtn.disabled = false;
            completeWorkoutBtn.innerHTML = `<span>✓ Log Today's Workout Complete</span>`;
        }
    });
}

async function updateHealthGoals(text) {
    try {
        saveGoalsBtn.disabled = true;
        saveGoalsBtn.textContent = "Updating...";

        const resp = await fetch(`/api/profile/${currentUserId}/goals`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                user_id: currentUserId,
                input_text: text
            })
        });

        if (!resp.ok) throw new Error("Failed to update health goals");
        const data = await resp.json();

        // Render returned data
        renderActiveGoals(data.health_goals);
        renderHealthcareRecommendations(data.healthcare_recommendations);
        renderRecommendedRoutines(data.recommended_routines);
        if (data.progress) {
            renderProgress(data.progress);
        }

        saveGoalsBtn.textContent = "Saved ✓";
        setTimeout(() => {
            saveGoalsBtn.disabled = false;
            saveGoalsBtn.innerHTML = `<span>Update Health Goals</span><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"></polyline></svg>`;
        }, 1200);

    } catch (err) {
        alert("Error updating health goals: " + err.message);
        saveGoalsBtn.disabled = false;
        saveGoalsBtn.textContent = "Update Health Goals";
    }
}

async function loadFullProfile() {
    try {
        const resp = await fetch(`/api/profile/${currentUserId}`);
        if (!resp.ok) throw new Error("Failed to load profile");
        const data = await resp.json();

        const user = data.user;
        const progress = data.progress;

        // Render Badges
        const statusBadge = document.getElementById("statusBadge");
        if (statusBadge) {
            statusBadge.textContent = user.session_status || "READY";
        }

        // Render Progress
        renderProgress(progress);

        // Render Goals
        renderActiveGoals(data.health_goals);

        // Render Healthcare Recs
        renderHealthcareRecommendations(data.healthcare_recommendations);

        // Render Recommended Routines
        renderRecommendedRoutines(data.recommended_routines);

    } catch (err) {
        console.error("Error loading profile:", err);
    }
}

function renderProgress(progress) {
    if (!progress) return;

    totalWorkoutCount.textContent = progress.workout_count || 0;
    currentDayDisplay.textContent = `Day ${progress.current_day || 0}`;
    streakDaysDisplay.textContent = `${progress.streak_days || 0}`;
    headerProgressBadge.textContent = `Day ${progress.current_day || 0} • ${progress.workout_count || 0} Workouts`;

    // Render Timeline matching Mock Image: (Day 0) -> (Day 1) -> (Day 2) -> ...
    const timeline = progress.timeline || [];
    let timelineHtml = "";

    timeline.forEach((step, idx) => {
        const isLast = idx === timeline.length - 1;
        const isCurrent = step.is_current;
        const isCompleted = step.status === "completed";

        timelineHtml += `
            <div class="timeline-step">
                <div class="timeline-node ${isCompleted ? 'completed' : ''} ${isCurrent ? 'active-today' : ''}" title="${step.status}">
                    ${isCompleted ? '✓' : step.day_number}
                </div>
                <span class="timeline-label">${step.label}${isCurrent ? ' (Today)' : ''}</span>
            </div>
        `;

        if (!isLast) {
            timelineHtml += `
                <div class="timeline-arrow ${isCompleted ? 'passed' : ''}">&rarr;</div>
            `;
        }
    });

    timelineTrack.innerHTML = timelineHtml;

    // Render Recent Workout Logs
    const logs = progress.recent_workouts || [];
    if (!logs || logs.length === 0) {
        workoutHistoryList.innerHTML = `<div class="empty-hint">No completed workouts logged yet. Complete today's session above to start tracking!</div>`;
    } else {
        workoutHistoryList.innerHTML = logs.map(l => `
            <div class="history-card">
                <div class="history-card-header">
                    <span style="color:var(--accent-blue)">${escapeHtml(l.routine_title)}</span>
                    <span style="color:var(--accent-green)">Day ${l.day_number}</span>
                </div>
                <div style="color:var(--text-muted); font-size:0.7rem;">
                    ⏱️ ${l.duration_min}m | 🎯 ${l.reps_completed} reps | ${l.completed_at ? l.completed_at.substring(0, 16) : 'Just now'}
                </div>
            </div>
        `).join("");
    }
}

function renderActiveGoals(goals) {
    if (!goals || goals.length === 0) {
        activeGoalsList.innerHTML = `<div class="empty-hint">No health goals logged yet. Speak or type above to set your targets.</div>`;
        return;
    }

    activeGoalsList.innerHTML = goals.map((g, idx) => `
        <div class="goal-card-item">
            <div>
                <strong>Goal ${idx + 1}:</strong> ${escapeHtml(g)}
            </div>
            <span class="goal-card-tag">ACTIVE TRACKING</span>
        </div>
    `).join("");
}

function renderHealthcareRecommendations(recs) {
    if (!recs || recs.length === 0) {
        healthcareRecsList.innerHTML = `<div class="empty-hint">Standard safety rules active. Update your health goals to receive clinical recommendations.</div>`;
        return;
    }

    healthcareRecsList.innerHTML = recs.map(r => `
        <div class="rec-item">
            <div class="rec-icon">🩺</div>
            <div class="rec-content">
                <p>${escapeHtml(r)}</p>
            </div>
        </div>
    `).join("");
}

function renderRecommendedRoutines(routines) {
    if (!routines || routines.length === 0) {
        recommendedRoutinesList.innerHTML = `<div class="empty-hint">Routines will appear here based on your health goals and orthopedic safety clearance.</div>`;
        return;
    }

    recommendedRoutinesList.innerHTML = routines.map(r => `
        <div class="routine-row-card">
            <div class="routine-row-top">
                <div class="routine-row-title">📋 ${escapeHtml(r.title)}</div>
                <button class="mini-btn" onclick="startRoutineDemo('${r.id}', '${escapeHtml(r.title)}')">Start &rarr;</button>
            </div>
            <div style="font-size:0.75rem; color:var(--text-secondary); margin-top:4px;">
                ${escapeHtml(r.description)}
            </div>
            <div class="routine-meta-pills">
                <span class="routine-meta-pill">⏱️ ${r.duration_min} min</span>
                <span class="routine-meta-pill">⚡ ${r.intensity_tier.toUpperCase()}</span>
                <span class="routine-meta-pill">🛡️ ${r.tags.slice(0, 2).join(', ')}</span>
            </div>
        </div>
    `).join("");
}

window.startRoutineDemo = function(routineId, title) {
    switchView("live-workout");
    document.getElementById("liveSubtitlesText").textContent = `Starting ${title}: Engage core, maintain neutral alignment, follow avatar cues.`;
};

// ==========================================
// 4. Concierge & SDAC Engine
// ==========================================
function setupConcierge() {
    // Preset scenarios
    document.querySelectorAll(".scenario-chips .chip-btn").forEach(chip => {
        chip.addEventListener("click", () => {
            const prompt = chip.dataset.prompt;
            userInput.value = prompt;
            submitTurn(prompt);
        });
    });

    chatForm.addEventListener("submit", (e) => {
        e.preventDefault();
        const text = userInput.value.trim();
        if (!text) return;
        userInput.value = "";
        submitTurn(text);
    });

    // Inspector tabs
    document.querySelectorAll(".inspector-tabs .tab-btn").forEach(btn => {
        btn.addEventListener("click", () => {
            const target = btn.dataset.tab;
            document.querySelectorAll(".inspector-tabs .tab-btn").forEach(b => b.classList.remove("active"));
            document.querySelectorAll(".inspector-section .tab-content").forEach(c => c.classList.remove("active"));
            btn.classList.add("active");
            document.getElementById(`tab-${target}`).classList.add("active");
        });
    });
}

async function submitTurn(text) {
    appendUserMessage(text);
    sendBtn.disabled = true;

    try {
        const resp = await fetch("/api/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                message: text,
                network_status: currentNetworkStatus,
                device_memory_headroom: currentMemoryHeadroom,
                user_id: currentUserId,
                session_id: `sess_${Date.now()}`
            })
        });

        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = await resp.json();
        renderBotMessage(data);
        renderPipeline(data);
        jsonViewer.textContent = JSON.stringify(data, null, 2);

        // Refresh profile if user profile was updated
        loadFullProfile();
    } catch (err) {
        appendBotErrorMessage(`Error: ${err.message}`);
    } finally {
        sendBtn.disabled = false;
    }
}

function appendUserMessage(text) {
    const div = document.createElement("div");
    div.className = "msg user";
    div.innerHTML = `<div class="msg-avatar">YOU</div><div class="msg-bubble">${escapeHtml(text)}</div>`;
    chatMessages.appendChild(div);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function appendBotErrorMessage(text) {
    const div = document.createElement("div");
    div.className = "msg bot emergency";
    div.innerHTML = `<div class="msg-avatar">ERR</div><div class="msg-bubble">${escapeHtml(text)}</div>`;
    chatMessages.appendChild(div);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function renderBotMessage(sdac) {
    const ur = sdac.user_response;
    const isEmergency = sdac.thought_process.routing_decision === "ACUTE_MEDICAL_EMERGENCY_HALT";
    const div = document.createElement("div");
    div.className = `msg bot ${isEmergency ? 'emergency' : ''}`;

    let resourceHtml = "";
    if (ur.attached_resources && ur.attached_resources.length > 0) {
        resourceHtml = ur.attached_resources.map(r => `
            <div class="resource-card" onclick="openGuideModal('${r.id}')" style="margin-top:8px; background:var(--bg-secondary); border:1px solid var(--border-color); padding:8px; border-radius:6px; cursor:pointer;">
                <div style="font-weight:700; color:var(--accent-cyan); font-size:0.78rem;">📖 ${escapeHtml(r.title)}</div>
                <div style="font-size:0.68rem; color:var(--text-muted);">${escapeHtml(r.offline_path)}</div>
            </div>
        `).join("");
    }

    div.innerHTML = `
        <div class="msg-avatar">G4</div>
        <div class="msg-bubble">
            <div>${formatMarkdown(ur.message)}</div>
            ${resourceHtml}
        </div>
    `;
    chatMessages.appendChild(div);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function renderPipeline(sdac) {
    const tp = sdac.thought_process;
    const sd = tp.sensed_demographics;
    const act = sdac.action;

    document.getElementById("badge-sense").textContent = "INGESTED";
    document.getElementById("badge-sense").className = "step-badge pass";
    document.getElementById("body-sense").innerHTML = `
        <div><strong>Demographics:</strong> Age=${sd.age_band}, Tier=${sd.fitness_tier}, Duration=${sd.target_duration_min}m</div>
        <div><strong>Orthopedic Flags:</strong> ${sd.orthopedic_flags.join(', ') || 'None'}</div>
    `;

    document.getElementById("badge-decide").textContent = tp.routing_decision;
    document.getElementById("badge-decide").className = "step-badge pass";
    document.getElementById("body-decide").innerHTML = `
        <div><strong>Decision:</strong> ${tp.routing_decision}</div>
        <div style="color:var(--text-muted); font-size:0.7rem;">${tp.audit_notes || ''}</div>
    `;

    document.getElementById("badge-act").textContent = act.tool_call;
    document.getElementById("badge-act").className = "step-badge pass";
    document.getElementById("body-act").innerHTML = `
        <div><strong>Tool:</strong> ${act.tool_call}()</div>
        <div style="font-family:var(--font-mono); font-size:0.68rem;">Params: ${JSON.stringify(act.parameters)}</div>
    `;

    document.getElementById("badge-check").textContent = tp.safety_audit_passed ? "PASSED" : "FAILED";
    document.getElementById("badge-check").className = `step-badge ${tp.safety_audit_passed ? 'pass' : 'fail'}`;
    document.getElementById("body-check").innerHTML = `
        <div><strong>Safety Audit:</strong> ${tp.safety_audit_passed ? 'CLEARED' : 'FAILED'} (Retries: ${tp.recovery_attempts})</div>
        <div><strong>Committed State:</strong> ${sdac.local_state_update.session_status}</div>
    `;
}

// ==========================================
// 5. Live View (Mock Sketch Controls)
// ==========================================
function setupLiveView() {
    muteBtn.addEventListener("click", () => {
        const isMuted = muteBtn.textContent.includes("Unmute");
        muteBtn.textContent = isMuted ? "🔊 Mute" : "🔇 Unmute";
    });

    camToggleBtn.addEventListener("click", () => {
        const isOn = camToggleBtn.textContent.includes("ON");
        camToggleBtn.textContent = isOn ? "📷 Camera: OFF" : "📷 Camera: ON";
        const badge = document.getElementById("cameraStatusBadge");
        badge.textContent = isOn ? "CAMERA PAUSED (OFF)" : "ACTIVE CAMERA";
        badge.className = isOn ? "badge amber" : "badge blue";
    });

    endWorkoutBtn.addEventListener("click", () => {
        if (confirm("End live workout session and log completed progress?")) {
            completeWorkoutBtn.click();
            switchView("profile");
        }
    });

    // Start ticker
    liveTimerInterval = setInterval(() => {
        liveSeconds++;
        const m = Math.floor(liveSeconds / 60).toString().padStart(2, '0');
        const s = (liveSeconds % 60).toString().padStart(2, '0');
        liveTimerText.textContent = `${m}:${s}`;
        document.getElementById("mockTotalTime").textContent = `${m}:${s}`;
    }, 1000);
}

// ==========================================
// 6. Telemetry Toggles
// ==========================================
function setupTelemetryToggles() {
    const netButtons = document.querySelectorAll("#networkToggle .toggle-btn");
    netButtons.forEach(btn => {
        btn.addEventListener("click", () => {
            netButtons.forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            currentNetworkStatus = btn.dataset.val;
        });
    });
}

// ==========================================
// 7. Modal (Offline Guide Viewer)
// ==========================================
function setupModal() {
    modalCloseBtn.addEventListener("click", () => guideModal.classList.remove("open"));
    modalBackdrop.addEventListener("click", () => guideModal.classList.remove("open"));
}

window.openGuideModal = async function(guideId) {
    try {
        const resp = await fetch(`/api/guide/view/${guideId}`);
        const data = await resp.json();
        modalTitle.textContent = data.title;
        guideMarkdownContent.textContent = data.content;
        guideModal.classList.add("open");
    } catch (err) {
        alert("Failed to load guide: " + err.message);
    }
};

// Utilities
function escapeHtml(str) {
    if (!str) return "";
    return str.replace(/[&<>"']/g, (m) => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#039;"
    })[m]);
}

function formatMarkdown(text) {
    if (!text) return "";
    let html = escapeHtml(text);
    html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    html = html.replace(/`(.*?)`/g, '<code>$1</code>');
    html = html.replace(/^### (.*$)/gim, '<h4 style="margin:8px 0 4px 0; color:var(--accent-blue)">$1</h4>');
    html = html.replace(/^## (.*$)/gim, '<h3 style="margin:10px 0 6px 0; color:var(--accent-cyan)">$1</h3>');
    html = html.replace(/\n\n/g, '<br><br>');
    html = html.replace(/\n/g, '<br>');
    return html;
}
