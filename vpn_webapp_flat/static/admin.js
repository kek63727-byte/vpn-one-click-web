/* admin.js v2 — панель управления прямо в мини-аппе.
   Подключается ПОСЛЕ основного инлайн-скрипта index.html:
     <script src="/static/admin.js"></script>
   Использует уже существующие в index.html: tg, showToast(), CONFIG,
   а также иконки #i-* из общего <svg><symbol> набора.

   v2: полностью новый визуальный слой (карточки, прогресс-бары, бейджи,
   аватарки, скелетоны загрузки) + блок "Триал-серверы: занято/свободно".
   Все новые стили инжектятся сюда же, index.html трогать не нужно. */

// ══════════════════════ СТИЛИ ══════════════════════ 
(function injectAdminStyles() {
  if (document.getElementById('adminUiStyles')) return;
  const css = `
  .adm-sheet { max-height: 86vh; overflow-y: auto; padding-bottom: 4px; }
  .adm-head { display: flex; align-items: center; gap: 12px; margin-bottom: 18px; position: relative; }
  .adm-head-icon { width: 44px; height: 44px; border-radius: 14px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; position: relative; overflow: hidden; }
  .adm-head-icon::before { content: ''; position: absolute; inset: 0; opacity: .18; }
  .adm-head-icon svg { width: 21px; height: 21px; position: relative; }
  .adm-head-text { min-width: 0; flex: 1; }
  .adm-head-title { font-size: 17px; font-weight: 800; letter-spacing: -0.2px; line-height: 1.25; }
  .adm-head-sub { font-size: 12px; color: var(--muted); margin-top: 1px; }
  .adm-x { width: 30px; height: 30px; border-radius: 9px; background: var(--card); border: 1px solid var(--border); color: var(--muted); display: flex; align-items: center; justify-content: center; cursor: pointer; flex-shrink: 0; }
  .adm-x:active { transform: scale(0.92); }
  .adm-x svg { width: 14px; height: 14px; }

  .tone-violet  .adm-head-icon { background: rgba(124,58,237,.16); color: #c9a9ff; }
  .tone-violet  .adm-head-icon::before { background: radial-gradient(circle, #7c3aed, transparent 70%); }
  .tone-cyan    .adm-head-icon { background: rgba(34,211,238,.16); color: #67e8f9; }
  .tone-cyan    .adm-head-icon::before { background: radial-gradient(circle, #22d3ee, transparent 70%); }
  .tone-green   .adm-head-icon { background: rgba(34,197,94,.16); color: #6ee7a8; }
  .tone-green   .adm-head-icon::before { background: radial-gradient(circle, #22c55e, transparent 70%); }
  .tone-gold    .adm-head-icon { background: rgba(246,196,83,.16); color: #fde68a; }
  .tone-gold    .adm-head-icon::before { background: radial-gradient(circle, #f6c453, transparent 70%); }
  .tone-orange  .adm-head-icon { background: rgba(245,158,11,.16); color: #fcd34d; }
  .tone-orange  .adm-head-icon::before { background: radial-gradient(circle, #f59e0b, transparent 70%); }
  .tone-pink    .adm-head-icon { background: rgba(236,72,153,.16); color: #f9a8d4; }
  .tone-pink    .adm-head-icon::before { background: radial-gradient(circle, #ec4899, transparent 70%); }
  .tone-red     .adm-head-icon { background: rgba(239,68,68,.16); color: #fca5a5; }
  .tone-red     .adm-head-icon::before { background: radial-gradient(circle, #ef4444, transparent 70%); }

  .adm-section-title { font-size: 10.5px; font-weight: 700; font-family: var(--mono); text-transform: uppercase; letter-spacing: 1.3px; color: var(--muted); margin: 18px 0 10px; }
  .adm-section-title:first-of-type { margin-top: 0; }

  .adm-grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 9px; margin-bottom: 4px; }
  .adm-stat-card { position: relative; background: linear-gradient(165deg, #17111f, #120d19); border: 1px solid var(--border); border-radius: 16px; padding: 14px; overflow: hidden; }
  .adm-stat-card::before { content: ''; position: absolute; right: -18px; top: -18px; width: 68px; height: 68px; border-radius: 50%; pointer-events: none; opacity: .5; }
  .adm-stat-card.c-violet::before { background: radial-gradient(circle, rgba(124,58,237,.35), transparent 70%); }
  .adm-stat-card.c-cyan::before   { background: radial-gradient(circle, rgba(34,211,238,.30), transparent 70%); }
  .adm-stat-card.c-green::before  { background: radial-gradient(circle, rgba(34,197,94,.30), transparent 70%); }
  .adm-stat-card.c-gold::before   { background: radial-gradient(circle, rgba(246,196,83,.30), transparent 70%); }
  .adm-stat-card.c-orange::before { background: radial-gradient(circle, rgba(245,158,11,.30), transparent 70%); }
  .adm-stat-card.c-red::before    { background: radial-gradient(circle, rgba(239,68,68,.30), transparent 70%); }
  .adm-stat-top { display: flex; align-items: center; justify-content: space-between; position: relative; }
  .adm-stat-value { font-size: 21px; font-weight: 900; font-family: var(--mono); letter-spacing: -0.4px; position: relative; }
  .adm-stat-label { font-size: 10.5px; color: var(--muted); margin-top: 2px; position: relative; }
  .adm-stat-delta { font-size: 10px; font-weight: 700; font-family: var(--mono); padding: 2px 7px; border-radius: 100px; position: relative; white-space: nowrap; }
  .adm-stat-delta.up   { background: rgba(34,197,94,.14); color: var(--green); }
  .adm-stat-delta.warn { background: rgba(245,158,11,.16); color: var(--orange); }

  .adm-bar-track { height: 6px; border-radius: 100px; background: rgba(255,255,255,.06); overflow: hidden; margin-top: 10px; position: relative; }
  .adm-bar-fill { height: 100%; border-radius: 100px; transition: width .5s cubic-bezier(.22,.9,.3,1); }
  .adm-bar-caption { display: flex; justify-content: space-between; font-size: 10.5px; color: var(--muted); margin-top: 5px; font-family: var(--mono); position: relative; }

  .adm-wide-card { position: relative; background: linear-gradient(165deg, #17111f, #120d19); border: 1px solid var(--border); border-radius: 16px; padding: 15px 16px; margin-bottom: 10px; overflow: hidden; }
  .adm-wide-card::before { content: ''; position: absolute; right: -24px; top: -24px; width: 90px; height: 90px; border-radius: 50%; opacity: .35; pointer-events: none; }
  .adm-wide-row { display: flex; align-items: center; justify-content: space-between; position: relative; gap: 10px; }
  .adm-wide-icon { width: 34px; height: 34px; border-radius: 10px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
  .adm-wide-icon svg { width: 16px; height: 16px; }
  .adm-wide-title { font-size: 13px; font-weight: 700; }
  .adm-wide-sub { font-size: 11px; color: var(--muted); margin-top: 1px; }
  .adm-wide-num { font-size: 15px; font-weight: 800; font-family: var(--mono); flex-shrink: 0; }

  .adm-list-item { display: flex; align-items: center; gap: 11px; padding: 11px 12px; border-radius: 14px; background: var(--card); border: 1px solid var(--border); margin-bottom: 7px; cursor: pointer; transition: transform .1s, border-color .15s; }
  .adm-list-item:active { transform: scale(0.98); }
  .adm-avatar { width: 36px; height: 36px; border-radius: 11px; background: linear-gradient(135deg, #7c3aed, #b794ff); display: flex; align-items: center; justify-content: center; font-weight: 800; font-size: 13px; color: #fff; flex-shrink: 0; }
  .adm-list-info { min-width: 0; flex: 1; }
  .adm-list-name { font-size: 13.5px; font-weight: 700; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .adm-list-meta { font-size: 11px; color: var(--muted); margin-top: 1px; font-family: var(--mono); }
  .adm-list-side { display: flex; align-items: center; gap: 6px; flex-shrink: 0; }
  .adm-chev { color: var(--muted); flex-shrink: 0; }
  .adm-chev svg { width: 15px; height: 15px; }

  .adm-badge { font-size: 9.5px; font-weight: 700; padding: 3px 8px; border-radius: 100px; font-family: var(--mono); white-space: nowrap; }
  .adm-badge.green  { background: rgba(34,197,94,.14); color: var(--green); }
  .adm-badge.red    { background: rgba(239,68,68,.14); color: var(--red); }
  .adm-badge.gold   { background: rgba(246,196,83,.16); color: var(--gold); }
  .adm-badge.gray   { background: rgba(148,163,184,.12); color: var(--dim); }
  .adm-badge.orange { background: rgba(245,158,11,.14); color: var(--orange); }
  .adm-badge.cyan   { background: rgba(34,211,238,.14); color: var(--cyan); }

  .adm-btn-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 14px; }
  .adm-btn { padding: 12px 10px; border-radius: 12px; background: var(--card); border: 1.5px solid var(--border); color: var(--text); font-size: 12.5px; font-weight: 700; text-align: center; cursor: pointer; display: flex; align-items: center; justify-content: center; gap: 6px; transition: border-color .15s, transform .1s; }
  .adm-btn:active { transform: scale(0.96); }
  .adm-btn svg { width: 14px; height: 14px; flex-shrink: 0; }
  .adm-btn.full { grid-column: 1 / -1; }
  .adm-btn.primary { background: linear-gradient(135deg, #7c3aed, #b794ff); border: none; color: #fff; }
  .adm-btn.danger { border-color: rgba(239,68,68,.35); color: var(--red); background: rgba(239,68,68,.06); }
  .adm-btn.ok { border-color: rgba(34,197,94,.35); color: var(--green); background: rgba(34,197,94,.06); }
  .adm-btn.ghost { background: transparent; }

  .adm-search { display: flex; gap: 8px; margin-bottom: 14px; }
  .adm-search input { flex: 1; background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 0 14px; height: 42px; color: var(--text); font-size: 13.5px; font-family: var(--sans); }
  .adm-search input::placeholder { color: var(--muted); }
  .adm-search button { width: 42px; height: 42px; border-radius: 12px; border: none; background: var(--accent); color: #fff; display: flex; align-items: center; justify-content: center; cursor: pointer; flex-shrink: 0; }

  .adm-toggle { width: 40px; height: 24px; border-radius: 100px; border: none; position: relative; cursor: pointer; flex-shrink: 0; transition: background .2s; background: rgba(148,163,184,.18); }
  .adm-toggle::after { content: ''; position: absolute; top: 3px; left: 3px; width: 18px; height: 18px; border-radius: 50%; background: #fff; transition: transform .2s; box-shadow: 0 1px 3px rgba(0,0,0,.3); }
  .adm-toggle.on { background: linear-gradient(135deg, #22c55e, #16a34a); }
  .adm-toggle.on::after { transform: translateX(16px); }

  .adm-empty { padding: 30px 16px; text-align: center; color: var(--muted); font-size: 13px; }
  .adm-empty svg { width: 30px; height: 30px; margin: 0 auto 10px; opacity: .5; display: block; }

  .adm-skel { border-radius: 14px; background: linear-gradient(100deg, var(--card) 30%, #1d1730 50%, var(--card) 70%); background-size: 200% 100%; animation: admSkel 1.3s ease-in-out infinite; }
  @keyframes admSkel { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }

  .adm-input-inline { width: 76px; background: var(--surface); border: 1px solid var(--border); border-radius: 9px; color: var(--text); padding: 7px; text-align: right; font-family: var(--mono); font-size: 13px; }
  .adm-textarea { width: 100%; min-height: 96px; background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 11px 13px; color: var(--text); font-size: 13px; font-family: var(--sans); resize: vertical; line-height: 1.5; }
  .adm-textarea.mono { font-family: var(--mono); font-size: 11.5px; }
  .adm-char-count { text-align: right; font-size: 11px; color: var(--muted); margin-top: 4px; font-family: var(--mono); }

  .adm-divider { height: 1px; background: var(--border); margin: 14px 0; }
  .adm-fade-in { animation: admFade .22s ease; }
  @keyframes admFade { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }

  @media (min-width: 560px) {
    #adminModal .modal-sheet { max-width: 460px; border-radius: 24px; margin: 0 auto 24px; }
  }
  `;
  const style = document.createElement('style');
  style.id = 'adminUiStyles';
  style.textContent = css;
  document.head.appendChild(style);
})();

