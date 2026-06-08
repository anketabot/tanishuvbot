const tg = window.Telegram?.WebApp;
if (tg) {
  tg.ready();
  tg.expand();
  try { tg.setHeaderColor('#1A73E8'); } catch(e) {}
  try { tg.setBackgroundColor('#F8FAFF'); } catch(e) {}
}

let userId = null;
let userName = '';
let userFirstName = '';

if (tg?.initDataUnsafe?.user?.id) {
  userId = tg.initDataUnsafe.user.id;
  userName = tg.initDataUnsafe.user.username || '';
  userFirstName = tg.initDataUnsafe.user.first_name || '';
} else if (tg?.initData) {
  const params = new URLSearchParams(tg.initData);
  const userJson = params.get('user');
  if (userJson) {
    try {
      const user = JSON.parse(userJson);
      userId = user.id;
      userName = user.username || '';
      userFirstName = user.first_name || '';
    } catch (e) {}
  }
}

if (!userId && localStorage.getItem('dating_profile')) {
  userId = 123456789;
}

const API_BASE_URL = 'https://tanishuvbot-production.up.railway.app';

const MAX_WEBAPP_DATA_SIZE = 6000;

function sendWebAppData(payload) {
  if (!tg) return;
  const json = JSON.stringify(payload);
  if (json.length <= MAX_WEBAPP_DATA_SIZE) {
    tg.sendData(json);
    return;
  }
  if (payload.action === 'save_profile' && payload.profile) {
    const safeProfile = { ...payload.profile, photo_base64: null };
    const safePayload = { ...payload, profile: safeProfile };
    const safeJson = JSON.stringify(safePayload);
    if (safeJson.length <= MAX_WEBAPP_DATA_SIZE) {
      tg.sendData(safeJson);
      showToast('Rasm telegramga yuborilmadi, lekin anketangiz saqlandi.');
      return;
    }
  }
  showToast('Xatolik: ma\'lumot juda uzun.');
}

const ICONS = {
  search: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>`,
  user: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>`,
  users: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>`,
  male: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="6" r="4"/><line x1="12" y1="10" x2="12" y2="16"/><line x1="6" y1="12" x2="18" y2="12"/><line x1="12" y1="16" x2="8" y2="22"/><line x1="12" y1="16" x2="16" y2="22"/></svg>`,
  female: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="6" r="4"/><path d="M6 20 L10 12 L14 12 L18 20"/><line x1="6" y1="18" x2="10" y2="12"/><line x1="18" y1="18" x2="14" y2="12"/></svg>`,
  heart: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg>`,
  message: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>`,
  ban: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="4.93" y1="4.93" x2="19.07" y2="19.07"/></svg>`,
  camera: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/><circle cx="12" cy="13" r="4"/></svg>`,
  check: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>`,
  edit: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>`,
  share: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/></svg>`,
  copy: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>`,
  alert: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>`,
  info: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>`,
  mapPin: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>`,
  target: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/></svg>`,
  book: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>`,
  atSign: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="4"/><path d="M16 8v5a3 3 0 0 0 6 0v-1a10 10 0 1 0-3.92 7.94"/></svg>`,
  x: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>`
};

let selectedGender = '';
let selectedSearchGender = '';
let selectedInterests = [];
let selectedGoals = [];
let selectedSearchGoals = [];
let photoBase64 = '';
let savedProfile = null;

const uzbekCities = [
  "Toshkent", "Samarqand", "Buxoro", "Namangan", "Andijon", "Farg'ona",
  "Nukus", "Qarshi", "Termiz", "Jizzax", "Sirdaryo", "Guliston",
  "Navoiy", "Urganch", "Xiva", "Marg'ilon", "Qo'qon", "Chirchiq",
  "Olmaliq", "Bekobod", "Yangiyo'l", "Nurafshon", "Denov", "Bog'ot",
  "Muborak", "G'uzor", "Kitob", "Shahrisabz", "Karshi", "Shofirkon",
  "Kogon", "Vobkent", "Qorovulbozor", "Beshariq", "Rishton", "Quva",
  "Oʻzbekiston", "Iskandar", "Zarafshon", "Uchqo'rg'on", "Chust",
  "Pop", "Toyloq", "Kattaqo'rg'on", "Urgut", "Payariq", "Paxtakor"
];

