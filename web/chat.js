const chatArea = document.getElementById("chatArea");
const chatForm = document.getElementById("chatForm");
const userInput = document.getElementById("userInput");
const sendBtn = document.getElementById("sendBtn");
const pincodeInput = document.getElementById("pincodeInput");

const SLOW_NOTICE_MS = 4000;
const DISCLAIMER_STARTS = ["I provide health AWARENESS", "मैं केवल सत्यापित स्रोतों"];

let sessionId = null;
try {
  sessionId = localStorage.getItem("aarogya_session");
} catch (e) {}
if (!sessionId) {
  sessionId = "s-" + Date.now().toString(36) + "-" + Math.random().toString(36).slice(2, 10);
  try {
    localStorage.setItem("aarogya_session", sessionId);
  } catch (e) {}
}

function scrollBottom() {
  chatArea.scrollTop = chatArea.scrollHeight;
}

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

// Split a reply into the answer, its source list and the standard disclaimer.
function parseReply(text) {
  const lines = String(text || "").split("\n");
  const body = [];
  let sources = [];
  let disclaimer = "";
  for (const line of lines) {
    const trimmed = line.trim();
    if (/^Sources?:/i.test(trimmed)) {
      sources = trimmed
        .replace(/^Sources?:/i, "")
        .split(/,(?![^(]*\))/)
        .map((s) => s.trim())
        .filter(Boolean);
    } else if (DISCLAIMER_STARTS.some((p) => trimmed.startsWith(p))) {
      disclaimer = trimmed;
    } else {
      body.push(line);
    }
  }
  return { body: body.join("\n").trim(), sources, disclaimer };
}

function routeLabel(d) {
  if (d.intent === "emergency") return "Safety rule, no LLM";
  if (d.factcheck) return "Fact check against curated myths";
  if (d.generator === "llm") return "LLM, answering from the retrieved entry";
  if (d.generator === "template") return "Template answer, no LLM";
  if (d.intent === "fallback") return "Out of scope, politely declined";
  if (d.flow && String(d.flow).startsWith("symptom")) return "Symptom flow, follow-up question";
  return "Rule-based reply";
}

function languageLabel(code) {
  const map = { en: "English", hi: "Hindi / Hinglish" };
  return map[code] || (code ? String(code).toUpperCase() : "unknown");
}

function timeLabel(ms) {
  if (typeof ms !== "number") return "n/a";
  if (ms < 100) return "under 0.1 s";
  return (ms / 1000).toFixed(1) + " s";
}

function buildTrace(d) {
  const details = el("details", "trace");
  details.appendChild(el("summary", "", "How this answer was made"));
  const grid = el("dl", "trace-grid");
  const rows = [
    ["Language", languageLabel(d.language)],
    ["Intent", String(d.intent || "unknown").replace(/_/g, " ")],
    ["Route", routeLabel(d)],
  ];
  if (d.factcheck && typeof d.factcheck.confidence === "number") {
    rows.push(["Confidence", d.factcheck.confidence.toFixed(0) + "%"]);
  }
  rows.push(["Time", timeLabel(d.latency_ms)]);
  for (const [k, v] of rows) {
    grid.appendChild(el("dt", "", k));
    grid.appendChild(el("dd", "", v));
  }
  details.appendChild(grid);
  return details;
}

function addUser(text) {
  const wrap = el("div", "msg user");
  wrap.appendChild(el("div", "bubble", text));
  wrap.appendChild(el("div", "meta", "You"));
  chatArea.appendChild(wrap);
  scrollBottom();
}

function addBot(data) {
  const parsed = parseReply(data.reply || "Sorry, something went wrong.");
  const wrap = el("div", "msg bot");
  const bubble = el("div", "bubble");

  const verdict = data.factcheck ? data.factcheck.verdict : null;
  if (verdict) {
    const badge = el("span", "verdict-badge verdict-" + verdict);
    badge.textContent = verdict + (data.factcheck.fear_mongering ? " (context)" : "");
    bubble.appendChild(badge);
    bubble.appendChild(document.createElement("br"));
  }
  bubble.appendChild(document.createTextNode(parsed.body));

  if (parsed.sources.length) {
    const list = el("div", "sources");
    for (const s of parsed.sources) list.appendChild(el("span", "source-chip", s));
    bubble.appendChild(list);
  }
  if (parsed.disclaimer) bubble.appendChild(el("div", "disclaimer-line", parsed.disclaimer));
  wrap.appendChild(bubble);

  if (data.intent && data.intent !== "greeting") wrap.appendChild(buildTrace(data));
  chatArea.appendChild(wrap);
  scrollBottom();
}

function addTyping() {
  const wrap = el("div", "msg bot typing");
  const bubble = el("div", "bubble");
  const dots = el("span", "dots");
  for (let i = 0; i < 3; i++) dots.appendChild(document.createElement("i"));
  bubble.appendChild(dots);
  wrap.appendChild(bubble);
  chatArea.appendChild(wrap);
  scrollBottom();
  const timer = setTimeout(() => {
    bubble.textContent = "Still working. Written answers can take up to 20 seconds on this small free server.";
    scrollBottom();
  }, SLOW_NOTICE_MS);
  return { remove: () => { clearTimeout(timer); wrap.remove(); } };
}

async function postChat(message) {
  const res = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, session_id: sessionId, pincode: pincodeInput.value.trim() || null }),
  });
  if (!res.ok) throw new Error("HTTP " + res.status);
  return res.json();
}

let busy = false;

async function sendMessage(text) {
  const msg = String(text || "").trim();
  if (!msg || busy) return;
  busy = true;
  addUser(msg);
  userInput.value = "";
  sendBtn.disabled = true;
  const typing = addTyping();
  try {
    const data = await postChat(msg);
    typing.remove();
    addBot(data);
  } catch (err) {
    typing.remove();
    addBot({ reply: "The server didn't respond. Please try again in a moment.", intent: "error" });
  } finally {
    busy = false;
    sendBtn.disabled = false;
    userInput.focus({ preventScroll: true });
  }
}

function askFromPage(message) {
  const chat = document.getElementById("chat");
  if (window.innerWidth <= 960) chat.scrollIntoView({ behavior: "smooth", block: "start" });
  sendMessage(message);
}

document.addEventListener("click", (e) => {
  const trigger = e.target.closest("[data-msg]");
  if (trigger) askFromPage(trigger.dataset.msg);
});

chatForm.addEventListener("submit", (e) => {
  e.preventDefault();
  sendMessage(userInput.value);
});

// The server prepends its long welcome to a session's first reply, so the session is
// greeted quietly here. The page shows its own short opening bubble instead of a
// visible "hi" from the user.
(async function boot() {
  try {
    await postChat("hi");
  } catch (e) {}
})();