// ══════════════════════ FETCH HELPER ══════════════════════
async function _adminFetch(url, extra) {
  if (!tg?.initData) { showToast('Открой мини-апп через бот'); return null; }
  try {
    const resp = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ init_data: tg.initData, ...(extra || {}) }),
    });
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) {
      showToast('❌ ' + (data.error || resp.status));
      return null;
    }
    return data;
  } catch (e) {
    showToast('❌ ' + e.message);
    return null;
  }
}

// ══════════════════════ МОДАЛ / ШАПКА ══════════════════════
const ADM_TONES = {
  users: 'violet', stats: 'cyan', servers: 'green', prices: 'gold',
  promo: 'orange', broadcast: 'pink', ban: 'red', ab: 'violet',
  backup: 'cyan', restock: 'green',
};
const ADM_ICONS = {
  users: 'i-users', stats: 'i-chart', servers: 'i-server', prices: 'i-tag',
  promo: 'i-gift', broadcast: 'i-bell', ban: 'i-ban', ab: 'i-chart',
  backup: 'i-download', restock: 'i-zap',
};

function _ensureAdminModal() {
  if (document.getElementById('adminModal')) return;
  const div = document.createElement('div');
  div.className = 'modal-overlay';
  div.id = 'adminModal';
  div.innerHTML = `
    <div class="modal-sheet config-modal-sheet adm-sheet">
      <div class="adm-head" id="adminModalHead"></div>
      <div id="adminModalBody"></div>
    </div>`;
  document.body.appendChild(div);
  div.addEventListener('click', (e) => { if (e.target === div) div.classList.remove('show'); });
}

function _showAdmin(key, title, sub, bodyHtml) {
  _ensureAdminModal();
  const tone = ADM_TONES[key] || 'violet';
  const icon = ADM_ICONS[key] || 'i-wrench';
  const sheet = document.querySelector('#adminModal .adm-sheet');
  sheet.className = `modal-sheet config-modal-sheet adm-sheet tone-${tone}`;
  document.getElementById('adminModalHead').innerHTML = `
    <div class="adm-head-icon"><svg class="icon"><use href="#${icon}"/></svg></div>
    <div class="adm-head-text">
      <div class="adm-head-title">${title}</div>
      ${sub ? `<div class="adm-head-sub">${sub}</div>` : ''}
    </div>
    <div class="adm-x" onclick="document.getElementById('adminModal').classList.remove('show')">
      <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 6l12 12M18 6L6 18"/></svg>
    </div>`;
  document.getElementById('adminModalBody').innerHTML = `<div class="adm-fade-in">${bodyHtml}</div>`;
  document.getElementById('adminModal').classList.add('show');
  patchIconHrefs?.(document.getElementById('adminModal'));
}

function _skeleton(rows = 3) {
  return Array.from({ length: rows }).map(() =>
    `<div class="adm-skel" style="height:56px;margin-bottom:8px;"></div>`).join('');
}

function _initials(name) {
  if (!name) return '?';
  return name.trim().split(/\s+/).slice(0, 2).map(w => w[0]?.toUpperCase() || '').join('') || '?';
}

// ── роутер ──
async function openAdmin(section) {
  const map = {
    stats: adminStats, users: adminUsers, servers: adminServers, prices: adminPrices,
    promo: adminPromo, broadcast: adminBroadcast, ban: adminBan, ab: adminAB,
    backup: adminBackup, restock: adminRestock,
  };
  const fn = map[section];
  if (!fn) { showToast('Раздел в разработке'); return; }
  await fn();
}

