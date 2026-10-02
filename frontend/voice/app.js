/**
 * Q1 Voice Agent — Browser Interface Logic.
 *
 * Coordinates:
 * - Vapi Web SDK for browser-based voice calls
 * - Fallback interactive simulator for testing qualification without live credentials
 * - Real-time state updates (transcript, qualification fields, Q2 citations)
 */

const API_BASE = window.location.origin;

// State
let callActive = false;
let vapiInstance = null;
let vapiAssistantId = null;
let currentCallId = null;
let turnCount = 0;
let qualificationState = {
    business_type: null,
    years_in_business: null,
    monthly_revenue: null,
    requested_amount: null,
    product: null,
};

// DOM Elements
const btnStart = document.getElementById("btn-start-call");
const btnEnd = document.getElementById("btn-end-call");
const btnMute = document.getElementById("btn-toggle-mic");
const statusDot = document.getElementById("call-status-dot");
const statusText = document.getElementById("call-status-text");
const agentBadge = document.getElementById("agent-state-badge");
const transcriptFeed = document.getElementById("transcript-feed");
const turnCounter = document.getElementById("turn-counter");
const inputForm = document.getElementById("text-input-form");
const textInput = document.getElementById("text-utterance");
const btnBrowser = document.getElementById("provider-btn-browser");
const btnVapi = document.getElementById("provider-btn-vapi");
const btnGemini = document.getElementById("provider-btn-gemini");
const btnWhisper = document.getElementById("provider-btn-whisper");

let activeProvider = "vapi";
let geminiSessionId = null;
let speechRecognizer = null;
let isMicMuted = false;

// Web Speech SpeechSynthesis setup
function speakAloud(text) {
    if (!('speechSynthesis' in window)) return;
    window.speechSynthesis.cancel(); // cancel pending speech
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 1.0;
    utterance.pitch = 1.0;
    // Prefer friendly English voice
    const voices = window.speechSynthesis.getVoices();
    const preferred = voices.find(v => v.lang.startsWith("en") && (v.name.includes("Natural") || v.name.includes("Google") || v.name.includes("Samantha") || v.name.includes("Female")));
    if (preferred) utterance.voice = preferred;
    window.speechSynthesis.speak(utterance);
}

// Web Speech Recognition setup
function initSpeechRecognition() {
    const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRec) {
        console.warn("Web Speech API not supported in this browser.");
        return null;
    }
    const rec = new SpeechRec();
    rec.continuous = true;
    rec.interimResults = false;
    rec.lang = "en-US";

    rec.onresult = (event) => {
        if (isMicMuted) return;
        const last = event.results[event.results.length - 1];
        if (last.isFinal) {
            const spokenText = last[0].transcript.trim();
            if (spokenText) {
                console.log("Recognized speech:", spokenText);
                processUserTurn(spokenText);
            }
        }
    };

    rec.onerror = (e) => {
        if (e.error !== "no-speech") {
            console.warn("Speech recognition error:", e.error);
        }
    };

    rec.onend = () => {
        // Automatically restart speech recognizer if call is still active
        if (callActive && (activeProvider === "browser" || activeProvider === "gemini_live" || activeProvider === "whisper") && !isMicMuted) {
            try {
                rec.start();
            } catch (err) {}
        }
    };

    return rec;
}

const fieldBusinessType = document.getElementById("field-business-type");
const fieldYears = document.getElementById("field-years");
const fieldRevenue = document.getElementById("field-revenue");
const fieldRequested = document.getElementById("field-requested");
const fieldProduct = document.getElementById("field-product");
const eligibilityBadge = document.getElementById("eligibility-badge");
const reasonsBox = document.getElementById("qualification-notes");
const reasonsList = document.getElementById("reasons-list");
const citationBox = document.getElementById("latest-citation-box");
const groundingStatus = document.getElementById("grounding-status");
const alertCard = document.getElementById("escalation-alert-card");

// Initialize
document.addEventListener("DOMContentLoaded", async () => {
    speechRecognizer = initSpeechRecognition();
    await setupVapiIfAvailable();
    setupEventListeners();
});

