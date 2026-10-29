/* Jigobourso v2 — bibliothèque commune : API, formats, navigation, graphiques SVG, dialogues. Aucune dépendance. */
'use strict';
const J = {};

J.esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
J.$ = (sel, root = document) => root.querySelector(sel);
J.$$ = (sel, root = document) => [...root.querySelectorAll(sel)];

/* ───── API ───── */
J.api = async function (route, { method = 'GET', body = null, params = {} } = {}) {
  const qs = new URLSearchParams({ r: route, ...params });
  const res = await fetch('api.php?' + qs, {
    method, credentials: 'same-origin',
    headers: body ? { 'Content-Type': 'application/json' } : {}, body: body ? JSON.stringify(body) : undefined,
  });
  let data = null;
  try { data = await res.json(); } catch (e) { /* réponse non JSON */ }
  if (res.status === 401 && !location.pathname.endsWith('login.html')) { location.href = 'login.html?next=' + encodeURIComponent(location.pathname.split('/').pop() + location.search); throw new Error('auth'); }
  if (!res.ok) throw new Error((data && data.error) || 'Erreur ' + res.status);
  return data;
};
J.post = (route, body) => J.api(route, { method: 'POST', body: body || {} });

/* ───── formats (français) ───── */
const nf = (d, o = {}) => new Intl.NumberFormat('fr-FR', { minimumFractionDigits: d, maximumFractionDigits: d, ...o });
J.num = (v, d = 2) => (v === null || v === undefined || isNaN(v)) ? '–' : nf(d).format(v);
J.pct = (v, d = 2, sign = true) => (v === null || v === undefined || isNaN(v)) ? '–' : nf(d, { signDisplay: sign ? 'exceptZero' : 'auto' }).format(v) + ' %';
J.eur = (v, d = 2) => (v === null || v === undefined || isNaN(v)) ? '–' : new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR', minimumFractionDigits: d, maximumFractionDigits: d }).format(v);
J.money = (v, cur, d = 2) => { if (v === null || v === undefined || isNaN(v)) return '–'; try { return new Intl.NumberFormat('fr-FR', { style: 'currency', currency: ((cur === 'GBp' || cur === 'GBX') ? 'GBP' : cur) || 'EUR', currencyDisplay: 'narrowSymbol', minimumFractionDigits: d, maximumFractionDigits: d }).format((cur === 'GBp' || cur === 'GBX') ? v / 100 : v); } catch (e) { return J.num(v, d) + ' ' + (cur || ''); } };
J.cls = v => (v > 0 ? 'up' : v < 0 ? 'down' : '');
J.date = s => { if (!s) return '–'; const d = new Date(s.replace(' ', 'T') + (s.length > 10 ? 'Z' : '')); return isNaN(d) ? s : d.toLocaleDateString('fr-FR', { day: '2-digit', month: 'short', year: 'numeric' }); };
J.dateTime = s => { if (!s) return '–'; const d = new Date(s.replace(' ', 'T') + 'Z'); return isNaN(d) ? s : d.toLocaleString('fr-FR', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }); };
J.ago = s => { if (!s) return '–'; const m = (Date.now() - new Date(s.replace(' ', 'T') + 'Z')) / 60000; return m < 1 ? 'à l’instant' : m < 60 ? Math.round(m) + ' min' : m < 1440 ? Math.round(m / 60) + ' h' : Math.round(m / 1440) + ' j'; };
J.priceLabel = r => r.price_stale ? 'Cours ancien' : ({ intraday: 'Cours différé', daily: 'Clôture', quote: 'Dernier cours' }[r.price_source || r.source] || 'Cours');