// ══════════════════ 1. СТАТИСТИКА ══════════════════
async function adminStats() {
  _showAdmin('stats', '📊 Статистика', 'Продажи, конверсия, склад', _skeleton(4));
  const d = await _adminFetch('/admin/stats_full');
  if (!d) return;

  const stockPct = d.free_paid + 0 > 0 ? 100 : 0; // просто индикатор наличия
  const trialFree = d.free_trial ?? 0;
  const trialTotal = d.trial_total; // может отсутствовать — см. примечание в admin_api.py
  const trialOccupied = trialTotal != null ? Math.max(0, trialTotal - trialFree) : null;
  const trialPct = trialTotal ? Math.round((trialOccupied / trialTotal) * 100) : null;

  const cards = [
    { v: `${d.day_rub} ₽`, l: 'Сегодня', c: 'green' },
    { v: `${d.week_rub} ₽`, l: '7 дней', c: 'cyan' },
    { v: `${d.month_rub} ₽`, l: '30 дней', c: 'violet' },
    { v: `${d.all_rub} ₽`, l: 'Всего', c: 'gold' },
    { v: `${d.mrr} ₽`, l: 'MRR / мес', c: 'green' },
    { v: d.users, l: 'Пользователей', c: 'violet' },
    { v: d.active_subs, l: 'Активных подписок', c: 'cyan' },
    { v: `${d.total_balance} ₽`, l: 'Баланс всех юзеров', c: 'gold' },
  ];

  const html = `
    <div class="adm-grid-2">
      ${cards.map(c => `
        <div class="adm-stat-card c-${c.c}">
          <div class="adm-stat-top"><div class="adm-stat-value">${c.v}</div></div>
          <div class="adm-stat-label">${c.l}</div>
        </div>`).join('')}
    </div>

    <div class="adm-section-title">Серверный пул</div>
    <div class="adm-wide-card">
      <div class="adm-wide-row">
        <div style="display:flex;align-items:center;gap:10px;">
          <div class="adm-wide-icon" style="background:rgba(34,197,94,.14);color:var(--green);"><svg class="icon"><use href="#i-server"/></svg></div>
          <div><div class="adm-wide-title">Платные — свободно</div><div class="adm-wide-sub">Готовых конфигов на продажу</div></div>
        </div>
        <div class="adm-wide-num">${d.free_paid}</div>
      </div>
    </div>
    <div class="adm-wide-card">
      <div class="adm-wide-row">
        <div style="display:flex;align-items:center;gap:10px;">
          <div class="adm-wide-icon" style="background:rgba(245,158,11,.14);color:var(--orange);"><svg class="icon"><use href="#i-gift"/></svg></div>
          <div><div class="adm-wide-title">Триал-серверы</div><div class="adm-wide-sub">${trialTotal != null ? `Занято ${trialOccupied} из ${trialTotal}` : `Свободно сейчас: ${trialFree}`}</div></div>
        </div>
        <div class="adm-wide-num">${trialTotal != null ? trialPct + '%' : trialFree}</div>
      </div>
      ${trialTotal != null ? `
        <div class="adm-bar-track"><div class="adm-bar-fill" style="width:${trialPct}%;background:${trialPct > 85 ? 'var(--red)' : trialPct > 60 ? 'var(--orange)' : 'var(--green)'};"></div></div>
        <div class="adm-bar-caption"><span>занято ${trialOccupied}</span><span>всего ${trialTotal}</span></div>
      ` : ''}
    </div>

    <div class="adm-section-title">Воронка</div>
    <div class="adm-wide-card">
      <div class="adm-wide-row">
        <div><div class="adm-wide-title">Триал → оплата</div><div class="adm-wide-sub">${d.trial_conv_n}</div></div>
        <div class="adm-wide-num" style="color:var(--green);">${d.trial_conv_rate}%</div>
      </div>
      <div class="adm-bar-track"><div class="adm-bar-fill" style="width:${d.trial_conv_rate}%;background:var(--green);"></div></div>
    </div>
    <div class="adm-wide-card">
      <div class="adm-wide-row">
        <div><div class="adm-wide-title">Отток за 30 дней</div><div class="adm-wide-sub">${d.churn_n}</div></div>
        <div class="adm-wide-num" style="color:var(--red);">${d.churn_rate}%</div>
      </div>
      <div class="adm-bar-track"><div class="adm-bar-fill" style="width:${d.churn_rate}%;background:var(--red);"></div></div>
    </div>
    <div class="adm-wide-card">
      <div class="adm-wide-row">
        <div><div class="adm-wide-title">Открытых предзаказов</div></div>
        <div class="adm-wide-num">${d.pending_preorders}</div>
      </div>
    </div>
  `;
  _showAdmin('stats', '📊 Статистика', 'Продажи, конверсия, склад', html);
}

// ══════════════════ 2. ПОЛЬЗОВАТЕЛИ ══════════════════
let _usersOffset = 0;

async function adminUsers(search) {
  _showAdmin('users', '👤 Пользователи', 'Поиск, баланс, модерация', _skeleton(5));
  const d = await _adminFetch('/admin/users', search ? { search } : { offset: _usersOffset });
  if (!d) return;

  let html = `
    <div class="adm-search">
      <input id="adminUserSearch" placeholder="ID или @username…" value="${search || ''}">
      <button onclick="adminUsers(document.getElementById('adminUserSearch').value.trim())">
        <svg class="icon" style="width:16px;height:16px;"><use href="#i-arrow-send"/></svg>
      </button>
    </div>`;

  if (!d.users.length) {
    html += `<div class="adm-empty"><svg><use href="#i-users"/></svg>Никого не найдено</div>`;
  } else {
    html += d.users.map(u => `
      <div class="adm-list-item" onclick="adminUserCard(${u.user_id})">
        <div class="adm-avatar">${_initials(u.full_name || u.username || String(u.user_id))}</div>
        <div class="adm-list-info">
          <div class="adm-list-name">${u.full_name || '—'} ${u.username ? '· @' + u.username : ''}</div>
          <div class="adm-list-meta">ID ${u.user_id}</div>
        </div>
        <div class="adm-list-side">
          <span class="adm-badge gold">${u.balance_rub || 0} ₽</span>
          <div class="adm-chev"><svg class="icon"><use href="#i-chevron"/></svg></div>
        </div>
      </div>`).join('');
    if (!search) {
      html += `<div class="adm-btn-grid">
        ${_usersOffset > 0 ? `<div class="adm-btn ghost" onclick="_usersOffset=Math.max(0,_usersOffset-10);adminUsers();">⬅️ Назад</div>` : '<div></div>'}
        ${_usersOffset + 10 < d.total ? `<div class="adm-btn ghost" onclick="_usersOffset+=10;adminUsers();">Дальше ➡️</div>` : '<div></div>'}
      </div>`;
    }
  }
  _showAdmin('users', '👤 Пользователи', `Всего: ${d.total}`, html);
}

async function adminUserCard(uid) {
  _showAdmin('users', '👤 Профиль', 'Загрузка…', _skeleton(3));
  const d = await _adminFetch('/admin/user_card', { user_id: uid });
  if (!d) return;
  const u = d.user;
  const html = `
    <div class="adm-wide-card">
      <div class="adm-wide-row">
        <div style="display:flex;align-items:center;gap:10px;">
          <div class="adm-avatar" style="width:44px;height:44px;font-size:16px;">${_initials(u.full_name || u.username || String(u.user_id))}</div>
          <div>
            <div class="adm-wide-title">${u.full_name || '—'} ${u.username ? '· @' + u.username : ''}</div>
            <div class="adm-wide-sub">ID <code>${u.user_id}</code></div>
          </div>
        </div>
        <span class="adm-badge ${u.banned ? 'red' : 'green'}">${u.banned ? 'забанен' : 'активен'}</span>
      </div>
    </div>
    <div class="adm-grid-2">
      <div class="adm-stat-card c-gold"><div class="adm-stat-value">${u.balance_rub || 0} ₽</div><div class="adm-stat-label">Баланс</div></div>
      <div class="adm-stat-card c-violet"><div class="adm-stat-value">${u.spent || 0} ₽</div><div class="adm-stat-label">Потрачено всего</div></div>
      <div class="adm-stat-card c-cyan"><div class="adm-stat-value">${u.invited || 0}</div><div class="adm-stat-label">Приглашено друзей</div></div>
    </div>

    <div class="adm-section-title">Действия</div>
    <div class="adm-btn-grid">
      <div class="adm-btn" onclick="adminUserAction(${uid},'days',7)">🎁 +7 дней</div>
      <div class="adm-btn" onclick="adminUserAction(${uid},'days',30)">🎁 +30 дней</div>
      <div class="adm-btn" onclick="adminUserAction(${uid},'balance',100)">💰 +100 ₽</div>
      <div class="adm-btn" onclick="adminUserAction(${uid},'balance',500)">💰 +500 ₽</div>
      <div class="adm-btn ${u.banned ? 'ok' : 'danger'}" onclick="adminUserAction(${uid},'${u.banned ? 'unban' : 'ban'}')">${u.banned ? '✅ Разбанить' : '⛔️ Забанить'}</div>
      <div class="adm-btn danger" onclick="adminUserAction(${uid},'refund')">💸 Рефанд</div>
      <div class="adm-btn" onclick="adminUserAction(${uid},'noprem')">👑 Откл. премиум</div>
      <div class="adm-btn primary" onclick="adminUserCustom(${uid})">✏️ Своя сумма/дни</div>
    </div>
    <div class="adm-divider"></div>
    <div class="adm-btn ghost full" style="width:100%;" onclick="adminUsers()">⬅️ К списку пользователей</div>`;
  _showAdmin('users', `👤 ${u.full_name || u.user_id}`, `ID ${u.user_id}`, html);
}