function setActiveProvider(provider) {
    activeProvider = provider;
    if (btnBrowser) btnBrowser.className = provider === "browser" ? "provider-toggle-btn active" : "provider-toggle-btn";
    if (btnVapi) btnVapi.className = provider === "vapi" ? "provider-toggle-btn active" : "provider-toggle-btn";
    if (btnGemini) btnGemini.className = provider === "gemini_live" ? "provider-toggle-btn active fallback" : "provider-toggle-btn";
    if (btnWhisper) btnWhisper.className = provider === "whisper" ? "provider-toggle-btn active fallback" : "provider-toggle-btn";
}

async function setupVapiIfAvailable() {
    let attempts = 0;
    const maxAttempts = 5;

    while (attempts < maxAttempts) {
        try {
            const resp = await fetch(`${API_BASE}/api/v1/vapi/config`);
            if (resp.ok) {
                const data = await resp.json();
                const VapiCtor = window.Vapi?.default || window.Vapi;

                if (data.configured && data.public_key && data.assistant_id && VapiCtor) {
                    vapiAssistantId = data.assistant_id;
                    vapiInstance = new VapiCtor(data.public_key);
                    attachVapiEvents(vapiInstance);
                    console.log("Vapi Web SDK initialized with public key and assistant ID.");
                    return; // Success!
                }

                console.warn(`Vapi SDK not ready (attempt ${attempts + 1}/${maxAttempts}). Waiting...`);
            }
        } catch (e) {
            console.warn(`Vapi config attempt ${attempts + 1} failed:`, e);
        }
        attempts++;
        await new Promise(resolve => setTimeout(resolve, 500)); // Wait 500ms before retrying
    }
    console.error("Vapi initialization failed after max attempts.");
}

function attachVapiEvents(vapi) {
    vapi.on("call-start", () => {
        setCallActive(true);
        addMessage("assistant", "Hello, thank you for calling commercial lending. How can I help you today?");
    });

    vapi.on("call-end", () => {
        setCallActive(false);
    });

    vapi.on("message", (msg) => {
        if (msg.type === "transcript" && msg.transcriptType === "final") {
            addMessage(msg.role, msg.transcript);
        }
    });

    vapi.on("error", (err) => {
        console.error("Vapi error:", err);
        const errMsg = err?.message || (typeof err === "object" ? JSON.stringify(err) : String(err));
        addMessage("system", `Vapi runtime error: ${errMsg}. Switching to backup voice provider (Gemini Live)...`);
        setActiveProvider("gemini_live");
        startGeminiLiveSession();
    });
}

function setupEventListeners() {
    btnStart.addEventListener("click", startCall);
    btnEnd.addEventListener("click", endCall);

    if (btnBrowser) {
        btnBrowser.addEventListener("click", () => setActiveProvider("browser"));
    }
    if (btnVapi) {
        btnVapi.addEventListener("click", () => setActiveProvider("vapi"));
    }
    if (btnGemini) {
        btnGemini.addEventListener("click", () => setActiveProvider("gemini_live"));
    }
    if (btnWhisper) {
        btnWhisper.addEventListener("click", () => setActiveProvider("whisper"));
    }

    if (btnMute) {
        btnMute.addEventListener("click", () => {
            isMicMuted = !isMicMuted;
            btnMute.innerHTML = isMicMuted ? '<span class="icon">🔇</span> Unmute' : '<span class="icon">🎙️</span> Mute';
            agentBadge.textContent = isMicMuted ? "Muted" : "Listening";
        });
    }

    inputForm.addEventListener("submit", (e) => {
        e.preventDefault();
        const text = textInput.value.trim();
        if (!text) return;
        textInput.value = "";
        processUserTurn(text);
    });

    // Scenario buttons
    document.querySelectorAll(".btn-scenario").forEach(btn => {
        btn.addEventListener("click", () => {
            const sc = btn.getAttribute("data-scenario");
            runScenario(sc);
        });
    });
}

function setCallActive(active) {
    callActive = active;
    btnStart.disabled = active;
    btnEnd.disabled = !active;
    btnMute.disabled = !active;

    if (active) {
        statusDot.className = "dot dot-active";
        statusText.textContent = activeProvider === "gemini_live" 
            ? "In Call (Gemini Live)" 
            : (activeProvider === "whisper" 
                ? "In Call (Whisper ASR)" 
                : (activeProvider === "vapi" ? "In Call (Vapi WebRTC)" : "In Call (Direct Voice)"));
        agentBadge.textContent = "Listening";
        agentBadge.className = "badge badge-accent";
    } else {
        statusDot.className = "dot dot-idle";
        statusText.textContent = "Call Ended";
        agentBadge.textContent = "Idle";
        agentBadge.className = "badge";
        if ('speechSynthesis' in window) {
            window.speechSynthesis.cancel();
        }
    }
}

