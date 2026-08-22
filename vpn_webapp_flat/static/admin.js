/* admin.js — панель управления прямо в мини-аппе.
   Подключается ПОСЛЕ основного инлайн-скрипта index.html:
     <script src="/static/admin.js"></script>
   Использует уже существующие в index.html: tg, showToast(), CONFIG. */

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

// ── универсальный модал ──
function _ensureAdminModal() {
  if (document.getElementById('adminModal')) return;
  const div = document.createElement('div');
  div.className = 'modal-overlay';
  div.id = 'adminModal';
  div.innerHTML = `
    <div class="modal-sheet config-modal-sheet">
      <div class="modal-title" id="adminModalTitle">Раздел</div>
      <div id="adminModalBody"></div>
      <button class="modal-cancel" onclick="document.getElementById('adminModal').classList.remove('show')">Закрыть</button>
    </div>`;
  document.body.appendChild(div);
}

function _showAdmin(title, bodyHtml) {
  _ensureAdminModal();
  document.getElementById('adminModalTitle').textContent = title;
  document.getElementById('adminModalBody').innerHTML = bodyHtml;
  document.getElementById('adminModal').classList.add('show');
}

function _adminRow(label, valueHtml) {
  return `<div style="display:flex;justify-content:space-between;gap:10px;padding:10px 0;border-bottom:1px solid var(--border);font-size:13px;">
    <span style="color:var(--muted);">${label}</span><span>${valueHtml}</span></div>`;
}

// ── роутер: кнопки в HTML должны звать openAdmin('users') вместо openBotCommand('admin_users') ──
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
  _showAdmin('📊 Статистика', '<div style="padding:20px;text-align:center;color:var(--muted);">Загрузка…</div>');
  const d = await _adminFetch('/admin/stats_full');
  if (!d) return;
  const html =
    _adminRow('Сегодня', `<b>${d.day_rub} ₽</b>`) +
    _adminRow('7 дней', `<b>${d.week_rub} ₽</b>`) +
    _adminRow('30 дней', `<b>${d.month_rub} ₽</b>`) +
    _adminRow('Всего', `<b>${d.all_rub} ₽</b>`) +
    _adminRow('MRR', `<b>${d.mrr} ₽/мес</b>`) +
    _adminRow('Пользователей', d.users) +
    _adminRow('Активных подписок', d.active_subs) +
    _adminRow('Свободно серверов', `${d.free_paid} платных · ${d.free_trial} пробных`) +
    _adminRow('Конверсия триал→оплата', `${d.trial_conv_rate}% (${d.trial_conv_n})`) +
    _adminRow('Отток за 30д', `${d.churn_rate}% (${d.churn_n})`) +
    _adminRow('Баланс у всех юзеров', `${d.total_balance} ₽`) +
    _adminRow('Открытых предзаказов', d.pending_preorders);
  _showAdmin('📊 Статистика', html);
}

// ══════════════════ 2. ПОЛЬЗОВАТЕЛИ ══════════════════
let _usersOffset = 0;

async function adminUsers(search) {
  _showAdmin('👤 Пользователи', '<div style="padding:20px;text-align:center;color:var(--muted);">Загрузка…</div>');
  const d = await _adminFetch('/admin/users', search ? { search } : { offset: _usersOffset });
  if (!d) return;
  let html = `
    <div class="promo-row" style="margin-bottom:12px;">
      <input class="promo-input" id="adminUserSearch" placeholder="ID или @username…">
      <button class="promo-submit" onclick="adminUsers(document.getElementById('adminUserSearch').value.trim())">🔎</button>
    </div>`;
  if (!d.users.length) {
    html += `<div style="padding:16px;color:var(--muted);text-align:center;">Никого не найдено.</div>`;
  } else {
    html += d.users.map(u => `
      <div class="conn-item" style="cursor:pointer;" onclick="adminUserCard(${u.user_id})">
        <div class="conn-info">
          <div class="conn-name">${u.full_name || '—'} ${u.username ? '@' + u.username : ''}</div>
          <div class="conn-meta">ID ${u.user_id} · 💰${u.balance_rub || 0} ₽</div>
        </div>
      </div>`).join('');
    if (!search) {
      html += `<div style="display:flex;gap:8px;margin-top:12px;">
        ${_usersOffset > 0 ? `<button class="modal-pay-btn secondary" style="flex:1;" onclick="_usersOffset=Math.max(0,_usersOffset-10);adminUsers();">⬅️ Назад</button>` : ''}
        ${_usersOffset + 10 < d.total ? `<button class="modal-pay-btn secondary" style="flex:1;" onclick="_usersOffset+=10;adminUsers();">Дальше ➡️</button>` : ''}
      </div>`;
    }
  }
  _showAdmin(`👤 Пользователи (${d.total})`, html);
}

