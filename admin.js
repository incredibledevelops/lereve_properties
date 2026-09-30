/* ============================================================
   LE RÊVE PROPERTIES — ADMIN PANEL LOGIC
   ============================================================ */

const ADMIN_CREDENTIALS = {
  email: 'admin@lereveproperties.com',
  password: 'lereve2026'
};

const STORAGE_KEYS = {
  auth: 'leReveAdminAuth',
  properties: 'leReveProperties',
  owners: 'leReveOwnerSubmissions',
  inquiries: 'leReveInquiries',
  reviews: 'leReveReviews',
  journal: 'leReveJournalSubs',
  settings: 'leReveSettings'
};

/* ---------- DEFAULT SEED DATA ---------- */
const DEFAULT_PROPERTIES = [
  { id:'prop-1', title:'The Royal Azure Villa', category:'Oceanfront Villas', location:'Amalfi Coast, Italy', originalPrice:3200, price:2450, rating:4.98, reviewsCount:42, beds:6, baths:7, guests:12,
    image:'https://images.unsplash.com/photo-1512917774080-9991f1c4c750?auto=format&fit=crop&w=1000&q=80',
    gallery:['https://images.unsplash.com/photo-1512917774080-9991f1c4c750?auto=format&fit=crop&w=1000&q=80','https://images.unsplash.com/photo-1600596542815-ffad4c1539a9?auto=format&fit=crop&w=1000&q=80','https://images.unsplash.com/photo-1600607687939-ce8a6c25118c?auto=format&fit=crop&w=1000&q=80'],
    amenities:['Infinity Pool','Private Chef','Ocean View','Yacht Dock','Wine Cellar'],
    description:'Perched dramatically on the cliffside of Amalfi, Villa Azure offers panoramic Mediterranean horizons, private direct ocean access via rock steps, and a dedicated butler team.' },
  { id:'prop-2', title:'Penthouse Mount Royal', category:'Penthouses', location:'Manhattan, New York', originalPrice:2800, price:2100, rating:4.96, reviewsCount:28, beds:4, baths:4.5, guests:8,
    image:'https://images.unsplash.com/photo-1502672260266-1c1ef2d93688?auto=format&fit=crop&w=1000&q=80',
    gallery:['https://images.unsplash.com/photo-1502672260266-1c1ef2d93688?auto=format&fit=crop&w=1000&q=80','https://images.unsplash.com/photo-1560448204-e02f11c3d0e2?auto=format&fit=crop&w=1000&q=80'],
    amenities:['Skyline View','Private Elevator','Heated Plunge Pool','24/7 Concierge','Heliport Access'],
    description:'A 360-degree glass penthouse atop Central Park. Includes high-security private elevator entry, double-height ceilings, and private rooftop heated pool.' },
  { id:'prop-3', title:'Château de Saint-Tropez', category:'Oceanfront Villas', location:'French Riviera, France', originalPrice:4500, price:3600, rating:5.0, reviewsCount:31, beds:8, baths:9, guests:16,
    image:'https://images.unsplash.com/photo-1613977257363-707ba9348227?auto=format&fit=crop&w=1000&q=80',
    gallery:['https://images.unsplash.com/photo-1613977257363-707ba9348227?auto=format&fit=crop&w=1000&q=80','https://images.unsplash.com/photo-1600585154340-be6161a56a0c?auto=format&fit=crop&w=1000&q=80'],
    amenities:['Private Beach','Butler Service','Spa & Sauna','Tennis Court','Helicopter Pad'],
    description:'An iconic French Riviera sanctuary complete with private golden sand beach access, manicured lavender gardens, and room for a full security entourage.' },
  { id:'prop-4', title:'The Modernist Alpine Chalet', category:'Alpine Chalets', location:'Zermatt, Switzerland', originalPrice:3800, price:2950, rating:4.99, reviewsCount:56, beds:5, baths:6, guests:10,
    image:'https://images.unsplash.com/photo-1542314831-068cd1dbfeeb?auto=format&fit=crop&w=1000&q=80',
    gallery:['https://images.unsplash.com/photo-1542314831-068cd1dbfeeb?auto=format&fit=crop&w=1000&q=80','https://images.unsplash.com/photo-1510798831971-661eb04b3739?auto=format&fit=crop&w=1000&q=80'],
    amenities:['Ski-in / Ski-out','Outdoor Heated Hot Tub','Sauna','Private Chef','Fireplace Salon'],
    description:'Unobstructed Matterhorn vistas with ski-in/ski-out privileges. Features bespoke reclaimed Swiss timber construction, state-of-the-art wellness sauna, and open fire pit.' },
  { id:'prop-5', title:'Estate de la Rosa', category:'Country Estates', location:'Tuscany, Italy', originalPrice:2200, price:1750, rating:4.95, reviewsCount:39, beds:7, baths:8, guests:14,
    image:'https://images.unsplash.com/photo-1564013799919-ab600027ffc6?auto=format&fit=crop&w=1000&q=80',
    gallery:['https://images.unsplash.com/photo-1564013799919-ab600027ffc6?auto=format&fit=crop&w=1000&q=80'],
    amenities:['Private Vineyard','Olive Grove','Infinity Pool','Cooking Masterclasses','Helipad'],
    description:'A restored 16th-century Tuscan estate surrounded by 40 private acres of organic vineyards and cypress trees. Includes an in-house sommelier.' },
  { id:'prop-6', title:'Villa Seraphina', category:'Oceanfront Villas', location:'Saint Barthélemy, Caribbean', originalPrice:5000, price:3900, rating:4.99, reviewsCount:64, beds:6, baths:7, guests:12,
    image:'https://images.unsplash.com/photo-1580587771525-78b9dba3b914?auto=format&fit=crop&w=1000&q=80',
    gallery:['https://images.unsplash.com/photo-1580587771525-78b9dba3b914?auto=format&fit=crop&w=1000&q=80'],
    amenities:['Infinity Pool','Private Dock','Full Staff','Ocean View','Private Gym'],
    description:'Ultra-contemporary St. Barts cliff residence featuring infinite turquoise waters, private yacht mooring, and open-air pavilion lounging.' }
];