// Chat state
let currentChatMatchId = null;
let currentChatPartner = null;
let chatRefreshInterval = null;
let chatsPollInterval = null;

function isRegistered() {
  return !!getProfile();
}

function getProfile() {
  if (savedProfile) return savedProfile;
  const data = localStorage.getItem('dating_profile');
  return data ? JSON.parse(data) : null;
}

function setSavedProfile(profile) {
  savedProfile = profile;
  if (profile) {
    localStorage.setItem('dating_profile', JSON.stringify(profile));
  } else {
    localStorage.removeItem('dating_profile');
  }
}

async function apiPost(endpoint, body) {
  const baseUrl = API_BASE_URL ? API_BASE_URL.replace(/\/$/, '') : `${window.location.protocol}//${window.location.host}`;
  try {
    const res = await fetch(`${baseUrl}${endpoint}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
      body: JSON.stringify(body),
      mode: 'cors'
    });
    return await res.json();
  } catch (e) {
    console.error('API error:', e);
    return { success: false, error: e.message };
  }
}

async function saveProfileToServer(profile, telegramId) {
  const data = await apiPost('/api/save_profile', { telegram_id: telegramId, profile });
  return data.success === true;
}

async function fetchUserProfile(telegramId) {
  const data = await apiPost('/api/profile', { telegram_id: telegramId });
  return data.success ? data.user : null;
}

// === CITY SUGGEST ===
function suggestCity(val) {
  showSuggestions('city-suggestions', val, (city) => {
    document.getElementById('inp-city').value = city;
    document.getElementById('city-suggestions').style.display = 'none';
  });
}

function suggestCitySearch(val) {
  showSuggestions('sf-city-suggestions', val, (city) => {
    document.getElementById('sf-city').value = city;
    document.getElementById('sf-city-suggestions').style.display = 'none';
  });
}

function showSuggestions(containerId, val, onSelect) {
  const box = document.getElementById(containerId);
  if (!val || val.length < 1) { box.style.display = 'none'; return; }
  const filtered = uzbekCities.filter(c => c.toLowerCase().includes(val.toLowerCase())).slice(0, 6);
  if (!filtered.length) { box.style.display = 'none'; return; }

  const fnName = `_sugg_${containerId}`;
  box.innerHTML = filtered.map(c =>
    `<div class="suggestion-item" onclick="window['${fnName}'] && window['${fnName}']('${c}')">${c}</div>`
  ).join('');
  window[fnName] = (city) => {
    onSelect(city);
    box.style.display = 'none';
  };
  box.style.display = 'block';
}

// === PAGE NAVIGATION ===
function showPage(name) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
  
  const pageEl = document.getElementById('page-' + name);
  if (pageEl) pageEl.classList.add('active');
  
  const navBtn = document.getElementById('nav-' + name);
  if (navBtn) navBtn.classList.add('active');

  if (name === 'search') {
    setDefaultSearchGender();
    loadPendingLikesIndicator();
  }
  if (name === 'myprofile') loadMyProfile();
  if (name === 'chats') loadChats();
}

// === SEARCH ===
function selectGender(g) {
  selectedGender = g;
  document.getElementById('gender-erkak').classList.toggle('selected', g === 'erkak');
  document.getElementById('gender-ayol').classList.toggle('selected', g === 'ayol');
}

function getOppositeGender(g) {
  return g === 'erkak' ? 'ayol' : g === 'ayol' ? 'erkak' : '';
}

function selectSearchGender(g) {
  selectedSearchGender = g;
  document.getElementById('sf-gender-erkak').classList.toggle('selected', g === 'erkak');
  document.getElementById('sf-gender-ayol').classList.toggle('selected', g === 'ayol');
}

function setDefaultSearchGender() {
  const profile = getProfile();
  const opposite = profile ? getOppositeGender(profile.gender) : '';
  if (opposite) selectSearchGender(opposite);
}

// === CHIP TOGGLE ===
function toggleChip(el, group) {
  el.classList.toggle('selected');
  const value = el.textContent.trim();

  if (group === 'interests') {
    if (el.classList.contains('selected')) selectedInterests.push(value);
    else selectedInterests = selectedInterests.filter(i => i !== value);
  } else if (group === 'goals') {
    if (el.classList.contains('selected')) selectedGoals.push(value);
    else selectedGoals = selectedGoals.filter(i => i !== value);
  } else if (group === 'sf-goals') {
    if (el.classList.contains('selected')) selectedSearchGoals.push(value);
    else selectedSearchGoals = selectedSearchGoals.filter(i => i !== value);
  }
}

// === PHOTO PREVIEW ===
function previewPhoto(input) {
  const file = input.files[0];
  if (!file) return;
  if (file.size > 5 * 1024 * 1024) { showToast('Rasm 5MB dan katta!'); return; }

  const reader = new FileReader();
  reader.onload = (e) => {
    photoBase64 = e.target.result;
    const preview = document.getElementById('photo-preview');
    preview.src = photoBase64;
    preview.style.display = 'block';
    document.getElementById('upload-icon').style.display = 'none';
    document.getElementById('upload-text').style.display = 'none';
    document.getElementById('upload-sub').style.display = 'none';
  };
  reader.readAsDataURL(file);
}

// === SAVE PROFILE ===
async function saveProfile() {
  const name = document.getElementById('inp-name').value.trim();
  const age = parseInt(document.getElementById('inp-age').value);
  const city = document.getElementById('inp-city').value.trim();
  const zodiac = document.getElementById('sel-zodiac').value;

  if (!selectedGender) { showToast('Jinsni tanlang!'); return; }
  if (!name) { showToast('Ismingizni kiriting!'); return; }
  if (!age || age < 16 || age > 80) { showToast('Yoshingizni to\'g\'ri kiriting! (16-80)'); return; }
  if (!city) { showToast('Shahar/tuman kiriting!'); return; }
  if (selectedGoals.length === 0) { showToast('Kamida 1 ta maqsad tanlang!'); return; }

  const profile = {
    gender: selectedGender,
    full_name: name,
    age: age,
    city: city,
    zodiac: zodiac,
    interests: selectedInterests,
    goals: selectedGoals,
    photo_base64: photoBase64 || null
  };

  setSavedProfile(profile);

  let serverSaved = false;
  if (userId) {
    serverSaved = await saveProfileToServer(profile, userId);
  }

  if (tg) {
    sendWebAppData({ action: 'save_profile', profile });
  }

  setDefaultSearchGender();
  showToast(serverSaved ? 'Anketa muvaffaqiyatli saqlandi!' : 'Anketa mahalliy saqlandi.');
  
  document.querySelector('.bottom-nav').style.display = 'flex';
  showPage('search');
}

// === SEARCH ===
function doSearch() {
  const filters = {};
  if (selectedSearchGender) filters.gender = selectedSearchGender;
  const ageFrom = document.getElementById('sf-age-from').value?.trim();
  if (ageFrom) filters.age_from = parseInt(ageFrom);
  const ageTo = document.getElementById('sf-age-to').value?.trim();
  if (ageTo) filters.age_to = parseInt(ageTo);
  const city = document.getElementById('sf-city').value?.trim();
  if (city) filters.city = city;
  if (selectedSearchGoals.length > 0) filters.goals = selectedSearchGoals;

  const resultsEl = document.getElementById('search-results');
  resultsEl.innerHTML = '<div class="loading"><div class="spinner"></div> Qidirilmoqda...</div>';

  fetchSearchResults(userId || 0, filters);
}

async function fetchSearchResults(telegramId, filters) {
  const resultsEl = document.getElementById('search-results');
  
  try {
    const data = await apiPost('/api/search', { telegram_id: telegramId || 0, filters });
    
    if (data.success && data.users && data.users.length > 0) {
      resultsEl.innerHTML = data.users.map(u => renderProfileCard(u)).join('');
    } else {
      resultsEl.innerHTML = `<div class="empty-state"><div class="empty-icon">${ICONS.info}</div><h3>Hech kim topilmadi</h3><p>Hozircha sizga mos foydalanuvchilar yo'q. Keyinroq qayta urinib ko'ring.</p></div>`;
    }
  } catch (error) {
    showToast('Server bilan aloqa yo\'q');
    resultsEl.innerHTML = `<div class="empty-state"><div class="empty-icon">${ICONS.alert}</div><h3>Ulana olmadi</h3><p>Internet aloqasini tekshiring.</p></div>`;
  }
}

async function loadPendingLikesIndicator() {
  const badge = document.getElementById('search-likes-badge');
  if (!badge || !userId) {
    if (badge) badge.style.display = 'none';
    return;
  }
  const data = await apiPost('/api/likes/received', { telegram_id: userId });
  const count = data.success ? (data.likes || []).length : 0;
  if (count > 0) {
    badge.textContent = count > 9 ? '9+' : count;
    badge.style.display = 'inline-flex';
  } else {
    badge.style.display = 'none';
  }
}

async function openIncomingLikesModal() {
  const modal = document.getElementById('likes-modal');
  const body = document.getElementById('likes-modal-body');
  if (!modal || !body) return;
  modal.style.display = 'flex';
  if (!userId) {
    body.innerHTML = `<div class="empty-state"><div class="empty-icon">${ICONS.alert}</div><h3>Foydalanuvchi aniqlanmadi</h3><p>Telegram ID topilmadi. Web Appni Telegram ichida oching yoki qayta kirib ko'ring.</p></div>`;
    return;
  }
  body.innerHTML = '<div class="loading"><div class="spinner"></div> Yuklanmoqda...</div>';

  const data = await apiPost('/api/likes/received', { telegram_id: userId });
  if (!data.success) {
    body.innerHTML = `<div class="empty-state"><div class="empty-icon">${ICONS.alert}</div><h3>Xatolik yuz berdi</h3><p>Qayta urinib ko'ring.</p></div>`;
    return;
  }

  const likes = data.likes || [];
  if (!likes.length) {
    body.innerHTML = `<div class="empty-state"><div class="empty-icon">${ICONS.info}</div><h3>Hozircha like yo'q</h3><p>Sizga hali hech kim like yubormagan.</p></div>`;
    return;
  }

  body.innerHTML = `
    <div class="section-title" style="margin-top:0;">Sizga like yuborganlar</div>
    <div class="likes-modal-body">
      ${likes.map(u => {
        const photo = u.photo_base64 || u.photo_file_id || '';
        return `
          <div class="like-notification-card" onclick="showProfileDetail(${JSON.stringify(u).replace(/"/g,'&quot;')}); closeLikesModal();">
            <div class="like-notification-photo">
              ${photo ? `<img src="${photo}" alt="${escapeJs(u.full_name)}" />` : `${u.gender === 'erkak' ? ICONS.male : ICONS.female}`}
            </div>
            <div class="like-notification-info">
              <div>
                <strong>${u.full_name}</strong>
                <div class="like-notification-meta">${u.age} yosh • ${u.city}</div>
              </div>
              <div class="like-notification-actions">
                <button class="like-btn" onclick="event.stopPropagation(); acceptLike(${u.telegram_id}, '${escapeJs(u.full_name)}', '${escapeJs(photo)}'); closeLikesModal();">Qabul</button>
                <button class="reject-btn" onclick="event.stopPropagation(); rejectLike(${u.telegram_id}, '${escapeJs(u.full_name)}');">Rad etish</button>
              </div>
            </div>
          </div>`;
      }).join('')}
    </div>`;
}

