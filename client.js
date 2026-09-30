/* ============================================================
   LE RÊVE PROPERTIES — CLIENT (GUEST) PANEL LOGIC
   ============================================================ */

const STORAGE = {
  auth:      'leReveClientAuth',
  session:   'leReveClientSession',
  users:     'leReveClientUsers',
  bookings:  'leReveClientBookings',
  inquiries: 'leReveInquiries',
  messages:  'leReveClientMessages',
  wishlist:  'leReveFavorites',
  properties:'leReveProperties',
  reviews:   'leReveReviews'
};

const DEMO_USER = {
  id: 'user-demo',
  name: 'Alexandra Whitmore',
  email: 'guest@lereve.com',
  password: 'guest2026',
  phone: '+44 20 7946 0958',
  country: 'United Kingdom',
  bio: 'Frequent traveler seeking architectural sanctuaries and quiet luxury.',
  memberSince: '2024-03-15',
  tier: 'Gold',
  preferences: {
    type: 'Oceanfront Villas',
    diet: 'Pescatarian, no shellfish',
    amenities: ['Infinity Pool', 'Private Chef', 'Spa'],
    comm: { newsletter: true, sms: false, promo: true }
  }
};

const DEMO_BOOKINGS = [
  {
    id: 'bk-1',
    property: 'The Royal Azure Villa',
    location: 'Amalfi Coast, Italy',
    image: 'https://images.unsplash.com/photo-1512917774080-9991f1c4c750?auto=format&fit=crop&w=800&q=80',
    checkIn: '2026-06-18',
    checkOut: '2026-06-25',
    guests: '2 Guests',
    total: 17150,
    status: 'confirmed',
    confirmationId: 'LR-2026-0618-AZURE',
    createdAt: '2026-02-10T10:15:00Z'
  },
  {
    id: 'bk-2',
    property: 'The Modernist Alpine Chalet',
    location: 'Zermatt, Switzerland',
    image: 'https://images.unsplash.com/photo-1542314831-068cd1dbfeeb?auto=format&fit=crop&w=800&q=80',
    checkIn: '2026-12-20',
    checkOut: '2026-12-27',
    guests: '4 Guests',
    total: 20650,
    status: 'confirmed',
    confirmationId: 'LR-2026-1220-ZERMATT',
    createdAt: '2026-03-01T14:20:00Z'
  },
  {
    id: 'bk-3',
    property: 'Penthouse Mount Royal',
    location: 'Manhattan, New York',
    image: 'https://images.unsplash.com/photo-1502672260266-1c1ef2d93688?auto=format&fit=crop&w=800&q=80',
    checkIn: '2025-09-10',
    checkOut: '2025-09-15',
    guests: '2 Guests',
    total: 10500,
    status: 'completed',
    confirmationId: 'LR-2025-0910-MTROYAL',
    createdAt: '2025-06-05T09:00:00Z'
  }
];

const DEMO_MESSAGES = [
  {
    id: 'msg-1',
    from: 'concierge',
    text: 'Welcome to Le Rêve, Alexandra. I\'m your dedicated concierge for your upcoming Amalfi stay. Please let me know if you\'d like a chef, chauffeur, or private yacht itinerary arranged.',
    timestamp: '2026-04-01T09:30:00Z'
  }
];

/* ---------- HELPERS ---------- */
const $ = (s) => document.querySelector(s);
const $$ = (s) => document.querySelectorAll(s);

function load(key, fallback) {
  try { const raw = localStorage.getItem(key); return raw ? JSON.parse(raw) : fallback; }
  catch(e) { return fallback; }
}
function save(key, val) { localStorage.setItem(key, JSON.stringify(val)); }
function uid(p='id') { return `${p}-${Date.now()}-${Math.random().toString(36).slice(2,7)}`; }

function escapeHtml(s='') {
  return String(s).replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
}
function formatDate(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  return isNaN(d) ? iso : d.toLocaleDateString('en-US', { month:'short', day:'numeric', year:'numeric' });
}
function formatDateTime(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  return isNaN(d) ? iso : d.toLocaleString('en-US', { month:'short', day:'numeric', hour:'2-digit', minute:'2-digit' });
}
function initials(name='') {
  return name.split(' ').map(w=>w[0]).slice(0,2).join('').toUpperCase() || '?';
}

/* ---------- DATA ACCESS ---------- */
function getUsers() { return load(STORAGE.users, []); }
function saveUsers(u) { save(STORAGE.users, u); }

function getCurrentUser() {
  const id = localStorage.getItem(STORAGE.auth) || sessionStorage.getItem(STORAGE.session);
  if (!id) return null;
  if (id === DEMO_USER.id) return { ...DEMO_USER };
  return getUsers().find(u => u.id === id) || null;
}
function updateCurrentUser(patch) {
  const u = getCurrentUser();
  if (!u) return;
  if (u.id === DEMO_USER.id) {
    // Persist demo user changes to a shadow copy
    const users = getUsers();
    const idx = users.findIndex(x => x.id === DEMO_USER.id);
    const merged = { ...(idx > -1 ? users[idx] : DEMO_USER), ...patch };
    if (idx > -1) users[idx] = merged; else users.push(merged);
    saveUsers(users);
  } else {
    const users = getUsers().map(x => x.id === u.id ? { ...x, ...patch } : x);
    saveUsers(users);
  }
}

