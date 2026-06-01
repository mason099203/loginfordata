function initChat(config) {
  const box = document.getElementById("chat-messages");
  const form = document.getElementById("chat-form");
  const input = document.getElementById("chat-input");
  if (!box || !form || !input) return;

  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  let wsPath = `${protocol}//${window.location.host}/ws/chat/${config.roomType}`;
  if (config.roomId) {
    wsPath += `/${config.roomId}`;
  }
  const ws = new WebSocket(wsPath);

  function appendMessage(msg) {
    const div = document.createElement("div");
    div.className = "chat-message";
    const time = new Date(msg.created_at).toLocaleString("zh-TW");
    div.innerHTML = `<div class="meta"><strong>${escapeHtml(msg.sender_name)}</strong> · ${time}</div><div>${escapeHtml(msg.content)}</div>`;
    box.appendChild(div);
    box.scrollTop = box.scrollHeight;
  }

  function escapeHtml(text) {
    const el = document.createElement("div");
    el.textContent = text;
    return el.innerHTML;
  }

  ws.onmessage = (event) => {
    appendMessage(JSON.parse(event.data));
  };

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const content = input.value.trim();
    if (!content || ws.readyState !== WebSocket.OPEN) return;
    ws.send(JSON.stringify({ content }));
    input.value = "";
  });
}

document.addEventListener("DOMContentLoaded", () => {
  const chatRoot = document.getElementById("chat-root");
  if (chatRoot) {
    initChat({
      roomType: chatRoot.dataset.roomType,
      roomId: chatRoot.dataset.roomId || null,
    });
  }
});
