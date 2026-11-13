/* Jigobourso — noyau JS commun : sélecteurs, échappement, appels API, formats français, stockage local, construction DOM.
   Chargé avant app.js sur toutes les pages ; tout le reste du code passe par `J`, jamais par une copie locale. */
'use strict';
const J = window.J = {};

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
J.num = (v, d = 2, dmax = d) => (v === null || v === undefined || isNaN(v)) ? '–' : nf(d, { maximumFractionDigits: dmax }).format(v);
J.pct = (v, d = 2, sign = true) => (v === null || v === undefined || isNaN(v)) ? '–' : nf(d, { signDisplay: sign ? 'exceptZero' : 'auto' }).format(v) + ' %';
J.eur = (v, d = 2) => (v === null || v === undefined || isNaN(v)) ? '–' : new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR', minimumFractionDigits: d, maximumFractionDigits: d }).format(v);
J.money = (v, cur, d = 2) => { if (v === null || v === undefined || isNaN(v)) return '–'; try { return new Intl.NumberFormat('fr-FR', { style: 'currency', currency: ((cur === 'GBp' || cur === 'GBX') ? 'GBP' : cur) || 'EUR', currencyDisplay: 'narrowSymbol', minimumFractionDigits: d, maximumFractionDigits: d }).format((cur === 'GBp' || cur === 'GBX') ? v / 100 : v); } catch (e) { return J.num(v, d) + ' ' + (cur || ''); } };
J.cls = v => (v > 0 ? 'up' : v < 0 ? 'down' : '');
J.date = s => { if (!s) return '–'; const d = new Date(s.replace(' ', 'T') + (s.length > 10 ? 'Z' : '')); return isNaN(d) ? s : d.toLocaleDateString('fr-FR', { day: '2-digit', month: 'short', year: 'numeric' }); };
J.dateTime = s => { if (!s) return '–'; const d = new Date(s.replace(' ', 'T') + 'Z'); return isNaN(d) ? s : d.toLocaleString('fr-FR', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }); };
J.ago = s => { if (!s) return '–'; const m = (Date.now() - new Date(s.replace(' ', 'T') + 'Z')) / 60000; return m < 1 ? 'à l’instant' : m < 60 ? Math.round(m) + ' min' : m < 1440 ? Math.round(m / 60) + ' h' : Math.round(m / 1440) + ' j'; };
J.priceLabel = r => r.price_stale ? 'Cours ancien' : ({ intraday: 'Cours différé', daily: 'Clôture', quote: 'Dernier cours' }[r.price_source || r.source] || 'Cours');