/* ───── statuts et explications ───── */
J.statusBadge = (status, label) => `<span class="badge ${{ retained: 'ok', rejected: 'ko', unknown: 'wait', excluded: 'ko' }[status] || ''}">${J.esc(label || status)}</span>`;
J.PERIODS = { day: 'Dernier jour', week: 'Dernière semaine', month: 'Dernier mois', quarter: 'Trois mois', half: 'Six mois', year: 'Un an' };
J.CRITERIA = {
  min_slope: ['pente', '% / séance', 'slope'], min_r2: ['régularité (R²)', '', 'r2'], min_er: ['efficacité (ER)', '', 'er'], min_return: ['performance', '%', 'perf'],
  max_return: ['performance maximale', '%', 'perf'], max_volatility: ['volatilité', '% / séance', 'volatility'], max_drawdown: ['repli maximal', '%', 'drawdown'],
};
J.TECH = { above_ma50: 'Cours au-dessus de la moyenne 50 jours', ma50_rising: 'Moyenne 50 jours en hausse', max_daily_change: 'Variation du jour', max_gap_ma20: 'Écart à la moyenne 20 jours' };
J.explain = function (r) {
  const per = J.PERIODS[r.period] || r.period;
  const ok = r.result === 'pass' ? 'pass' : r.result === 'fail' ? 'fail' : 'missing';
  let text;
  if (r.criterion === 'freshness') text = `Données non à jour : dernière clôture ${J.date(r.value)} (attendue ${J.date(r.threshold)}).`;
  else if (r.criterion === 'data') text = `${per} : ${{ history: 'historique trop court', break: 'rupture de cours dans la période', invalid: 'données inexploitables' }[r.metric] || 'donnée absente'} (${r.threshold} clôtures nécessaires).`;
  else if (r.period === 'technical') text = `${J.TECH[r.criterion] || r.criterion} : ${r.result === 'missing' ? 'non évaluable' : r.result === 'pass' ? 'respecté' : 'non respecté'}.`;
  else {
    const [label, unit] = J.CRITERIA[r.criterion] || [r.criterion, ''];
    const min = r.criterion.startsWith('min');
    const d = r.metric === 'r2' || r.metric === 'er' ? 2 : 3;
    text = `${per} : ${label} ${J.num(r.value, d)}${unit && unit !== '' ? ' ' + unit : ''} — ${min ? 'minimum' : 'maximum'} ${J.num(r.threshold, d)}.`;
  }
  return `<div class="reason ${ok}"><span class="mark">${ok === 'pass' ? '✓' : ok === 'fail' ? '✗' : '?'}</span><span>${J.esc(text)}</span></div>`;
};