/* ---------- BOOKINGS ---------- */
function getBookings() {
  const u = getCurrentUser();
  if (!u) return [];
  const all = load(STORAGE.bookings, {});
  // First-time: seed demo bookings for the demo user
  if (!all[u.id] && u.id === DEMO_USER.id) {
    all[u.id] = DEMO_BOOKINGS;
    save(STORAGE.bookings, all);
  }
  return all[u.id] || [];
}
function saveBookings(list) {
  const u = getCurrentUser();
  if (!u) return;
  const all = load(STORAGE.bookings, {});
  all[u.id] = list;
  save(STORAGE.bookings, all);
}

/* ---------- MESSAGES ---------- */
function getMessages() {
  const u = getCurrentUser();
  if (!u) return [];
  const all = load(STORAGE.messages, {});
  if (!all[u.id] && u.id === DEMO_USER.id) {
    all[u.id] = DEMO_MESSAGES;
    save(STORAGE.messages, all);
  }
  return all[u.id] || [];
}
function saveMessages(list) {
  const u = getCurrentUser();
  if (!u) return;
  const all = load(STORAGE.messages, {});
  all[u.id] = list;
  save(STORAGE.messages, all);
}

/* ---------- WISHLIST ---------- */
function getWishlistIds() {
  return new Set(load(STORAGE.wishlist, []));
}
function saveWishlistIds(set) {
  save(STORAGE.wishlist, [...set]);
}

/* ---------- PROPERTIES (READ-ONLY) ---------- */
function getProperties() {
  return load(STORAGE.properties, []);
}

/* ---------- AUTH FLOW ---------- */
function switchAuthTab(tab) {
  const isLogin = tab === 'login';
  $('#loginForm').classList.toggle('hidden', !isLogin);
  $('#registerForm').classList.toggle('hidden', isLogin);
  $('#tabLogin').className = isLogin
    ? 'flex-1 py-2.5 rounded-full text-xs font-bold uppercase tracking-widest bg-primary text-gold transition-all'
    : 'flex-1 py-2.5 rounded-full text-xs font-bold uppercase tracking-widest text-charcoal/60 hover:text-primary transition-all';
  $('#tabRegister').className = !isLogin
    ? 'flex-1 py-2.5 rounded-full text-xs font-bold uppercase tracking-widest bg-primary text-gold transition-all'
    : 'flex-1 py-2.5 rounded-full text-xs font-bold uppercase tracking-widest text-charcoal/60 hover:text-primary transition-all';
}

function togglePw(inputId, iconId) {
  const input = document.getElementById(inputId);
  const icon = document.getElementById(iconId);
  if (input.type === 'password') { input.type = 'text'; icon.className = 'fa-regular fa-eye-slash'; }
  else { input.type = 'password'; icon.className = 'fa-regular fa-eye'; }
}

function handleClientLogin(e) {
  e.preventDefault();
  const email = $('#loginEmail').value.trim().toLowerCase();
  const pw = $('#loginPassword').value;

  let user = null;
  if (email === DEMO_USER.email && pw === DEMO_USER.password) {
    user = DEMO_USER;
  } else {
    user = getUsers().find(u => u.email.toLowerCase() === email && u.password === pw);
  }
  if (!user) { clientToast('Invalid email or password.', 'error'); return; }

  if ($('#rememberMe').checked) localStorage.setItem(STORAGE.auth, user.id);
  else sessionStorage.setItem(STORAGE.session, user.id);

  clientToast(`Welcome back, ${user.name.split(' ')[0]}`, 'success');
  showClient();
}

function handleClientRegister(e) {
  e.preventDefault();
  const email = $('#regEmail').value.trim().toLowerCase();
  if (email === DEMO_USER.email || getUsers().some(u => u.email.toLowerCase() === email)) {
    clientToast('An account with that email already exists.', 'error'); return;
  }
  const newUser = {
    id: uid('user'),
    name: $('#regName').value.trim(),
    email,
    password: $('#regPassword').value,
    phone: $('#regPhone').value.trim(),
    country: '',
    bio: '',
    memberSince: new Date().toISOString().slice(0,10),
    tier: 'Silver',
    preferences: {
      type: 'Oceanfront Villas',
      diet: '',
      amenities: [],
      comm: { newsletter: true, sms: true, promo: true }
    }
  };
  const users = getUsers(); users.push(newUser); saveUsers(users);

  localStorage.setItem(STORAGE.auth, newUser.id);
  clientToast('Account created. Welcome to Le Rêve.', 'success');
  showClient();
}

function handleClientLogout() {
  if (!confirm('Sign out of the guest portal?')) return;
  localStorage.removeItem(STORAGE.auth);
  sessionStorage.removeItem(STORAGE.session);
  window.location.reload();
}

function showClient() {
  const user = getCurrentUser();
  if (!user) return;
  $('#authScreen').classList.add('hidden');
  $('#clientShell').classList.remove('hidden');

  // Header
  $('#userNameTop').textContent = user.name;
  $('#userAvatarTop').textContent = initials(user.name);
  $('#welcomeName').textContent = `Welcome back, ${user.name.split(' ')[0]}`;

  renderAll();
  updateBadges();
  handleHashRoute();
}