async function adminUserAction(uid, action, value) {
  const d = await _adminFetch('/admin/user_action', { user_id: uid, action, value });
  if (!d) return;
  showToast('✅ Готово');
  tg?.HapticFeedback?.notificationOccurred('success');
  adminUserCard(uid);
}

function adminUserCustom(uid) {
  const kind = prompt('Что изменить: "дни" или "баланс"?', 'дни');
  if (!kind) return;
  const val = prompt('На сколько (можно отрицательное число)?', '7');
  if (val === null) return;
  const action = kind.trim().toLowerCase().startsWith('б') ? 'balance' : 'days';
  adminUserAction(uid, action, parseInt(val, 10) || 0);
}

// ══════════════════ БАН / РАЗБАН ══════════════════
async function adminBan() {
  const html = `
    <div class="adm-search">
      <input id="adminBanId" placeholder="ID пользователя" inputmode="numeric">
    </div>
    <div class="adm-btn-grid">
      <div class="adm-btn danger" onclick="_adminBanGo(true)">⛔️ Забанить</div>
      <div class="adm-btn ok" onclick="_adminBanGo(false)">✅ Разбанить</div>
    </div>
    <div style="margin-top:14px;font-size:11.5px;color:var(--muted);text-align:center;">Полная карточка юзера — в разделе «Пользователи».</div>`;
  _showAdmin('ban', '⛔️ Бан / Разбан', 'Быстрая блокировка по ID', html);
}
async function _adminBanGo(ban) {
  const idEl = document.getElementById('adminBanId');
  const uid = parseInt(idEl.value, 10);
  if (!uid) { showToast('Введи ID'); return; }
  const d = await _adminFetch('/admin/user_action', { user_id: uid, action: ban ? 'ban' : 'unban' });
  if (!d) return;
  showToast(ban ? '⛔️ Забанен' : '✅ Разбанен');
  tg?.HapticFeedback?.notificationOccurred('success');
}

// ══════════════════ 3. СЕРВЕРЫ ══════════════════
async function adminServers() {
  _showAdmin('servers', '🌍 Серверы', 'Склад и регионы', _skeleton(5));
  const d = await _adminFetch('/admin/servers');
  if (!d) return;

  let html = d.regions.map(r => {
    const pct = r.total > 0 ? Math.round(((r.total - r.free) / r.total) * 100) : 0;
    const barColor = pct > 85 ? 'var(--red)' : pct > 60 ? 'var(--orange)' : 'var(--green)';
    return `
    <div class="adm-wide-card">
      <div class="adm-wide-row">
        <div style="display:flex;align-items:center;gap:10px;">
          <div class="adm-wide-icon" style="background:rgba(124,58,237,.14);color:var(--accent2);"><svg class="icon"><use href="#i-globe"/></svg></div>
          <div>
            <div class="adm-wide-title">${r.is_premium ? '⭐️ ' : ''}${r.region}</div>
            <div class="adm-wide-sub">🟢 ${r.free} свободно из ${r.total}</div>
          </div>
        </div>
        <div style="display:flex;gap:6px;">
          <div class="adm-btn ghost" style="padding:8px 10px;" onclick="_adminServerToggle('${r.region}', ${!r.is_premium})">${r.is_premium ? 'Снять ⭐️' : 'Сделать ⭐️'}</div>
          <div class="adm-btn danger" style="padding:8px 10px;" onclick="_adminServerDelete('${r.region}')">🗑</div>
        </div>
      </div>
      <div class="adm-bar-track"><div class="adm-bar-fill" style="width:${pct}%;background:${barColor};"></div></div>
    </div>`;
  }).join('');

  html += `
    <div class="adm-section-title">Добавить регион</div>
    <div class="adm-search">
      <input id="adminNewRegion" placeholder="Название региона…">
      <button onclick="_adminServerAdd()"><svg class="icon" style="width:16px;height:16px;"><use href="#i-check"/></svg></button>
    </div>`;
  _showAdmin('servers', '🌍 Серверы', `${d.regions.length} регионов`, html);
}
async function _adminServerToggle(region, premium) {
  const d = await _adminFetch('/admin/servers/toggle_premium', { region, premium });
  if (d) adminServers();
}
async function _adminServerDelete(region) {
  if (!confirm(`Удалить регион «${region}» из каталога?`)) return;
  const d = await _adminFetch('/admin/servers/delete', { region });
  if (d) adminServers();
}
async function _adminServerAdd() {
  const region = document.getElementById('adminNewRegion').value.trim();
  if (!region) return;
  const d = await _adminFetch('/admin/servers/add', { region, premium: false });
  if (d) { showToast('✅ Регион добавлен'); adminServers(); }
}

// ══════════════════ 4. ЦЕНЫ ══════════════════
async function adminPrices() {
  _showAdmin('prices', '💲 Цены', 'Тарифы и скидки', _skeleton(4));
  const d = await _adminFetch('/admin/prices');
  if (!d) return;
  const html = d.plans.map(p => `
    <div class="adm-section-title">${p.title}</div>
    ${p.items.map(it => `
      <div class="adm-list-item" style="cursor:default;">
        <div class="adm-list-info">
          <div class="adm-list-name">${it.devices} устр · ${it.period_ru}</div>
        </div>
        <div class="adm-list-side">
          <input type="number" class="adm-input-inline" value="${it.rub}" id="pp_${p.plan}_${it.devices}_${it.period}">
          <div class="adm-btn ghost" style="padding:9px 11px;" onclick="_adminPriceSave('${p.plan}',${it.devices},'${it.period}')">
            <svg class="icon" style="width:14px;height:14px;"><use href="#i-check"/></svg>
          </div>
        </div>
      </div>`).join('')}
  `).join('');
  _showAdmin('prices', '💲 Цены', 'Тарифы и скидки', html);
}
async function _adminPriceSave(plan, devices, period) {
  const el = document.getElementById(`pp_${plan}_${devices}_${period}`);
  const rub = parseInt(el.value, 10);
  if (isNaN(rub) || rub < 0) { showToast('Некорректная цена'); return; }
  const d = await _adminFetch('/admin/prices/set', { plan, devices, period, rub });
  if (d) { showToast('✅ Сохранено'); tg?.HapticFeedback?.notificationOccurred('success'); }
}