function closeLikesModal(e) {
  if (e && e.target !== e.currentTarget) return;
  document.getElementById('likes-modal').style.display = 'none';
}

async function rejectLike(fromUserId, name) {
  if (!userId) return;
  const data = await apiPost('/api/likes/reject', { telegram_id: userId, from_user: fromUserId });
  if (data.success) {
    showToast(`Siz ${name} ni rad qildingiz.`);
    loadPendingLikesIndicator();
    openIncomingLikesModal();
  } else {
    showToast('Xatolik yuz berdi. Iltimos qayta urinib ko‘ring.');
  }
}

function renderProfileCard(u) {
  const icon = u.gender === 'erkak' ? ICONS.male : ICONS.female;
  const goals = (u.goals || []).map(g => `<span class="tag">${g}</span>`).join('');
  const interests = (u.interests || []).map(i => `<span class="tag" style="background:var(--accent-soft);color:var(--accent);">${i}</span>`).join('');
  const photo = u.photo || u.photo_file_id || u.photo_base64;
  const photoHtml = photo
    ? `<img src="${photo}" alt="${u.full_name}" loading="lazy" />`
    : `<div style="display:flex;align-items:center;justify-content:center;width:100%;height:100%;color:var(--primary);">${icon}</div>`;

  const writeBtn = u.can_write
    ? `<button class="action-btn btn-write" onclick="event.stopPropagation(); initiateChat(${u.telegram_id}, '${escapeJs(u.full_name)}', '${escapeJs(photo || '')}')">
         <span class="btn-icon">${ICONS.message}</span> Yozish
       </button>`
    : `<button class="action-btn btn-write" onclick="event.stopPropagation(); showWriteRequirement()" style="opacity:0.5;">
         <span class="btn-icon">${ICONS.message}</span> Yozish
       </button>`;

  return `
  <div class="profile-card" onclick="showProfileDetail(${JSON.stringify(u).replace(/"/g, '&quot;')})">
    <div class="profile-photo">${photoHtml}</div>
    <div class="profile-info">
      <div class="profile-name"><span style="display:inline-flex;vertical-align:middle;margin-right:6px;">${icon}</span> ${u.full_name}</div>
      <div class="profile-age-city">Yosh: ${u.age} &nbsp;•&nbsp; Shahar: ${u.city}</div>
      <div class="profile-tags" style="margin-top:8px;">${goals}${interests}</div>
    </div>
    <div class="profile-actions">
      <button class="action-btn btn-like" onclick="event.stopPropagation(); sendLike(${u.telegram_id})">
        <span class="btn-icon">${ICONS.heart}</span> Like
      </button>
      ${writeBtn}
      <button class="action-btn btn-block" onclick="event.stopPropagation(); sendBlock(${u.telegram_id})">
        <span class="btn-icon">${ICONS.ban}</span> Blok
      </button>
    </div>
  </div>`;
}

