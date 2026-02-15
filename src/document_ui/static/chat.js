const chatForm = document.getElementById("chat-form");
const chatInput = document.getElementById("chat-input");
const sendButton = document.getElementById("chat-send");
const chatMessages = document.getElementById("chat-messages");
const chatError = document.getElementById("chat-error");

const PLACEHOLDER_SEARCHING = "Searching documents...";
const PLACEHOLDER_THINKING = "Generating answer...";

const escapeHtml = (str) => {
  const div = document.createElement("div");
  div.textContent = str == null ? "" : str;
  return div.innerHTML;
};

/** Markdown to HTML: bold, bullets (- * •), subheadings (# ## ###), paragraphs. Escapes HTML first. */
const simpleMarkdownToHtml = (text) => {
  if (!text || !String(text).trim()) return "";
  let s = escapeHtml(String(text));
  s = s.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  const lines = s.split("\n");
  const out = [];
  let inList = false;
  for (let i = 0; i < lines.length; i++) {
    const raw = lines[i];
    const trimmed = raw.trim();
    // Sub headings: # ## ### (map to h2, h3, h4)
    const headingMatch = /^(#{1,3})\s+(.+)$/.exec(trimmed);
    if (headingMatch) {
      if (inList) {
        out.push("</ul>");
        inList = false;
      }
      const level = Math.min(headingMatch[1].length + 1, 4);
      out.push("<h" + level + " class=\"chat-heading\">" + headingMatch[2] + "</h" + level + ">");
      continue;
    }
    // Bullets: - item, * item, • item (optional leading space)
    const bulletMatch = /^[-*•]\s+(.+)$/.exec(trimmed) || /^\d+\.\s+(.+)$/.exec(trimmed);
    if (bulletMatch) {
      if (!inList) {
        out.push("<ul class=\"chat-list\">");
        inList = true;
      }
      out.push("<li>" + bulletMatch[1] + "</li>");
      continue;
    }
    // Normal paragraph (including empty line to close list)
    if (inList) {
      out.push("</ul>");
      inList = false;
    }
    if (trimmed) out.push("<p>" + trimmed + "</p>");
  }
  if (inList) out.push("</ul>");
  return out.length ? out.join("") : "<p>" + s + "</p>";
};

const renderMessage = (message, role) => {
  const bubble = document.createElement("article");
  bubble.className = `chat-message ${role}`;

  const content = document.createElement("p");
  content.textContent = message;
  bubble.appendChild(content);

  chatMessages.appendChild(bubble);
  chatMessages.scrollTop = chatMessages.scrollHeight;
};

const createAssistantBubble = (placeholderText = null) => {
  const bubble = document.createElement("article");
  bubble.className = "chat-message assistant";

  const content = document.createElement("div");
  content.className = "chat-message-body";
  if (placeholderText) {
    content.textContent = placeholderText;
    content.setAttribute("aria-busy", "true");
  }
  bubble.appendChild(content);
  chatMessages.appendChild(bubble);
  chatMessages.scrollTop = chatMessages.scrollHeight;

  return { bubble, content };
};

const renderAssistantMessage = (answer, sources = []) => {
  const { bubble, content } = createAssistantBubble();
  content.innerHTML = simpleMarkdownToHtml(answer);

  if (sources.length) {
    const sourceContainer = document.createElement("small");
    sourceContainer.className = "chat-sources";
    sourceContainer.textContent = `Sources: ${sources.map((s) => s.chunk_id).join(", ")}`;
    bubble.appendChild(sourceContainer);
  }
};

const loadChatHistory = async () => {
  const response = await fetch("/api/chat/history");
  if (!response.ok) {
    return;
  }

  const data = await response.json();
  const messages = data.messages || [];

  if (!messages.length) {
    renderAssistantMessage("Hi! Ask me anything about your uploaded files.");
    return;
  }

  messages.forEach((message) => {
    renderMessage(message.question, "user");
    renderAssistantMessage(message.answer, message.sources || []);
  });
};

const streamAnswer = async (question) => {
  const { bubble, content } = createAssistantBubble(PLACEHOLDER_SEARCHING);

  const response = await fetch("/api/chat/stream", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ question }),
  });

  if (!response.ok) {
    content.textContent = "";
    content.removeAttribute("aria-busy");
    const data = await response.json().catch(() => ({}));
    throw new Error(data.error || "Failed to generate answer.");
  }

  if (!response.body) {
    content.textContent = "";
    content.removeAttribute("aria-busy");
    throw new Error("Streaming response is not available in this browser.");
  }

  content.textContent = PLACEHOLDER_THINKING;
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffered = "";
  let fullAnswer = "";
  let firstChunk = true;

  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      break;
    }

    buffered += decoder.decode(value, { stream: true });
    const lines = buffered.split("\n");
    buffered = lines.pop() || "";

    for (const line of lines) {
      if (!line.trim()) continue;

      let event;
      try {
        event = JSON.parse(line);
      } catch (_) {
        continue;
      }

      if (event.type === "chunk") {
        if (firstChunk) {
          content.removeAttribute("aria-busy");
          firstChunk = false;
        }
        fullAnswer += event.content;
        content.textContent = fullAnswer;
        chatMessages.scrollTop = chatMessages.scrollHeight;
      } else if (event.type === "done") {
        content.removeAttribute("aria-busy");
        content.innerHTML = simpleMarkdownToHtml(fullAnswer);
        if (event.sources?.length) {
          const sourceContainer = document.createElement("small");
          sourceContainer.className = "chat-sources";
          sourceContainer.textContent = `Sources: ${event.sources.map((s) => s.chunk_id).join(", ")}`;
          bubble.appendChild(sourceContainer);
        }
        chatMessages.scrollTop = chatMessages.scrollHeight;
      } else if (event.type === "error") {
        content.removeAttribute("aria-busy");
        throw new Error(event.error || "Failed to stream answer.");
      }
    }
  }

  if (content.getAttribute("aria-busy") === "true") {
    content.removeAttribute("aria-busy");
    if (fullAnswer) content.innerHTML = simpleMarkdownToHtml(fullAnswer);
  }
};

chatForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const question = chatInput.value.trim();
  if (!question) {
    return;
  }

  chatError.classList.add("hidden");
  chatError.textContent = "";
  renderMessage(question, "user");

  sendButton.disabled = true;
  chatInput.disabled = true;
  chatInput.value = "";

  try {
    await streamAnswer(question);
  } catch (error) {
    chatError.classList.remove("hidden");
    chatError.textContent = error.message;
  } finally {
    sendButton.disabled = false;
    chatInput.disabled = false;
    chatInput.focus();
  }
});

loadChatHistory();