// ══════════════════ 5. ПРОМОКОДЫ ══════════════════
async function adminPromo() {
  _showAdmin('promo', '🎟 Промокоды', 'Создание и управление', _skeleton(3));
  const d = await _adminFetch('/admin/promo');
  if (!d) return;
  _renderPromo(d.promos);
}
function _renderPromo(promos) {
  let html = !promos.length ? `<div class="adm-empty"><svg><use href="#i-gift"/></svg>Пока нет промокодов</div>` :
    promos.map(p => `
      <div class="adm-list-item" style="cursor:default;">
        <div class="adm-list-info">
          <div class="adm-list-name">${p.code}</div>
          <div class="adm-list-meta">${p.kind === 'balance' ? '+' + p.amount_rub + ' ₽' : '−' + p.percent + '%'} · использован ${p.used}/${p.max_uses || '∞'}</div>
        </div>
        <div class="adm-list-side">
          <button class="adm-toggle ${p.active ? 'on' : ''}" onclick="_adminPromoToggle('${p.code}')"></button>
          <div class="adm-btn danger" style="padding:8px 10px;" onclick="_adminPromoDelete('${p.code}')">🗑</div>
        </div>
      </div>`).join('');
  html += `
    <div class="adm-section-title">Новый промокод</div>
    <div style="display:flex;flex-direction:column;gap:8px;">
      <input class="adm-textarea" style="min-height:auto;height:42px;" id="pcCode" placeholder="КОД (напр. SALE20)">
      <div style="display:flex;gap:8px;">
        <select id="pcKind" style="flex:1;background:var(--surface);border:1px solid var(--border);border-radius:12px;color:var(--text);padding:0 10px;height:42px;">
          <option value="discount">Скидка %</option>
          <option value="balance">На баланс ₽</option>
        </select>
        <input class="adm-textarea" style="min-height:auto;height:42px;flex:1;" id="pcValue" type="number" placeholder="Значение">
      </div>
      <input class="adm-textarea" style="min-height:auto;height:42px;" id="pcMax" type="number" placeholder="Лимит активаций (0 = без лимита)">
      <div class="adm-btn primary full" onclick="_adminPromoCreate()">➕ Создать промокод</div>
    </div>`;
  _showAdmin('promo', '🎟 Промокоды', `Активных: ${promos.filter(p => p.active).length}`, html);
}
async function _adminPromoToggle(code) {
  const d = await _adminFetch('/admin/promo/toggle', { code });
  if (d) _renderPromo(d.promos);
}
async function _adminPromoDelete(code) {
  if (!confirm(`Удалить промокод ${code}?`)) return;
  const d = await _adminFetch('/admin/promo/delete', { code });
  if (d) _renderPromo(d.promos);
}
async function _adminPromoCreate() {
  const code = document.getElementById('pcCode').value.trim();
  const kind = document.getElementById('pcKind').value;
  const value = parseInt(document.getElementById('pcValue').value, 10);
  const max_uses = parseInt(document.getElementById('pcMax').value, 10) || 0;
  if (!code || !value) { showToast('Заполни код и значение'); return; }
  const d = await _adminFetch('/admin/promo/create', { code, kind, value, max_uses });
  if (d) { showToast('✅ Создан'); _renderPromo(d.promos); }
}

// ══════════════════ 6. РАССЫЛКА ══════════════════
async function adminBroadcast() {
  const html = `
    <textarea id="adminBcastText" class="adm-textarea" placeholder="Текст сообщения всем пользователям…" oninput="document.getElementById('bcastCount').textContent = this.value.length"></textarea>
    <div class="adm-char-count" id="bcastCount">0</div>
    <div class="adm-btn primary full" style="margin-top:8px;" onclick="_adminBroadcastSend()">📣 Отправить всем</div>`;
  _showAdmin('broadcast', '📣 Рассылка', 'Сообщение всем пользователям', html);
}
async function _adminBroadcastSend() {
  const text = document.getElementById('adminBcastText').value.trim();
  if (!text) { showToast('Введи текст'); return; }
  if (!confirm('Отправить это сообщение ВСЕМ пользователям?')) return;
  showToast('📣 Отправляю…');
  const d = await _adminFetch('/admin/broadcast', { text });
  if (d) _showAdmin('broadcast', '📣 Рассылка', 'Готово', `
    <div class="adm-grid-2">
      <div class="adm-stat-card c-green"><div class="adm-stat-value">${d.sent}</div><div class="adm-stat-label">Доставлено</div></div>
      <div class="adm-stat-card c-red"><div class="adm-stat-value">${d.failed}</div><div class="adm-stat-label">Ошибок</div></div>
    </div>`);
}

// ══════════════════ 7. A/B ТЕСТЫ ══════════════════
async function adminAB() {
  _showAdmin('ab', '🧪 A/B тесты', 'Анализ конверсии', _skeleton(2));
  const d = await _adminFetch('/admin/ab');
  if (!d) return;
  if (!d.enabled) {
    _showAdmin('ab', '🧪 A/B тесты', '', `<div class="adm-empty"><svg><use href="#i-chart"/></svg>Эксперимент выключен.<br>Включается через AB_EXPERIMENT в .env бота.</div>`);
    return;
  }
  const maxConv = Math.max(1, ...d.variants.map(v => v.conv_all));
  const html = d.variants.map(v => `
    <div class="adm-wide-card">
      <div class="adm-wide-row">
        <div><div class="adm-wide-title">Вариант ${v.variant}</div><div class="adm-wide-sub">👥${v.users} · 🧪${v.trials} · 💳${v.paid}</div></div>
        <div class="adm-wide-num" style="color:var(--green);">${v.conv_all}%</div>
      </div>
      <div class="adm-bar-track"><div class="adm-bar-fill" style="width:${(v.conv_all / maxConv) * 100}%;background:var(--accent2);"></div></div>
    </div>`).join('');
  _showAdmin('ab', `🧪 ${d.title}`, d.metric, html);
}

// ══════════════════ 8. БЭКАП БАЗЫ ══════════════════
async function adminBackup() {
  const html = `
    <div class="adm-wide-card">
      <div class="adm-wide-row">
        <div style="display:flex;align-items:center;gap:10px;">
          <div class="adm-wide-icon" style="background:rgba(34,211,238,.14);color:var(--cyan);"><svg class="icon"><use href="#i-download"/></svg></div>
          <div><div class="adm-wide-title">backup.db</div><div class="adm-wide-sub">Полная резервная копия базы</div></div>
        </div>
      </div>
    </div>
    <div class="adm-btn primary full" onclick="_adminBackupGo()">⬇️ Скачать бэкап</div>`;
  _showAdmin('backup', '💾 Бэкап базы', 'Резервная копия', html);
}
async function _adminBackupGo() {
  if (!tg?.initData) { showToast('Открой мини-апп через бот'); return; }
  showToast('⏳ Готовлю бэкап…');
  try {
    const resp = await fetch('/admin/backup', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ init_data: tg.initData }),
    });
    if (!resp.ok) { showToast('❌ Не удалось получить бэкап'); return; }
    const blob = await resp.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = 'backup.db';
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 4000);
    showToast('✅ Бэкап скачан');
  } catch (e) {
    showToast('❌ ' + e.message);
  }
}