/* ───── graphiques SVG ───── */
J.spark = function (values, w = 120, h = 34) {
  if (!values || values.length < 2) return '<span class="muted small">–</span>';
  const min = Math.min(...values), max = Math.max(...values), span = max - min || 1;
  const pts = values.map((v, i) => [i * (w / (values.length - 1)), h - 3 - (v - min) / span * (h - 6)]);
  const d = pts.map((p, i) => (i ? 'L' : 'M') + p[0].toFixed(1) + ' ' + p[1].toFixed(1)).join('');
  const up = values[values.length - 1] >= values[0];
  return `<svg class="spark" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" style="color:var(--${up ? 'up' : 'down'})"><path class="area" d="${d}L${w} ${h}L0 ${h}Z"/><path d="${d}" stroke="currentColor"/></svg>`;
};
J.lineChart = function (el, series, { ma = [], unit = '', time = false } = {}) {
  /* series : [[x, y]] avec x = libellé de date ; ma : [[x, y]] moyenne mobile */
  const W = 900, H = 260, L = 8, R = 56, T = 12, B = 24;
  if (!series || series.length < 2) { el.innerHTML = '<div class="empty">Pas assez de données pour tracer la courbe.</div>'; return; }
  const ys = series.map(p => p[1]).concat(ma.map(p => p[1]));
  let min = Math.min(...ys), max = Math.max(...ys); const pad = (max - min) * .06 || 1; min -= pad; max += pad;
  const X = i => L + i * (W - L - R) / (series.length - 1), Y = v => T + (max - v) / (max - min) * (H - T - B);
  const path = series.map((p, i) => (i ? 'L' : 'M') + X(i).toFixed(1) + ' ' + Y(p[1]).toFixed(1)).join('');
  let grid = '';
  for (let k = 0; k <= 4; k++) { const v = min + (max - min) * k / 4, y = Y(v); grid += `<line class="grid" x1="${L}" x2="${W - R}" y1="${y}" y2="${y}"/><text x="${W - R + 6}" y="${y + 4}">${J.num(v, v > 100 ? 0 : 2)}</text>`; }
  let xl = '';
  for (let k = 0; k <= 4; k++) { const i = Math.round(k * (series.length - 1) / 4); xl += `<text x="${X(i)}" y="${H - 6}" text-anchor="${k === 0 ? 'start' : k === 4 ? 'end' : 'middle'}">${J.esc(time ? String(series[i][0]).slice(11, 16) : J.date(series[i][0]))}</text>`; }
  const off = series.length - ma.length;
  const maPath = ma.length > 1 ? ma.map((p, i) => (i ? 'L' : 'M') + X(i + off).toFixed(1) + ' ' + Y(p[1]).toFixed(1)).join('') : '';
  el.innerHTML = `<svg class="chart" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" role="img" aria-label="Évolution du cours">${grid}${xl}<path class="area" d="${path}L${X(series.length - 1)} ${H - B}L${L} ${H - B}Z"/>${maPath ? `<path class="ma" d="${maPath}"/>` : ''}<path class="line" d="${path}"/><g id="hover"></g><rect x="${L}" y="${T}" width="${W - L - R}" height="${H - T - B}" fill="transparent" id="hit"/></svg><div class="small muted" id="readout" style="min-height:1.4em"></div>`;
  const svg = el.querySelector('svg'), hit = el.querySelector('#hit'), ro = el.querySelector('#readout'), hv = el.querySelector('#hover');
  hit.addEventListener('mousemove', e => {
    const r = svg.getBoundingClientRect(), x = (e.clientX - r.left) / r.width * W, i = Math.max(0, Math.min(series.length - 1, Math.round((x - L) / ((W - L - R) / (series.length - 1)))));
    hv.innerHTML = `<circle cx="${X(i)}" cy="${Y(series[i][1])}" r="4" fill="var(--accent)"/>`;
    ro.textContent = (time ? J.dateTime(series[i][0]) : J.date(series[i][0])) + ' — ' + J.num(series[i][1], 2) + (unit ? ' ' + unit : '');
  });
  hit.addEventListener('mouseleave', () => { hv.innerHTML = ''; ro.textContent = ''; });
};
J.barChart = function (el, data, { unit = '€' } = {}) {
  if (!data.length) { el.innerHTML = '<div class="empty">Aucune vente enregistrée.</div>'; return; }
  const W = 600, H = 200, B = 26, max = Math.max(...data.map(d => Math.abs(d[1])), 1), bw = Math.min(70, (W - 20) / data.length - 12), mid = (H - B) / 2;
  el.innerHTML = `<svg class="chart" viewBox="0 0 ${W} ${H}" style="height:200px"><line class="grid" x1="0" x2="${W}" y1="${mid}" y2="${mid}"/>${data.map((d, i) => { const x = 20 + i * ((W - 20) / data.length), h = Math.abs(d[1]) / max * (mid - 18); return `<rect x="${x}" y="${d[1] >= 0 ? mid - h : mid}" width="${bw}" height="${Math.max(h, 1)}" rx="5" fill="var(--${d[1] >= 0 ? 'up' : 'down'})"/><text x="${x + bw / 2}" y="${H - 8}" text-anchor="middle">${J.esc(d[0])}</text><text x="${x + bw / 2}" y="${d[1] >= 0 ? mid - h - 4 : mid + h + 12}" text-anchor="middle">${J.num(d[1], 0)} ${unit}</text>`; }).join('')}</svg>`;
};

/* ───── dialogues, messages ───── */
J.toast = function (msg) { const t = document.createElement('div'); t.className = 'toast'; t.textContent = msg; document.body.appendChild(t); setTimeout(() => t.remove(), 3200); };
J.dialog = function ({ title, body, actions = [], onopen }) {
  const d = document.createElement('dialog');
  d.innerHTML = `<form method="dialog"><div class="head"><h2 style="margin:0">${J.esc(title)}</h2><button class="btn small" value="x" aria-label="Fermer">✕</button></div><div class="body">${body}</div><div class="foot"></div></form>`;
  const foot = d.querySelector('.foot');
  actions.forEach(a => { const b = document.createElement('button'); b.type = 'button'; b.className = 'btn ' + (a.cls || ''); b.textContent = a.label; b.onclick = async () => { try { b.disabled = true; const keep = await a.run(d); if (!keep) d.close(); } catch (e) { J.formError(d, e.message); } finally { b.disabled = false; } }; foot.appendChild(b); });
  document.body.appendChild(d); d.addEventListener('close', () => d.remove()); d.showModal(); if (onopen) onopen(d); return d;
};
J.formError = (d, msg) => { let e = d.querySelector('.notice.err'); if (!e) { e = document.createElement('div'); e.className = 'notice err'; d.querySelector('.body').appendChild(e); } e.textContent = msg; };
J.confirm = (title, text, okLabel = 'Confirmer') => new Promise(res => { let done = false; const d = J.dialog({ title, body: `<p>${J.esc(text)}</p>`, actions: [{ label: 'Annuler', run: () => { } }, { label: okLabel, cls: 'primary', run: () => { done = true; } }] }); d.addEventListener('close', () => res(done)); });
J.field = (label, input) => `<label class="field">${J.esc(label)}${input}</label>`;