/* ---------- SECTION ROUTING ---------- */
function switchClientSection(name) {
  $$('.section').forEach(s => s.classList.add('hidden'));
  const target = document.getElementById(`section-${name}`);
  if (target) target.classList.remove('hidden');

  $$('.sidebar-link').forEach(l => l.classList.remove('active'));
  const link = document.querySelector(`.sidebar-link[data-section="${name}"]`);
  if (link) link.classList.add('active');

  const titles = {
    overview:    ['Overview', 'Your luxury travel snapshot'],
    bookings:    ['My Bookings', 'Upcoming and past stays'],
    wishlist:    ['Wishlist', 'Estates you\'ve saved'],
    inquiries:   ['My Inquiries', 'Reservation requests in progress'],
    messages:    ['Concierge Chat', 'Direct line to your dedicated team'],
    profile:     ['Profile', 'Manage your personal details'],
    preferences: ['Preferences', 'Tailor your luxury experience']
  };
  const [t, s] = titles[name] || ['Overview', ''];
  $('#pageTitle').textContent = t;
  $('#pageSubtitle').textContent = s;

  if (name === 'messages') {
    renderMessages();
    // Clear unread indicator
    $('#notifDot').classList.add('hidden');
  }
  if (name === 'profile') renderProfile();
  if (name === 'preferences') renderPreferences();
  if (name === 'inquiries') renderInquiries();

  if (window.innerWidth < 1024) closeSidebar();
}

function handleHashRoute() {
  const hash = (window.location.hash || '#overview').replace('#','');
  switchClientSection(hash);
}

function toggleSidebar() {
  $('#sidebar').classList.toggle('open');
  $('#sidebarOverlay').classList.toggle('hidden');
}
function closeSidebar() {
  $('#sidebar').classList.remove('open');
  $('#sidebarOverlay').classList.add('hidden');
}

/* ---------- RENDER: EVERYTHING ---------- */
function renderAll() {
  renderOverview();
  renderBookings();
  renderWishlist();
  renderInquiries();
  renderMessages();
  renderProfile();
  renderPreferences();
}

/* ---------- OVERVIEW ---------- */
function renderOverview() {
  const bookings = getBookings();
  const today = new Date().toISOString().slice(0,10);
  const upcoming = bookings.filter(b => b.checkIn >= today && b.status === 'confirmed');
  const past = bookings.filter(b => b.checkIn < today || b.status === 'completed');
  const wishlist = getWishlistIds();
  const user = getCurrentUser();

  $('#statUpcoming').textContent = upcoming.length;
  $('#statWishlist').textContent = wishlist.size;
  $('#statPast').textContent = past.length;
  $('#statTier').textContent = user.tier || 'Silver';

  // Upcoming stay card
  const container = $('#upcomingStayCard');
  if (upcoming.length === 0) {
    container.innerHTML = `<div class="text-center py-10">
      <i class="fa-solid fa-umbrella-beach text-3xl text-gold/50 mb-3"></i>
      <p class="text-charcoal/60 text-sm mb-4">You have no upcoming stays yet.</p>
      <a href="index.html#listings" class="inline-block bg-primary text-gold hover:bg-gold hover:text-primary px-6 py-3 rounded-full text-xs font-bold uppercase tracking-wider transition-all">Browse Estates</a>
    </div>`;
  } else {
    const b = upcoming.sort((a,b) => a.checkIn.localeCompare(b.checkIn))[0];
    container.innerHTML = `
      <div class="flex flex-col sm:flex-row gap-5">
        <img src="${escapeHtml(b.image)}" alt="" class="w-full sm:w-40 h-40 sm:h-auto rounded-2xl object-cover border border-gold/30">
        <div class="flex-1">
          <div class="flex items-start justify-between gap-3 mb-2">
            <div>
              <p class="text-[10px] uppercase tracking-widest text-gold font-bold">Confirmed</p>
              <h4 class="font-serif text-2xl font-semibold text-primary">${escapeHtml(b.property)}</h4>
              <p class="text-xs text-charcoal/60 mt-1"><i class="fa-solid fa-location-dot text-gold mr-1"></i> ${escapeHtml(b.location)}</p>
            </div>
          </div>
          <div class="grid grid-cols-3 gap-3 mt-4 p-4 rounded-xl bg-ivory border border-gold/20">
            <div>
              <p class="text-[10px] uppercase text-charcoal/50 font-semibold">Check-in</p>
              <p class="text-sm font-bold text-primary">${formatDate(b.checkIn)}</p>
            </div>
            <div>
              <p class="text-[10px] uppercase text-charcoal/50 font-semibold">Check-out</p>
              <p class="text-sm font-bold text-primary">${formatDate(b.checkOut)}</p>
            </div>
            <div>
              <p class="text-[10px] uppercase text-charcoal/50 font-semibold">Guests</p>
              <p class="text-sm font-bold text-primary">${escapeHtml(b.guests)}</p>
            </div>
          </div>
          <div class="flex flex-wrap gap-2 mt-4">
            <button onclick="openBookingDetail('${b.id}')" class="bg-primary text-gold hover:bg-gold hover:text-primary px-5 py-2.5 rounded-full text-xs font-bold uppercase tracking-wider transition-all">View Details</button>
            <button onclick="switchClientSection('messages')" class="border border-primary/20 text-primary hover:border-gold px-5 py-2.5 rounded-full text-xs font-bold uppercase tracking-wider transition-all">Message Concierge</button>
          </div>
        </div>
      </div>
    `;
  }

  // Recent activity
  const act = $('#recentActivityList');
  const items = [];
  bookings.slice(0, 3).forEach(b => items.push({
    icon: b.status === 'completed' ? 'fa-check-circle' : 'fa-calendar-check',
    color: b.status === 'completed' ? 'text-emerald-600 bg-emerald-50' : 'text-primary bg-primary/10',
    text: `${b.status === 'completed' ? 'Completed stay at' : 'Booked'} ${b.property}`,
    date: b.createdAt
  }));
  if (wishlist.size > 0) items.push({
    icon: 'fa-heart', color: 'text-gold-dark bg-gold/15',
    text: `Saved ${wishlist.size} ${wishlist.size === 1 ? 'estate' : 'estates'} to wishlist`,
    date: new Date().toISOString()
  });

  if (items.length === 0) {
    act.innerHTML = `<p class="text-sm text-charcoal/50 text-center py-6">Activity will appear here.</p>`;
  } else {
    act.innerHTML = items.map(a => `
      <div class="flex items-start gap-3">
        <div class="w-9 h-9 rounded-full ${a.color} flex items-center justify-center flex-shrink-0">
          <i class="fa-solid ${a.icon} text-xs"></i>
        </div>
        <div class="min-w-0 flex-1">
          <p class="text-sm text-charcoal/80 leading-snug">${escapeHtml(a.text)}</p>
          <p class="text-[10px] text-charcoal/40 mt-0.5">${formatDateTime(a.date)}</p>
        </div>
      </div>
    `).join('');
  }
}