async function startGeminiLiveSession() {
    try {
        const resp = await fetch(`${API_BASE}/api/v1/gemini/session/start`, { method: "POST" });
        if (resp.ok) {
            const data = await resp.json();
            geminiSessionId = data.session_id;
            addMessage("assistant", data.greeting || "Hello! Connected to Gemini Live backup voice assistant.");
            return;
        }
    } catch (e) {
        console.warn("Could not start Gemini Live session on backend:", e);
    }
    addMessage("assistant", "Hello! I am your commercial loan qualification assistant. How can I help you today?");
}

async function startCall() {
    currentCallId = "call_" + Math.random().toString(36).substring(2, 9);
    turnCount = 0;
    transcriptFeed.innerHTML = "";
    resetQualificationState();
    setCallActive(true);

    // 1. Direct Voice Mode (Mic & TTS via Web Speech API)
    if (activeProvider === "browser") {
        if (speechRecognizer) {
            try {
                speechRecognizer.start();
            } catch (err) {
                console.log("Speech recognizer already active or starting:", err);
            }
        }
        addMessage("assistant", "Hello, thank you for calling commercial lending! I can answer any loan questions or see what financing your business qualifies for. How can I help you today?");
        return;
    }

    // 2. Vapi WebRTC Provider (Primary)
    if (activeProvider === "vapi") {
        if (!vapiInstance) {
            await setupVapiIfAvailable();
        }
        if (vapiInstance && vapiAssistantId) {
            try {
                addMessage("system", "Connecting to Vapi WebRTC voice assistant...");
                await vapiInstance.start(vapiAssistantId);
                addMessage("system", "Vapi connected successfully.");
                return;
            } catch (e) {
                console.error("Vapi failed:", e);
                const errMsg = e?.message || (typeof e === "object" ? JSON.stringify(e) : String(e));
                addMessage("system", `Vapi WebRTC connection error: ${errMsg}. Moving to Fallback 1 (Gemini Live)...`);
                setActiveProvider("gemini_live");
                try {
                    await startGeminiLiveSession();
                    if (speechRecognizer) speechRecognizer.start();
                    return;
                } catch (geminiErr) {
                    console.error("Gemini Live failed:", geminiErr);
                    addMessage("system", "Gemini Live failed. Moving to Fallback 2 (Whisper ASR)...");
                    setActiveProvider("whisper");
                    if (speechRecognizer) speechRecognizer.start();
                    addMessage("assistant", "Hello! I am your commercial loan assistant powered by Whisper ASR fallback. How can I assist you today?");
                    return;
                }
            }
        } else {
            addMessage("system", "Vapi credentials not found. Moving to Fallback 1 (Gemini Live)...");
            setActiveProvider("gemini_live");
            try {
                await startGeminiLiveSession();
                if (speechRecognizer) speechRecognizer.start();
                return;
            } catch (geminiErr) {
                addMessage("system", "Moving to Fallback 2 (Whisper ASR)...");
                setActiveProvider("whisper");
                if (speechRecognizer) speechRecognizer.start();
                addMessage("assistant", "Hello! Connected via Whisper ASR backup. How can I help you today?");
                return;
            }
        }
    }

    // 3. Gemini Live Provider (Fallback 1)
    if (activeProvider === "gemini_live") {
        try {
            await startGeminiLiveSession();
            if (speechRecognizer) speechRecognizer.start();
        } catch (e) {
            addMessage("system", "Gemini Live unavailable. Switching to Fallback 2 (Whisper ASR)...");
            setActiveProvider("whisper");
            if (speechRecognizer) speechRecognizer.start();
            addMessage("assistant", "Hello! Connected via Whisper ASR backup. How can I help you today?");
        }
        return;
    }

    // 4. Whisper ASR Provider (Fallback 2)
    if (activeProvider === "whisper") {
        if (speechRecognizer) {
            try {
                speechRecognizer.start();
            } catch (err) {}
        }
        addMessage("assistant", "Hello! I am your commercial loan qualification assistant powered by Whisper ASR fallback. How can I help you today?");
        return;
    }
}