const DEFAULT_REVIEWS = [
  { id:'rev-1', name:'Lady Eleanor Vance', property:'The Royal Azure Villa • Amalfi', rating:5, text:'The Amalfi coastline from Villa Azure was beyond magic. The private yacht trip arranged by our Le Rêve butler made our 10th anniversary unforgettable.', avatar:'https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=200&q=80', status:'published', date:'2026-03-12' },
  { id:'rev-2', name:'Marcus Rothberg', property:'Penthouse Mount Royal • NYC', rating:5, text:'Impeccable privacy in Manhattan. Penthouse Mount Royal delivered views that took our breath away. The check-in was seamless.', avatar:'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?auto=format&fit=crop&w=200&q=80', status:'published', date:'2026-02-28' },
  { id:'rev-3', name:'Sophia Thorne', property:'Alpine Chalet • Zermatt', rating:5, text:'Ski-in ski-out perfection in Zermatt. Heated hot tub right under the stars with Matterhorn views. We will return every winter!', avatar:'https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?auto=format&fit=crop&w=200&q=80', status:'published', date:'2026-02-05' }
];

/* ---------- HELPERS ---------- */
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

function load(key, fallback) {
  try {
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) : fallback;
  } catch(e) { return fallback; }
}
function save(key, value) { localStorage.setItem(key, JSON.stringify(value)); }