/* ---------- BOOKINGS ---------- */
let bookingFilter = 'all';
function filterBookings(filter, btn) {
  bookingFilter = filter;
  $$('.booking-filter-btn').forEach(b => {
    b.classList.remove('active', 'bg-primary', 'text-gold');
    b.classList.add('border', 'border-primary/20', 'bg-white', 'text-primary');
  });
  btn.classList.add('active', 'bg-primary', 'text-gold');
  btn.classList.remove('border', 'border-primary/20', 'bg-white', 'text-primary');
  renderBookings();
}

function renderBookings() {
  const container = $('#bookingsList');
  const today = new Date().toISOString().slice(0,10);
  let list = getBookings();
  if (bookingFilter === 'upcoming') list = list.filter(b => b.checkIn >= today && b.status === 'confirmed');
  if (bookingFilter === 'past') list = list.filter(b => b.checkIn < today || b.status === 'completed');

  if (list.length === 0) {
    container.innerHTML = `<div class="col-span-full text-center py-16 bg-white rounded-2xl border border-dashed border-gold/40">
      <i class="fa-solid fa-suitcase-rolling text-4xl text-gold/40 mb-3"></i>
      <p class="text-charcoal/60 text-sm">No bookings to show.</p>
    </div>`;
    return;
  }

  container.innerHTML = list.map(b => {
    const isUpcoming = b.checkIn >= today && b.status === 'confirmed';
    const statusColor = b.status === 'confirmed' ? 'text-emerald-600 bg-emerald-50'
                      : b.status === 'completed' ? 'text-charcoal/60 bg-ivory-dark'
                      : 'text-amber-600 bg-amber-50';
    return `
      <div class="bg-white rounded-2xl overflow-hidden border border-gold/20 shadow-sm hover:border-gold transition-all group cursor-pointer" onclick="openBookingDetail('${b.id}')">
        <div class="relative aspect-[16/10] overflow-hidden bg-primary-dark">
          <img src="${escapeHtml(b.image)}" alt="${escapeHtml(b.property)}" class="w-full h-full object-cover group-hover:scale-105 transition-transform duration-700">
          <div class="absolute inset-0 bg-gradient-to-t from-primary/70 via-transparent to-transparent"></div>
          <span class="absolute top-3 left-3 text-[10px] font-bold uppercase tracking-wider px-3 py-1 rounded-full ${statusColor}">${escapeHtml(b.status)}</span>
          ${isUpcoming ? `<span class="absolute top-3 right-3 text-[10px] font-bold uppercase tracking-wider px-3 py-1 rounded-full bg-gold text-primary">Upcoming</span>` : ''}
          <div class="absolute bottom-3 left-3 right-3">
            <h4 class="font-serif text-xl font-semibold text-ivory">${escapeHtml(b.property)}</h4>
            <p class="text-[11px] text-ivory/80"><i class="fa-solid fa-location-dot mr-1"></i>${escapeHtml(b.location)}</p>
          </div>
        </div>
        <div class="p-5">
          <div class="grid grid-cols-3 gap-2 text-center text-xs mb-4">
            <div><p class="text-[10px] uppercase text-charcoal/50 font-semibold">In</p><p class="font-bold text-primary">${formatDate(b.checkIn)}</p></div>
            <div><p class="text-[10px] uppercase text-charcoal/50 font-semibold">Out</p><p class="font-bold text-primary">${formatDate(b.checkOut)}</p></div>
            <div><p class="text-[10px] uppercase text-charcoal/50 font-semibold">Guests</p><p class="font-bold text-primary">${escapeHtml(b.guests.split(' ')[0])}</p></div>
          </div>
          <div class="flex items-center justify-between pt-3 border-t border-charcoal/5">
            <div>
              <p class="text-[10px] uppercase text-charcoal/50 font-semibold">Total</p>
              <p class="font-serif text-xl font-bold text-primary">$${Number(b.total).toLocaleString()}</p>
            </div>
            <button onclick="event.stopPropagation(); openBookingDetail('${b.id}')" class="bg-primary text-gold hover:bg-gold hover:text-primary px-4 py-2 rounded-full text-xs font-bold uppercase tracking-wider transition-all">Details</button>
          </div>
        </div>
      </div>
    `;
  }).join('');
}

