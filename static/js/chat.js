/* ============================================================
   LE RÊVE — CHAT (client-side polling + send)
   ============================================================ */
(function () {
  'use strict';

  const C = window.LeReve;

  function buildBubble({ text, from, timestamp }) {
    const isMe = from === 'me';
    const wrap = document.createElement('div');
    wrap.className = `flex ${isMe ? 'justify-end' : 'justify-start'} animate-fade-in`;
    if (timestamp) wrap.dataset.ts = timestamp;

    const inner = document.createElement('div');
    inner.className = 'max-w-[80%] sm:max-w-[70%]';

    if (!isMe) {
      const label = document.createElement('div');
      label.className = 'flex items-center gap-2 mb-1';
      label.innerHTML = `
        <div class="w-6 h-6 rounded-full bg-primary text-gold flex items-center justify-center text-[10px]">
          <i class="fa-solid fa-bell-concierge"></i>
        </div>
        <span class="text-[11px] font-semibold text-primary">Concierge</span>`;
      inner.appendChild(label);
    }

    const bubble = document.createElement('div');
    bubble.className = isMe
      ? 'bg-primary text-ivory rounded-2xl px-4 py-3 shadow-sm'
      : 'bg-white text-charcoal border border-gold/20 rounded-2xl px-4 py-3 shadow-sm';
    const p = document.createElement('p');
    p.className = 'text-sm leading-relaxed whitespace-pre-wrap break-words';
    p.textContent = text;
    bubble.appendChild(p);

    const time = document.createElement('p');
    time.className = `text-[10px] text-charcoal/40 mt-1 ${isMe ? 'text-right' : ''}`;
    time.textContent = new Date().toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });

    inner.appendChild(bubble);
    inner.appendChild(time);
    wrap.appendChild(inner);
    return wrap;
  }

  window.LeReve.initChat = function (opts) {
    const chatBox = document.getElementById('chatMessages');
    const form = document.getElementById('chatForm');
    const input = document.getElementById('chatInput');
    const sendBtn = document.getElementById('sendBtn');
    if (!chatBox || !form || !input || !sendBtn) return;

    C.scrollToBottom('chatMessages');

    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const text = input.value.trim();
      if (!text) return;

      document.getElementById('emptyChat')?.remove();

      const original = sendBtn.innerHTML;
      sendBtn.disabled = true;
      sendBtn.classList.add('opacity-60','cursor-wait');
      sendBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i>';

      input.value = '';

      try {
        const data = await C.postJSON(opts.sendUrl, { text });
        if (!data.success) {
          input.value = text;
          C.toast(data.error || 'Send failed', 'error');
          return;
        }
        chatBox.appendChild(buildBubble({ text, from: 'me', timestamp: new Date().toISOString() }));
        C.scrollToBottom('chatMessages', true);
      } catch (e) {
        input.value = text;
        C.toast('Network error', 'error');
      } finally {
        sendBtn.disabled = false;
        sendBtn.classList.remove('opacity-60','cursor-wait');
        sendBtn.innerHTML = original;
        input.focus();
      }
    });

    // Poll every 5s for new messages
    if (opts.pollUrl) {
      let lastTs = '';
      const last = chatBox.querySelector('[data-ts]:last-child');
      if (last) lastTs = last.dataset.ts || '';

      setInterval(async () => {
        try {
          const url = opts.pollUrl + (lastTs ? `?since=${encodeURIComponent(lastTs)}` : '');
          const res = await fetch(url, { credentials: 'same-origin' });
          if (!res.ok) return;
          const data = await res.json();
          if (!data.success || !data.messages) return;

          let appended = false;
          data.messages.forEach(m => {
            if (chatBox.querySelector(`[data-msg-id="${m.id}"]`)) return;
            const from = (opts.role === 'client' && m.sender === 'admin')
                       || (opts.role === 'admin'  && m.sender === 'client')
                       ? 'concierge' : 'me';
            chatBox.appendChild(buildBubble({ text: m.text, from, timestamp: m.created_at }));
            appended = true;
            if (m.created_at > lastTs) lastTs = m.created_at;
          });
          if (appended) C.scrollToBottom('chatMessages', true);
        } catch (e) {}
      }, 5000);
    }
  };
})();