// ══════════════════ 9. ЗАЯВКИ НА ЗАКУПКУ ══════════════════
async function adminRestock() {
  _showAdmin('restock', '📦 Закупки', 'Открытые заявки склада', _skeleton(3));
  const d = await _adminFetch('/admin/restock');
  if (!d) return;
  _renderRestock(d);
}
function _renderRestock(d) {
  const STATUS = {
    new: { l: '🆕 новая', c: 'gray' }, awaiting_payment: { l: '⏳ ждёт оплаты', c: 'orange' },
    paid: { l: '💸 оплачено', c: 'cyan' }, done: { l: '✅ закрыта', c: 'green' }, canceled: { l: '❌ отменена', c: 'red' },
  };
  let html = !d.orders.length ? `<div class="adm-empty"><svg><use href="#i-zap"/></svg>Активных заявок нет</div>` :
    d.orders.map(o => {
      const st = STATUS[o.status] || { l: o.status, c: 'gray' };
      return `
      <div class="adm-list-item" onclick="_adminRestockOpen(${o.id})">
        <div class="adm-list-info">
          <div class="adm-list-name">${o.urgent ? '🔥 ' : ''}#${o.id} · ${o.region}</div>
        </div>
        <div class="adm-list-side">
          <span class="adm-badge ${st.c}">${st.l}</span>
          <div class="adm-chev"><svg class="icon"><use href="#i-chevron"/></svg></div>
        </div>
      </div>`;
    }).join('');

  if (d.low_stock?.length) {
    html += `<div class="adm-section-title" style="color:var(--orange);">⚠️ Низкий запас</div>`;
    html += d.low_stock.map(r => `
      <div class="adm-list-item" style="cursor:default;">
        <div class="adm-list-info"><div class="adm-list-name">${r.region}</div><div class="adm-list-meta">🟢${r.free}${r.has_preorder ? ' · есть предзаказ' : ''}</div></div>
        <div class="adm-btn ghost" style="padding:8px 12px;" onclick="_adminRestockCreate('${r.region}')">➕ Заявка</div>
      </div>`).join('');
  }
  _showAdmin('restock', '📦 Закупки', `Партия: ${d.batch}`, html);
}
async function _adminRestockCreate(region) {
  const d = await _adminFetch('/admin/restock/create', { region });
  if (d) adminRestock();
}
async function _adminRestockOpen(id) {
  const d = await _adminFetch('/admin/restock');
  if (!d) return;
  const o = d.orders.find(x => x.id === id);
  if (!o) return;
  const pct = o.need > 0 ? Math.round((o.added / o.need) * 100) : 0;

  let actions = '';
  if (['new', 'awaiting_payment'].includes(o.status)) {
    actions = `
      <div class="adm-section-title">Оплата закупки</div>
      <input class="adm-textarea" style="min-height:auto;height:42px;margin-bottom:8px;" id="rsAmount" type="number" placeholder="Сумма ₽" value="${o.amount_rub || ''}">
      <div class="adm-btn ghost full" style="margin-bottom:10px;" onclick="_adminRestockAmount(${id})">💾 Сохранить сумму</div>
      <input class="adm-textarea" style="min-height:auto;height:42px;margin-bottom:8px;" id="rsUrl" placeholder="https://ссылка на оплату" value="${o.pay_url || ''}">
      <div class="adm-btn ghost full" style="margin-bottom:10px;" onclick="_adminRestockUrl(${id})">🔗 Сохранить ссылку</div>
      ${o.pay_url ? `<div class="adm-btn ok full" style="margin-bottom:8px;" onclick="_adminRestockStatus(${id},'paid')">✅ Отметить оплаченной</div>` : ''}
      <div class="adm-btn danger full" onclick="_adminRestockStatus(${id},'canceled')">❌ Отменить заявку</div>`;
  } else if (o.status === 'paid') {
    actions = `
      <div class="adm-section-title">Вставить .conf</div>
      <textarea id="rsConfigs" class="adm-textarea mono" placeholder="Один или несколько [Interface] блоков подряд…"></textarea>
      <div class="adm-btn primary full" style="margin-top:8px;margin-bottom:8px;" onclick="_adminRestockAddConfigs(${id})">➕ Добавить конфиги</div>
      <div class="adm-btn ok full" onclick="_adminRestockStatus(${id},'done')">✅ Завершить заявку</div>`;
  }

  const html = `
    <div class="adm-wide-card">
      <div class="adm-wide-row"><div class="adm-wide-title">${o.region}</div><div class="adm-wide-num">${o.added}/${o.need}</div></div>
      <div class="adm-bar-track"><div class="adm-bar-fill" style="width:${pct}%;background:var(--green);"></div></div>
      <div class="adm-bar-caption"><span>добавлено</span><span>нужно</span></div>
    </div>
    ${actions}
    <div class="adm-divider"></div>
    <div class="adm-btn ghost full" onclick="adminRestock()">⬅️ К заявкам</div>`;
  _showAdmin('restock', `📦 Заявка #${id}`, o.region, html);
}
async function _adminRestockAmount(id) {
  const amount_rub = parseInt(document.getElementById('rsAmount').value, 10);
  if (!amount_rub) { showToast('Укажи сумму'); return; }
  const d = await _adminFetch('/admin/restock/update', { id, amount_rub });
  if (d) { showToast('✅'); _adminRestockOpen(id); }
}
async function _adminRestockUrl(id) {
  const pay_url = document.getElementById('rsUrl').value.trim();
  const d = await _adminFetch('/admin/restock/update', { id, pay_url });
  if (d) { showToast('✅'); _adminRestockOpen(id); }
  else showToast('❌ Ссылка должна начинаться с https://');
}
async function _adminRestockStatus(id, status) {
  const d = await _adminFetch('/admin/restock/update', { id, status });
  if (d) { showToast('✅'); status === 'canceled' || status === 'done' ? adminRestock() : _adminRestockOpen(id); }
}
async function _adminRestockAddConfigs(id) {
  const text = document.getElementById('rsConfigs').value;
  if (!text.trim()) return;
  const d = await _adminFetch('/admin/restock/add_configs', { id, text });
  if (d) { showToast(`✅ Добавлено: ${d.added}${d.skipped ? `, пропущено: ${d.skipped}` : ''}`); _adminRestockOpen(id); }
}

// ══════════════════ 10. ТРАНЗАКЦИИ (пополнения + покупки) ══════════════════
const _PERIOD_RU_TX = { month: '1 мес', '3month': '3 мес', '6month': '6 мес', year: '1 год' };
const _PLAN_EMOJI   = { standard: '🛡', premium: '💎', ultimate: '⚡️' };

const _TX_KIND = {
  topup_invoice: { label: 'Выставлен счёт', color: 'orange', icon: 'i-receipt',    sign: ''  },
  topup_paid:    { label: 'Пополнение',     color: 'green',  icon: 'i-arrow-send', sign: '+' },
  order_paid:    { label: 'Покупка',        color: 'cyan',   icon: 'i-bag',        sign: '-' },
  order_failed:  { label: 'Не оплачено',    color: 'red',    icon: 'i-ban',        sign: ''  },
  freeze:        { label: 'Заморозка',      color: 'cyan',   icon: 'i-zap',        sign: '-' },
  freeze_failed: { label: 'Заморозка ✗',    color: 'red',    icon: 'i-ban',        sign: ''  },
  refund:        { label: 'Рефанд',         color: 'red',    icon: 'i-download',   sign: '+' },
};
const _TX_COLOR_VAR = { green: 'var(--green)', red: 'var(--red)', orange: 'var(--orange)', cyan: 'var(--cyan)', gray: 'var(--muted)' };
const _TX_FILTERS = [
  ['all', 'Все'], ['topup_paid', 'Пополнения'], ['order_paid', 'Покупки'],
  ['freeze', 'Заморозки'], ['order_failed', 'Неудачные'],
];
const _TX_SOURCE_LABEL = { bot: 'бот', webapp: 'мини-апп', webhook: 'вебхук', admin: 'админ' };

function _renderTxItem(item) {
  const conf = _TX_KIND[item.kind] || { label: item.kind, color: 'gray', icon: 'i-receipt', sign: '' };
  const name = item.full_name
    ? `${item.full_name}${item.username ? ' · @' + item.username : ''}`
    : (item.username ? '@' + item.username : 'ID ' + item.user_id);
  const dt = (item.created_at || '').slice(0, 16).replace('T', ' ');
  const m = item.meta || {};
  let detail = '';

  if (item.kind === 'topup_invoice' || item.kind === 'topup_paid') {
    detail = m.method || '';
  } else if (item.kind === 'order_paid') {
    const emoji = _PLAN_EMOJI[m.plan] || '📦';
    const period = _PERIOD_RU_TX[m.period] || m.period || '';
    detail = `${emoji} ${m.plan || ''} · ${m.region || ''} · ${period} · ${m.devices || 1} устр`;
  } else if (item.kind === 'order_failed') {
    const reasons = { need_topup: 'не хватило баланса', need_topup_race: 'не хватило баланса', no_stock: 'нет серверов' };
    detail = `${m.plan || ''} · ${m.region || ''} · ${reasons[m.reason] || m.reason || ''}`;
  } else if (item.kind === 'freeze' || item.kind === 'freeze_failed') {
    const reasons = { cooldown: 'кулдаун', need_topup: 'не хватило баланса', need_topup_race: 'не хватило баланса' };
    detail = `${m.region || ''}${m.reason ? ' · ' + (reasons[m.reason] || m.reason) : ''}`;
  } else if (item.kind === 'refund') {
    detail = m.order_id ? `заказ #${m.order_id}` : '';
  }

  const amountText = item.amount ? `${conf.sign}${item.amount.toLocaleString('ru')} ₽` : '';
  const colorVar = _TX_COLOR_VAR[conf.color] || _TX_COLOR_VAR.gray;

  return `
    <div class="adm-list-item" onclick="adminUserCard(${item.user_id})" style="border-left:3px solid ${colorVar};margin-bottom:7px;">
      <div style="width:36px;height:36px;border-radius:11px;background:rgba(255,255,255,.06);color:${colorVar};display:flex;align-items:center;justify-content:center;flex-shrink:0;">
        <svg class="icon" style="width:17px;height:17px;"><use href="#${conf.icon}"/></svg>
      </div>
      <div class="adm-list-info">
        <div class="adm-list-name">${amountText ? amountText + ' — ' : ''}${name}</div>
        <div class="adm-list-meta">${dt}${detail ? ' · ' + detail : ''}</div>
        ${item.source ? `<div class="adm-list-meta" style="color:var(--dim);">через ${_TX_SOURCE_LABEL[item.source] || item.source}</div>` : ''}
      </div>
      <div class="adm-list-side">
        <span class="adm-badge ${conf.color}">${conf.label}</span>
        <div class="adm-chev"><svg class="icon"><use href="#i-chevron"/></svg></div>
      </div>
    </div>`;
}