function endCall() {
    if (speechRecognizer) {
        try {
            speechRecognizer.stop();
        } catch (e) {}
    }
    if (vapiInstance && activeProvider === "vapi") {
        try { vapiInstance.stop(); } catch (e) {}
    }
    if (geminiSessionId) {
        fetch(`${API_BASE}/api/v1/gemini/session/${geminiSessionId}/end`, { method: "POST" }).catch(() => {});
        geminiSessionId = null;
    }
    setCallActive(false);
    addMessage("system", "Call session concluded.");
}

function addMessage(role, text) {
    const bubble = document.createElement("div");
    bubble.className = `chat-bubble bubble-${role}`;
    bubble.textContent = text;
    transcriptFeed.appendChild(bubble);
    transcriptFeed.scrollTop = transcriptFeed.scrollHeight;
    turnCount++;
    turnCounter.textContent = `Turn: ${turnCount}`;

    // Speak aloud with voice if role is assistant
    if (role === "assistant" && (activeProvider === "browser" || activeProvider === "gemini_live" || activeProvider === "whisper")) {
        speakAloud(text);
    }
}


// Interactive Turn Processor
async function processUserTurn(text) {
    if (!callActive) {
        startCall();
    }
    addMessage("user", text);
    agentBadge.textContent = "Processing";

    // If Gemini Live is active, dispatch to backend Gemini Live session endpoint
    if (activeProvider === "gemini_live" && geminiSessionId) {
        try {
            const resp = await fetch(`${API_BASE}/api/v1/gemini/session/${geminiSessionId}/message`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ text }),
            });
            if (resp.ok) {
                const data = await resp.json();
                addMessage("assistant", data.assistant_response);
                if (data.citations && data.citations.length > 0) {
                    renderCitations({ grounded: data.grounded, confidence: 0.95, citations: data.citations });
                }
                if (data.escalated) {
                    triggerEscalation("Customer requested specialist via Gemini Live");
                }
                if (data.qualification_state) {
                    const qs = data.qualification_state;
                    if (qs.business_type && qs.business_type.value) qualificationState.business_type = qs.business_type.value;
                    if (qs.years_in_business && qs.years_in_business.value) qualificationState.years_in_business = qs.years_in_business.value;
                    if (qs.monthly_revenue && qs.monthly_revenue.value) qualificationState.monthly_revenue = qs.monthly_revenue.value;
                    if (qs.requested_amount && qs.requested_amount.value) qualificationState.requested_amount = qs.requested_amount.value;
                    updateQualificationUI();
                }
                agentBadge.textContent = "Listening";
                return;
            }
        } catch (e) {
            console.error("Gemini Live message error:", e);
        }
    }

    // Unified LLM Turn Processing
    try {
        const resp = await fetch(`${API_BASE}/api/v1/agent/turn`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ 
                transcript: text, 
                state: qualificationState,
                call_id: currentCallId
            }),
        });

        if (resp.ok) {
            const data = await resp.json();
            
            if (data.response) {
                addMessage("assistant", data.response);
            }
            
            if (data.citations && data.citations.length > 0) {
                renderCitations({ grounded: data.grounded, confidence: data.confidence || 0.95, citations: data.citations });
            } else if (data.grounded === false) {
                renderCitations({ grounded: false, confidence: 0, citations: [] });
            }

            if (data.escalated) {
                triggerEscalation(data.escalation_reason || "Customer requested live specialist");
            }
            
            if (data.state) {
                qualificationState = { ...qualificationState, ...data.state };
                updateQualificationUI();
                
                if (data.state.eligibility === "ELIGIBLE") {
                    eligibilityBadge.textContent = "ELIGIBLE";
                    eligibilityBadge.className = "badge badge-eligible";
                } else if (data.state.eligibility === "INELIGIBLE") {
                    eligibilityBadge.textContent = "INELIGIBLE";
                    eligibilityBadge.className = "badge badge-ineligible";
                }
            }
        } else {
            console.error("Agent turn error: Status", resp.status);
            addMessage("assistant", "I'm sorry, I encountered an error processing your request.");
        }
    } catch (e) {
        console.error("Agent turn fetch error:", e);
        addMessage("assistant", "I'm sorry, I encountered an error connecting to the server.");
    }

    agentBadge.textContent = "Listening";
}