function uid(prefix='id') { return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2,7)}`; }

function escapeHtml(str='') {
  return String(str).replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
}

function formatDate(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  return isNaN(d) ? iso : d.toLocaleDateString('en-US', { month:'short', day:'numeric', year:'numeric' });
}

/* ---------- AUTH ---------- */
function isAuthed() { return localStorage.getItem(STORAGE_KEYS.auth) === 'true'; }

function handleLogin(e) {
  e.preventDefault();
  const email = $('#loginEmail').value.trim().toLowerCase();
  const pw = $('#loginPassword').value;
  if (email === ADMIN_CREDENTIALS.email && pw === ADMIN_CREDENTIALS.password) {
    if ($('#rememberMe').checked) localStorage.setItem(STORAGE_KEYS.auth, 'true');
    else sessionStorage.setItem(STORAGE_KEYS.auth, 'true');
    showAdmin();
    adminToast('Welcome back, Admin', 'success');
  } else {
    adminToast('Invalid credentials. Please try again.', 'error');
  }
}

function handleLogout() {
  if (!confirm('Sign out of the admin console?')) return;
  localStorage.removeItem(STORAGE_KEYS.auth);
  sessionStorage.removeItem(STORAGE_KEYS.auth);
  window.location.reload();
}

function togglePasswordVisibility() {
  const input = $('#loginPassword');
  const icon = $('#pwToggleIcon');
  if (input.type === 'password') { input.type = 'text'; icon.className = 'fa-regular fa-eye-slash'; }
  else { input.type = 'password'; icon.className = 'fa-regular fa-eye'; }
}

function showAdmin() {
  $('#loginScreen').classList.add('hidden');
  $('#adminShell').classList.remove('hidden');
  bootstrapData();
  loadSettings();
  renderAll();
  updateBadges();
  handleHashRoute();
}

/* ---------- DATA BOOTSTRAP ---------- */
function bootstrapData() {
  if (!localStorage.getItem(STORAGE_KEYS.properties)) save(STORAGE_KEYS.properties, DEFAULT_PROPERTIES);
  if (!localStorage.getItem(STORAGE_KEYS.reviews)) save(STORAGE_KEYS.reviews, DEFAULT_REVIEWS);
  if (!localStorage.getItem(STORAGE_KEYS.owners)) save(STORAGE_KEYS.owners, []);
  if (!localStorage.getItem(STORAGE_KEYS.inquiries)) save(STORAGE_KEYS.inquiries, []);
  if (!localStorage.getItem(STORAGE_KEYS.journal)) save(STORAGE_KEYS.journal, []);
}

function getProperties() { return load(STORAGE_KEYS.properties, []); }
function getOwners() { return load(STORAGE_KEYS.owners, []); }
function getInquiries() { return load(STORAGE_KEYS.inquiries, []); }
function getReviews() { return load(STORAGE_KEYS.reviews, []); }
function getJournal() { return load(STORAGE_KEYS.journal, []); }

/* ---------- SECTION ROUTING ---------- */
function switchSection(name) {
  $$('.section').forEach(s => s.classList.add('hidden'));
  const target = document.getElementById(`section-${name}`);
  if (target) target.classList.remove('hidden');

  $$('.sidebar-link').forEach(l => l.classList.remove('active'));
  const link = document.querySelector(`.sidebar-link[data-section="${name}"]`);
  if (link) link.classList.add('active');

  const titles = {
    dashboard: ['Dashboard', 'Overview of your luxury portfolio'],
    properties: ['Properties', 'Manage all estate listings'],
    owners: ['Owner Submissions', 'Review incoming estate applications'],
    inquiries: ['Inquiries', 'Guest reservation requests'],
    reviews: ['Reviews', 'Moderate guest testimonials'],
    journal: ['Journal Subscribers', 'Private newsletter list'],
    settings: ['Settings', 'Site configuration & data management']
  };
  const [t, s] = titles[name] || ['Dashboard', ''];
  $('#pageTitle').textContent = t;
  $('#pageSubtitle').textContent = s;

  if (window.innerWidth < 1024) closeSidebar();
}

function handleHashRoute() {
  const hash = (window.location.hash || '#dashboard').replace('#','');
  switchSection(hash);
}

function toggleSidebar() {
  const sb = $('#sidebar');
  const ov = $('#sidebarOverlay');
  sb.classList.toggle('open');
  ov.classList.toggle('hidden');
}
function closeSidebar() {
  $('#sidebar').classList.remove('open');
  $('#sidebarOverlay').classList.add('hidden');
}

/* ---------- RENDER ALL ---------- */
function renderAll() {
  renderDashboard();
  renderProperties();
  renderOwners();
  renderInquiries();
  renderReviews();
  renderJournal();
}

/* ---------- DASHBOARD ---------- */
function renderDashboard() {
  const props = getProperties();
  const inqs = getInquiries();
  const owners = getOwners();
  const revs = getReviews();

  $('#statProperties').textContent = props.length;
  $('#statInquiries').textContent = inqs.length;
  $('#statOwners').textContent = owners.length;
  $('#statReviews').textContent = revs.length;

  const newInq = inqs.filter(i => i.status === 'new').length;
  const pendOwn = owners.filter(o => o.status === 'pending').length;

  const elNewInq = $('#statNewInquiries');
  elNewInq.textContent = newInq > 0 ? `${newInq} New` : 'Caught up';
  elNewInq.className = newInq > 0
    ? 'text-[10px] font-bold uppercase tracking-wider text-amber-600 bg-amber-50 px-2 py-0.5 rounded-full'
    : 'text-[10px] font-bold uppercase tracking-wider text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded-full';

  const elNewOwn = $('#statNewOwners');
  elNewOwn.textContent = pendOwn > 0 ? `${pendOwn} Pending` : 'Caught up';
  elNewOwn.className = pendOwn > 0
    ? 'text-[10px] font-bold uppercase tracking-wider text-amber-600 bg-amber-50 px-2 py-0.5 rounded-full'
    : 'text-[10px] font-bold uppercase tracking-wider text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded-full';

  // Recent inquiries list (latest 4)
  const list = $('#recentInquiriesList');
  const recent = [...inqs].sort((a,b) => new Date(b.createdAt||0) - new Date(a.createdAt||0)).slice(0,4);
  if (recent.length === 0) {
    list.innerHTML = `<p class="text-sm text-charcoal/50 text-center py-8">No inquiries yet. Guest submissions will appear here.</p>`;
  } else {
    list.innerHTML = recent.map(i => `
      <div class="flex items-start gap-3 p-3 rounded-xl hover:bg-ivory/60 transition-all cursor-pointer" onclick="openInquiryDetail('${i.id}')">
        <div class="w-10 h-10 rounded-full bg-primary/10 text-primary flex items-center justify-center flex-shrink-0">
          <i class="fa-solid fa-user text-sm"></i>
        </div>
        <div class="flex-1 min-w-0">
          <div class="flex items-center justify-between gap-2">
            <p class="text-sm font-semibold text-primary truncate">${escapeHtml(i.name || 'Guest')}</p>
            <span class="text-[10px] uppercase tracking-wider font-bold ${i.status === 'new' ? 'text-amber-600' : 'text-emerald-600'}">${i.status || 'new'}</span>
          </div>
          <p class="text-xs text-charcoal/60 truncate">${escapeHtml(i.property || 'General Inquiry')}</p>
          <p class="text-[10px] text-charcoal/40 mt-0.5">${formatDate(i.createdAt)}</p>
        </div>
      </div>
    `).join('');
  }
}

/* ---------- PROPERTIES ---------- */
function renderProperties() {
  const tbody = $('#propertiesTableBody');
  const q = ($('#propertySearch')?.value || '').toLowerCase().trim();
  const props = getProperties().filter(p =>
    !q || p.title.toLowerCase().includes(q) || p.location.toLowerCase().includes(q) || p.category.toLowerCase().includes(q)
  );

  if (props.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6" class="px-5 py-10 text-center text-charcoal/50 text-sm">No properties found.</td></tr>`;
    return;
  }

  tbody.innerHTML = props.map(p => `
    <tr class="hover:bg-ivory/50 transition-colors">
      <td class="px-5 py-3">
        <div class="flex items-center gap-3">
          <img src="${escapeHtml(p.image)}" alt="" class="w-12 h-12 rounded-lg object-cover border border-gold/20 flex-shrink-0">
          <div class="min-w-0">
            <p class="font-semibold text-primary text-sm truncate max-w-[200px]">${escapeHtml(p.title)}</p>
            <p class="text-[11px] text-charcoal/50">${p.beds} bd • ${p.baths} ba • ${p.guests} guests</p>
          </div>
        </div>
      </td>
      <td class="px-5 py-3"><span class="text-[10px] font-bold uppercase tracking-wider text-primary bg-gold/15 px-2.5 py-1 rounded-full border border-gold/30">${escapeHtml(p.category)}</span></td>
      <td class="px-5 py-3 text-xs text-charcoal/70">${escapeHtml(p.location)}</td>
      <td class="px-5 py-3">
        <p class="text-xs text-charcoal/40 line-through">$${Number(p.originalPrice).toLocaleString()}</p>
        <p class="font-semibold text-primary text-sm">$${Number(p.price).toLocaleString()}</p>
      </td>
      <td class="px-5 py-3"><span class="text-xs font-bold text-primary"><i class="fa-solid fa-star text-gold mr-1"></i>${p.rating}</span></td>
      <td class="px-5 py-3">
        <div class="flex items-center justify-end gap-2">
          <button onclick="openPropertyModal('${p.id}')" class="w-8 h-8 rounded-lg bg-ivory hover:bg-gold hover:text-primary text-primary transition-all flex items-center justify-center" title="Edit">
            <i class="fa-solid fa-pen text-xs"></i>
          </button>
          <button onclick="deleteProperty('${p.id}')" class="w-8 h-8 rounded-lg bg-red-50 hover:bg-red-500 hover:text-white text-red-500 transition-all flex items-center justify-center" title="Delete">
            <i class="fa-solid fa-trash text-xs"></i>
          </button>
        </div>
      </td>
    </tr>
  `).join('');
}

