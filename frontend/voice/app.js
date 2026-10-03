/**
 * Q1 Voice Agent — Browser Interface Logic (v2.0 Durable).
 *
 * Architecture:
 *   Vapi (PRIMARY) → Gemini Live (Fallback 1) → Direct Voice (Fallback 2)
 *
 * Provider Lifecycle States:
 *   IDLE → STARTING → ACTIVE → FAILED → ENDED
 *
 * Key durability guarantees:
 *   - Vapi SDK loaded from local bundle (no CDN/CommonJS crash)
 *   - Only fallback on TERMINAL failures, not transient error events
 *   - No duplicate call starts
 *   - No duplicate fallback transitions
 *   - No simultaneous Vapi + Gemini
 *   - SpeechRecognition guarded with explicit state machine
 *   - XSS-safe citation rendering (textContent, never innerHTML for user data)
 */

const API_BASE = window.location.origin;

// ──────────────────────────────────────────────────────────────────────────────
// Provider Lifecycle
// ──────────────────────────────────────────────────────────────────────────────

const ProviderState = Object.freeze({
  IDLE:     "IDLE",
  STARTING: "STARTING",
  ACTIVE:   "ACTIVE",
  FAILED:   "FAILED",
  ENDED:    "ENDED",
});

/** Recognition lifecycle — prevents InvalidStateError */
const RecogState = Object.freeze({
  IDLE:     "idle",
  STARTING: "starting",
  LISTENING:"listening",
  STOPPING: "stopping",
});

// ──────────────────────────────────────────────────────────────────────────────
// State
// ──────────────────────────────────────────────────────────────────────────────

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

let activeProvider = "browser";
let providerState = ProviderState.IDLE;
let fallbackStarted = false;          // Prevents duplicate fallback transitions
let callStartInProgress = false;      // Prevents duplicate call starts
let geminiSessionId = null;
let speechRecognizer = null;
let recogState = RecogState.IDLE;
let isMicMuted = false;

// ──────────────────────────────────────────────────────────────────────────────
// DOM Elements
// ──────────────────────────────────────────────────────────────────────────────

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

// ──────────────────────────────────────────────────────────────────────────────
// Web Speech TTS
// ──────────────────────────────────────────────────────────────────────────────

function speakAloud(text) {
  if (!("speechSynthesis" in window)) return;
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.rate = 1.0;
  utterance.pitch = 1.0;
  const voices = window.speechSynthesis.getVoices();
  const preferred = voices.find(
    (v) =>
      v.lang.startsWith("en") &&
      (v.name.includes("Natural") ||
        v.name.includes("Google") ||
        v.name.includes("Samantha") ||
        v.name.includes("Female"))
  );
  if (preferred) utterance.voice = preferred;
  window.speechSynthesis.speak(utterance);
}

// ──────────────────────────────────────────────────────────────────────────────
// Web Speech Recognition — guarded with explicit state machine
// ──────────────────────────────────────────────────────────────────────────────

function initSpeechRecognition() {
  const SpeechRec =
    window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRec) {
    console.warn("Web Speech API not supported in this browser.");
    return null;
  }
  const rec = new SpeechRec();
  rec.continuous = true;
  rec.interimResults = false;
  rec.lang = "en-US";

  rec.onstart = () => {
    recogState = RecogState.LISTENING;
  };

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
    if (e.error === "aborted") {
      recogState = RecogState.IDLE;
      return;
    }
    if (e.error !== "no-speech") {
      console.warn("Speech recognition error:", e.error);
    }
    // On most errors, onend will fire and handle restart
  };

  rec.onend = () => {
    recogState = RecogState.IDLE;
    // Auto-restart if call is still active and provider uses local mic
    if (
      callActive &&
      !isMicMuted &&
      activeProvider !== "vapi" // Vapi handles its own audio
    ) {
      safeStartRecognition();
    }
  };

  return rec;
}

/** Safely start recognition — only if not already starting/listening. */
function safeStartRecognition() {
  if (!speechRecognizer) return;
  if (recogState === RecogState.STARTING || recogState === RecogState.LISTENING) {
    return; // Already active — do nothing
  }
  try {
    recogState = RecogState.STARTING;
    speechRecognizer.start();
  } catch (err) {
    console.warn("Speech recognition start error:", err.message);
    recogState = RecogState.IDLE;
  }
}