function openBookingDetail(id) {
  const b = getBookings().find(x => x.id === id);
  if (!b) return;
  const today = new Date().toISOString().slice(0,10);
  const isUpcoming = b.checkIn >= today && b.status === 'confirmed';
  const nights = Math.max(1, Math.round((new Date(b.checkOut) - new Date(b.checkIn)) / 86400000));

  const content = $('#detailModalContent');
  content.innerHTML = `
    <img src="${escapeHtml(b.image)}" class="w-full h-56 object-cover rounded-2xl mb-6 border border-gold/20">
    <div class="flex items-center gap-2 mb-2">
      <span class="text-[10px] font-bold uppercase tracking-widest px-3 py-1 rounded-full ${b.status === 'confirmed' ? 'bg-emerald-50 text-emerald-600' : 'bg-ivory-dark text-charcoal/60'}">${escapeHtml(b.status)}</span>
      ${isUpcoming ? `<span class="text-[10px] font-bold uppercase tracking-widest px-3 py-1 rounded-full bg-gold text-primary">Upcoming</span>` : ''}
    </div>
    <h3 class="font-serif text-3xl font-semibold text-primary mb-1">${escapeHtml(b.property)}</h3>
    <p class="text-sm text-charcoal/60 mb-6"><i class="fa-solid fa-location-dot text-gold mr-1"></i> ${escapeHtml(b.location)}</p>

    <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 p-4 rounded-xl bg-ivory border border-gold/20 mb-6">
      <div><p class="text-[10px] uppercase text-charcoal/50 font-semibold mb-0.5">Check-in</p><p class="text-sm font-bold text-primary">${formatDate(b.checkIn)}</p></div>
      <div><p class="text-[10px] uppercase text-charcoal/50 font-semibold mb-0.5">Check-out</p><p class="text-sm font-bold text-primary">${formatDate(b.checkOut)}</p></div>
      <div><p class="text-[10px] uppercase text-charcoal/50 font-semibold mb-0.5">Nights</p><p class="text-sm font-bold text-primary">${nights}</p></div>
      <div><p class="text-[10px] uppercase text-charcoal/50 font-semibold mb-0.5">Guests</p><p class="text-sm font-bold text-primary">${escapeHtml(b.guests)}</p></div>
    </div>

    <div class="space-y-2 mb-6">
      <div class="flex justify-between text-sm"><span class="text-charcoal/60">Confirmation ID</span><span class="font-mono font-semibold text-primary text-xs">${escapeHtml(b.confirmationId || '—')}</span></div>
      <div class="flex justify-between text-sm"><span class="text-charcoal/60">Total</span><span class="font-serif text-xl font-bold text-primary">$${Number(b.total).toLocaleString()}</span></div>
    </div>

    <div class="flex flex-wrap gap-3">
      <button onclick="closeDetailModal(); switchClientSection('messages');" class="flex-1 bg-primary text-gold hover:bg-gold hover:text-primary px-5 py-3 rounded-xl text-xs font-bold uppercase tracking-wider transition-all"><i class="fa-solid fa-comments mr-1"></i> Message Concierge</button>
      ${isUpcoming ? `<button onclick="cancelBooking('${b.id}')" class="flex-1 border border-red-200 text-red-500 hover:bg-red-50 px-5 py-3 rounded-xl text-xs font-bold uppercase tracking-wider transition-all">Request Cancellation</button>` : ''}
    </div>
  `;
  $('#detailModal').classList.remove('hidden');
  $('#detailModal').classList.add('flex');
}

function cancelBooking(id) {
  if (!confirm('Request cancellation for this booking? Your concierge will confirm shortly.')) return;
  const list = getBookings().map(b => b.id === id ? { ...b, status: 'cancellation-requested' } : b);
  saveBookings(list);
  closeDetailModal();
  renderBookings();
  renderOverview();
  clientToast('Cancellation request sent to concierge.', 'info');
}