function escapeJs(str) {
  if (!str) return '';
  return str.replace(/'/g, "\\'").replace(/"/g, '\\"');
}

function showWriteRequirement() {
  showToast('Yozish uchun 2 ta do\'st taklif qiling yoki o\'zaro like bosing!');
}

// === PROFILE DETAIL MODAL ===
function showProfileDetail(user) {
  const modal = document.getElementById('profile-modal');
  const body = document.getElementById('profile-modal-body');
  
  const icon = user.gender === 'erkak' ? ICONS.male : ICONS.female;
  const goals = (user.goals || []).map(g => `<span class="tag">${g}</span>`).join('');
  const interests = (user.interests || []).map(i => `<span class="tag" style="background:var(--accent-soft);color:var(--accent);">${i}</span>`).join('');
  const photo = user.photo || user.photo_file_id || user.photo_base64;

  body.innerHTML = `
    <div style="text-align:center; margin-bottom:24px;">
      <div style="width:130px;height:130px;border-radius:50%;margin:0 auto;overflow:hidden;background:linear-gradient(135deg, var(--primary-ultra-light), var(--gray-200));box-shadow:var(--shadow);">
        ${photo ? `<img src="${photo}" style="width:100%;height:100%;object-fit:cover;" />` : `<div style="display:flex;align-items:center;justify-content:center;height:100%;">${icon}</div>`}
      </div>
      <h2 style="margin-top:16px;font-family:var(--font-main);font-size:24px;">${user.full_name}</h2>
      <p style="color:var(--text-muted);font-size:15px;margin-top:4px;">${user.age} yosh • ${user.city} • ${user.zodiac || ''}</p>
    </div>
    <div style="margin-bottom:20px;">
      <div class="section-title">Maqsad</div>
      <div class="profile-tags">${goals}</div>
    </div>
    <div style="margin-bottom:24px;">
      <div class="section-title">Qiziqishlar</div>
      <div class="profile-tags">${interests}</div>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">
      <button class="btn-primary" onclick="sendLike(${user.telegram_id}); closeProfileModal();" style="padding:14px;">
        <span class="btn-icon">${ICONS.heart}</span> Like
      </button>
      ${user.can_write ? `
      <button class="btn-secondary" onclick="initiateChat(${user.telegram_id}, '${escapeJs(user.full_name)}', '${escapeJs(photo || '')}'); closeProfileModal();" style="padding:14px;">
        <span class="btn-icon">${ICONS.message}</span> Yozish
      </button>
      ` : `
      <button class="btn-secondary" onclick="showWriteRequirement();" style="padding:14px;opacity:0.6;">
        <span class="btn-icon">${ICONS.message}</span> Yozish
      </button>
      `}
    </div>
  `;
  
  modal.style.display = 'flex';
}