/* ───── formats : compléments (valeurs nulles, signes typographiques, dates courtes) ───── */
J.isNum = v => typeof v === 'number' && isFinite(v);
J.int = v => J.num(v, 0);
const sgn = (v, plus = true, eps = 0.004) => v > eps ? (plus ? '+' : '') : v < -eps ? '−' : '';   // vrai signe moins (U+2212)
J.sign = sgn;
J.numS = (v, d = 2, plus = true) => J.isNum(v) ? sgn(v, plus) + J.num(Math.abs(v), d) : '–';       // « +1,25 » / « −0,40 »
J.pctS = (v, d = 2, plus = true) => J.isNum(v) ? sgn(v, plus) + J.num(Math.abs(v), d) + ' %' : '–';
J.eurS = (v, d = 2, plus = true) => J.isNum(v) ? sgn(v, plus) + J.eur(Math.abs(v), d) : '–';
J.dayShort = d => d ? new Date(d + 'T00:00:00').toLocaleDateString('fr-FR', { day: 'numeric', month: 'short' }) : '–';
J.dayFull = d => d ? new Date(d + 'T00:00:00').toLocaleDateString('fr-FR', { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' }) : '–';

/* ───── stockage local : JSON, clé préfixée, jamais d'exception, abonnement aux changements ───── */
J.store = (() => {
  const mem = new Map(), subs = new Map();
  const raw = { get: k => { try { return localStorage.getItem(k); } catch (e) { return mem.has(k) ? mem.get(k) : null; } },
    set: (k, v) => { try { localStorage.setItem(k, v); } catch (e) { mem.set(k, v); } },
    del: k => { try { localStorage.removeItem(k); } catch (e) { mem.delete(k); } } };
  const fire = (k, v) => (subs.get(k) || []).forEach(fn => { try { fn(v); } catch (e) { /* un abonné ne casse pas les autres */ } });
  const api = {
    get(key, fallback = null) { const t = raw.get(key); if (t === null) return fallback; try { return JSON.parse(t); } catch (e) { return fallback; } },
    set(key, value) { raw.set(key, JSON.stringify(value)); fire(key, value); return value; },
    remove(key) { raw.del(key); fire(key, null); },
    has: key => raw.get(key) !== null,
    text: { get: (k, f = null) => { const t = raw.get(k); return t === null ? f : t; }, set: (k, v) => raw.set(k, String(v)) },
    subscribe(key, fn) { if (!subs.has(key)) subs.set(key, []); subs.get(key).push(fn); return () => subs.set(key, subs.get(key).filter(f => f !== fn)); },
    fn: prefix => (k, v) => v === undefined ? api.get(prefix + k) : (api.set(prefix + k, v), undefined),   // store(k) lit, store(k, v) écrit
    scope: prefix => ({ get: (k, f) => api.get(prefix + k, f), set: (k, v) => api.set(prefix + k, v), remove: k => api.remove(prefix + k), subscribe: (k, fn) => api.subscribe(prefix + k, fn) }),
  };
  window.addEventListener('storage', e => { if (e.key && subs.has(e.key)) fire(e.key, e.newValue === null ? null : (() => { try { return JSON.parse(e.newValue); } catch (x) { return null; } })()); });
  return api;
})();

/* ───── DOM : J.dom.h('tag.classe#id', { attrs, on: { click } }, ...enfants) ───── */
J.dom = {
  h(spec, props, ...kids) {
    if (props && (typeof props !== 'object' || props instanceof Node || Array.isArray(props))) { kids.unshift(props); props = null; }
    const m = /^([a-z0-9-]*)((?:[.#][\w-]+)*)$/i.exec(spec) || [], el = document.createElement(m[1] || 'div');
    for (const t of (m[2] || '').match(/[.#][\w-]+/g) || []) t[0] === '#' ? (el.id = t.slice(1)) : el.classList.add(t.slice(1));
    for (const [k, v] of Object.entries(props || {})) {
      if (v === null || v === undefined || v === false) continue;
      if (k === 'on') for (const [ev, fn] of Object.entries(v)) el.addEventListener(ev, fn);
      else if (k === 'class') el.className += (el.className ? ' ' : '') + v;
      else if (k === 'text') el.textContent = v;
      else if (k === 'html') el.innerHTML = v;
      else if (k === 'style' && typeof v === 'object') Object.assign(el.style, v);
      else if (k === 'dataset') Object.assign(el.dataset, v);
      else el.setAttribute(k, v === true ? '' : v);
    }
    for (const c of kids.flat(Infinity)) if (c !== null && c !== undefined && c !== false) el.append(c instanceof Node ? c : document.createTextNode(String(c)));
    return el;
  },
};


/* ───── dates : tout `toLocale…` / `Intl.DateTimeFormat` des pages passe par ici ───── */
J.dayNumeric = d => d ? new Date(d + 'T00:00:00').toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit', year: 'numeric' }) : '–';   // 05/11/2026
J.dateTimeShort = s => { try { return new Date(String(s).replace(' ', 'T') + (/Z|[+-]\d\d:?\d\d$/.test(s) ? '' : 'Z')).toLocaleString('fr-FR', { dateStyle: 'short', timeStyle: 'short' }); } catch (e) { return ''; } };
J.fold = s => String(s ?? '').toLocaleLowerCase('fr');                    // comparaison de recherche insensible à la casse

/* ───── graphiques SVG : briques communes à charts.js et intraday.js ───── */
J.svg = (name, attrs = {}, text) => { const e = document.createElementNS('http://www.w3.org/2000/svg', name); for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v); if (text !== undefined) e.textContent = text; return e; };
J.priceDec = p => (p < 1 ? 4 : p < 10 ? 3 : 2);                              // décimales d'un cours selon son ordre de grandeur
J.ticks = (lo, hi, n = 5) => {                                                // graduations « rondes » entre lo et hi
  const span = hi - lo || 1, raw = span / n, mag = Math.pow(10, Math.floor(Math.log10(raw)));
  const step = [1, 2, 2.5, 5, 10].map(m => m * mag).find(s => s >= raw) || mag * 10, out = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) out.push(+v.toFixed(8));
  return out;
};
J.chartBox = (host, svg) => { const tip = J.dom.h('div.chart-tip'); tip.hidden = true; host.append(J.dom.h('div.chart-wrap', svg, tip)); return tip; };   // enveloppe + infobulle
J.tz = tz => ({                                                           // formats d'un fuseau (graphiques intraday)
  time: ms => new Intl.DateTimeFormat('fr-FR', { timeZone: tz, hour: '2-digit', minute: '2-digit', hour12: false }).format(ms),
  day: ms => new Intl.DateTimeFormat('fr-FR', { timeZone: tz, weekday: 'short', day: 'numeric', month: 'short' }).format(ms),
  dayLong: ms => new Intl.DateTimeFormat('fr-FR', { timeZone: tz, weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' }).format(ms),
  minute: ms => +new Intl.DateTimeFormat('en-GB', { timeZone: tz, minute: 'numeric' }).format(ms),
  zone: ms => (new Intl.DateTimeFormat('fr-FR', { timeZone: tz, timeZoneName: 'short' }).formatToParts(ms).find(p => p.type === 'timeZoneName') || {}).value || tz,
});

/* ───── composants HTML partagés : badge, segment (choix exclusif), onglets ───── */
// kind : '' | ok | warn | danger | info | accent ; opts : { sm, outline, cls, title }
J.badge = (text, kind = '', opts = {}) => `<span class="badge${kind ? ' ' + kind : ''}${opts.sm ? ' sm' : ''}${opts.outline ? ' outline' : ''}${opts.cls ? ' ' + opts.cls : ''}"${opts.title ? ` title="${J.esc(opts.title)}"` : ''}>${J.esc(text)}</span>`;
// items : [[valeur, libellé]] ; attr : nom de l'attribut portant la valeur (défaut data-v) ; opts : { id, radio, label }
J.seg = (items, cur, attr = 'data-v', opts = {}) => `<div class="seg"${opts.id ? ` id="${J.esc(opts.id)}"` : ''}${opts.radio ? ' role="radiogroup"' : ''}${opts.label ? ` aria-label="${J.esc(opts.label)}"` : ''}>${items.map(([v, l]) =>
  `<button type="button"${opts.radio ? ` role="radio" aria-checked="${v === cur}"` : ''} class="${v === cur ? 'on' : ''}" ${attr}="${J.esc(v)}">${l}</button>`).join('')}</div>`;
J.tabs = (items, cur, attr = 'data-tab', opts = {}) => `<div class="tabs${opts.big ? ' big' : ''}" role="tablist"${opts.label ? ` aria-label="${J.esc(opts.label)}"` : ''}>${items.map(([v, l, n]) =>
  `<button type="button" role="tab" aria-selected="${v === cur}" class="${v === cur ? 'on' : ''}" ${attr}="${J.esc(v)}">${l}${n === undefined ? '' : ` <span class="count">${J.esc(n)}</span>`}</button>`).join('')}</div>`;

/* ───── tableaux : en-têtes, tri, ligne vide, rendu complet ─────
   Colonne : 'Libellé' | ['Libellé', 'num'] | { label, num, cls, title, sort: 'clé', width, scope }. Tri courant : { key, dir: 'asc'|'desc' }.
   Une colonne triable porte un <button data-sort="clé"> et aria-sort ; le clic se branche avec J.table.onSort(racine, fn). */
J.table = (() => {
  const norm = c => typeof c === 'string' ? { label: c } : Array.isArray(c) ? { label: c[0], num: c[1] === 'num', ...(typeof c[1] === 'object' ? c[1] : {}) } : c;
  const arrow = (key, sort) => sort && sort.key === key ? (sort.dir === 'asc' ? ' ▲' : ' ▼') : '';
  const th = (c, sort) => { c = norm(c);
    const cls = [c.num ? 'num' : '', c.cls || ''].filter(Boolean).join(' ');
    const attrs = `${cls ? ` class="${cls}"` : ''}${c.scope ? ` scope="${c.scope}"` : ''}${c.title ? ` title="${J.esc(c.title)}"` : ''}${c.width ? ` data-style="width:${c.width}px;min-width:${c.width}px"` : ''}`;
    if (!c.sort) return `<th${attrs}>${c.label}</th>`;
    const on = sort && sort.key === c.sort;
    return `<th${attrs} aria-sort="${on ? (sort.dir === 'asc' ? 'ascending' : 'descending') : 'none'}"><button type="button" data-sort="${J.esc(c.sort)}">${c.label}${arrow(c.sort, sort)}</button></th>`; };
  const headRow = (cols, sort) => cols.map(c => th(c, sort)).join('');
  const T = {
    th, headRow,
    head: (cols, sort) => `<thead><tr>${headRow(cols, sort)}</tr></thead>`,
    empty: (cols, msg, cls = 'muted') => `<tr><td colspan="${cols.length}" class="${cls}">${msg}</td></tr>`,
    // rows : tableau de lignes ; chaque ligne = tableau de cellules (HTML) ou { cells, cls, attrs } ; la classe num vient de la colonne
    body(cols, rows, opts = {}) {
      if (!rows.length) return `<tbody>${opts.empty === undefined ? '' : T.empty(cols, opts.empty)}</tbody>`;
      const cn = cols.map(norm);
      return `<tbody>${rows.map(r => { const o = Array.isArray(r) ? { cells: r } : r;
        return `<tr${o.cls ? ` class="${o.cls}"` : ''}${o.attrs ? ' ' + o.attrs : ''}>${o.cells.map((c, i) => `<td${cn[i] && cn[i].num ? ' class="num"' : ''}>${c}</td>`).join('')}</tr>`; }).join('')}</tbody>`;
    },
    // tableau complet dans son conteneur défilant : { cols, rows, cls, sort, empty, wrap }
    render: ({ cols, rows, cls = '', sort = null, empty, wrap = 'table-wrap' }) =>
      `<div class="${wrap}"><table${cls ? ` class="${cls}"` : ''}>${T.head(cols, sort)}${T.body(cols, rows, { empty })}</table></div>`,
    // comparaison : valeurs absentes toujours en dernier, nombres comme des nombres, textes en français
    cmp(a, b, dir = 'asc') {
      const na = a === null || a === undefined || (typeof a === 'number' && isNaN(a)), nb2 = b === null || b === undefined || (typeof b === 'number' && isNaN(b));
      if (na || nb2) return na && nb2 ? 0 : na ? 1 : -1;
      const c = typeof a === 'string' || typeof b === 'string' ? String(a).localeCompare(String(b), 'fr') : a - b;
      return dir === 'asc' ? c : -c;
    },
    // tri stable sur un ou plusieurs critères [{ key, dir }] ; val(ligne, clé) ; tie(a, b) départage les égalités
    sortRows(rows, sorts, val, tie) {
      return rows.map((r, i) => [r, i]).sort((A, B) => { for (const { key, dir } of sorts) { const c = T.cmp(val(A[0], key), val(B[0], key), dir); if (c) return c; }
        return (tie ? tie(A[0], B[0]) : 0) || A[1] - B[1]; }).map(a => a[0]);
    },
    // prochain tri au clic sur une colonne : même clé → inverse la direction ; sinon direction par défaut de la colonne
    nextSort: (cur, key, defDir = 'asc') => cur && cur.key === key ? { key, dir: cur.dir === 'asc' ? 'desc' : 'asc' } : { key, dir: defDir },
    onSort(root, fn) { root.addEventListener('click', e => { const b = e.target.closest('[data-sort]'); if (b && root.contains(b)) fn(b.dataset.sort, b); }); },
  };
  return T;
})();

// Styles de données (couleurs, largeurs, positions calculées) : les gabarits écrivent data-style="…", appliqué ici par l'API CSSOM
// (autorisée par la CSP, contrairement à l'attribut style). Le MutationObserver s'exécute avant le prochain rendu.
(() => {
  'use strict';
  const probe = document.createElement ? document.createElement('span') : null;
  // fusion sans écraser : une valeur déjà posée par le code (el.style.x = …, exécuté juste après un innerHTML) l'emporte sur le gabarit
  const apply = (el, force) => {
    const v = el.getAttribute('data-style'); if (v === null || !el.style || !probe) return;
    probe.style.cssText = v;
    for (let k = 0; k < probe.style.length; k++) { const prop = probe.style[k]; if (force || !el.style.getPropertyValue(prop)) el.style.setProperty(prop, probe.style.getPropertyValue(prop), probe.style.getPropertyPriority(prop)); }
  };
  const scan = root => { if (root.nodeType !== 1) return; if (root.hasAttribute('data-style')) apply(root, false); root.querySelectorAll('[data-style]').forEach(e => apply(e)); };
  J.applyStyles = scan;
  if (typeof MutationObserver === 'undefined' || !document.documentElement) return;      // tests Node sans DOM
  new MutationObserver(list => { for (const m of list) { if (m.type === 'attributes') apply(m.target, true); else m.addedNodes.forEach(scan); } })
    .observe(document.documentElement, { childList: true, subtree: true, attributes: true, attributeFilter: ['data-style'] });
  scan(document.documentElement);
})();