/** Safely stop recognition. */
function safeStopRecognition() {
  if (!speechRecognizer) return;
  if (recogState === RecogState.IDLE || recogState === RecogState.STOPPING) {
    return;
  }
  try {
    recogState = RecogState.STOPPING;
    speechRecognizer.stop();
  } catch (err) {
    recogState = RecogState.IDLE;
  }
}

// ──────────────────────────────────────────────────────────────────────────────
// Provider Selection UI
// ──────────────────────────────────────────────────────────────────────────────

function setActiveProvider(provider) {
  activeProvider = provider;
  if (btnBrowser)
    btnBrowser.className =
      provider === "browser"
        ? "provider-toggle-btn active"
        : "provider-toggle-btn";
  if (btnVapi)
    btnVapi.className =
      provider === "vapi"
        ? "provider-toggle-btn active"
        : "provider-toggle-btn";
  if (btnGemini)
    btnGemini.className =
      provider === "gemini_live"
        ? "provider-toggle-btn active fallback"
        : "provider-toggle-btn";
  if (btnWhisper)
    btnWhisper.className =
      provider === "whisper"
        ? "provider-toggle-btn active fallback"
        : "provider-toggle-btn";
}

// ──────────────────────────────────────────────────────────────────────────────
// Vapi Initialization — deterministic, from local bundle
// ──────────────────────────────────────────────────────────────────────────────

async function setupVapiIfAvailable() {
  // The local bundle sets window.Vapi directly
  const VapiCtor = window.Vapi;

  if (!VapiCtor) {
    console.warn("Vapi SDK bundle not loaded — window.Vapi is undefined.");
    return false;
  }

  try {
    const resp = await fetch(`${API_BASE}/api/v1/vapi/config`);
    if (!resp.ok) {
      console.warn("Vapi config endpoint returned:", resp.status);
      return false;
    }

    const data = await resp.json();

    if (!data.configured) {
      console.info(
        "Vapi is not configured on the backend; the local browser demo will be used."
      );
      return false;
    }

    if (data.public_key && data.assistant_id) {
      vapiAssistantId = data.assistant_id;
      vapiInstance = new VapiCtor(data.public_key);
      attachVapiEvents(vapiInstance);
      console.log(
        "Vapi Web SDK initialized with public key and assistant ID."
      );
      return true;
    }

    console.warn("Vapi config missing public_key or assistant_id.");
    return false;
  } catch (e) {
    console.warn("Vapi config fetch error:", e);
    return false;
  }
}

function attachVapiEvents(vapi) {
  vapi.on("call-start", () => {
    providerState = ProviderState.ACTIVE;
    setCallActive(true);
    addMessage(
      "assistant",
      "Hello, thank you for calling commercial lending. How can I help you today?"
    );
  });

  vapi.on("call-end", () => {
    providerState = ProviderState.ENDED;
    setCallActive(false);
  });

  vapi.on("message", (msg) => {
    if (msg.type === "transcript" && msg.transcriptType === "final") {
      addMessage(msg.role, msg.transcript);
    }
  });

  vapi.on("error", (err) => {
    console.error("Vapi error event:", err);

    // IMPORTANT: Not all error events are terminal failures.
    // Only fallback on errors that indicate the call cannot continue.
    const errMsg =
      err?.message ||
      (typeof err === "object" ? JSON.stringify(err) : String(err));
    const errCode = err?.code || err?.errorCode || "";

    // Terminal errors that warrant fallback:
    const isTerminal =
      providerState !== ProviderState.ACTIVE || // Error before call was active
      errCode === "meeting-ended" ||
      errCode === "call-ended" ||
      /connection.*(?:failed|closed|lost)/i.test(errMsg) ||
      /meeting.*(?:ended|left)/i.test(errMsg) ||
      /transport.*(?:closed|error)/i.test(errMsg);

    if (isTerminal) {
      addMessage(
        "system",
        `Vapi call failure: ${errMsg}. Switching to Gemini Live fallback...`
      );
      providerState = ProviderState.FAILED;
      triggerFallbackToGemini();
    } else {
      // Non-terminal error — log but don't fallback
      console.warn("Non-terminal Vapi error (not triggering fallback):", errMsg);
      addMessage(
        "system",
        `Vapi warning: ${errMsg} (call still active)`
      );
    }
  });
}

// ──────────────────────────────────────────────────────────────────────────────
// Fallback Chain: Vapi → Gemini Live → Direct Voice
// ──────────────────────────────────────────────────────────────────────────────