async function adminTransactions(kind = 'all') {
  _showAdmin('stats', '💰 Транзакции', 'Загрузка…', _skeleton(6));
  const d = await _adminFetch('/admin/transactions', { kind });
  if (!d) return;
  const s = d.summary;

  const filters = _TX_FILTERS.map(([k, label]) =>
    `<div class="adm-btn ${kind === k ? 'primary' : 'ghost'}" style="flex:1;padding:9px 4px;font-size:11px;" onclick="adminTransactions('${k}')">${label}</div>`
  ).join('');

  const summaryHtml = `
    <div class="adm-grid-2" style="margin-bottom:14px;">
      <div class="adm-stat-card c-green">
        <div class="adm-stat-value">${(s.topup_sum || 0).toLocaleString('ru')} ₽</div>
        <div class="adm-stat-label">Пополнено всего</div>
        <div style="font-size:10px;color:var(--muted);margin-top:2px;">${s.topup_cnt} операций</div>
      </div>
      <div class="adm-stat-card c-violet">
        <div class="adm-stat-value">${(s.order_sum || 0).toLocaleString('ru')} ₽</div>
        <div class="adm-stat-label">Продаж всего</div>
        <div style="font-size:10px;color:var(--muted);margin-top:2px;">${s.order_cnt} заказов</div>
      </div>
      <div class="adm-stat-card c-cyan">
        <div class="adm-stat-value">${s.active_configs}</div>
        <div class="adm-stat-label">Конфигов активно</div>
        <div style="font-size:10px;color:var(--muted);margin-top:2px;">+ ${s.active_trials} триалов</div>
      </div>
      <div class="adm-stat-card c-gold">
        <div class="adm-stat-value">${(s.total_balance || 0).toLocaleString('ru')} ₽</div>
        <div class="adm-stat-label">Баланс всех юзеров</div>
      </div>
    </div>`;

  const listHtml = !d.items.length
    ? `<div class="adm-empty"><svg><use href="#i-receipt"/></svg>Событий нет</div>`
    : d.items.map(_renderTxItem).join('');

  const html = `
    <div style="display:flex;gap:6px;margin-bottom:14px;flex-wrap:wrap;">${filters}</div>
    ${summaryHtml}
    <div class="adm-section-title">Лента · последние ${d.items.length}</div>
    ${listHtml}`;

  _showAdmin('stats', '💰 Транзакции', 'счета · оплаты · заморозки · отказы', html);
}

// Регистрируем в роутере openAdmin
const _origOpenAdmin = openAdmin;
// eslint-disable-next-line no-global-assign
openAdmin = async function(section) {
  if (section === 'transactions') return adminTransactions();
  return _origOpenAdmin(section);
};

// ═══════════════════════════════════════════════════════════════
// ПАТЧ ДЛЯ admin.js — добавь этот блок В САМЫЙ НИЗ файла, ПОСЛЕ
// существующего блока:
//   const _origOpenAdmin = openAdmin;
//   openAdmin = async function(section) { ... };
// Порядок важен: этот патч должен идти СТРОГО ПОСЛЕ него, иначе
// раздел 'team' не подключится (см. пояснение в конце этого файла).
// Использует уже существующие _adminFetch / _showAdmin / _skeleton /
// adm-* стили — ничего больше подключать не нужно.
// ═══════════════════════════════════════════════════════════════

const _TEAM_ROLE_ICON = {
  qa: 'i-shield', idea: 'i-zap', hr: 'i-users', dev: 'i-server',
  design: 'i-star', marketing: 'i-bell', other: 'i-gift',
};
const _TEAM_STATUS = {
  new:       { l: '🆕 новая',      c: 'gray'   },
  contacted: { l: '💬 связались',  c: 'cyan'   },
  hired:     { l: '✅ нанят',      c: 'green'  },
  rejected:  { l: '❌ отклонена',  c: 'red'    },
};

let _teamStatusFilter = 'all';

async function adminTeam() {
  _showAdmin('team', '🧑\u200d💼 Заявки в команду', 'Загрузка…', _skeleton(4));
  const d = await _adminFetch('/admin/team_applications', { status: _teamStatusFilter });
  if (!d) return;
  _renderTeamList(d);
}

function _renderTeamList(d) {
  const counts = d.counts || {};
  const total = Object.values(counts).reduce((a, b) => a + b, 0);

  const filters = ['all', 'new', 'contacted', 'hired', 'rejected'].map(k => {
    const label = { all: 'Все', new: 'Новые', contacted: 'В работе', hired: 'Наняты', rejected: 'Откл.' }[k];
    const n = k === 'all' ? total : (counts[k] || 0);
    return `<div class="adm-btn ${_teamStatusFilter === k ? 'primary' : 'ghost'}"
      style="flex:1;padding:9px 4px;font-size:11px;" onclick="_teamStatusFilter='${k}';adminTeam();">${label}${n ? ` (${n})` : ''}</div>`;
  }).join('');

  const list = !d.applications.length
    ? `<div class="adm-empty"><svg><use href="#i-users"/></svg>Заявок пока нет</div>`
    : d.applications.map(a => {
        const st = _TEAM_STATUS[a.status] || _TEAM_STATUS.new;
        const dt = (a.created_at || '').slice(0, 16).replace('T', ' ');
        const salary = (a.salary_from || a.salary_to)
          ? `${a.salary_from || '—'}–${a.salary_to || '—'} ${a.currency || ''}` : null;
        return `
        <div class="adm-list-item" onclick="adminTeamCard(${a.id})">
          <div class="adm-avatar">${_initials(a.full_name || a.username || String(a.user_id))}</div>
          <div class="adm-list-info">
            <div class="adm-list-name">${a.full_name || '—'} ${a.username ? '· @' + a.username : ''}</div>
            <div class="adm-list-meta">${a.role_title} · ${a.experience_title}${salary ? ' · ' + salary : ''}</div>
            <div class="adm-list-meta" style="color:var(--dim);">${dt} · ${a.contact_tg}</div>
          </div>
          <div class="adm-list-side">
            <span class="adm-badge ${st.c}">${st.l}</span>
            <div class="adm-chev"><svg class="icon"><use href="#i-chevron"/></svg></div>
          </div>
        </div>`;
      }).join('');

  const html = `<div style="display:flex;gap:6px;margin-bottom:14px;flex-wrap:wrap;">${filters}</div>${list}`;
  _showAdmin('team', '🧑\u200d💼 Заявки в команду', `Всего: ${total}`, html);
}