/* ---------- WISHLIST ---------- */
function renderWishlist() {
  const grid = $('#wishlistGrid');
  const ids = getWishlistIds();
  const all = getProperties();
  const items = all.filter(p => ids.has(p.id));

  if (items.length === 0) {
    grid.innerHTML = `<div class="col-span-full text-center py-16 bg-white rounded-2xl border border-dashed border-gold/40">
      <i class="fa-regular fa-heart text-4xl text-gold/40 mb-3"></i>
      <p class="text-charcoal/60 text-sm mb-4">Your wishlist is empty.</p>
      <a href="index.html#listings" class="inline-block bg-primary text-gold hover:bg-gold hover:text-primary px-6 py-3 rounded-full text-xs font-bold uppercase tracking-wider transition-all">Discover Estates</a>
    </div>`;
    return;
  }

  grid.innerHTML = items.map(p => `
    <div class="bg-white rounded-2xl overflow-hidden border border-gold/20 shadow-sm hover:border-gold transition-all group">
      <div class="relative aspect-[4/3] overflow-hidden bg-primary-dark">
        <img src="${escapeHtml(p.image)}" alt="${escapeHtml(p.title)}" class="w-full h-full object-cover group-hover:scale-105 transition-transform duration-700">
        <div class="absolute inset-0 bg-gradient-to-t from-primary/80 via-transparent to-black/10"></div>
        <span class="absolute top-3 left-3 bg-primary/90 text-gold backdrop-blur-sm text-[10px] font-bold uppercase tracking-widest px-2.5 py-1 rounded-full border border-gold/30">${escapeHtml(p.category)}</span>
        <button onclick="removeFromWishlist('${p.id}')" class="absolute top-3 right-3 w-9 h-9 rounded-full bg-gold text-primary flex items-center justify-center shadow-md hover:bg-white transition-all">
          <i class="fa-solid fa-heart"></i>
        </button>
      </div>
      <div class="p-5">
        <div class="flex items-center justify-between text-xs text-charcoal/60 mb-2">
          <span><i class="fa-solid fa-location-dot text-gold mr-1"></i>${escapeHtml(p.location)}</span>
          <span class="font-bold text-primary"><i class="fa-solid fa-star text-gold mr-1"></i>${p.rating}</span>
        </div>
        <h4 class="font-serif text-xl font-semibold text-primary mb-3">${escapeHtml(p.title)}</h4>
        <div class="flex items-center justify-between pt-3 border-t border-charcoal/5">
          <div>
            <p class="text-[10px] text-charcoal/50 line-through">$${Number(p.originalPrice).toLocaleString()}</p>
            <p class="font-serif text-xl font-bold text-primary">$${Number(p.price).toLocaleString()}<span class="text-[10px] font-normal text-charcoal/50 ml-1">/ night</span></p>
          </div>
          <a href="index.html#listings" class="bg-primary text-gold hover:bg-gold hover:text-primary px-4 py-2 rounded-full text-[11px] font-bold uppercase tracking-wider transition-all">Book</a>
        </div>
      </div>
    </div>
  `).join('');
}

function removeFromWishlist(id) {
  const ids = getWishlistIds();
  ids.delete(id);
  saveWishlistIds(ids);
  renderWishlist();
  renderOverview();
  updateBadges();
  clientToast('Removed from wishlist.', 'info');
}

/* ---------- INQUIRIES ---------- */
function renderInquiries() {
  const tbody = $('#inquiriesTableBody');
  const u = getCurrentUser();
  if (!u) return;
  const all = load(STORAGE.inquiries, []);
  const mine = all.filter(i => i.email?.toLowerCase() === u.email.toLowerCase());

  if (mine.length === 0) {
    tbody.innerHTML = `<tr><td colspan="5" class="px-5 py-10 text-center text-charcoal/50 text-sm">You have no inquiries yet.</td></tr>`;
    return;
  }

  const colors = {
    new: 'text-amber-600 bg-amber-50',
    contacted: 'text-blue-600 bg-blue-50',
    booked: 'text-emerald-600 bg-emerald-50',
    archived: 'text-charcoal/60 bg-ivory-dark'
  };

  tbody.innerHTML = mine.map(i => `
    <tr class="hover:bg-ivory/50 transition-colors">
      <td class="px-5 py-3 text-sm font-semibold text-primary">${escapeHtml(i.property || 'General Inquiry')}</td>
      <td class="px-5 py-3 text-xs text-charcoal/60">${i.checkIn ? `${formatDate(i.checkIn)} → ${formatDate(i.checkOut)}` : '—'}</td>
      <td class="px-5 py-3 text-xs text-charcoal/70">${escapeHtml(i.guests || '—')}</td>
      <td class="px-5 py-3"><span class="text-[10px] font-bold uppercase tracking-wider px-2.5 py-1 rounded-full ${colors[i.status] || colors.new}">${escapeHtml(i.status || 'new')}</span></td>
      <td class="px-5 py-3 text-right">
        <button onclick="viewInquiry('${i.id}')" class="text-xs font-semibold text-gold hover:text-gold-dark uppercase tracking-wider">View</button>
      </td>
    </tr>
  `).join('');
}