function openPropertyModal(id) {
  const modal = $('#propertyModal');
  const form = $('#propertyForm');
  form.reset();

  if (id) {
    const p = getProperties().find(x => x.id === id);
    if (!p) return;
    $('#propertyModalTitle').textContent = 'Edit Property';
    $('#propId').value = p.id;
    $('#propTitle').value = p.title;
    $('#propCategory').value = p.category;
    $('#propLocation').value = p.location;
    $('#propOriginalPrice').value = p.originalPrice;
    $('#propPrice').value = p.price;
    $('#propBeds').value = p.beds;
    $('#propBaths').value = p.baths;
    $('#propGuests').value = p.guests;
    $('#propRating').value = p.rating;
    $('#propReviewsCount').value = p.reviewsCount;
    $('#propImage').value = p.image;
    $('#propGallery').value = (p.gallery||[]).join('\n');
    $('#propAmenities').value = (p.amenities||[]).join(', ');
    $('#propDescription').value = p.description || '';
  } else {
    $('#propertyModalTitle').textContent = 'Add Property';
    $('#propId').value = '';
    $('#propRating').value = 5;
    $('#propReviewsCount').value = 0;
  }

  modal.classList.remove('hidden');
  modal.classList.add('flex');
}

function closePropertyModal() {
  const modal = $('#propertyModal');
  modal.classList.add('hidden');
  modal.classList.remove('flex');
}

function saveProperty(e) {
  e.preventDefault();
  const props = getProperties();
  const id = $('#propId').value;

  const payload = {
    title: $('#propTitle').value.trim(),
    category: $('#propCategory').value,
    location: $('#propLocation').value.trim(),
    originalPrice: Number($('#propOriginalPrice').value),
    price: Number($('#propPrice').value),
    beds: Number($('#propBeds').value),
    baths: Number($('#propBaths').value),
    guests: Number($('#propGuests').value),
    rating: Number($('#propRating').value),
    reviewsCount: Number($('#propReviewsCount').value),
    image: $('#propImage').value.trim(),
    gallery: $('#propGallery').value.split('\n').map(s=>s.trim()).filter(Boolean),
    amenities: $('#propAmenities').value.split(',').map(s=>s.trim()).filter(Boolean),
    description: $('#propDescription').value.trim()
  };

  if (id) {
    const idx = props.findIndex(p => p.id === id);
    if (idx > -1) props[idx] = { ...props[idx], ...payload };
    adminToast('Property updated successfully.', 'success');
  } else {
    props.push({ id: uid('prop'), ...payload });
    adminToast('Property added successfully.', 'success');
  }

  save(STORAGE_KEYS.properties, props);
  closePropertyModal();
  renderProperties();
  renderDashboard();
}

function deleteProperty(id) {
  if (!confirm('Delete this property permanently?')) return;
  const props = getProperties().filter(p => p.id !== id);
  save(STORAGE_KEYS.properties, props);
  renderProperties();
  renderDashboard();
  adminToast('Property deleted.', 'info');
}

/* ---------- OWNERS ---------- */
function renderOwners() {
  const tbody = $('#ownersTableBody');
  const owners = getOwners();

  if (owners.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6" class="px-5 py-10 text-center text-charcoal/50 text-sm">No owner submissions yet.</td></tr>`;
    return;
  }

  tbody.innerHTML = owners.map(o => {
    const statusColors = {
      pending: 'text-amber-600 bg-amber-50',
      approved: 'text-emerald-600 bg-emerald-50',
      rejected: 'text-red-600 bg-red-50'
    };
    return `
      <tr class="hover:bg-ivory/50 transition-colors">
        <td class="px-5 py-3">
          <p class="font-semibold text-primary text-sm">${escapeHtml(o.name)}</p>
          <p class="text-[11px] text-charcoal/50">${escapeHtml(o.email)}</p>
        </td>
        <td class="px-5 py-3 text-xs text-charcoal/70">${escapeHtml(o.propType || '—')}</td>
        <td class="px-5 py-3 text-xs text-charcoal/70">${escapeHtml(o.location || '—')}</td>
        <td class="px-5 py-3 text-xs text-charcoal/60">${formatDate(o.createdAt)}</td>
        <td class="px-5 py-3"><span class="text-[10px] font-bold uppercase tracking-wider px-2.5 py-1 rounded-full ${statusColors[o.status] || statusColors.pending}">${o.status || 'pending'}</span></td>
        <td class="px-5 py-3">
          <div class="flex items-center justify-end gap-2">
            <button onclick="openOwnerDetail('${o.id}')" class="w-8 h-8 rounded-lg bg-ivory hover:bg-gold hover:text-primary text-primary transition-all flex items-center justify-center" title="View"><i class="fa-solid fa-eye text-xs"></i></button>
            <button onclick="deleteOwner('${o.id}')" class="w-8 h-8 rounded-lg bg-red-50 hover:bg-red-500 hover:text-white text-red-500 transition-all flex items-center justify-center" title="Delete"><i class="fa-solid fa-trash text-xs"></i></button>
          </div>
        </td>
      </tr>
    `;
  }).join('');
}