async function triggerFallbackToGemini() {
  // Guard: prevent duplicate fallback
  if (fallbackStarted) {
    console.warn("Fallback already in progress — ignoring duplicate.");
    return;
  }
  fallbackStarted = true;

  // Stop Vapi if it's still running
  if (vapiInstance) {
    try {
      vapiInstance.stop();
    } catch (e) {
      // ignore
    }
  }

  setActiveProvider("gemini_live");
  providerState = ProviderState.STARTING;

  try {
    await startGeminiLiveSession();
    providerState = ProviderState.ACTIVE;
    safeStartRecognition();
  } catch (e) {
    console.error("Gemini Live fallback failed:", e);
    addMessage(
      "system",
      "Gemini Live unavailable. Falling back to Direct Voice (browser speech)."
    );
    setActiveProvider("browser");
    providerState = ProviderState.ACTIVE;
    safeStartRecognition();
    addMessage(
      "assistant",
      "Hello! I'm your commercial loan assistant. How can I help you today?"
    );
  }
}

async function startGeminiLiveSession() {
  const payload = {
    call_id: currentCallId,
    state: qualificationState,
  };
  const resp = await fetch(`${API_BASE}/api/v1/gemini/session/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (resp.ok) {
    const data = await resp.json();
    geminiSessionId = data.session_id;
    addMessage(
      "assistant",
      data.greeting ||
        "Hello! Connected to Gemini voice assistant. How can I help you?"
    );
    if (data.qualification_state) {
      qualificationState = { ...qualificationState, ...data.qualification_state };
      updateQualificationUI();
      updateEligibilityBadge(data.qualification_state.eligibility);
    }
    return;
  }
  throw new Error(`Gemini session start failed: HTTP ${resp.status}`);
}

// ──────────────────────────────────────────────────────────────────────────────
// Call Start / End
// ──────────────────────────────────────────────────────────────────────────────

function setCallActive(active) {
  callActive = active;
  btnStart.disabled = active;
  btnEnd.disabled = !active;
  btnMute.disabled = !active;

  if (active) {
    statusDot.className = "dot dot-active";
    const providerLabels = {
      vapi: "Vapi WebRTC",
      gemini_live: "Gemini Live",
      whisper: "Whisper ASR",
      browser: "Direct Voice",
    };
    statusText.textContent = `In Call (${providerLabels[activeProvider] || activeProvider})`;
    agentBadge.textContent = "Listening";
    agentBadge.className = "badge badge-accent";
  } else {
    statusDot.className = "dot dot-idle";
    statusText.textContent = "Call Ended";
    agentBadge.textContent = "Idle";
    agentBadge.className = "badge";
    callStartInProgress = false;
    fallbackStarted = false;
    providerState = ProviderState.IDLE;
    if ("speechSynthesis" in window) {
      window.speechSynthesis.cancel();
    }
  }
}

async function startCall() {
  // Guard: prevent duplicate start
  if (callStartInProgress || callActive) {
    console.warn("Call start already in progress or call active — ignoring.");
    return;
  }
  callStartInProgress = true;
  fallbackStarted = false;
  providerState = ProviderState.STARTING;

  currentCallId = "call_" + Math.random().toString(36).substring(2, 9);
  turnCount = 0;
  transcriptFeed.innerHTML = "";
  resetQualificationState();

  // ── 1. Vapi WebRTC (Primary) ──
  if (activeProvider === "vapi") {
    if (!vapiInstance) {
      const initialized = await setupVapiIfAvailable();
      if (!initialized) {
        addMessage(
          "system",
          "Vapi credentials are not configured. Using Direct Voice demo; typed tests work without provider keys."
        );
        setActiveProvider("browser");
        providerState = ProviderState.ACTIVE;
        setCallActive(true);
        safeStartRecognition();
        addMessage(
          "assistant",
          "Hello, thank you for calling commercial lending. How can I help you today?"
        );
        return;
      }
    }

    if (vapiInstance && vapiAssistantId) {
      try {
        addMessage("system", "Connecting to Vapi WebRTC voice assistant...");
        await vapiInstance.start(vapiAssistantId);
        // call-start event will fire → sets ACTIVE and calls setCallActive(true)
        addMessage("system", "Vapi connected successfully.");
        return;
      } catch (e) {
        console.error("Vapi start() failed:", e);
        const errMsg =
          e?.message ||
          (typeof e === "object" ? JSON.stringify(e) : String(e));
        addMessage(
          "system",
          `Vapi WebRTC connection error: ${errMsg}. Triggering fallback chain...`
        );
        providerState = ProviderState.FAILED;
        setCallActive(true); // Keep call active — fallback will handle provider
        await triggerFallbackToGemini();
        return;
      }
    }

    // vapiInstance exists but no assistantId — configuration issue
    addMessage(
      "system",
      "Vapi assistant not configured. Using Direct Voice demo."
    );
    setActiveProvider("browser");
    providerState = ProviderState.ACTIVE;
    setCallActive(true);
    safeStartRecognition();
    addMessage(
      "assistant",
      "Hello, thank you for calling commercial lending. How can I help you today?"
    );
    return;
  }

  // ── 2. Gemini Live (Fallback 1 / Manual selection) ──
  if (activeProvider === "gemini_live") {
    setCallActive(true);
    try {
      await startGeminiLiveSession();
      providerState = ProviderState.ACTIVE;
      safeStartRecognition();
    } catch (e) {
      addMessage(
        "system",
        "Gemini Live unavailable. Switching to Direct Voice..."
      );
      setActiveProvider("browser");
      providerState = ProviderState.ACTIVE;
      safeStartRecognition();
      addMessage(
        "assistant",
        "Hello! Connected via browser voice. How can I help you today?"
      );
    }
    return;
  }

  // ── 3. Direct Voice / Whisper (Fallback 2) ──
  providerState = ProviderState.ACTIVE;
  setCallActive(true);
  safeStartRecognition();
  addMessage(
    "assistant",
    "Hello, thank you for calling commercial lending! I can answer any loan questions or see what financing your business qualifies for. How can I help you today?"
  );
}

function endCall() {
  safeStopRecognition();

  if (vapiInstance && activeProvider === "vapi") {
    try {
      vapiInstance.stop();
    } catch (e) {
      // ignore
    }
  }

  if (geminiSessionId) {
    fetch(
      `${API_BASE}/api/v1/gemini/session/${geminiSessionId}/end`,
      { method: "POST" }
    ).catch(() => {});
    geminiSessionId = null;
  }

  if (currentCallId) {
    fetch(
      `${API_BASE}/api/v1/agent/sessions/${encodeURIComponent(currentCallId)}`,
      { method: "DELETE" }
    ).catch(() => {});
  }

  setCallActive(false);
  addMessage("system", "Call session concluded.");
}

// ──────────────────────────────────────────────────────────────────────────────
// Message Rendering (XSS-safe)
// ──────────────────────────────────────────────────────────────────────────────

function addMessage(role, text) {
  const bubble = document.createElement("div");
  bubble.className = `chat-bubble bubble-${role}`;
  bubble.textContent = text; // textContent — safe from XSS
  transcriptFeed.appendChild(bubble);
  transcriptFeed.scrollTop = transcriptFeed.scrollHeight;
  turnCount++;
  turnCounter.textContent = `Turn: ${turnCount}`;

  // Speak aloud if assistant and using local audio providers
  if (
    role === "assistant" &&
    activeProvider !== "vapi" // Vapi handles its own TTS
  ) {
    speakAloud(text);
  }
}

// ──────────────────────────────────────────────────────────────────────────────
// Turn Processing
// ──────────────────────────────────────────────────────────────────────────────

async function processUserTurn(text) {
  if (!callActive) {
    await startCall();
  }
  addMessage("user", text);
  agentBadge.textContent = "Processing";

  // If Gemini Live is active, use Gemini session endpoint
  if (activeProvider === "gemini_live" && geminiSessionId) {
    try {
      const resp = await fetch(
        `${API_BASE}/api/v1/gemini/session/${geminiSessionId}/message`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text }),
        }
      );
      if (resp.ok) {
        const data = await resp.json();
        addMessage("assistant", data.assistant_response);
        if (data.citations && data.citations.length > 0) {
          renderCitations({
            grounded: data.grounded,
            confidence: 0.95,
            citations: data.citations,
          });
        } else if (data.grounded === false) {
          renderCitations({ grounded: false, confidence: 0, citations: [] });
        }
        if (data.escalated) {
          triggerEscalation(
            "Customer requested specialist via Gemini Live"
          );
        }
        if (data.qualification_state) {
          const qs = data.qualification_state;
          qualificationState = { ...qualificationState, ...qs };
          updateQualificationUI();
          updateEligibilityBadge(qs.eligibility);
        }
        agentBadge.textContent = "Listening";
        return;
      }
    } catch (e) {
      console.error("Gemini Live message error:", e);
    }
  }

  // Unified LLM Turn Processing (browser / whisper / gemini fallback)
  try {
    const resp = await fetch(`${API_BASE}/api/v1/agent/turn`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        transcript: text,
        state: qualificationState,
        call_id: currentCallId,
      }),
    });

    if (resp.ok) {
      const data = await resp.json();

      if (data.response) {
        addMessage("assistant", data.response);
      }

      if (data.citations && data.citations.length > 0) {
        renderCitations({
          grounded: data.grounded,
          confidence: data.confidence || 0.95,
          citations: data.citations,
        });
      } else if (data.grounded === false) {
        renderCitations({ grounded: false, confidence: 0, citations: [] });
      }

      if (data.escalated) {
        triggerEscalation(
          data.escalation_reason || "Customer requested live specialist"
        );
      }

      if (data.state) {
        qualificationState = { ...qualificationState, ...data.state };
        updateQualificationUI();
        updateEligibilityBadge(data.state.eligibility);
      }
    } else {
      console.error("Agent turn error: Status", resp.status);
      addMessage(
        "assistant",
        "I'm sorry, I had trouble processing that. Could you try again?"
      );
    }
  } catch (e) {
    console.error("Agent turn fetch error:", e);
    addMessage(
      "assistant",
      "I'm sorry, I'm having trouble connecting to the server. Please try again in a moment."
    );
  }

  agentBadge.textContent = "Listening";
}

// ──────────────────────────────────────────────────────────────────────────────
// Qualification State UI
// ──────────────────────────────────────────────────────────────────────────────

function updateQualificationUI() {
  fieldBusinessType.textContent = qualificationState.business_type || "—";
  fieldBusinessType.className = qualificationState.business_type
    ? "field-value"
    : "field-value empty";

  fieldYears.textContent =
    qualificationState.years_in_business !== null
      ? `${qualificationState.years_in_business} years`
      : "—";
  fieldYears.className =
    qualificationState.years_in_business !== null
      ? "field-value"
      : "field-value empty";

  fieldRevenue.textContent =
    qualificationState.monthly_revenue !== null
      ? `$${qualificationState.monthly_revenue.toLocaleString()}`
      : "—";
  fieldRevenue.className =
    qualificationState.monthly_revenue !== null
      ? "field-value"
      : "field-value empty";

  fieldRequested.textContent =
    qualificationState.requested_amount !== null
      ? `$${qualificationState.requested_amount.toLocaleString()}`
      : "—";
  fieldRequested.className =
    qualificationState.requested_amount !== null
      ? "field-value"
      : "field-value empty";

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
  // Safe reset — no innerHTML with user data
  citationBox.textContent = "";
  const placeholder = document.createElement("p");
  placeholder.className = "placeholder-text";
  placeholder.textContent =
    "When a knowledge question or objection is raised, retrieved Q2 source chunks and content hash lineage appear here.";
  citationBox.appendChild(placeholder);
}

function updateEligibilityBadge(eligibility) {
  if (eligibility === "ELIGIBLE") {
    eligibilityBadge.textContent = "ELIGIBLE";
    eligibilityBadge.className = "badge badge-eligible";
  } else if (eligibility === "INELIGIBLE") {
    eligibilityBadge.textContent = "INELIGIBLE";
    eligibilityBadge.className = "badge badge-ineligible";
  }
}

// ──────────────────────────────────────────────────────────────────────────────
// Citation Rendering (XSS-safe — uses DOM APIs, not innerHTML for user data)
// ──────────────────────────────────────────────────────────────────────────────

function renderCitations(data) {
  if (!data.grounded || !data.citations || data.citations.length === 0) {
    groundingStatus.textContent = "Abstained (Low Confidence)";
    groundingStatus.className = "badge badge-pending";

    citationBox.textContent = "";
    const warning = document.createElement("p");
    warning.style.color = "#fca5a5";
    warning.textContent = `⚠️ Safe Abstention: Confidence was ${data.confidence.toFixed(2)} (< 0.60 threshold). Response refrained from hallucination.`;
    citationBox.appendChild(warning);
    return;
  }

  groundingStatus.textContent = `Grounded (${(data.confidence * 100).toFixed(0)}% Conf)`;
  groundingStatus.className = "badge badge-eligible";

  citationBox.textContent = "";
  const container = document.createElement("div");
  container.style.cssText = "display:flex; flex-direction:column; gap:0.5rem;";

  data.citations.forEach((c, i) => {
    const card = document.createElement("div");
    card.style.cssText =
      "background: rgba(255,255,255,0.03); padding: 0.5rem; border-radius: 4px; border-left: 3px solid #3b82f6;";

    const title = document.createElement("div");
    title.style.cssText = "font-weight:600; font-size:0.8rem; color:#93c5fd;";
    title.textContent = `[Source ${i + 1}] ${c.source_name} (v${c.version})`;

    const meta = document.createElement("div");
    meta.style.cssText =
      "font-size:0.75rem; color:#64748b; font-family:monospace;";
    const hashDisplay = c.content_hash ? c.content_hash.substring(0, 10) + "..." : "N/A";
    meta.textContent = `Hash: ${hashDisplay} | Conf: ${c.confidence}`;

    const snippet = document.createElement("div");
    snippet.style.cssText = "font-size:0.8rem; margin-top:0.25rem;";
    snippet.textContent = `"${c.snippet}"`;

    card.appendChild(title);
    card.appendChild(meta);
    card.appendChild(snippet);
    container.appendChild(card);
  });

  citationBox.appendChild(container);
}

function triggerEscalation(reason) {
  alertCard.classList.remove("hidden");
  document.getElementById("alert-message").textContent = `Reason: ${reason}. Underwriter notified.`;
}

// ──────────────────────────────────────────────────────────────────────────────
// Scenarios
// ──────────────────────────────────────────────────────────────────────────────

async function runScenario(type) {
  await startCall();
  if (type === "cooperative") {
    await delay(500);
    await processUserTurn(
      "We are a retail trading company with 3 years in operations."
    );
    await delay(800);
    await processUserTurn(
      "Our monthly revenue is around 600k and we need a 1.5 million loan."
    );
  } else if (type === "objection") {
    await delay(500);
    await processUserTurn(
      "Why is there a requirement to be in business for at least 2 years?"
    );
  } else if (type === "ambiguous") {
    await delay(500);
    await processUserTurn("Our revenue is around fifty.");
  } else if (type === "out_of_scope") {
    await delay(500);
    await processUserTurn(
      "What is the weather forecast for Tokyo tomorrow?"
    );
  } else if (type === "escalation") {
    await delay(500);
    await processUserTurn(
      "I want to speak with a human manager please."
    );
  }
}

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// ──────────────────────────────────────────────────────────────────────────────
// Event Listeners
// ──────────────────────────────────────────────────────────────────────────────

function setupEventListeners() {
  btnStart.addEventListener("click", startCall);
  btnEnd.addEventListener("click", endCall);

  if (btnBrowser) {
    btnBrowser.addEventListener("click", () => {
      if (!callActive) setActiveProvider("browser");
    });
  }
  if (btnVapi) {
    btnVapi.addEventListener("click", () => {
      if (!callActive) setActiveProvider("vapi");
    });
  }
  if (btnGemini) {
    btnGemini.addEventListener("click", () => {
      if (!callActive) setActiveProvider("gemini_live");
    });
  }
  if (btnWhisper) {
    btnWhisper.addEventListener("click", () => {
      if (!callActive) setActiveProvider("whisper");
    });
  }

  if (btnMute) {
    btnMute.addEventListener("click", () => {
      isMicMuted = !isMicMuted;
      btnMute.innerHTML = isMicMuted
        ? '<span class="icon">🔇</span> Unmute'
        : '<span class="icon">🎙️</span> Mute';
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
  document.querySelectorAll(".btn-scenario").forEach((btn) => {
    btn.addEventListener("click", () => {
      const sc = btn.getAttribute("data-scenario");
      runScenario(sc);
    });
  });
}

// ──────────────────────────────────────────────────────────────────────────────
// Initialize
// ──────────────────────────────────────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", async () => {
  speechRecognizer = initSpeechRecognition();
  setActiveProvider("browser");
  setupEventListeners();

  // Try to set up Vapi in background — if it works, enable the Vapi button
  const vapiReady = await setupVapiIfAvailable();
  if (vapiReady) {
    console.log("Vapi ready — user can select Vapi provider.");
    // Don't auto-switch; let user choose or stay on browser
  }
});
