/* ============================================================
   LE RÊVE PROPERTIES — SHARED FRONTEND HELPERS
   ============================================================ */
(function () {
  'use strict';

  const cfg = window.LeReveConfig || {};

  const LeReve = {

    // ---------- Config accessors ----------
    csrf:  () => cfg.csrf || '',
    currency: () => cfg.currency || '₵',
    isLoggedIn: () => !!cfg.isLoggedIn,
    isAdmin:    () => !!cfg.isAdmin,
    user:       () => cfg.user || {},

    // ---------- Safety ----------
    escapeHtml(str) {
      return String(str ?? '').replace(/[&<>"']/g, m => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
      }[m]));
    },

    // ---------- Formatting ----------
    formatCurrency(n, symbol) {
      const num = Number(n) || 0;
      const sym = symbol || LeReve.currency();
      return sym + num.toLocaleString('en-GH', { minimumFractionDigits: 0, maximumFractionDigits: 0 });
    },

    // ---------- Toast ----------
    toast(msg, type = 'success') {
      const container = document.getElementById('toastContainer')
                     || document.getElementById('clientToast')
                     || document.getElementById('adminToast');
      if (!container) { console.log(msg); return; }

      const colors = {
        success: 'bg-primary text-gold border-gold',
        error:   'bg-red-600 text-white border-red-400',
        info:    'bg-gold text-primary border-primary',
      };
      const icons = {
        success: 'fa-circle-check',
        error:   'fa-circle-exclamation',
        info:    'fa-circle-info',
      };

      const t = document.createElement('div');
      t.className = `pointer-events-auto flex items-center gap-3 px-5 py-3.5 rounded-2xl border shadow-2xl text-xs font-semibold animate-slide-in ${colors[type] || colors.success}`;
      t.innerHTML = `<i class="fa-solid ${icons[type] || icons.success} text-lg"></i><span>${LeReve.escapeHtml(msg)}</span>`;
      container.appendChild(t);

      setTimeout(() => {
        t.classList.add('opacity-0', 'transition-opacity', 'duration-300');
        setTimeout(() => t.remove(), 300);
      }, 4000);
    },

    // ---------- Password toggle ----------
    togglePassword(inputId, iconId) {
      const input = document.getElementById(inputId);
      const icon = document.getElementById(iconId);
      if (!input || !icon) return;
      if (input.type === 'password') {
        input.type = 'text';
        icon.className = 'fa-regular fa-eye-slash';
      } else {
        input.type = 'password';
        icon.className = 'fa-regular fa-eye';
      }
      input.focus();
    },

    // ---------- Sidebar ----------
    toggleSidebar() {
      const sb = document.getElementById('sidebar');
      const ov = document.getElementById('sidebarOverlay');
      const btn = document.getElementById('sidebarToggleBtn');
      if (!sb || !ov) return;
      const isOpen = sb.classList.toggle('open');
      ov.classList.toggle('hidden', !isOpen);
      if (btn) btn.setAttribute('aria-expanded', String(isOpen));
    },

    closeSidebar() {
      const sb = document.getElementById('sidebar');
      const ov = document.getElementById('sidebarOverlay');
      if (!sb || !ov) return;
      sb.classList.remove('open');
      ov.classList.add('hidden');
    },

    // ---------- Scroll ----------
    scrollToBottom(elementId, smooth) {
      const el = document.getElementById(elementId);
      if (!el) return;
      if (smooth) el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' });
      else el.scrollTop = el.scrollHeight;
    },

    // ---------- Modal helpers ----------
    openModal(el) {
      if (!el) return;
      el.classList.remove('hidden');
      el.classList.add('flex');
      document.body.classList.add('modal-open');
    },
    closeModal(el) {
      if (!el) return;
      el.classList.add('hidden');
      el.classList.remove('flex');
      document.body.classList.remove('modal-open');
    },

    // ---------- HTTP ----------
    async postJSON(url, data) {
      const res = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': LeReve.csrf(),
        },
        body: JSON.stringify(data || {}),
      });
      return res.json();
    },
  };

  // Global escapes
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') LeReve.closeSidebar();
  });
  document.addEventListener('click', (e) => {
    const link = e.target.closest('.sidebar-link');
    if (link && window.innerWidth < 1024) LeReve.closeSidebar();
  });
  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.flash-msg').forEach(el => {
      setTimeout(() => {
        el.classList.add('opacity-0', 'transition-opacity', 'duration-500');
        setTimeout(() => el.remove(), 500);
      }, 6000);
    });
  });

  window.LeReve = LeReve;
})();