function openOwnerDetail(id) {
  const o = getOwners().find(x => x.id === id);
  if (!o) return;
  const content = $('#detailModalContent');
  content.innerHTML = `
    <h3 class="font-serif text-2xl font-semibold text-primary mb-1">Owner Submission</h3>
    <p class="text-xs text-charcoal/60 mb-6">Received ${formatDate(o.createdAt)}</p>
    <div class="space-y-3 text-sm">
      <div class="flex justify-between border-b border-charcoal/10 pb-2"><span class="text-charcoal/60">Owner</span><span class="font-semibold text-primary">${escapeHtml(o.name)}</span></div>
      <div class="flex justify-between border-b border-charcoal/10 pb-2"><span class="text-charcoal/60">Email</span><span class="font-semibold text-primary">${escapeHtml(o.email)}</span></div>
      <div class="flex justify-between border-b border-charcoal/10 pb-2"><span class="text-charcoal/60">Phone</span><span class="font-semibold text-primary">${escapeHtml(o.phone || '—')}</span></div>
      <div class="flex justify-between border-b border-charcoal/10 pb-2"><span class="text-charcoal/60">Property Type</span><span class="font-semibold text-primary">${escapeHtml(o.propType || '—')}</span></div>
      <div class="flex justify-between border-b border-charcoal/10 pb-2"><span class="text-charcoal/60">Location</span><span class="font-semibold text-primary">${escapeHtml(o.location || '—')}</span></div>
      <div class="flex justify-between border-b border-charcoal/10 pb-2"><span class="text-charcoal/60">Capacity</span><span class="font-semibold text-primary">${escapeHtml(o.bedrooms || '—')}</span></div>
      ${o.photoUrl ? `<div class="border-b border-charcoal/10 pb-2"><p class="text-charcoal/60 mb-1">Photo / Deck Link</p><a href="${escapeHtml(o.photoUrl)}" target="_blank" class="text-gold hover:underline text-xs break-all">${escapeHtml(o.photoUrl)}</a></div>` : ''}
      ${o.message ? `<div class="border-b border-charcoal/10 pb-2"><p class="text-charcoal/60 mb-1">Highlights</p><p class="text-primary">${escapeHtml(o.message)}</p></div>` : ''}
    </div>
    <div class="flex flex-wrap gap-3 mt-6">
      <button onclick="setOwnerStatus('${o.id}','approved')" class="flex-1 bg-emerald-600 text-white hover:bg-emerald-700 px-4 py-2.5 rounded-xl text-xs font-bold uppercase tracking-wider transition-all"><i class="fa-solid fa-check mr-1"></i> Approve</button>
      <button onclick="setOwnerStatus('${o.id}','rejected')" class="flex-1 bg-red-500 text-white hover:bg-red-600 px-4 py-2.5 rounded-xl text-xs font-bold uppercase tracking-wider transition-all"><i class="fa-solid fa-xmark mr-1"></i> Reject</button>
      <button onclick="closeDetailModal()" class="flex-1 border border-charcoal/15 hover:bg-ivory px-4 py-2.5 rounded-xl text-xs font-semibold transition-all">Close</button>
    </div>
  `;
  $('#detailModal').classList.remove('hidden');
  $('#detailModal').classList.add('flex');
}

function setOwnerStatus(id, status) {
  const owners = getOwners().map(o => o.id === id ? { ...o, status } : o);
  save(STORAGE_KEYS.owners, owners);
  closeDetailModal();
  renderOwners();
  renderDashboard();
  updateBadges();
  adminToast(`Owner submission ${status}.`, status === 'approved' ? 'success' : 'info');
}

function deleteOwner(id) {
  if (!confirm('Delete this owner submission?')) return;
  save(STORAGE_KEYS.owners, getOwners().filter(o => o.id !== id));
  renderOwners();
  renderDashboard();
  updateBadges();
  adminToast('Owner submission deleted.', 'info');
}