/* ───── page : en-tête commun ───── */
J.init = async function (page, { admin = false } = {}) {
  const me = await J.api('auth/me');
  if (!me.user) { location.href = 'login.html?next=' + encodeURIComponent(location.pathname.split('/').pop() + location.search); return null; }
  if (admin && !me.user.is_admin) { location.href = 'index.html'; return null; }
  J.user = me.user;
  const prefs = me.user.prefs || {};
  J.applyTheme(prefs.theme || localStorage.getItem('jigo_theme') || 'auto');
  document.body.classList.toggle('advanced', prefs.mode === 'advanced');
  J.buildShell(page, me.user);
  return me.user;
};

/* ───── coquille : barre latérale repliable à sous-menus, en-tête, tiroir mobile ───── */
J.ICONS = {
  compass: '<circle cx="12" cy="12" r="9"/><path d="M15.5 8.5l-2 5-5 2 2-5z"/>', wallet: '<path d="M3 7a2 2 0 0 1 2-2h13v4"/><path d="M3 7v10a2 2 0 0 0 2 2h14a1 1 0 0 0 1-1V9a1 1 0 0 0-1-1H5a2 2 0 0 1-2-1"/><circle cx="16" cy="13.5" r="1"/>',
  chart: '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>', pulse: '<path d="M3 12h4l3-8 4 16 3-8h4"/>', db: '<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v6c0 1.7 3.6 3 8 3s8-1.3 8-3V5M4 11v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6"/>',
  shield: '<path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z"/>', menu: '<path d="M4 6h16M4 12h16M4 18h16"/>', search: '<circle cx="11" cy="11" r="7"/><path d="M20 20l-4-4"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>', moon: '<path d="M21 13a8 8 0 1 1-10-10 7 7 0 0 0 10 10z"/>',
  panel: '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M9 4v16"/>', chev: '<path d="M9 6l6 6-6 6"/>',
};
J.icon = (n, cls = 'ic') => `<svg class="${cls}" viewBox="0 0 24 24" aria-hidden="true">${J.ICONS[n]}</svg>`;
J.NAV = (admin) => [
  { sec: 'Marchés' },
  { id: 'explorer', label: 'Explorer', icon: 'compass', file: ['index.html', 'titre.html'], children: [
    { label: 'Classement', href: 'index.html', on: q => !q.has('kind') && !q.has('compare') && !q.has('preset') },
    { label: 'Actions', href: 'index.html?kind=equity', on: q => q.get('kind') === 'equity' && !q.has('compare') },
    { label: 'ETF', href: 'index.html?kind=etf', on: q => q.get('kind') === 'etf' && !q.has('compare') },
    { label: 'Comparer actions / ETF', href: 'index.html?compare=1', on: q => q.has('compare') },
    { label: 'Recherche libre', href: 'index.html?preset=free', on: q => q.get('preset') === 'free' }] },
  { sec: 'Mon patrimoine' },
  { id: 'portefeuilles', label: 'Portefeuilles', icon: 'wallet', file: ['portefeuilles.html'], dynamic: 'portfolios', children: [{ label: 'Vue d’ensemble', href: 'portefeuilles.html', on: q => !q.has('id') }] },
  { id: 'bilan', label: 'Bilans', icon: 'chart', file: ['bilan.html'], children: [{ label: 'Bilan global', href: 'bilan.html', on: () => true }] },
  { sec: 'Méthode' },
  { id: 'suivi', label: 'Suivi des classements', icon: 'pulse', file: ['suivi.html'], href: 'suivi.html' },
  { id: 'donnees', label: 'Données', icon: 'db', file: ['donnees.html'], children: [
    { label: 'Sources et fraîcheur', href: 'donnees.html', on: (q, h) => h !== '#places' }, { label: 'Couverture par place', href: 'donnees.html#places', on: (q, h) => h === '#places' }] },
  ...(admin ? [{ sec: 'Administration' }, { id: 'admin', label: 'Administration', icon: 'shield', file: ['admin.html'], children: [
    { label: 'FinanceDatabase', href: 'admin.html#fdb', on: (q, h) => !h || h === '#fdb' }, { label: 'Yahoo Finance', href: 'admin.html#yahoo', on: (q, h) => h === '#yahoo' },
    { label: 'Actions / ETF', href: 'admin.html#titres', on: (q, h) => h === '#titres' }, { label: 'Cron', href: 'admin.html#cron', on: (q, h) => h === '#cron' }, { label: 'Journaux', href: 'admin.html#logs', on: (q, h) => h === '#logs' },
    { label: 'Utilisateurs', href: 'admin.html#users', on: (q, h) => h === '#users' }, { label: 'Réglages', href: 'admin.html#settings', on: (q, h) => h === '#settings' }] }] : []),
];
J.buildShell = function (page, user) {
  const file = location.pathname.split('/').pop() || 'index.html', store = { get: k => { try { return localStorage.getItem(k); } catch (e) { return null; } }, set: (k, v) => { try { localStorage.setItem(k, v); } catch (e) { } } };
  const nav = J.NAV(user.is_admin), narrow = () => matchMedia('(max-width: 960px)').matches;
  const isOn = c => { const href = c.href.split('#')[0].split('?')[0]; return href === file && c.on(new URLSearchParams(location.search), location.hash); };
  let opened; try { opened = JSON.parse(store.get('jigo_nav_open') || '{}'); } catch (e) { opened = {}; }
  const html = nav.map(n => {
    if (n.sec) return `<div class="sec">${J.esc(n.sec)}</div>`;
    const here = n.file.includes(file);
    if (!n.children) return `<a class="nv ${here ? 'on' : ''}" href="${n.href}" title="${J.esc(n.label)}">${J.icon(n.icon)}<span class="lbl">${J.esc(n.label)}</span></a>`;
    const open = here || opened[n.id];
    return `<div class="grp ${open ? 'open' : ''} ${here ? 'cur' : ''}" data-id="${n.id}"><button class="nv" type="button" aria-expanded="${!!open}" title="${J.esc(n.label)}">${J.icon(n.icon)}<span class="lbl">${J.esc(n.label)}</span>${J.icon('chev', 'chev')}</button>
      <div class="sub" data-sub="${n.id}">${n.children.map(c => `<a class="sv ${here && isOn(c) ? 'on' : ''}" href="${c.href}">${J.esc(c.label)}</a>`).join('')}</div></div>`;
  }).join('');
  const initial = (user.username || '?').slice(0, 1);
  document.body.classList.add('has-shell');
  if (store.get('jigo_side') === 'collapsed' && !narrow()) document.body.classList.add('side-collapsed');
  document.body.insertAdjacentHTML('afterbegin', `<aside class="side" id="side" aria-label="Navigation principale">
    <a class="brand" href="index.html"><svg viewBox="0 0 28 28" aria-hidden="true"><rect width="28" height="28" rx="8" fill="#12a77b"/><path d="M5 20l6-7 4 4 8-10" fill="none" stroke="#fff" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/><circle cx="23" cy="7" r="2.2" fill="#e8b73c"/></svg><span>Jigobourso<small>Analyse des marchés</small></span></a>
    <nav class="side-scroll" id="nav">${html}</nav>
    <div class="side-foot"><button class="who" id="user-btn" type="button" title="Mon compte"><span class="avatar">${J.esc(initial)}</span><span><b>${J.esc(user.username)}</b><span>${user.is_admin ? 'Administrateur' : 'Utilisateur'}</span></span></button>
      <button class="nv" id="collapse-btn" type="button" title="Réduire le menu">${J.icon('panel')}<span class="lbl">Réduire le menu</span></button></div></aside><div class="side-scrim" id="scrim"></div>
    <header class="hdr"><button class="icon-btn" id="menu-btn" type="button" aria-label="Afficher ou masquer le menu" aria-controls="side" aria-expanded="true">${J.icon('menu', '')}</button><div class="crumbs" id="crumbs"></div><span class="grow"></span>
      <form id="quick-form" class="quick" role="search">${J.icon('search', '')}<input id="quick" type="search" placeholder="Rechercher un titre, un ISIN…" aria-label="Rechercher un titre"></form>
      <button class="icon-btn" id="theme-btn" type="button" aria-label="Changer de thème" title="Thème clair / sombre"></button></header>`);
  const body = document.body, side = J.$('#side'), btn = J.$('#menu-btn');
  const sync = () => { const open = narrow() ? body.classList.contains('side-open') : !body.classList.contains('side-collapsed'); btn.setAttribute('aria-expanded', open); J.$('#collapse-btn .lbl').textContent = 'Réduire le menu'; };
  const toggle = () => { if (narrow()) body.classList.toggle('side-open'); else { body.classList.toggle('side-collapsed'); store.set('jigo_side', body.classList.contains('side-collapsed') ? 'collapsed' : 'open'); closeFly(); } sync(); };
  btn.onclick = toggle; J.$('#collapse-btn').onclick = () => { if (narrow()) body.classList.remove('side-open'); else toggle(); sync(); };
  J.$('#scrim').onclick = () => { body.classList.remove('side-open'); sync(); };
  document.addEventListener('keydown', e => { if (e.key === 'Escape') { body.classList.remove('side-open'); closeFly(); sync(); } });
  matchMedia('(max-width: 960px)').addEventListener('change', () => { body.classList.remove('side-open'); sync(); });
  /* groupes dépliables */
  J.$$('.grp > .nv', side).forEach(b => b.onclick = () => { const g = b.parentElement; if (body.classList.contains('side-collapsed') && !narrow()) { location.href = nav.find(n => n.id === g.dataset.id).children[0].href; return; } g.classList.toggle('open'); b.setAttribute('aria-expanded', g.classList.contains('open')); opened[g.dataset.id] = g.classList.contains('open'); store.set('jigo_nav_open', JSON.stringify(opened)); });
  J.$$('#nav a', side).forEach(a => a.addEventListener('click', () => { if (narrow()) body.classList.remove('side-open'); }));
  /* menu volant quand la barre est réduite */
  let fly = null; const closeFly = () => { if (fly) { fly.remove(); fly = null; } };
  J.$$('.grp', side).forEach(g => { const n = nav.find(x => x.id === g.dataset.id); g.addEventListener('mouseenter', () => { if (!body.classList.contains('side-collapsed') || narrow()) return; closeFly(); const r = g.getBoundingClientRect(); fly = document.createElement('div'); fly.className = 'fly'; fly.style.left = (r.right + 6) + 'px'; fly.style.top = r.top + 'px';
    fly.innerHTML = `<div class="ttl">${J.esc(n.label)}</div>` + J.$$('.sv', g).map(a => `<a class="sv ${a.classList.contains('on') ? 'on' : ''}" href="${a.getAttribute('href')}">${a.textContent}</a>`).join(''); fly.addEventListener('mouseleave', closeFly); document.body.appendChild(fly); });
    g.addEventListener('mouseleave', e => { if (!fly || !fly.contains(e.relatedTarget)) setTimeout(() => { if (fly && !fly.matches(':hover') && !g.matches(':hover')) closeFly(); }, 120); }); });
  /* portefeuilles : un sous-menu par portefeuille */
  if (J.$('[data-sub="portefeuilles"]')) J.api('portfolios').then(r => { const sub = J.$('[data-sub="portefeuilles"]'), cur = new URLSearchParams(location.search).get('id'); r.portfolios.forEach(p => sub.insertAdjacentHTML('beforeend', `<a class="sv ${file === 'portefeuilles.html' && (cur == p.id || (!cur && false)) ? 'on' : ''}" href="portefeuilles.html?id=${p.id}">${J.esc(p.name)}${p.is_default ? ' ★' : ''}</a>`)); }).catch(() => { });
  /* en-tête : fil d'Ariane, recherche, thème */
  const active = nav.find(n => n.file && n.file.includes(file)), child = active && active.children ? active.children.find(isOn) : null;
  J.$('#crumbs').innerHTML = active ? `<span>${J.esc(active.label)}</span>` + (file === 'titre.html' ? '<i>›</i><b>Fiche</b>' : child ? `<i>›</i><b>${J.esc(child.label)}</b>` : '') : '';
  J.$('#quick-form').onsubmit = e => { e.preventDefault(); const v = J.$('#quick').value.trim(); if (v) location.href = 'index.html?q=' + encodeURIComponent(v); };
  const themeIcon = () => { J.$('#theme-btn').innerHTML = J.icon(document.documentElement.dataset.theme === 'dark' ? 'sun' : 'moon', ''); };
  J.$('#theme-btn').onclick = async () => { const t = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark'; J.applyTheme(t); themeIcon(); try { J.user.prefs = (await J.post('auth/prefs', { theme: t })).prefs; } catch (e) { } };
  themeIcon(); J.$('#user-btn').onclick = J.accountDialog; sync();
  window.addEventListener('hashchange', () => { J.$$('.sv', side).forEach(a => { const h = a.getAttribute('href'); if (h.includes('#') && h.split('#')[0] === file) a.classList.toggle('on', ('#' + h.split('#')[1]) === location.hash || (!location.hash && h.endsWith('#data'))); }); });
};
J.applyTheme = t => { const dark = t === 'dark' || (t === 'auto' && matchMedia('(prefers-color-scheme: dark)').matches); document.documentElement.dataset.theme = dark ? 'dark' : 'light'; localStorage.setItem('jigo_theme', t); };
J.accountDialog = function () {
  const prefs = J.user.prefs || {};
  J.dialog({
    title: 'Mon compte', body: `<div class="row between"><span>Affichage</span><span class="seg" id="mode"><button type="button" data-v="simple">Simple</button><button type="button" data-v="advanced">Avancé</button></span></div>
    <div class="row between"><span>Thème</span><span class="seg" id="theme"><button type="button" data-v="auto">Auto</button><button type="button" data-v="light">Clair</button><button type="button" data-v="dark">Sombre</button></span></div>
    <hr style="border:0;border-top:1px solid var(--line);width:100%"><h3>Mes coordonnées</h3>${J.field('Pseudo', `<input id="account-name" autocomplete="username" value="${J.esc(J.user.username)}" maxlength="30">`)}${J.field('E-mail', `<input id="account-email" type="email" autocomplete="email" value="${J.esc(J.user.email || '')}" maxlength="190">`)}<p class="account-note">Une nouvelle adresse doit être confirmée par e-mail. L’adresse actuelle reste utilisable jusque-là.</p><h3>Confirmer mes modifications</h3>${J.field('Mot de passe actuel', '<input type="password" id="pw0" autocomplete="current-password">')}${J.field('Nouveau (10 caractères minimum)', '<input type="password" id="pw1" autocomplete="new-password">')}`,
    actions: [{ label: 'Se déconnecter', cls: 'danger', run: async () => { await J.post('auth/logout'); location.href = 'login.html'; return true; }, },
    { label: 'Enregistrer mes coordonnées', run: async d => { const r = await J.post('auth/account', { username: J.$('#account-name', d).value, email: J.$('#account-email', d).value, current: J.$('#pw0', d).value }); J.toast(r.message); J.user = (await J.api('auth/me')).user; const label=J.$('#user-btn b'); if(label)label.textContent=J.user.username; } },
    { label: 'Changer le mot de passe', run: async d => { await J.post('auth/password', { current: J.$('#pw0', d).value, new: J.$('#pw1', d).value }); J.toast('Mot de passe modifié'); } }],
    onopen: d => {
      for (const [id, key, cur] of [['mode', 'mode', prefs.mode || 'simple'], ['theme', 'theme', prefs.theme || localStorage.getItem('jigo_theme') || 'auto']]) {
        const seg = J.$('#' + id, d); J.$$('button', seg).forEach(b => { b.classList.toggle('on', b.dataset.v === cur); b.onclick = async () => { J.$$('button', seg).forEach(x => x.classList.toggle('on', x === b)); J.user.prefs = (await J.post('auth/prefs', { [key]: b.dataset.v })).prefs; if (key === 'theme') J.applyTheme(b.dataset.v); else { document.body.classList.toggle('advanced', b.dataset.v === 'advanced'); window.dispatchEvent(new Event('jigo-mode')); } }; });
      }
    },
  });
};
window.J = J;

if (!document.querySelector('script[src*="passwords.js"]')) { const p=document.createElement('script'); p.src='assets/passwords.js'+new URL(document.currentScript.src).search; document.head.appendChild(p); }