function updateQualificationUI() {
    fieldBusinessType.textContent = qualificationState.business_type || "—";
    fieldBusinessType.className = qualificationState.business_type ? "field-value" : "field-value empty";

    fieldYears.textContent = qualificationState.years_in_business !== null ? `${qualificationState.years_in_business} years` : "—";
    fieldYears.className = qualificationState.years_in_business !== null ? "field-value" : "field-value empty";

    fieldRevenue.textContent = qualificationState.monthly_revenue !== null ? `$${qualificationState.monthly_revenue.toLocaleString()}` : "—";
    fieldRevenue.className = qualificationState.monthly_revenue !== null ? "field-value" : "field-value empty";

    fieldRequested.textContent = qualificationState.requested_amount !== null ? `$${qualificationState.requested_amount.toLocaleString()}` : "—";
    fieldRequested.className = qualificationState.requested_amount !== null ? "field-value" : "field-value empty";

    fieldProduct.textContent = qualificationState.product || "—";
}

function resetQualificationState() {
    qualificationState = {
        business_type: null,
        years_in_business: null,
        monthly_revenue: null,
        requested_amount: null,
        product: null,
    };
    updateQualificationUI();
    eligibilityBadge.textContent = "PENDING";
    eligibilityBadge.className = "badge badge-pending";
    alertCard.classList.add("hidden");
    citationBox.innerHTML = '<p class="placeholder-text">When a knowledge question or objection is raised, retrieved Q2 source chunks and content hash lineage appear here.</p>';
}

function renderCitations(data) {
    if (!data.grounded || !data.citations || data.citations.length === 0) {
        groundingStatus.textContent = "Abstained (Low Confidence)";
        groundingStatus.className = "badge badge-pending";
        citationBox.innerHTML = `<p style="color: #fca5a5;">⚠️ Safe Abstention: Confidence was ${data.confidence.toFixed(2)} (< 0.60 threshold). Response refrained from hallucination.</p>`;
        return;
    }

    groundingStatus.textContent = `Grounded (${(data.confidence * 100).toFixed(0)}% Conf)`;
    groundingStatus.className = "badge badge-eligible";

    let html = '<div style="display:flex; flex-direction:column; gap:0.5rem;">';
    data.citations.forEach((c, i) => {
        html += `
            <div style="background: rgba(255,255,255,0.03); padding: 0.5rem; border-radius: 4px; border-left: 3px solid #3b82f6;">
                <div style="font-weight:600; font-size:0.8rem; color:#93c5fd;">[Source ${i+1}] ${c.source_name} (v${c.version})</div>
                <div style="font-size:0.75rem; color:#64748b; font-family:monospace;">Hash: ${c.content_hash.substring(0, 10)}... | Conf: ${c.confidence}</div>
                <div style="font-size:0.8rem; margin-top:0.25rem;">"${c.snippet}"</div>
            </div>
        `;
    });
    html += '</div>';
    citationBox.innerHTML = html;
}

function triggerEscalation(reason) {
    alertCard.classList.remove("hidden");
    document.getElementById("alert-message").textContent = `Reason: ${reason}. Underwriter notified.`;
}

// Scenarios
async function runScenario(type) {
    startCall();
    if (type === "cooperative") {
        await delay(500);
        await processUserTurn("We are a retail trading company with 3 years in operations.");
        await delay(800);
        await processUserTurn("Our monthly revenue is around 600k and we need a 1.5 million loan.");
    } else if (type === "objection") {
        await delay(500);
        await processUserTurn("Why is there a requirement to be in business for at least 2 years?");
    } else if (type === "ambiguous") {
        await delay(500);
        await processUserTurn("Our revenue is around fifty.");
    } else if (type === "out_of_scope") {
        await delay(500);
        await processUserTurn("What is the weather forecast for Tokyo tomorrow?");
    } else if (type === "escalation") {
        await delay(500);
        await processUserTurn("I want to speak with a human manager please.");
    }
}

function delay(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}