function viewInquiry(id) {
  const all = load(STORAGE.inquiries, []);
  const i = all.find(x => x.id === id);
  if (!i) return;
  const content = $('#detailModalContent');
  content.innerHTML = `
    <h3 class="font-serif text-2xl font-semibold text-primary mb-1">Inquiry Details</h3>
    <p class="text-xs text-charcoal/60 mb-6">Submitted ${formatDate(i.createdAt)}</p>
    <div class="space-y-3 text-sm">
      <div class="flex justify-between border-b border-charcoal/10 pb-2"><span class="text-charcoal/60">Property</span><span class="font-semibold text-primary">${escapeHtml(i.property || 'General')}</span></div>
      <div class="flex justify-between border-b border-charcoal/10 pb-2"><span class="text-charcoal/60">Check-in</span><span class="font-semibold text-primary">${formatDate(i.checkIn)}</span></div>
      <div class="flex justify-between border-b border-charcoal/10 pb-2"><span class="text-charcoal/60">Check-out</span><span class="font-semibold text-primary">${formatDate(i.checkOut)}</span></div>
      <div class="flex justify-between border-b border-charcoal/10 pb-2"><span class="text-charcoal/60">Guests</span><span class="font-semibold text-primary">${escapeHtml(i.guests || '—')}</span></div>
      <div class="flex justify-between border-b border-charcoal/10 pb-2"><span class="text-charcoal/60">Status</span><span class="font-semibold text-primary capitalize">${escapeHtml(i.status || 'new')}</span></div>
      ${i.message ? `<div class="border-b border-charcoal/10 pb-2"><p class="text-charcoal/60 mb-1">Your Notes</p><p class="text-primary">${escapeHtml(i.message)}</p></div>` : ''}
    </div>
    <div class="flex gap-3 mt-6">
      <button onclick="closeDetailModal(); switchClientSection('messages');" class="flex-1 bg-primary text-gold hover:bg-gold hover:text-primary px-4 py-3 rounded-xl text-xs font-bold uppercase tracking-wider transition-all">Message Concierge</button>
      <button onclick="closeDetailModal()" class="flex-1 border border-charcoal/15 hover:bg-ivory px-4 py-3 rounded-xl text-xs font-semibold transition-all">Close</button>
    </div>
  `;
  $('#detailModal').classList.remove('hidden');
  $('#detailModal').classList.add('flex');
}

/* ---------- MESSAGES ---------- */
function renderMessages() {
  const box = $('#chatMessages');
  const msgs = getMessages();
  if (msgs.length === 0) {
    box.innerHTML = `<p class="text-center text-charcoal/50 text-sm py-8">No messages yet. Say hello to your concierge!</p>`;
    return;
  }
  box.innerHTML = msgs.map(m => {
    const isMe = m.from === 'me';
    return `
      <div class="flex ${isMe ? 'justify-end' : 'justify-start'}">
        <div class="max-w-[80%] sm:max-w-[70%]">
          ${!isMe ? `<div class="flex items-center gap-2 mb-1"><div class="w-7 h-7 rounded-full bg-primary text-gold flex items-center justify-center text-[10px]"><i class="fa-solid fa-bell-concierge"></i></div><span class="text-[11px] font-semibold text-primary">Concierge</span></div>` : ''}
          <div class="${isMe ? 'bg-primary text-ivory' : 'bg-white text-charcoal border border-gold/20'} rounded-2xl px-4 py-3 shadow-sm">
            <p class="text-sm leading-relaxed">${escapeHtml(m.text)}</p>
          </div>
          <p class="text-[10px] text-charcoal/40 mt-1 ${isMe ? 'text-right' : ''}">${formatDateTime(m.timestamp)}</p>
        </div>
      </div>
    `;
  }).join('');
  box.scrollTop = box.scrollHeight;
}

function sendMessage(e) {
  e.preventDefault();
  const input = $('#chatInput');
  const text = input.value.trim();
  if (!text) return;

  const msgs = getMessages();
  msgs.push({ id: uid('msg'), from: 'me', text, timestamp: new Date().toISOString() });
  saveMessages(msgs);
  input.value = '';
  renderMessages();

  // Auto concierge reply after 1.2s
  setTimeout(() => {
    const replies = [
      'Thank you for your message. I will look into this and revert within the hour.',
      'Noted with pleasure. I will coordinate the details and confirm shortly.',
      'Excellent choice. Let me arrange that for you right away.',
      'I have flagged this with our estate team and will follow up with options.'
    ];
    const reply = replies[Math.floor(Math.random() * replies.length)];
    const msgs2 = getMessages();
    msgs2.push({ id: uid('msg'), from: 'concierge', text: reply, timestamp: new Date().toISOString() });
    saveMessages(msgs2);
    renderMessages();
    $('#notifDot').classList.remove('hidden');
  }, 1200);
}

/* ---------- PROFILE ---------- */
function renderProfile() {
  const u = getCurrentUser();
  if (!u) return;
  $('#profName').value = u.name || '';
  $('#profEmail').value = u.email || '';
  $('#profPhone').value = u.phone || '';
  $('#profCountry').value = u.country || '';
  $('#profBio').value = u.bio || '';

  $('#memberTierBig').textContent = u.tier || 'Silver';
  $('#memberSince').textContent = formatDate(u.memberSince);
  const bookings = getBookings();
  const today = new Date().toISOString().slice(0,10);
  const completed = bookings.filter(b => b.checkIn < today || b.status === 'completed');
  $('#totalStays').textContent = completed.length;
  let nights = 0;
  const countries = new Set();
  completed.forEach(b => {
    nights += Math.max(1, Math.round((new Date(b.checkOut) - new Date(b.checkIn)) / 86400000));
    const c = (b.location || '').split(',').pop().trim();
    if (c) countries.add(c);
  });
  $('#totalNights').textContent = nights;
  $('#totalCountries').textContent = countries.size;
}