async function adminTeamCard(id) {
  _showAdmin('team', '🧑\u200d💼 Анкета', 'Загрузка…', _skeleton(3));
  const d = await _adminFetch('/admin/team_applications/card', { id });
  if (!d) return;
  const a = d.application;
  const st = _TEAM_STATUS[a.status] || _TEAM_STATUS.new;
  const salary = (a.salary_from || a.salary_to)
    ? `${a.salary_from || '—'}–${a.salary_to || '—'} ${a.currency || ''} · ${a.payment_type === 'percent' ? 'процент от прибыли' : 'фиксированная'}`
    : 'не указана';

  const html = `
    <div class="adm-wide-card">
      <div class="adm-wide-row">
        <div style="display:flex;align-items:center;gap:10px;">
          <div class="adm-avatar" style="width:44px;height:44px;font-size:16px;">${_initials(a.full_name || a.username || String(a.user_id))}</div>
          <div>
            <div class="adm-wide-title">${a.full_name || '—'} ${a.username ? '· @' + a.username : ''}</div>
            <div class="adm-wide-sub">ID <code>${a.user_id}</code></div>
          </div>
        </div>
        <span class="adm-badge ${st.c}">${st.l}</span>
      </div>
    </div>

    <div class="adm-wide-card">
      <div class="adm-wide-row"><div class="adm-wide-icon" style="background:rgba(124,58,237,.14);color:var(--accent2);"><svg class="icon"><use href="#${_TEAM_ROLE_ICON[a.role] || 'i-users'}"/></svg></div>
        <div style="flex:1;"><div class="adm-wide-title">${a.role_title}</div><div class="adm-wide-sub">Опыт: ${a.experience_title}</div></div>
      </div>
    </div>
    <div class="adm-wide-card"><div class="adm-wide-sub" style="margin-bottom:2px;">Ожидаемая оплата</div><div class="adm-wide-title" style="font-size:13px;">${salary}</div></div>
    <div class="adm-wide-card"><div class="adm-wide-sub" style="margin-bottom:2px;">Связь</div><div class="adm-wide-title" style="font-size:13px;">${a.contact_tg}</div></div>
    ${a.comment ? `<div class="adm-wide-card"><div class="adm-wide-sub" style="margin-bottom:4px;">Комментарий</div><div style="font-size:12.5px;color:var(--dim);line-height:1.5;">${a.comment}</div></div>` : ''}
    ${a.resume_filename ? `
      <div class="adm-btn ghost full" style="margin-bottom:10px;" onclick="_teamDownloadResume('${a.resume_filename}','${a.resume_mime || ''}', ${a.id})">
        <svg class="icon"><use href="#i-download"/></svg>&nbsp;Скачать: ${a.resume_filename}
      </div>` : ''}

    <div class="adm-section-title">Статус</div>
    <div class="adm-btn-grid">
      <div class="adm-btn ${a.status==='contacted'?'primary':''}" onclick="_teamSetStatus(${a.id},'contacted')">💬 Связались</div>
      <div class="adm-btn ok ${a.status==='hired'?'primary':''}" onclick="_teamSetStatus(${a.id},'hired')">✅ Нанять</div>
      <div class="adm-btn danger full" onclick="_teamSetStatus(${a.id},'rejected')">❌ Отклонить</div>
    </div>
    <div class="adm-divider"></div>
    <div class="adm-btn ghost full" onclick="adminTeam()">⬅️ К списку заявок</div>`;
  _showAdmin('team', '🧑\u200d💼 Анкета', `#${a.id}`, html);
}

async function _teamSetStatus(id, status) {
  const d = await _adminFetch('/admin/team_applications/status', { id, status });
  if (!d) return;
  showToast('✅ Статус обновлён');
  tg?.HapticFeedback?.notificationOccurred('success');
  adminTeamCard(id);
}

// резюме хранится в base64 только в карточке (не в списке) — качаем через data URL
async function _teamDownloadResume(filename, mime, id) {
  const d = await _adminFetch('/admin/team_applications/card', { id });
  if (!d || !d.application?.resume_b64) { showToast('❌ Файл недоступен'); return; }
  const a = document.createElement('a');
  a.href = `data:${mime || 'application/octet-stream'};base64,${d.application.resume_b64}`;
  a.download = filename;
  document.body.appendChild(a); a.click(); a.remove();
}

// ── регистрация в роутере (добавь 'team: adminTeam,' в map внутри openAdmin
//    ИЛИ просто оставь этот перехват — он работает независимо от map) ──
const _origOpenAdminTeam = openAdmin;
openAdmin = async function(section) {
  if (section === 'team') return adminTeam();
  return _origOpenAdminTeam(section);
};

// ══════════════════ АКЦИЯ (отдельно от обычных цен) ══════════════════
async function adminPromoYear() {
  _showAdmin('promo', '🔥 Акция · Год', 'Отдельная от обычных цен', _skeleton(3));
  const d = await _adminFetch('/admin/promo_year');
  if (!d) return;
  _renderPromoYear(d);
}

function _renderPromoYear(d) {
  const p = d.prices || {};
  const html = `
    <div class="adm-wide-card">
      <div class="adm-wide-row">
        <div><div class="adm-wide-title">Акция активна</div><div class="adm-wide-sub">Показывать баннер и применять цены</div></div>
        <button class="adm-toggle ${d.enabled ? 'on' : ''}" id="promoToggle" onclick="_promoToggleEnabled()"></button>
      </div>
    </div>
    <div class="adm-section-title">Тариф и период акции</div>
    <div style="display:flex;gap:8px;margin-bottom:14px;">
      <select id="promoPlan" style="flex:1;background:var(--surface);border:1px solid var(--border);border-radius:12px;color:var(--text);padding:0 10px;height:42px;">
        <option value="standard" ${d.plan==='standard'?'selected':''}>Standard</option>
        <option value="premium" ${d.plan==='premium'?'selected':''}>Premium</option>
        <option value="ultimate" ${d.plan==='ultimate'?'selected':''}>Ultimate</option>
      </select>
      <select id="promoPeriod" style="flex:1;background:var(--surface);border:1px solid var(--border);border-radius:12px;color:var(--text);padding:0 10px;height:42px;">
        <option value="month" ${d.period==='month'?'selected':''}>1 месяц</option>
        <option value="3month" ${d.period==='3month'?'selected':''}>3 месяца</option>
        <option value="6month" ${d.period==='6month'?'selected':''}>6 месяцев</option>
        <option value="year" ${d.period==='year'?'selected':''}>1 год</option>
      </select>
    </div>
    <div class="adm-section-title">Цены акции, ₽</div>
    <div class="adm-list-item" style="cursor:default;">
      <div class="adm-list-info"><div class="adm-list-name">1 устройство</div></div>
      <input type="number" class="adm-input-inline" id="promoP1" value="${p['1'] || ''}">
    </div>
    <div class="adm-list-item" style="cursor:default;">
      <div class="adm-list-info"><div class="adm-list-name">2 устройства</div></div>
      <input type="number" class="adm-input-inline" id="promoP2" value="${p['2'] || ''}">
    </div>
    <div class="adm-list-item" style="cursor:default;">
      <div class="adm-list-info"><div class="adm-list-name">4 устройства</div></div>
      <input type="number" class="adm-input-inline" id="promoP4" value="${p['4'] || ''}">
    </div>
    <div class="adm-btn primary full" style="margin-top:10px;" onclick="_promoSave()">💾 Сохранить акцию</div>
<div style="margin-top:10px;font-size:11.5px;color:var(--muted);text-align:center;">
  Кнопка «Сохранить» сразу включает акцию. Чтобы выключить — используй тумблер выше.
</div>
  _showAdmin('promo', '🔥 Акция · Год', d.enabled ? 'Активна' : 'Выключена', html);
  window._promoState = d;
}

async function _promoToggleEnabled() {
  const newEnabled = !window._promoState.enabled;
  const d = await _adminFetch('/admin/promo_year/set', { enabled: newEnabled });
  if (d) { showToast(newEnabled ? '✅ Акция включена' : '⏸ Акция выключена'); adminPromoYear(); }
}

async function _promoSave() {
  const plan = document.getElementById('promoPlan').value;
  const period = document.getElementById('promoPeriod').value;
  const prices = {
    1: parseInt(document.getElementById('promoP1').value, 10) || 0,
    2: parseInt(document.getElementById('promoP2').value, 10) || 0,
    4: parseInt(document.getElementById('promoP4').value, 10) || 0,
  };

  // Проверяем, что хотя бы одна цена реально введена
  if (!prices[1] && !prices[2] && !prices[4]) {
    showToast('❌ Заполни хотя бы одну цену');
    return;
  }

  // Сохраняем цены И сразу включаем акцию — так пользователю не нужно
  // отдельно щёлкать тумблер после ввода цифр.
  const d = await _adminFetch('/admin/promo_year/set', { plan, period, prices, enabled: true });
  if (d) { showToast('✅ Акция сохранена и включена'); adminPromoYear(); }
}