/* ---------- INQUIRIES ---------- */
function renderInquiries() {
  const tbody = $('#inquiriesTableBody');
  const inqs = getInquiries();

  if (inqs.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6" class="px-5 py-10 text-center text-charcoal/50 text-sm">No inquiries yet.</td></tr>`;
    return;
  }

  tbody.innerHTML = inqs.map(i => {
    const statusColors = {
      new: 'text-amber-600 bg-amber-50',
      contacted: 'text-blue-600 bg-blue-50',
      booked: 'text-emerald-600 bg-emerald-50',
      archived: 'text-charcoal/60 bg-ivory-dark'
    };
    return `
      <tr class="hover:bg-ivory/50 transition-colors cursor-pointer" onclick="openInquiryDetail('${i.id}')">
        <td class="px-5 py-3">
          <p class="font-semibold text-primary text-sm">${escapeHtml(i.name)}</p>
          <p class="text-[11px] text-charcoal/50">${escapeHtml(i.email || '')}</p>
        </td>
        <td class="px-5 py-3 text-xs text-charcoal/70">${escapeHtml(i.property || 'General')}</td>
        <td class="px-5 py-3 text-xs text-charcoal/60">${i.checkIn ? `${formatDate(i.checkIn)} → ${formatDate(i.checkOut)}` : '—'}</td>
        <td class="px-5 py-3 text-xs text-charcoal/70">${escapeHtml(i.guests || '—')}</td>
        <td class="px-5 py-3"><span class="text-[10px] font-bold uppercase tracking-wider px-2.5 py-1 rounded-full ${statusColors[i.status] || statusColors.new}">${i.status || 'new'}</span></td>
        <td class="px-5 py-3">
          <div class="flex items-center justify-end gap-2" onclick="event.stopPropagation()">
            <button onclick="deleteInquiry('${i.id}')" class="w-8 h-8 rounded-lg bg-red-50 hover:bg-red-500 hover:text-white text-red-500 transition-all flex items-center justify-center" title="Delete"><i class="fa-solid fa-trash text-xs"></i></button>
          </div>
        </td>
      </tr>
    `;
  }).join('');
}

function openInquiryDetail(id) {
  const i = getInquiries().find(x => x.id === id);
  if (!i) return;
  const content = $('#detailModalContent');
  content.innerHTML = `
    <h3 class="font-serif text-2xl font-semibold text-primary mb-1">Guest Inquiry</h3>
    <p class="text-xs text-charcoal/60 mb-6">Received ${formatDate(i.createdAt)}</p>
    <div class="space-y-3 text-sm">
      <div class="flex justify-between border-b border-charcoal/10 pb-2"><span class="text-charcoal/60">Guest</span><span class="font-semibold text-primary">${escapeHtml(i.name)}</span></div>
      <div class="flex justify-between border-b border-charcoal/10 pb-2"><span class="text-charcoal/60">Email</span><span class="font-semibold text-primary">${escapeHtml(i.email)}</span></div>
      <div class="flex justify-between border-b border-charcoal/10 pb-2"><span class="text-charcoal/60">Phone</span><span class="font-semibold text-primary">${escapeHtml(i.phone || '—')}</span></div>
      <div class="flex justify-between border-b border-charcoal/10 pb-2"><span class="text-charcoal/60">Property</span><span class="font-semibold text-primary">${escapeHtml(i.property || 'General')}</span></div>
      <div class="flex justify-between border-b border-charcoal/10 pb-2"><span class="text-charcoal/60">Check-In</span><span class="font-semibold text-primary">${formatDate(i.checkIn)}</span></div>
      <div class="flex justify-between border-b border-charcoal/10 pb-2"><span class="text-charcoal/60">Check-Out</span><span class="font-semibold text-primary">${formatDate(i.checkOut)}</span></div>
      <div class="flex justify-between border-b border-charcoal/10 pb-2"><span class="text-charcoal/60">Guests</span><span class="font-semibold text-primary">${escapeHtml(i.guests || '—')}</span></div>
      ${i.message ? `<div class="border-b border-charcoal/10 pb-2"><p class="text-charcoal/60 mb-1">Special Requests</p><p class="text-primary">${escapeHtml(i.message)}</p></div>` : ''}
    </div>
    <div class="mt-6">
      <p class="text-xs font-bold uppercase tracking-wider text-primary/80 mb-2">Set Status</p>
      <div class="flex flex-wrap gap-2">
        <button onclick="setInquiryStatus('${i.id}','new')" class="px-3 py-2 rounded-lg text-xs font-semibold border ${i.status==='new'?'bg-amber-500 text-white border-amber-500':'border-charcoal/15 hover:bg-amber-50'}">New</button>
        <button onclick="setInquiryStatus('${i.id}','contacted')" class="px-3 py-2 rounded-lg text-xs font-semibold border ${i.status==='contacted'?'bg-blue-600 text-white border-blue-600':'border-charcoal/15 hover:bg-blue-50'}">Contacted</button>
        <button onclick="setInquiryStatus('${i.id}','booked')" class="px-3 py-2 rounded-lg text-xs font-semibold border ${i.status==='booked'?'bg-emerald-600 text-white border-emerald-600':'border-charcoal/15 hover:bg-emerald-50'}">Booked</button>
        <button onclick="setInquiryStatus('${i.id}','archived')" class="px-3 py-2 rounded-lg text-xs font-semibold border ${i.status==='archived'?'bg-charcoal text-white border-charcoal':'border-charcoal/15 hover:bg-ivory'}">Archived</button>
      </div>
    </div>
    <div class="flex gap-3 mt-6">
      <a href="mailto:${escapeHtml(i.email)}" class="flex-1 bg-primary text-gold hover:bg-gold hover:text-primary px-4 py-2.5 rounded-xl text-xs font-bold uppercase tracking-wider transition-all text-center"><i class="fa-solid fa-reply mr-1"></i> Reply by Email</a>
      <button onclick="closeDetailModal()" class="flex-1 border border-charcoal/15 hover:bg-ivory px-4 py-2.5 rounded-xl text-xs font-semibold transition-all">Close</button>
    </div>
  `;
  $('#detailModal').classList.remove('hidden');
  $('#detailModal').classList.add('flex');
}