function saveProfile(e) {
  e.preventDefault();
  const patch = {
    name: $('#profName').value.trim(),
    email: $('#profEmail').value.trim().toLowerCase(),
    phone: $('#profPhone').value.trim(),
    country: $('#profCountry').value.trim(),
    bio: $('#profBio').value.trim()
  };
  updateCurrentUser(patch);
  const u = getCurrentUser();
  $('#userNameTop').textContent = u.name;
  $('#userAvatarTop').textContent = initials(u.name);
  $('#welcomeName').textContent = `Welcome back, ${u.name.split(' ')[0]}`;
  clientToast('Profile updated.', 'success');
}

function changePassword(e) {
  e.preventDefault();
  const cur = $('#pwCurrent').value;
  const nw = $('#pwNew').value;
  const cf = $('#pwConfirm').value;
  const u = getCurrentUser();
  if (u.password !== cur) { clientToast('Current password is incorrect.', 'error'); return; }
  if (nw !== cf) { clientToast('New passwords do not match.', 'error'); return; }
  updateCurrentUser({ password: nw });
  e.target.reset();
  clientToast('Password updated successfully.', 'success');
}

/* ---------- PREFERENCES ---------- */
function renderPreferences() {
  const u = getCurrentUser();
  if (!u) return;
  const p = u.preferences || {};
  $('#prefType').value = p.type || 'Oceanfront Villas';
  $('#prefDiet').value = p.diet || '';
  $$('.pref-amenity').forEach(cb => {
    cb.checked = (p.amenities || []).includes(cb.value);
  });
  const c = p.comm || {};
  $('#commNewsletter').checked = c.newsletter !== false;
  $('#commSMS').checked = !!c.sms;
  $('#commPromo').checked = c.promo !== false;
}

function savePreferences(e) {
  e.preventDefault();
  const amenities = [...$$('.pref-amenity')].filter(cb => cb.checked).map(cb => cb.value);
  updateCurrentUser({
    preferences: {
      ...(getCurrentUser().preferences || {}),
      type: $('#prefType').value,
      diet: $('#prefDiet').value.trim(),
      amenities
    }
  });
  clientToast('Preferences saved.', 'success');
}

function saveComm() {
  updateCurrentUser({
    preferences: {
      ...(getCurrentUser().preferences || {}),
      comm: {
        newsletter: $('#commNewsletter').checked,
        sms: $('#commSMS').checked,
        promo: $('#commPromo').checked
      }
    }
  });
  clientToast('Communication preferences updated.', 'success');
}

/* ---------- BADGES ---------- */
function updateBadges() {
  const bookings = getBookings();
  const today = new Date().toISOString().slice(0,10);
  const upcoming = bookings.filter(b => b.checkIn >= today && b.status === 'confirmed').length;
  const wishSize = getWishlistIds().size;

  const bB = $('#bookingsBadge'), wB = $('#wishlistBadge');
  if (upcoming > 0) { bB.textContent = upcoming; bB.classList.remove('hidden'); } else bB.classList.add('hidden');
  if (wishSize > 0) { wB.textContent = wishSize; wB.classList.remove('hidden'); } else wB.classList.add('hidden');
}

/* ---------- MODAL ---------- */
function closeDetailModal() {
  const m = $('#detailModal');
  m.classList.add('hidden');
  m.classList.remove('flex');
}

/* ---------- TOAST ---------- */
function clientToast(message, type = 'success') {
  const container = $('#clientToast');
  const toast = document.createElement('div');
  const bg = type === 'success' ? 'bg-primary text-gold border-gold'
           : type === 'error' ? 'bg-red-600 text-white border-red-400'
           : 'bg-gold text-primary border-primary';
  const icon = type === 'success' ? 'fa-circle-check'
             : type === 'error' ? 'fa-circle-exclamation'
             : 'fa-circle-info';
  toast.className = `pointer-events-auto flex items-center gap-3 px-5 py-3.5 rounded-2xl border shadow-2xl text-xs font-semibold tracking-wide animate-fade-in ${bg}`;
  toast.innerHTML = `<i class="fa-solid ${icon} text-lg"></i><span>${escapeHtml(message)}</span>`;
  container.appendChild(toast);
  setTimeout(() => {
    toast.classList.add('opacity-0', 'transition-opacity', 'duration-300');
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

/* ---------- INIT ---------- */
document.addEventListener('DOMContentLoaded', () => {
  if (localStorage.getItem(STORAGE.auth) || sessionStorage.getItem(STORAGE.session)) {
    showClient();
  }
  ['detailModal'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.addEventListener('click', e => { if (e.target === el) closeDetailModal(); });
  });
  document.addEventListener('keydown', e => { if (e.key === 'Escape') closeDetailModal(); });
});

/* ---------- PUBLIC API (for index.html integration) ---------- */
window.LeReveClientAPI = {
  isLoggedIn: () => !!(localStorage.getItem(STORAGE.auth) || sessionStorage.getItem(STORAGE.session)),
  getCurrentUser
};