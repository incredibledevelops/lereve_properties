/* ============================================================
   LE RÊVE — BOOKING MODAL (Paystack flow)
   Shared by index.html and stays.html.

   This module is self-contained: it doesn't assume the base.html
   globals are on `window`. It uses safe accessors that fall back
   to `LeReve.*` and, finally, to plain DOM operations.

   Public API (attached to window.LeReve):
     - configureBooking(opts)
     - openBookingModal(prop)
     - renderBookingForm(prop)
     - switchToGuestInquiry(prop)
   ============================================================ */
(function () {
  'use strict';

  const C = window.LeReve || (window.LeReve = {});

  /* ---------- Config (set by the page before init) ---------- */
  const config = {
    paystackInitUrl:     '/paystack/initialize',
    paystackCallbackUrl: '/paystack/callback',
    loginUrl:            '/login',
    registerUrl:         '/register',
    inquiryUrl:          '/api/inquiries',
  };

  C.configureBooking = function (opts) {
    Object.assign(config, opts || {});
  };

  /* ============================================================
     SAFE ACCESSORS for the base.html globals
     ------------------------------------------------------------
     Each one tries, in order:
       1. window.<name>          (if base.html exposes it)
       2. LeReve.<method>        (if shared.js provides it)
       3. inline fallback        (so this script never throws)
     ============================================================ */

  function g_isLoggedIn() {
    if (typeof window.IS_LOGGED_IN === 'boolean') return window.IS_LOGGED_IN;
    if (window.IS_LOGGED_IN === 'true')           return true;
    if (window.IS_LOGGED_IN === 'false')          return false;
    if (C.isLoggedIn && typeof C.isLoggedIn === 'function') return !!C.isLoggedIn();
    return false;
  }

  function g_isAdmin() {
    if (typeof window.IS_ADMIN === 'boolean') return window.IS_ADMIN;
    if (window.IS_ADMIN === 'true')           return true;
    if (window.IS_ADMIN === 'false')          return false;
    if (C.isAdmin && typeof C.isAdmin === 'function') return !!C.isAdmin();
    return false;
  }

  function g_toast(msg, type) {
    if (typeof window.showToast === 'function') {
      window.showToast(msg, type);
      return;
    }
    if (C.toast && typeof C.toast === 'function') {
      C.toast(msg, type);
      return;
    }
    // Last-resort: console only (never throws)
    console.log('[toast ' + (type || 'info') + '] ' + msg);
  }

  function g_esc(s) {
    if (typeof window.escapeHtml === 'function') return window.escapeHtml(s);
    if (C.escapeHtml && typeof C.escapeHtml === 'function') return C.escapeHtml(s);
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function g_money(n) {
    if (typeof window.formatGHS === 'function') return window.formatGHS(n);
    if (C.formatCurrency && typeof C.formatCurrency === 'function') {
      return C.formatCurrency(n);
    }
    const sym = window.CURRENCY_SYMBOL || '₵';
    const num = Number(n) || 0;
    return sym + num.toLocaleString('en-GH', {
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    });
  }

  function g_openModal(el) {
    if (typeof window.openModal === 'function') return window.openModal(el);
    if (!el) return;
    el.classList.remove('hidden');
    el.classList.add('flex');
    document.body.classList.add('modal-open');
  }

  function g_closeModal(el) {
    if (typeof window.closeModal === 'function') return window.closeModal(el);
    if (!el) return;
    el.classList.add('hidden');
    el.classList.remove('flex');
    document.body.classList.remove('modal-open');
  }

  function g_csrf() {
    if (window.CSRF_TOKEN) return window.CSRF_TOKEN;
    if (typeof window.LeReveConfig !== 'undefined' && window.LeReveConfig.csrf) {
      return window.LeReveConfig.csrf;
    }
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.content : '';
  }

  /* ============================================================
     BOOKING MODAL — entry point
     ============================================================ */
  C.openBookingModal = function (prop) {
    if (!prop) { g_toast('Property not found.', 'error'); return; }

    if (g_isAdmin()) {
      g_toast('Admins cannot book via the guest portal.', 'info');
      return;
    }

    const modal = document.getElementById('bookingModal');
    if (!modal) {
      g_toast('Booking is temporarily unavailable.', 'error');
      return;
    }

    if (!g_isLoggedIn()) {
      renderSignInPrompt(prop);
    } else {
      renderBookingForm(prop);
    }
    g_openModal(modal);
  };

  /* ============================================================
     SIGN-IN PROMPT
     ============================================================ */
  function renderSignInPrompt(prop) {
    const host = document.getElementById('bookingModalContent');
    host.innerHTML = `
      <div class="p-8 sm:p-10 text-center">
        <div class="w-16 h-16 mx-auto rounded-full bg-gold/15 text-gold flex items-center justify-center mb-4">
          <i class="fa-solid fa-lock text-2xl" aria-hidden="true"></i>
        </div>
        <h3 class="font-serif text-3xl font-semibold text-primary mb-2">Sign In to Book</h3>
        <p class="text-sm text-charcoal/70 mb-6 max-w-sm mx-auto">
          Create a free account or sign in to reserve
          <strong>${g_esc(prop.title)}</strong>.
          Payment is handled securely by Paystack.
        </p>
        <div class="flex flex-col sm:flex-row gap-3">
          <a href="${config.loginUrl}"
             class="flex-1 bg-primary text-gold hover:bg-gold hover:text-primary px-6 py-3.5 rounded-xl
                    text-xs font-bold uppercase tracking-widest transition-all">
            <i class="fa-solid fa-right-to-bracket mr-1" aria-hidden="true"></i> Sign In
          </a>
          <a href="${config.registerUrl}"
             class="flex-1 bg-gold text-primary hover:bg-primary hover:text-gold px-6 py-3.5 rounded-xl
                    text-xs font-bold uppercase tracking-widest transition-all">
            <i class="fa-solid fa-user-plus mr-1" aria-hidden="true"></i> Create Account
          </a>
        </div>
        <p class="text-[10px] text-charcoal/40 mt-5">
          Or <button type="button" data-action="guest-inquiry"
                     class="text-gold hover:underline font-semibold">
              submit a guest inquiry without an account
          </button>
        </p>
      </div>`;

    host.querySelector('[data-action="guest-inquiry"]')
        ?.addEventListener('click', () => C.switchToGuestInquiry(prop));
  }

  /* ============================================================
     PAYMENT FORM
     ============================================================ */
  C.renderBookingForm = renderBookingForm;

  function renderBookingForm(prop) {
    const today    = new Date().toISOString().split('T')[0];
    const tomorrow = new Date(Date.now() + 86400000).toISOString().split('T')[0];
    const perNight = Number(prop.price) || 0;
    const host     = document.getElementById('bookingModalContent');

    host.innerHTML = `
      <div class="p-6 sm:p-8">
        <div class="flex items-start gap-4 mb-6">
          <div class="w-16 h-16 rounded-xl border border-gold/30 flex-shrink-0 bg-primary-dark overflow-hidden">
            <img src="${g_esc(prop.image)}" alt="" class="w-full h-full object-cover">
          </div>
          <div class="min-w-0">
            <span class="text-[10px] uppercase tracking-widest text-gold font-bold">Reserve &amp; Pay</span>
            <h3 class="font-serif text-2xl font-semibold text-primary leading-tight mt-1">
              ${g_esc(prop.title)}
            </h3>
            <p class="text-xs text-charcoal/60 mt-0.5">
              <i class="fa-solid fa-location-dot text-gold mr-1" aria-hidden="true"></i>
              ${g_esc(prop.location)}
            </p>
          </div>
        </div>

        <div class="p-3 rounded-xl bg-ivory border border-gold/20 mb-5 flex items-center justify-between">
          <span class="text-xs text-charcoal/60">Nightly rate</span>
          <span class="font-serif text-lg font-bold text-primary">${g_money(perNight)}</span>
        </div>

        <form id="bookingPayForm" class="space-y-4" novalidate>
          <input type="hidden" name="property_id" value="${g_esc(prop.id)}">

          <div class="grid grid-cols-2 gap-4">
            <div>
              <label for="bookCheckIn"
                     class="block text-xs font-bold uppercase tracking-wider text-primary/80 mb-1">
                Check-In *
              </label>
              <input type="date" id="bookCheckIn" name="check_in" required
                     min="${today}" value="${tomorrow}"
                     class="w-full px-4 py-2.5 rounded-xl border border-charcoal/15 bg-ivory/40
                            focus:bg-white focus:outline-none focus:ring-2 focus:ring-gold text-sm">
            </div>
            <div>
              <label for="bookCheckOut"
                     class="block text-xs font-bold uppercase tracking-wider text-primary/80 mb-1">
                Check-Out *
              </label>
              <input type="date" id="bookCheckOut" name="check_out" required
                     min="${tomorrow}"
                     class="w-full px-4 py-2.5 rounded-xl border border-charcoal/15 bg-ivory/40
                            focus:bg-white focus:outline-none focus:ring-2 focus:ring-gold text-sm">
            </div>
          </div>

          <div>
            <label for="bookGuests"
                   class="block text-xs font-bold uppercase tracking-wider text-primary/80 mb-1">
              Guests
            </label>
            <select id="bookGuests" name="guests"
                    class="w-full px-4 py-2.5 rounded-xl border border-charcoal/15 bg-ivory/40
                           focus:bg-white focus:outline-none focus:ring-2 focus:ring-gold text-sm">
              <option value="1-2 Guests">1-2 Guests</option>
              <option value="3-5 Guests">3-5 Guests</option>
              <option value="6-10 Guests">6-10 Guests</option>
              <option value="10+ Guests">10+ Guests (Private Charter)</option>
            </select>
          </div>

          <div class="p-4 rounded-2xl bg-primary text-ivory">
            <div class="flex items-center justify-between text-sm">
              <span class="text-ivory/70">Nights</span>
              <span id="summaryNights" class="font-semibold">—</span>
            </div>
            <div class="flex items-center justify-between text-sm mt-1.5">
              <span class="text-ivory/70">Subtotal</span>
              <span id="summarySubtotal" class="font-semibold">—</span>
            </div>
            <div class="flex items-center justify-between pt-3 mt-3 border-t border-gold/20">
              <span class="text-sm font-bold text-gold uppercase tracking-wider">Total</span>
              <span id="summaryTotal" class="font-serif text-2xl font-bold text-gold">—</span>
            </div>
          </div>

          <p class="text-[11px] text-charcoal/60 flex items-start gap-1.5">
            <i class="fa-solid fa-shield-halved text-gold mt-0.5" aria-hidden="true"></i>
            <span>
              You'll be redirected to <strong>Paystack</strong> to complete payment securely.
              Your reservation is confirmed once payment succeeds.
            </span>
          </p>

          <button type="submit" id="payNowBtn"
                  class="w-full bg-gold text-primary hover:bg-primary hover:text-gold
                         py-3.5 rounded-xl font-bold uppercase tracking-widest text-xs
                         focus:outline-none focus-visible:ring-2 focus-visible:ring-gold
                         transition-all shadow-luxury flex items-center justify-center gap-2
                         disabled:opacity-60 disabled:cursor-wait">
            <i class="fa-solid fa-lock" aria-hidden="true"></i>
            <span>Pay with Paystack</span>
          </button>

          <p class="text-[10px] text-center text-charcoal/50">
            Or <button type="button" data-action="guest-inquiry"
                       class="text-gold hover:underline font-semibold">
                ask a question first
            </button> without paying.
          </p>
        </form>
      </div>`;

    host.querySelector('[data-action="guest-inquiry"]')
        ?.addEventListener('click', () => C.switchToGuestInquiry(prop));

    /* ---- Dynamic summary ---- */
    const form      = host.querySelector('#bookingPayForm');
    const checkIn   = host.querySelector('#bookCheckIn');
    const checkOut  = host.querySelector('#bookCheckOut');
    const guestsEl  = host.querySelector('#bookGuests');
    const nightsEl  = host.querySelector('#summaryNights');
    const subEl     = host.querySelector('#summarySubtotal');
    const totalEl   = host.querySelector('#summaryTotal');
    const payBtn    = host.querySelector('#payNowBtn');

    function recalc() {
      const ci = checkIn.value;
      const co = checkOut.value;
      if (!ci || !co) {
        nightsEl.textContent = subEl.textContent = totalEl.textContent = '—';
        return;
      }
      const nights = Math.round((new Date(co) - new Date(ci)) / 86400000);
      if (nights < 1) {
        nightsEl.textContent = subEl.textContent = totalEl.textContent = '—';
        return;
      }
      const sub = nights * perNight;
      nightsEl.textContent = `${nights} night${nights === 1 ? '' : 's'}`;
      subEl.textContent    = g_money(sub);
      totalEl.textContent  = g_money(sub);
    }

    checkIn.addEventListener('change', () => {
      if (checkIn.value) {
        const next = new Date(checkIn.value);
        next.setDate(next.getDate() + 1);
        checkOut.min = next.toISOString().split('T')[0];
        if (checkOut.value && checkOut.value <= checkIn.value) {
          checkOut.value = checkOut.min;
        }
      }
      recalc();
    });
    checkOut.addEventListener('change', recalc);
    recalc();

    /* ---- Submit ---- */
    form.addEventListener('submit', async (e) => {
      e.preventDefault();

      const ci = checkIn.value;
      const co = checkOut.value;
      if (!ci || !co) {
        g_toast('Please select check-in and check-out dates.', 'error');
        return;
      }
      if (co <= ci) {
        g_toast('Check-out must be after check-in.', 'error');
        return;
      }

      const original = payBtn.innerHTML;
      payBtn.disabled = true;
      payBtn.innerHTML =
        '<i class="fa-solid fa-spinner fa-spin" aria-hidden="true"></i>' +
        '<span>Redirecting to Paystack…</span>';

      try {
        const res = await fetch(config.paystackInitUrl, {
          method: 'POST',
          credentials: 'same-origin',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': g_csrf(),
          },
          body: JSON.stringify({
            property_id: prop.id,
            check_in:    ci,
            check_out:   co,
            guests:      guestsEl.value,
          }),
        });

        const data = await res.json().catch(() => ({}));

        if (!res.ok || !data.success) {
          g_toast(
            data.error || 'Could not start payment. Please try again.',
            'error'
          );
          payBtn.disabled = false;
          payBtn.innerHTML = original;
          return;
        }

        window.location.href = data.authorization_url;
      } catch (err) {
        g_toast('Network error. Please try again.', 'error');
        payBtn.disabled = false;
        payBtn.innerHTML = original;
      }
    });
  }

  /* ============================================================
     GUEST INQUIRY FALLBACK
     ============================================================ */
  C.switchToGuestInquiry = switchToGuestInquiry;

  function switchToGuestInquiry(prop) {
    const host     = document.getElementById('bookingModalContent');
    const loggedIn = g_isLoggedIn();
    const user     = window.CURRENT_USER || (C.user && C.user()) || {};

    host.innerHTML = `
      <div class="p-6 sm:p-8">
        <div class="flex items-start gap-4 mb-6">
          <div class="w-16 h-16 rounded-xl border border-gold/30 flex-shrink-0 bg-primary-dark overflow-hidden">
            <img src="${g_esc(prop.image)}" alt="" class="w-full h-full object-cover">
          </div>
          <div class="min-w-0">
            <span class="text-[10px] uppercase tracking-widest text-gold font-bold">
              Ask About This Estate
            </span>
            <h3 class="font-serif text-2xl font-semibold text-primary leading-tight mt-1">
              ${g_esc(prop.title)}
            </h3>
            <p class="text-xs text-charcoal/60 mt-0.5">
              <i class="fa-solid fa-location-dot text-gold mr-1" aria-hidden="true"></i>
              ${g_esc(prop.location)}
            </p>
          </div>
        </div>

        <div class="p-3 rounded-xl bg-ivory border border-gold/20 mb-5 flex items-center justify-between">
          <span class="text-xs text-charcoal/60">Nightly rate</span>
          <span class="font-serif text-lg font-bold text-primary">${g_money(prop.price)}</span>
        </div>

        <form id="bookingInquiryForm" class="space-y-4" novalidate>
          <input type="hidden" name="property"    value="${g_esc(prop.title)}">
          <input type="hidden" name="property_id" value="${g_esc(prop.id)}">

          <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label for="bookingName"
                     class="block text-xs font-bold uppercase tracking-wider text-primary/80 mb-1">
                Full Name *
              </label>
              <input type="text" id="bookingName" name="name" required maxlength="120"
                     value="${g_esc(loggedIn ? (user.name || '') : '')}"
                     class="w-full px-4 py-2.5 rounded-xl border border-charcoal/15 bg-ivory/40
                            focus:bg-white focus:outline-none focus:ring-2 focus:ring-gold text-sm">
            </div>
            <div>
              <label for="bookingEmail"
                     class="block text-xs font-bold uppercase tracking-wider text-primary/80 mb-1">
                Email *
              </label>
              <input type="email" id="bookingEmail" name="email" required maxlength="200"
                     value="${g_esc(loggedIn ? (user.email || '') : '')}"
                     class="w-full px-4 py-2.5 rounded-xl border border-charcoal/15 bg-ivory/40
                            focus:bg-white focus:outline-none focus:ring-2 focus:ring-gold text-sm">
            </div>
          </div>

          <div>
            <label for="bookingPhone"
                   class="block text-xs font-bold uppercase tracking-wider text-primary/80 mb-1">
              Phone *
            </label>
            <input type="tel" id="bookingPhone" name="phone" required maxlength="40"
                   placeholder="+233 XX XXX XXXX"
                   class="w-full px-4 py-2.5 rounded-xl border border-charcoal/15 bg-ivory/40
                          focus:bg-white focus:outline-none focus:ring-2 focus:ring-gold text-sm">
          </div>

          <div>
            <label for="bookingMessage"
                   class="block text-xs font-bold uppercase tracking-wider text-primary/80 mb-1">
              Your Question
            </label>
            <textarea id="bookingMessage" name="message" rows="3" maxlength="2000"
                      placeholder="Tell us what you'd like to know..."
                      class="w-full px-4 py-2.5 rounded-xl border border-charcoal/15 bg-ivory/40
                             focus:bg-white focus:outline-none focus:ring-2 focus:ring-gold
                             text-sm resize-none"></textarea>
          </div>

          <button type="submit" id="bookingSubmitBtn"
                  class="w-full bg-primary text-gold hover:bg-gold hover:text-primary
                         py-3.5 rounded-xl font-bold uppercase tracking-widest text-xs
                         focus:outline-none focus-visible:ring-2 focus-visible:ring-gold
                         transition-all shadow-luxury flex items-center justify-center gap-2
                         disabled:opacity-60 disabled:cursor-wait">
            <i class="fa-solid fa-paper-plane" aria-hidden="true"></i>
            <span>Send Inquiry</span>
          </button>
        </form>
      </div>`;

    const form = host.querySelector('#bookingInquiryForm');
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const btn = host.querySelector('#bookingSubmitBtn');
      const original = btn.innerHTML;
      btn.disabled = true;
      btn.innerHTML =
        '<i class="fa-solid fa-spinner fa-spin" aria-hidden="true"></i><span>Sending…</span>';

      const fd = new FormData(form);
      const payload = {
        name:     (fd.get('name')     || '').toString().trim(),
        email:    (fd.get('email')    || '').toString().trim(),
        phone:    (fd.get('phone')    || '').toString().trim(),
        property: (fd.get('property') || '').toString().trim(),
        message:  (fd.get('message')  || '').toString().trim(),
        guests:   '—',
        check_in: '',
        check_out: '',
      };

      if (!payload.name || !payload.email || !payload.phone) {
        g_toast('Please fill in all required fields.', 'error');
        btn.disabled = false;
        btn.innerHTML = original;
        return;
      }

      try {
        const res = await fetch(config.inquiryUrl, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': g_csrf(),
          },
          body: JSON.stringify(payload),
        });
        const data = await res.json();
        if (data.success) {
          g_toast(
            `Thank you, ${payload.name.split(' ')[0]}! Your question has been sent.`,
            'success'
          );
          const modal = document.getElementById('bookingModal');
          if (modal) g_closeModal(modal);
        } else {
          g_toast(data.error || 'Submission failed. Please try again.', 'error');
        }
      } catch (err) {
        g_toast('Network error. Please try again.', 'error');
      } finally {
        btn.disabled = false;
        btn.innerHTML = original;
      }
    });
  }
})();