function closeProfileModal(e) {
  if (e && e.target !== e.currentTarget) return;
  document.getElementById('profile-modal').style.display = 'none';
}

// === ACTIONS ===
function sendLike(toUser) {
  if (tg) {
    tg.sendData(JSON.stringify({ action: 'like_user', to_user: toUser }));
  }
  showToast('Like yuborildi! 💙');
}

function sendBlock(blockedId) {
  if (confirm('Bu foydalanuvchini bloklamoqchimisiz?')) {
    if (tg) {
      tg.sendData(JSON.stringify({ action: 'block_user', blocked_id: blockedId }));
    }
    showToast('Bloklandi!');
  }
}

async function initiateChat(toUserId, name, photo) {
  if (!userId) return;
  
  const data = await apiPost('/api/initiate_chat', { from_user: userId, to_user: toUserId });
  if (data.success && data.match_id) {
    openChatRoom(data.match_id, name, photo);
  } else {
    showToast('Yozish uchun 2 ta do\'st taklif qiling yoki o\'zaro like bosing!');
  }
}

// === CHATS PAGE ===
async function loadChats() {
  if (!userId) return;
  
  const [likesData, matchesData] = await Promise.all([
    apiPost('/api/likes/received', { telegram_id: userId }),
    apiPost('/api/matches', { telegram_id: userId })
  ]);

  const likes = likesData.success ? likesData.likes : [];
  const matches = matchesData.success ? matchesData.matches : [];

  renderIncomingLikes(likes);
  renderChatList(matches);

  const badge = document.getElementById('chat-badge');
  const totalCount = likes.length;
  if (totalCount > 0) {
    badge.textContent = totalCount > 9 ? '9+' : totalCount;
    badge.style.display = 'block';
  } else {
    badge.style.display = 'none';
  }
}