async function adminUserCard(uid) {
  const d = await _adminFetch('/admin/user_card', { user_id: uid });
  if (!d) return;
  const u = d.user;
  const html = `
    ${_adminRow('Имя', `${u.full_name || '—'} ${u.username ? '@' + u.username : ''}`)}
    ${_adminRow('ID', `<code>${u.user_id}</code>`)}
    ${_adminRow('Баланс', `<b>${u.balance_rub || 0} ₽</b>`)}
    ${_adminRow('Потрачено всего', `${u.spent || 0} ₽`)}
    ${_adminRow('Приглашено', u.invited || 0)}
    ${_adminRow('Статус', u.banned ? '⛔️ забанен' : '✅ активен')}
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:14px;">
      <button class="modal-amount-btn" onclick="adminUserAction(${uid},'days',7)">+7 дней</button>
      <button class="modal-amount-btn" onclick="adminUserAction(${uid},'days',30)">+30 дней</button>
      <button class="modal-amount-btn" onclick="adminUserAction(${uid},'balance',100)">+100 ₽</button>
      <button class="modal-amount-btn" onclick="adminUserAction(${uid},'balance',500)">+500 ₽</button>
      <button class="modal-amount-btn" onclick="adminUserAction(${uid},'${u.banned ? 'unban' : 'ban'}')">${u.banned ? '✅ Разбанить' : '⛔️ Забанить'}</button>
      <button class="modal-amount-btn" onclick="adminUserAction(${uid},'refund')">💸 Рефанд последнего</button>
      <button class="modal-amount-btn" onclick="adminUserAction(${uid},'noprem')">👑 Откл. премиум</button>
      <button class="modal-amount-btn" onclick="adminUserCustom(${uid})">✏️ Своя сумма/дни</button>
    </div>
    <button class="modal-pay-btn secondary" style="margin-top:10px;" onclick="adminUsers()">⬅️ К списку</button>`;
  _showAdmin(`👤 ${u.full_name || u.user_id}`, html);
}

