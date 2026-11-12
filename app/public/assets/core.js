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