function renderIncomingLikes(likes) {
  const section = document.getElementById('incoming-likes-section');
  const list = document.getElementById('incoming-likes-list');
  
  if (!likes.length) {
    section.style.display = 'none';
    return;
  }
  
  section.style.display = 'block';
  list.innerHTML = likes.map(u => {
    const photo = u.photo_base64 || u.photo_file_id || '';
    return `
    <div class="like-item">
      <img class="like-item-photo" src="${photo}" alt="" onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';">
      <div style="display:none;align-items:center;justify-content:center;width:56px;height:56px;border-radius:50%;background:linear-gradient(135deg, var(--primary-ultra-light), var(--gray-200));flex-shrink:0;color:var(--primary);">
        ${u.gender === 'erkak' ? ICONS.male : ICONS.female}
      </div>
      <div class="like-item-info">
        <div class="like-item-name">${u.full_name}, ${u.age}</div>
        <div class="like-item-details">${u.city}</div>
      </div>
      <div class="like-actions">
        <button class="like-btn accept" onclick="acceptLike(${u.telegram_id}, '${escapeJs(u.full_name)}', '${escapeJs(photo)}')">Qabul</button>
        <button class="like-btn reject" onclick="skipLike(${u.telegram_id})">O'tkaz</button>
      </div>
    </div>`;
  }).join('');
}