async function adminUserAction(uid, action, value) {
  const d = await _adminFetch('/admin/user_action', { user_id: uid, action, value });
  if (!d) return;
  showToast('✅ Готово');
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

// ══════════════════ БАН / РАЗБАН (быстрый доступ по ID) ══════════════════
async function adminBan() {
  const html = `
    <div class="promo-row">
      <input class="promo-input" id="adminBanId" placeholder="ID пользователя" inputmode="numeric">
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:10px;">
      <button class="modal-amount-btn" onclick="_adminBanGo(true)">⛔️ Забанить</button>
      <button class="modal-amount-btn" onclick="_adminBanGo(false)">✅ Разбанить</button>
    </div>
    <div style="margin-top:14px;font-size:12px;color:var(--muted);">Полная карточка юзера — в разделе «Пользователи».</div>`;
  _showAdmin('⛔️ Бан / Разбан', html);
}
async function _adminBanGo(ban) {
  const idEl = document.getElementById('adminBanId');
  const uid = parseInt(idEl.value, 10);
  if (!uid) { showToast('Введи ID'); return; }
  const d = await _adminFetch('/admin/user_action', { user_id: uid, action: ban ? 'ban' : 'unban' });
  if (!d) return;
  showToast(ban ? '⛔️ Забанен' : '✅ Разбанен');
}

// ══════════════════ 3. СЕРВЕРЫ ══════════════════
async function adminServers() {
  _showAdmin('🌍 Серверы', '<div style="padding:20px;text-align:center;color:var(--muted);">Загрузка…</div>');
  const d = await _adminFetch('/admin/servers');
  if (!d) return;
  let html = d.regions.map(r => `
    <div class="conn-item">
      <div class="conn-info">
        <div class="conn-name">${r.is_premium ? '⭐️' : '▫️'} ${r.region}</div>
        <div class="conn-meta">🟢${r.free} свободно / всего ${r.total}</div>
      </div>
      <div class="conn-side">
        <button class="conn-dl-btn" onclick="_adminServerToggle('${r.region}', ${!r.is_premium})">${r.is_premium ? 'Снять ⭐️' : 'Сделать ⭐️'}</button>
        <button class="conn-dl-btn report-btn" onclick="_adminServerDelete('${r.region}')">🗑</button>
      </div>
    </div>`).join('');
  html += `
    <div class="promo-row" style="margin-top:14px;">
      <input class="promo-input" id="adminNewRegion" placeholder="Новый регион…">
      <button class="promo-submit" onclick="_adminServerAdd()">➕</button>
    </div>`;
  _showAdmin('🌍 Серверы', html);
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
  if (d) adminServers();
}

// ══════════════════ 4. ЦЕНЫ ══════════════════
async function adminPrices() {
  _showAdmin('💲 Цены', '<div style="padding:20px;text-align:center;color:var(--muted);">Загрузка…</div>');
  const d = await _adminFetch('/admin/prices');
  if (!d) return;
  const html = d.plans.map(p => `
    <div style="margin-bottom:14px;">
      <div style="font-weight:700;margin-bottom:6px;">${p.title}</div>
      ${p.items.map(it => `
        <div class="conn-item" style="padding:6px 0;">
          <div class="conn-info"><div class="conn-name" style="font-size:13px;">${it.devices} устр · ${it.period_ru}</div></div>
          <div class="conn-side">
            <input type="number" value="${it.rub}" id="pp_${p.plan}_${it.devices}_${it.period}"
              style="width:70px;background:var(--card);border:1px solid var(--border);border-radius:8px;color:var(--text);padding:6px;text-align:right;">
            <button class="conn-dl-btn" onclick="_adminPriceSave('${p.plan}',${it.devices},'${it.period}')">💾</button>
          </div>
        </div>`).join('')}
    </div>`).join('');
  _showAdmin('💲 Цены', html);
}
async function _adminPriceSave(plan, devices, period) {
  const el = document.getElementById(`pp_${plan}_${devices}_${period}`);
  const rub = parseInt(el.value, 10);
  if (isNaN(rub) || rub < 0) { showToast('Некорректная цена'); return; }
  const d = await _adminFetch('/admin/prices/set', { plan, devices, period, rub });
  if (d) showToast('✅ Сохранено');
}

// ══════════════════ 5. ПРОМОКОДЫ ══════════════════
async function adminPromo() {
  _showAdmin('🎟 Промокоды', '<div style="padding:20px;text-align:center;color:var(--muted);">Загрузка…</div>');
  const d = await _adminFetch('/admin/promo');
  if (!d) return;
  _renderPromo(d.promos);
}
function _renderPromo(promos) {
  let html = !promos.length ? `<div style="padding:12px;color:var(--muted);">Пока нет промокодов.</div>` :
    promos.map(p => `
      <div class="conn-item">
        <div class="conn-info">
          <div class="conn-name">${p.active ? '🟢' : '🔴'} ${p.code}</div>
          <div class="conn-meta">${p.kind === 'balance' ? '+' + p.amount_rub + ' ₽' : '−' + p.percent + '%'} · ${p.used}/${p.max_uses || '∞'}</div>
        </div>
        <div class="conn-side">
          <button class="conn-dl-btn" onclick="_adminPromoToggle('${p.code}')">${p.active ? '⏸' : '▶️'}</button>
          <button class="conn-dl-btn report-btn" onclick="_adminPromoDelete('${p.code}')">🗑</button>
        </div>
      </div>`).join('');
  html += `
    <div style="margin-top:14px;display:flex;flex-direction:column;gap:8px;">
      <input class="promo-input" id="pcCode" placeholder="КОД (напр. SALE20)">
      <div style="display:flex;gap:8px;">
        <select id="pcKind" style="flex:1;background:var(--card);border:1px solid var(--border);border-radius:12px;color:var(--text);padding:0 10px;height:44px;">
          <option value="discount">Скидка %</option>
          <option value="balance">На баланс ₽</option>
        </select>
        <input class="promo-input" id="pcValue" type="number" placeholder="Значение" style="flex:1;">
      </div>
      <input class="promo-input" id="pcMax" type="number" placeholder="Лимит активаций (0 = без лимита)">
      <button class="modal-pay-btn" onclick="_adminPromoCreate()">➕ Создать</button>
    </div>`;
  _showAdmin('🎟 Промокоды', html);
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
    <textarea id="adminBcastText" placeholder="Текст сообщения всем пользователям…"
      style="width:100%;min-height:120px;background:var(--card);border:1px solid var(--border);border-radius:12px;padding:12px 14px;color:var(--text);font-size:14px;font-family:var(--sans);resize:none;margin-bottom:12px;"></textarea>
    <button class="modal-pay-btn" onclick="_adminBroadcastSend()">📣 Отправить всем</button>`;
  _showAdmin('📣 Рассылка', html);
}
async function _adminBroadcastSend() {
  const text = document.getElementById('adminBcastText').value.trim();
  if (!text) { showToast('Введи текст'); return; }
  if (!confirm('Отправить это сообщение ВСЕМ пользователям?')) return;
  showToast('📣 Отправляю…');
  const d = await _adminFetch('/admin/broadcast', { text });
  if (d) _showAdmin('📣 Рассылка', `<div style="padding:12px;">✅ Доставлено: <b>${d.sent}</b><br>❌ Ошибок: <b>${d.failed}</b></div>`);
}

// ══════════════════ 7. A/B ТЕСТЫ ══════════════════
async function adminAB() {
  _showAdmin('🧪 A/B тесты', '<div style="padding:20px;text-align:center;color:var(--muted);">Загрузка…</div>');
  const d = await _adminFetch('/admin/ab');
  if (!d) return;
  if (!d.enabled) {
    _showAdmin('🧪 A/B тесты', `<div style="padding:12px;color:var(--muted);">Эксперимент выключен. Включается через AB_EXPERIMENT в .env бота.</div>`);
    return;
  }
  const html = `<div style="margin-bottom:10px;color:var(--muted);font-size:12px;">${d.metric}</div>` +
    d.variants.map(v => `
      <div class="conn-item">
        <div class="conn-info">
          <div class="conn-name">Вариант ${v.variant}</div>
          <div class="conn-meta">👥${v.users} · 🧪${v.trials} · 💳${v.paid} · конв. <b>${v.conv_all}%</b></div>
        </div>
      </div>`).join('');
  _showAdmin(`🧪 ${d.title}`, html);
}

// ══════════════════ 8. БЭКАП БАЗЫ ══════════════════
async function adminBackup() {
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
  _showAdmin('📦 Закупки', '<div style="padding:20px;text-align:center;color:var(--muted);">Загрузка…</div>');
  const d = await _adminFetch('/admin/restock');
  if (!d) return;
  _renderRestock(d);
}
function _renderRestock(d) {
  const STATUS = { new: '🆕 новая', awaiting_payment: '⏳ ждёт оплаты', paid: '💸 оплачено', done: '✅ закрыта', canceled: '❌ отменена' };
  let html = !d.orders.length ? `<div style="padding:8px;color:var(--muted);">Активных заявок нет.</div>` :
    d.orders.map(o => `
      <div class="conn-item" style="cursor:pointer;" onclick="_adminRestockOpen(${o.id})">
        <div class="conn-info">
          <div class="conn-name">${o.urgent ? '🔥 ' : ''}#${o.id} ${o.region}</div>
          <div class="conn-meta">${STATUS[o.status] || o.status}</div>
        </div>
      </div>`).join('');
  if (d.low_stock?.length) {
    html += `<div style="margin-top:12px;font-size:12px;color:var(--orange);font-weight:700;">⚠️ Низкий запас:</div>`;
    html += d.low_stock.map(r => `
      <div class="conn-item" style="padding:6px 0;">
        <div class="conn-info"><div class="conn-name" style="font-size:13px;">${r.region} — 🟢${r.free}${r.has_preorder ? ' · есть предзаказ' : ''}</div></div>
        <button class="conn-dl-btn" onclick="_adminRestockCreate('${r.region}')">➕ Заявка</button>
      </div>`).join('');
  }
  _showAdmin('📦 Закупки', html);
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
  let actions = '';
  if (['new', 'awaiting_payment'].includes(o.status)) {
    actions = `
      <div style="display:flex;flex-direction:column;gap:8px;margin-top:12px;">
        <input class="promo-input" id="rsAmount" type="number" placeholder="Сумма ₽" value="${o.amount_rub || ''}">
        <button class="modal-amount-btn" onclick="_adminRestockAmount(${id})">💾 Сохранить сумму</button>
        <input class="promo-input" id="rsUrl" placeholder="https://ссылка на оплату" value="${o.pay_url || ''}">
        <button class="modal-amount-btn" onclick="_adminRestockUrl(${id})">🔗 Сохранить ссылку</button>
        ${o.pay_url ? `<button class="modal-amount-btn" onclick="_adminRestockStatus(${id},'paid')">✅ Отметить оплаченной</button>` : ''}
        <button class="modal-amount-btn" onclick="_adminRestockStatus(${id},'canceled')">❌ Отменить</button>
      </div>`;
  } else if (o.status === 'paid') {
    actions = `
      <div style="margin-top:12px;">
        <div class="config-block-label" style="margin-bottom:6px;">Вставь .conf (можно несколько подряд)</div>
        <textarea id="rsConfigs" style="width:100%;min-height:100px;background:var(--card);border:1px solid var(--border);border-radius:12px;padding:10px;color:var(--text);font-size:12px;font-family:var(--mono);"></textarea>
        <button class="modal-amount-btn" style="width:100%;margin-top:8px;" onclick="_adminRestockAddConfigs(${id})">➕ Добавить</button>
        <button class="modal-amount-btn" style="width:100%;margin-top:8px;" onclick="_adminRestockStatus(${id},'done')">✅ Завершить заявку</button>
      </div>`;
  }
  _showAdmin(`📦 Заявка #${id}`, `
    ${_adminRow('Регион', o.region)}
    ${_adminRow('Нужно', o.need)}
    ${_adminRow('Добавлено', `${o.added}/${o.need}`)}
    ${_adminRow('Статус', o.status)}
    ${actions}
    <button class="modal-pay-btn secondary" style="margin-top:12px;" onclick="adminRestock()">⬅️ К заявкам</button>`);
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
