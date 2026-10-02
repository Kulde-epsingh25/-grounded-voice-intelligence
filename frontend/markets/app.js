const marketSelect = document.getElementById("market-select");
const transcriptFeed = document.getElementById("transcript-feed");
const transcriptInput = document.getElementById("transcript-input");
const statusBadge = document.getElementById("session-status");
const micButton = document.getElementById("mic-button");
const endButton = document.getElementById("end-button");
const speakReplies = document.getElementById("speak-replies");

let sessionId = newSessionId();
let marketConfigs = {};
let recognition = null;

function newSessionId() {
  return `localized-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

function addMessage(role, text) {
  const message = document.createElement("div");
  message.className = `market-message ${role}`;
  message.textContent = text;
  transcriptFeed.appendChild(message);
  transcriptFeed.scrollTop = transcriptFeed.scrollHeight;
}

function setStatus(text, state = "pending") {
  statusBadge.textContent = text;
  statusBadge.className = `badge ${state === "connected" ? "badge-eligible" : "badge-pending"}`;
}

function refreshMarketInfo() {
  const config = marketConfigs[marketSelect.value];
  if (!config) return;
  document.getElementById("market-sector").textContent =
    `${config.sector.replaceAll("_", " ")} · Supported: ${config.supported_languages.join(", ")} · ASR: ${config.asr.provider} / ${config.asr.model}`;
  document.getElementById("market-greeting").textContent = config.greeting;
  transcriptInput.placeholder = marketSelect.value === "PH"
    ? "Example: Magandang araw po. Gusto ko pong magtanong tungkol sa premium ng policy."
    : "Example: Halo Kak, saya mau tanya soal tenor dan cicilan pembiayaan.";
}

async function loadMarkets() {
  const response = await fetch("/api/v1/localization/markets");
  if (!response.ok) throw new Error("Could not load market configuration.");
  const configs = await response.json();
  marketConfigs = Object.fromEntries(configs.map(config => [config.market, config]));
  refreshMarketInfo();
}

async function sendUtterance(text) {
  const utterance = text.trim();
  if (!utterance) return;
  addMessage("user", utterance);
  transcriptInput.value = "";
  setStatus("PROCESSING");

  try {
    const response = await fetch(`/api/v1/localization/${marketSelect.value}/turn`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId, transcript: utterance }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "The localized agent could not process that turn.");

    addMessage("assistant", data.response);
    document.getElementById("detected-language").textContent = data.language;
    document.getElementById("detected-register").textContent = data.register;
    document.getElementById("code-switch").textContent = data.code_switch_detected ? "Detected" : "Not detected";
    document.getElementById("language-confidence").textContent = `${Math.round(data.language_confidence * 100)}% (heuristic)`;
    document.getElementById("grounding").textContent = data.grounded ? "Grounded with citations" : "Safe fallback";
    document.getElementById("detected-terms").textContent = data.detected_terms.length ? data.detected_terms.join(", ") : "None";
    setStatus(data.escalated ? "ESCALATION" : `TURN ${data.turn_index}`, "connected");

    if (data.citations?.length) {
      addMessage("system", `Sources: ${data.citations.map(citation => citation.source_name).join(", ")}`);
    }
    if (speakReplies.checked && "speechSynthesis" in window) {
      const speech = new SpeechSynthesisUtterance(data.response);
      speech.lang = marketSelect.value === "PH" ? "fil-PH" : "id-ID";
      const matchingVoice = speechSynthesis.getVoices().find(voice => voice.lang.toLowerCase().startsWith(marketSelect.value === "PH" ? "fil" : "id"));
      if (matchingVoice) speech.voice = matchingVoice;
      speechSynthesis.speak(speech);
    }
  } catch (error) {
    addMessage("system", error.message);
    setStatus("ERROR");
  }
}

function configureMicrophone() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    addMessage("system", "This browser does not provide speech recognition. You can still type utterances.");
    return;
  }

  recognition = new SpeechRecognition();
  recognition.lang = marketSelect.value === "PH" ? "fil-PH" : "id-ID";
  recognition.continuous = false;
  recognition.interimResults = false;
  recognition.onresult = event => {
    const transcript = event.results[0][0].transcript;
    transcriptInput.value = transcript;
    sendUtterance(transcript);
  };
  recognition.onerror = event => addMessage("system", `Microphone recognition: ${event.error}. You can type the utterance instead.`);
  recognition.onend = () => { micButton.disabled = false; };
  micButton.disabled = true;
  try {
    recognition.start();
  } catch (error) {
    micButton.disabled = false;
    addMessage("system", "Could not start the microphone. Check browser permission or type the utterance.");
  }
}

marketSelect.addEventListener("change", async () => {
  await endSession();
  refreshMarketInfo();
});

document.getElementById("turn-form").addEventListener("submit", event => {
  event.preventDefault();
  sendUtterance(transcriptInput.value);
});

document.querySelector(".sample-button").addEventListener("click", () => {
  transcriptInput.value = marketSelect.value === "PH"
    ? "Magandang araw po. I need info sa premium ng policy at coverage."
    : "Halo Kak, cicilan saya jatuh tempo kapan? Bisa jelasin tenor pembiayaan?";
  transcriptInput.focus();
});

micButton.addEventListener("click", configureMicrophone);
endButton.addEventListener("click", endSession);

async function endSession() {
  if (recognition) {
    try { recognition.stop(); } catch (error) {}
    recognition = null;
  }
  if (sessionId) {
    await fetch(`/api/v1/localization/sessions/${encodeURIComponent(sessionId)}`, { method: "DELETE" }).catch(() => {});
  }
  sessionId = newSessionId();
  transcriptFeed.replaceChildren();
  for (const id of ["detected-language", "detected-register", "code-switch", "language-confidence", "grounding", "detected-terms"]) {
    document.getElementById(id).textContent = "—";
  }
  setStatus("READY");
}

loadMarkets().catch(error => {
  addMessage("system", error.message);
  setStatus("ERROR");
});