function renderChatList(matches) {
  const list = document.getElementById('chat-list');
  const empty = document.getElementById('chats-empty');
  
  if (!matches.length) {
    list.innerHTML = '';
    empty.style.display = 'block';
    return;
  }
  
  empty.style.display = 'none';
  list.innerHTML = matches.map(m => {
    const photo = m.photo_base64 || m.photo_file_id || '';
    return `
    <div class="chat-list-item" onclick="openChatRoom(${m.match_id}, '${escapeJs(m.full_name)}', '${escapeJs(photo)}')">
      <img class="chat-list-photo" src="${photo}" alt="" onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';">
      <div style="display:none;align-items:center;justify-content:center;width:52px;height:52px;border-radius:50%;background:linear-gradient(135deg, var(--primary-ultra-light), var(--gray-200));flex-shrink:0;color:var(--primary);">
        ${m.gender === 'erkak' ? ICONS.male : ICONS.female}
      </div>
      <div class="chat-list-info">
        <div class="chat-list-name">${m.full_name}</div>
        <div class="chat-list-preview">Suhbatni boshlash uchun bosing</div>
      </div>
    </div>`;
  }).join('');
}

async function acceptLike(fromUserId, name, photo) {
  const data = await apiPost('/api/likes/accept', { telegram_id: userId, from_user: fromUserId });
  if (data.success && data.match_id) {
    showMatchOverlay();
    loadChats();
    loadPendingLikesIndicator();
    setTimeout(() => {
      openChatRoom(data.match_id, name, photo);
    }, 800);
  } else {
    showToast('Xatolik yuz berdi');
  }
}

async function skipLike(fromUserId) {
  // Just hide for now (could add reject API)
  showToast('O\'tkazib yuborildi');
  loadChats();
}

function showMatchOverlay() {
  document.getElementById('match-overlay').style.display = 'flex';
}

function closeMatchOverlay() {
  document.getElementById('match-overlay').style.display = 'none';
}

// === CHAT ROOM ===
async function openChatRoom(matchId, name, photo) {
  currentChatMatchId = matchId;
  currentChatPartner = { name, photo };
  
  document.getElementById('chat-user-name').textContent = name;
  document.getElementById('chat-user-photo').src = photo || '';
  document.getElementById('chat-modal').style.display = 'flex';
  document.getElementById('chat-input').focus();
  
  await loadChatMessages(matchId);
  
  if (chatRefreshInterval) clearInterval(chatRefreshInterval);
  chatRefreshInterval = setInterval(() => loadChatMessages(matchId), 1000);
}

async function loadChatMessages(matchId) {
  const data = await apiPost('/api/chat/messages', { match_id: matchId });
  if (data.success) {
    renderMessages(data.messages);
  }
}

function renderMessages(messages) {
  const container = document.getElementById('chat-messages');
  const wasAtBottom = container.scrollTop + container.clientHeight >= container.scrollHeight - 20;
  
  container.innerHTML = messages.map(m => `
    <div class="chat-bubble ${m.sender_id == userId ? 'me' : 'them'}">
      ${escapeHtml(m.message)}
      <div class="chat-time">${new Date(m.created_at).toLocaleTimeString('uz-UZ', {hour: '2-digit', minute:'2-digit'})}</div>
    </div>
  `).join('');
  
  if (wasAtBottom || messages.length <= 5) {
    container.scrollTop = container.scrollHeight;
  }
}

async function sendChatMessage() {
  const input = document.getElementById('chat-input');
  const text = input.value.trim();
  if (!text || !currentChatMatchId) return;
  
  const data = await apiPost('/api/chat/send', {
    match_id: currentChatMatchId,
    sender_id: userId,
    message: text
  });
  
  if (data.success) {
    input.value = '';
    await loadChatMessages(currentChatMatchId);
  } else {
    showToast('Xabar yuborilmadi: ' + (data.error || 'Noma\'lum xatolik'));
  }
}