function setInquiryStatus(id, status) {
  const inqs = getInquiries().map(i => i.id === id ? { ...i, status } : i);
  save(STORAGE_KEYS.inquiries, inqs);
  closeDetailModal();
  renderInquiries();
  renderDashboard();
  updateBadges();
  adminToast(`Inquiry marked as ${status}.`, 'success');
}

function deleteInquiry(id) {
  if (!confirm('Delete this inquiry?')) return;
  save(STORAGE_KEYS.inquiries, getInquiries().filter(i => i.id !== id));
  renderInquiries();
  renderDashboard();
  updateBadges();
  adminToast('Inquiry deleted.', 'info');
}

/* ---------- REVIEWS ---------- */
function renderReviews() {
  const grid = $('#reviewsGrid');
  const revs = getReviews();

  if (revs.length === 0) {
    grid.innerHTML = `<div class="col-span-full text-center py-16 text-charcoal/50 text-sm bg-white rounded-2xl border border-gold/20">No reviews yet.</div>`;
    return;
  }

  grid.innerHTML = revs.map(r => `
    <div class="bg-white rounded-2xl p-6 border border-gold/20 shadow-sm flex flex-col">
      <div class="flex items-center gap-1 text-gold text-xs mb-3">
        ${Array.from({length:5}).map((_,i)=>`<i class="fa-solid fa-star ${i < r.rating ? '' : 'text-charcoal/20'}"></i>`).join('')}
        <span class="ml-auto text-[10px] font-bold uppercase tracking-wider ${r.status==='published'?'text-emerald-600':r.status==='pending'?'text-amber-600':'text-red-600'}">${r.status || 'published'}</span>
      </div>
      <p class="text-charcoal/80 text-sm italic flex-1 mb-4">"${escapeHtml(r.text)}"</p>
      <div class="flex items-center gap-3 pt-3 border-t border-charcoal/5">
        <img src="${escapeHtml(r.avatar || 'https://via.placeholder.com/40')}" alt="" class="w-10 h-10 rounded-full object-cover border-2 border-gold">
        <div class="min-w-0 flex-1">
          <p class="font-serif text-base font-semibold text-primary truncate">${escapeHtml(r.name)}</p>
          <p class="text-[11px] text-gold truncate">${escapeHtml(r.property)}</p>
        </div>
      </div>
      <div class="flex gap-2 mt-4">
        ${r.status !== 'published' ? `<button onclick="setReviewStatus('${r.id}','published')" class="flex-1 bg-emerald-600 text-white hover:bg-emerald-700 px-3 py-2 rounded-lg text-[10px] font-bold uppercase tracking-wider transition-all">Publish</button>` : `<button onclick="setReviewStatus('${r.id}','pending')" class="flex-1 border border-charcoal/15 hover:bg-ivory px-3 py-2 rounded-lg text-[10px] font-bold uppercase tracking-wider transition-all">Unpublish</button>`}
        <button onclick="deleteReview('${r.id}')" class="w-9 h-9 rounded-lg bg-red-50 hover:bg-red-500 hover:text-white text-red-500 transition-all flex items-center justify-center"><i class="fa-solid fa-trash text-xs"></i></button>
      </div>
    </div>
  `).join('');
}

function setReviewStatus(id, status) {
  const revs = getReviews().map(r => r.id === id ? { ...r, status } : r);
  save(STORAGE_KEYS.reviews, revs);
  renderReviews();
  adminToast(`Review ${status}.`, 'success');
}

function deleteReview(id) {
  if (!confirm('Delete this review?')) return;
  save(STORAGE_KEYS.reviews, getReviews().filter(r => r.id !== id));
  renderReviews();
  renderDashboard();
  adminToast('Review deleted.', 'info');
}

/* ---------- JOURNAL ---------- */
function renderJournal() {
  const tbody = $('#journalTableBody');
  const subs = getJournal();

  if (subs.length === 0) {
    tbody.innerHTML = `<tr><td colspan="3" class="px-5 py-10 text-center text-charcoal/50 text-sm">No subscribers yet.</td></tr>`;
    return;
  }

  tbody.innerHTML = subs.map(s => `
    <tr class="hover:bg-ivory/50 transition-colors">
      <td class="px-5 py-3 text-sm text-primary font-medium">${escapeHtml(s.email)}</td>
      <td class="px-5 py-3 text-xs text-charcoal/60">${formatDate(s.subscribedAt)}</td>
      <td class="px-5 py-3 text-right">
        <button onclick="deleteJournalSub('${s.id}')" class="w-8 h-8 rounded-lg bg-red-50 hover:bg-red-500 hover:text-white text-red-500 transition-all inline-flex items-center justify-center"><i class="fa-solid fa-trash text-xs"></i></button>
      </td>
    </tr>
  `).join('');
}

function deleteJournalSub(id) {
  if (!confirm('Remove this subscriber?')) return;
  save(STORAGE_KEYS.journal, getJournal().filter(s => s.id !== id));
  renderJournal();
  adminToast('Subscriber removed.', 'info');
}

