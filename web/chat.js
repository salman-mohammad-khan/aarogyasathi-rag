const chatArea = document.getElementById("chatArea");
const chatForm = document.getElementById("chatForm");
const userInput = document.getElementById("userInput");
const sendBtn = document.getElementById("sendBtn");

// A slow written answer shows what is happening instead of a bare spinner.
const SLOW_STAGES = [
  [3000, "Searching the health library…"],
  [7000, "Writing the answer from the official documents…"],
  [15000, "Still writing. This can take up to 20 seconds."],
];
// Instant answers (rules, myth matches) would appear before the eye can follow, so the
// typing indicator is shown for at least this long. Slower answers are not delayed further.
const MIN_REPLY_MS = 600;
const MAX_REPLY_MS = 1000;
const GREETING_DELAY_MS = 800;

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function replyDelay() {
  return MIN_REPLY_MS + Math.random() * (MAX_REPLY_MS - MIN_REPLY_MS);
}
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
  if (d.intent === "library_answer") {
    if (d.tier === "trusted_web") return "Not in the library; answered from a trusted health website, with its link";
    if (d.tier === "general") return "Not in the library or trusted websites; low-risk general information, labelled";
    if (d.flow === "not_covered") return "Not in the library or trusted websites, so no answer was made up";
    if (d.flow === "dose_removed") return "Library answer (medicine amounts removed for safety)";
    if (d.flow === "medicine_choice") return "Choosing a medicine is a doctor's job, so the bot refers you";
    if (d.flow === "error") return "The answer model did not respond";
    return "Answered from the official health library, with citations";
  }
  if (d.intent === "guard") return "Instruction override blocked by a rule";
  if (d.intent === "emergency" && d.flow === "llm_safety") return "Safety check by the model (the word rules found nothing)";
  if (d.intent === "emergency" && d.flow === "emergency_first_aid") return "Safety rule first, then cited first aid from the library";
  if (d.intent === "emergency") return "Safety rule, no LLM";
  if (d.factcheck) {
    const basis = {
      curated: "Fact check: matched a curated, human-checked myth",
      library: "Fact check against the official health library, with citations",
      trusted_web: "Fact check against a trusted health website",
      general: "Fact check: no source found; cautious general view, labelled",
      none: "Fact check: no evidence found in any source",
    }[d.factcheck.basis];
    return basis || "Fact check against curated myths";
  }
  if (d.intent === "greeting") return "Greeting";
  return "Rule-based reply";
}

function languageLabel(code) {
  const map = { en: "English", hi: "Hindi", hinglish: "Hinglish" };
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

// Answer models write light Markdown ("*   point", "**bold**"); the bubble shows plain text, so turn list markers
// into bullets, drop the bold markers and collapse runs of blank lines.
function tidyMarkdown(text) {
  return String(text)
    .replace(/^[ \t]*[*\-•][ \t]+/gm, "• ")
    .replace(/\*\*(.+?)\*\*/g, "$1")
    .replace(/[ \t]+$/gm, "")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

// Where a v2 answer came from (S4b). Shown on top of the answer so the user knows how far to trust it.
const TIER_LABELS = {
  library: "From the official health library",
  trusted_web: "From a trusted health website (not my library)",
  general: "General information, not from a verified source",
};

// v2 answers cite numbered sources: "[1] National Guidelines for Dengue 2023, page 47" with a link to the PDF.
function buildCitations(sources) {
  const box = el("div", "citations");
  box.appendChild(el("div", "citations-title", "Sources"));
  const list = el("ol", "citations-list");
  const seen = new Set(); // a web page cited as [1]..[4] is listed once
  for (const s of sources) {
    const key = s.url + "|" + (s.page || "");
    if (seen.has(key)) continue;
    seen.add(key);
    const item = el("li");
    item.value = s.n;
    const label = s.title + (s.page ? ", page " + s.page : "");
    if (typeof s.url === "string" && s.url.startsWith("https://")) {
      const link = el("a", "", label);
      link.href = s.url + (s.url.toLowerCase().endsWith(".pdf") && s.page ? "#page=" + s.page : "");
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      item.appendChild(link);
    } else {
      item.textContent = label;
    }
    if (s.publisher) item.appendChild(el("span", "citation-publisher", " (" + s.publisher + ")"));
    list.appendChild(item);
  }
  box.appendChild(list);
  return box;
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
    // Labels can contain spaces ("PARTLY TRUE"), which would split into two CSS classes; use underscores.
    const badge = el("span", "verdict-badge verdict-" + String(verdict).replace(/\s+/g, "_"));
    badge.textContent = verdict + (data.factcheck.fear_mongering ? " (context)" : "");
    bubble.appendChild(badge);
    bubble.appendChild(document.createElement("br"));
  }
  const tier = TIER_LABELS[data.tier];
  if (tier) bubble.appendChild(el("div", "tier-label tier-" + data.tier, tier));
  bubble.appendChild(document.createTextNode(tidyMarkdown(parsed.body)));

  if (Array.isArray(data.sources) && data.sources.length) {
    bubble.appendChild(buildCitations(data.sources));
  } else if (parsed.sources.length) {
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
  const timers = SLOW_STAGES.map(([ms, text]) =>
    setTimeout(() => {
      bubble.textContent = text;
      scrollBottom();
    }, ms)
  );
  return { remove: () => { timers.forEach(clearTimeout); wrap.remove(); } };
}

async function postChat(message) {
  const res = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, session_id: sessionId }),
  });
  if (!res.ok) throw new Error("HTTP " + res.status);
  return res.json();
}

let busy = false;
let bootDone = Promise.resolve();

async function sendMessage(text) {
  const msg = String(text || "").trim();
  if (!msg || busy) return;
  busy = true;
  addUser(msg);
  userInput.value = "";
  sendBtn.disabled = true;
  const startedAt = Date.now();
  const typing = addTyping();
  try {
    await bootDone;
    const data = await postChat(msg);
    const remaining = replyDelay() - (Date.now() - startedAt);
    if (remaining > 0) await sleep(remaining);
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

// The v1 server prepended a long welcome to a session's first reply in each language, so the page used to send
// two quiet greetings at load. v2 does not, and those two calls are no longer made.

// The opening greeting appears after a short typing indicator, like every other reply.
(function openingGreeting() {
  const first = chatArea.querySelector(".msg.bot");
  if (!first) return;
  first.remove();
  const typing = addTyping();
  setTimeout(() => {
    typing.remove();
    chatArea.insertBefore(first, chatArea.firstChild);
    scrollBottom();
  }, GREETING_DELAY_MS);
})();