function closeChatRoom() {
  document.getElementById('chat-modal').style.display = 'none';
  if (chatRefreshInterval) clearInterval(chatRefreshInterval);
  currentChatMatchId = null;
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// === MY PROFILE ===
function loadMyProfile() {
  const el = document.getElementById('my-profile-content');
  const profile = getProfile();
  
  if (!profile) {
    el.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">${ICONS.info}</div>
        <h3>Anketa topilmadi</h3>
        <p>Iltimos, anketangizni to'ldiring.</p>
      </div>`;
    return;
  }

  const genderIcon = profile.gender === 'erkak' ? ICONS.male : ICONS.female;
  const goalsText = (profile.goals || []).join(', ') || 'ko\'rsatilmagan';
  const interestsText = (profile.interests || []).join(', ') || 'ko\'rsatilmagan';

  const photoHtml = profile.photo_base64
    ? `<img src="${profile.photo_base64}" alt="photo" />`
    : `<div style="display:flex;align-items:center;justify-content:center;width:100%;height:100%;color:var(--primary);">${genderIcon}</div>`;

  el.innerHTML = `
    <div class="my-profile-wrap">
      <div class="my-profile-photo">${photoHtml}</div>
      <div class="card">
        <div class="info-row">
          <span class="info-icon">${ICONS.user}</span>
          <div>
            <div class="info-label">Ism</div>
            <div class="info-value">${profile.full_name}</div>
          </div>
        </div>
        <div class="info-row">
          <span class="info-icon">${ICONS.atSign}</span>
          <div>
            <div class="info-label">Username</div>
            <div class="info-value">${userName ? '@' + userName : 'Yo\'q'}</div>
          </div>
        </div>
        <div class="info-row">
          <span class="info-icon">${ICONS.info}</span>
          <div>
            <div class="info-label">Yosh</div>
            <div class="info-value">${profile.age} yosh</div>
          </div>
        </div>
        <div class="info-row">
          <span class="info-icon">${ICONS.mapPin}</span>
          <div>
            <div class="info-label">Shahar</div>
            <div class="info-value">${profile.city}</div>
          </div>
        </div>
        <div class="info-row">
          <span class="info-icon">${ICONS.target}</span>
          <div>
            <div class="info-label">Maqsad</div>
            <div class="info-value">${goalsText}</div>
          </div>
        </div>
        <div class="info-row">
          <span class="info-icon">${ICONS.book}</span>
          <div>
            <div class="info-label">Qiziqishlar</div>
            <div class="info-value">${interestsText}</div>
          </div>
        </div>
      </div>
    </div>`;
}

// === TOAST ===
function showToast(msg, duration = 2500) {
  const toast = document.getElementById('toast');
  toast.textContent = msg;
  toast.classList.add('show');
  setTimeout(() => toast.classList.remove('show'), duration);
}

// === INIT ===
async function init() {
  if (userId) {
    const serverProfile = await fetchUserProfile(userId);
    const localProfile = getProfile();

    if (serverProfile) {
      if (!localProfile || JSON.stringify(localProfile) !== JSON.stringify(serverProfile)) {
        setSavedProfile(serverProfile);
      }
    } else if (localProfile) {
      setSavedProfile(null);
      showToast('Serverda profil topilmadi, qayta ro\'yxatdan o\'ting.');
    }
  }

  if (!isRegistered()) {
    showPage('profile');
    document.querySelector('.bottom-nav').style.display = 'none';
  } else {
    const params = new URLSearchParams(window.location.search);
    const page = params.get('page') || 'search';
    showPage(page);
    document.querySelector('.bottom-nav').style.display = 'flex';
  }

  // Poll for new likes every 30 seconds when chats page is not active
  setInterval(() => {
    if (userId && !document.getElementById('page-chats').classList.contains('active')) {
      apiPost('/api/likes/received', { telegram_id: userId }).then(data => {
        if (data.success && data.likes.length > 0) {
          const badge = document.getElementById('chat-badge');
          badge.textContent = data.likes.length > 9 ? '9+' : data.likes.length;
          badge.style.display = 'block';
        }
      });
    }
  }, 30000);

  document.addEventListener('click', (e) => {
    if (!e.target.closest('.form-input')) {
      document.querySelectorAll('.suggestions-box').forEach(b => b.style.display = 'none');
    }
  });
}

init();