/* ---------- BADGES ---------- */
function updateBadges() {
  const inqNew = getInquiries().filter(i => i.status === 'new' || !i.status).length;
  const ownPending = getOwners().filter(o => o.status === 'pending' || !o.status).length;
  const inqBadge = $('#inquiryCountBadge');
  const ownBadge = $('#ownerCountBadge');

  if (inqNew > 0) { inqBadge.textContent = inqNew; inqBadge.classList.remove('hidden'); } else inqBadge.classList.add('hidden');
  if (ownPending > 0) { ownBadge.textContent = ownPending; ownBadge.classList.remove('hidden'); } else ownBadge.classList.add('hidden');

  $('#notifDot').style.display = (inqNew + ownPending) > 0 ? 'block' : 'none';
}

/* ---------- SETTINGS ---------- */
function loadSettings() {
  const s = load(STORAGE_KEYS.settings, {
    siteName: 'Le Rêve Properties',
    contactEmail: 'concierge@lereveproperties.com',
    whatsapp: '+1 800 LE-REVE',
    instagram: '@lereveproperties'
  });
  $('#setSiteName').value = s.siteName;
  $('#setContactEmail').value = s.contactEmail;
  $('#setWhatsapp').value = s.whatsapp;
  $('#setInstagram').value = s.instagram;
}

function saveSettings(e) {
  e.preventDefault();
  const s = {
    siteName: $('#setSiteName').value.trim(),
    contactEmail: $('#setContactEmail').value.trim(),
    whatsapp: $('#setWhatsapp').value.trim(),
    instagram: $('#setInstagram').value.trim()
  };
  save(STORAGE_KEYS.settings, s);
  adminToast('Settings saved.', 'success');
}

function exportData() {
  const data = {
    exportedAt: new Date().toISOString(),
    properties: getProperties(),
    owners: getOwners(),
    inquiries: getInquiries(),
    reviews: getReviews(),
    journal: getJournal(),
    settings: load(STORAGE_KEYS.settings, {})
  };
  const blob = new Blob([JSON.stringify(data, null, 2)], { type:'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `lereve-backup-${new Date().toISOString().slice(0,10)}.json`;
  a.click();
  URL.revokeObjectURL(url);
  adminToast('Data exported successfully.', 'success');
}

function importData(e) {
  const file = e.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = (ev) => {
    try {
      const data = JSON.parse(ev.target.result);
      if (data.properties) save(STORAGE_KEYS.properties, data.properties);
      if (data.owners) save(STORAGE_KEYS.owners, data.owners);
      if (data.inquiries) save(STORAGE_KEYS.inquiries, data.inquiries);
      if (data.reviews) save(STORAGE_KEYS.reviews, data.reviews);
      if (data.journal) save(STORAGE_KEYS.journal, data.journal);
      if (data.settings) save(STORAGE_KEYS.settings, data.settings);
      renderAll();
      loadSettings();
      updateBadges();
      adminToast('Data imported successfully.', 'success');
    } catch(err) {
      adminToast('Invalid JSON file.', 'error');
    }
  };
  reader.readAsText(file);
  e.target.value = '';
}

function resetAllData() {
  if (!confirm('This will delete ALL data and restore defaults. Continue?')) return;
  Object.values(STORAGE_KEYS).forEach(k => localStorage.removeItem(k));
  bootstrapData();
  renderAll();
  loadSettings();
  updateBadges();
  adminToast('All data reset to defaults.', 'info');
}

/* ---------- MODALS ---------- */
function closeDetailModal() {
  const m = $('#detailModal');
  m.classList.add('hidden');
  m.classList.remove('flex');
}

/* ---------- TOAST ---------- */
function adminToast(message, type = 'success') {
  const container = $('#adminToast');
  const toast = document.createElement('div');
  const bg = type === 'success' ? 'bg-primary text-gold border-gold' :
             type === 'error' ? 'bg-red-600 text-white border-red-400' :
             'bg-gold text-primary border-primary';
  const icon = type === 'success' ? 'fa-circle-check' :
               type === 'error' ? 'fa-circle-exclamation' : 'fa-circle-info';
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
  // Restore session if remembered
  if (localStorage.getItem(STORAGE_KEYS.auth) === 'true' || sessionStorage.getItem(STORAGE_KEYS.auth) === 'true') {
    showAdmin();
  }

  // Close modals on backdrop click
  ['propertyModal','detailModal'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.addEventListener('click', (e) => { if (e.target === el) el.classList.add('hidden'); });
  });

  // Escape key closes modals
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      closePropertyModal();
      closeDetailModal();
    }
  });
});

/* ---------- PUBLIC API for integration with index.html ---------- */
window.LeReveAdminAPI = {
  getProperties: () => load(STORAGE_KEYS.properties, DEFAULT_PROPERTIES),
  getReviews: () => load(STORAGE_KEYS.reviews, DEFAULT_REVIEWS),
  getSettings: () => load(STORAGE_KEYS.settings, {}),
  addInquiry: (inq) => {
    const list = load(STORAGE_KEYS.inquiries, []);
    list.unshift({ id: uid('inq'), status:'new', createdAt: new Date().toISOString(), ...inq });
    save(STORAGE_KEYS.inquiries, list);
  },
  addOwnerSubmission: (owner) => {
    const list = load(STORAGE_KEYS.owners, []);
    list.unshift({ id: uid('own'), status:'pending', createdAt: new Date().toISOString(), ...owner });
    save(STORAGE_KEYS.owners, list);
  },
  addJournalSub: (email) => {
    const list = load(STORAGE_KEYS.journal, []);
    if (!list.some(s => s.email.toLowerCase() === email.toLowerCase())) {
      list.unshift({ id: uid('sub'), email, subscribedAt: new Date().toISOString() });
      save(STORAGE_KEYS.journal, list);
    }
  }
};