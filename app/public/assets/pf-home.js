/* Portefeuille V4 : un seul espace, deux zones (Vue d'ensemble, Transactions), détail en panneau avec le Plan de suivi.
   Calculs : pf-math.js. Tracé : J.financialChart (financial-chart.js, moteur partagé). Plan de suivi : plan-suivi.js (calculs : engine/analytics/position_plan.py). Couleurs : variables du thème. */
(function (root) {
  'use strict';
  const PFM = root.PFM, isNum = PFM.isNum;
  const store = (k, v) => { try { if (v === undefined) return JSON.parse(localStorage.getItem('jigo_pfx_' + k)); localStorage.setItem('jigo_pfx_' + k, JSON.stringify(v)); } catch (e) { return null; } };
  const PER = PFM.PERIODS, PERKEYS = PER.map(p => p[0]);
  const perName = k => (PER.find(x => x[0] === k) || [0, ''])[1];
  const INTRA = { '1d': 1, '2d': 2, '5d': 5, '1w': 7 };               // séances d'historique 15 min recherchées ; 2S et au-delà : quotidien
  const mkBox = (id, mode) => ({ id, mode, per: 'all', unit: 'pct', view: null, hidden: new Set(), focus: null, token: 0 });
  const S = { zone: 'overview', sort: store('sort') || 'value', dir: store('dir') || -1, closed: false, sel: null, tr: null, trErr: null,
    main: Object.assign(mkBox('px-main', store('mode') === 'market' ? 'market' : 'perso'), { per: PERKEYS.includes(store('per')) ? store('per') : 'all', unit: store('unit') === 'eur' ? 'eur' : 'pct' }),
    det: Object.assign(mkBox('px-det', 'perso'), { per: 'all' }) };
  let C = null;
  const BARS = {};
  const esc = s => J.esc(String(s == null ? '' : s));
  const eur = (v, d = 2) => isNum(v) ? J.eur(v, d) : '–';
  const sg = v => isNum(v) ? (v > 0.004 ? '+' : v < -0.004 ? '−' : '') + J.eur(Math.abs(v), 2) : '–';
  const pc = (v, d = 2) => isNum(v) ? (v > 0.004 ? '+' : v < -0.004 ? '−' : '') + J.num(Math.abs(v), Math.abs(v) >= 1000 ? 0 : d) + ' %' : '–';
  const pt = v => isNum(v) ? (v > 0.004 ? '+' : v < -0.004 ? '−' : '') + J.num(Math.abs(v), 2) + ' pt' : '–';
  const cl = v => isNum(v) ? (v > 0.004 ? 'up' : v < -0.004 ? 'down' : '') : '';
  const cssv = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim() || '#2563eb';
  const pal = () => ['#0891b2', '#d97706', '#7c3aed', '#db2777', '#65a30d', '#dc2626', '#059669', '#ca8a04', '#4f46e5', '#0d9488', '#9333ea', '#ea580c'];
  const pkey = p => p.listing_id ? String(p.listing_id) : 'S' + String(p.symbol).toUpperCase();
  const all = () => [...C.D.positions, ...C.D.closed];
  const open = () => C.D.positions.filter(p => p.qty > 0);
  const lineOf = p => C.H.lines.find(l => l.key === pkey(p));
  const mk = () => C.H.market && C.H.market.dates ? C.H.market : { dates: [], lines: [], intraday: { dates: [], lines: [] } };
  const mDates = () => mk().dates.map(d => d.slice(0, 10));
  const lastIdx = (a, d) => { let r = -1; for (let i = 0; i < a.length; i++) { if (a[i] <= d) r = i; else break; } return r; };
  const colorOf = key => { const i = open().findIndex(p => pkey(p) === key); return pal()[(i < 0 ? 0 : i) % pal().length]; };
  const I = { chev: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 5l7 7-7 7" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>', ext: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 17L17 7M9 7h8v8" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>', bell: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 17h12l-1.5-2V10a4.5 4.5 0 00-9 0v5zM10 20h4" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>' };

  /* ───────── plan de suivi (état lu dans tracking/state ; calculé par le moteur, lecture seule) ───────── */
  function loadTracking() { return S.trP = loadTracking1(); }
  async function loadTracking1() { try { S.tr = await J.api('tracking/state', { params: { portfolio: C.current } }); S.trErr = null; } catch (e) { S.tr = null; S.trErr = e.message || 'indisponible'; } }
  const planOf = p => S.tr && p.listing_id ? (S.tr.positions[String(p.listing_id)] || null) : null;
  function watchOf(p) {
    const base = { rank: 5, strat: null, origin: null };
    if (!p.listing_id) return Object.assign(base, { k: 'none', t: 'Sans cotation' });
    if (!S.tr) return Object.assign(base, { k: 'na', t: S.trErr ? 'Indisponible' : 'Chargement…' });
    const pl = planOf(p); if (!pl) return Object.assign(base, { k: 'na', t: 'Indisponible' });
    const c = root.PlanSuivi.chip(pl), o = (pl.origins || []).find(x => x.label);
    return { k: c.k, t: c.t, rank: c.rank, strat: pl.watch ? pl.watch.label : null, origin: o ? o.label : null };
  }
  function planSummary() {
    if (!S.tr) return `<div class="px-sum"><span class="px-ab">${I.bell}<b>Synthèse du suivi</b></span><span class="muted">${S.trErr ? 'Indisponible : ' + esc(S.trErr) : 'Chargement…'}</span></div>`;
    const ws = open().filter(p => p.listing_id).map(watchOf), n = k => ws.filter(w => w.k === k).length;
    const parts = [[n('ko'), 'sortie à envisager', 'ko'], [n('rv'), 'à réévaluer', 'rv'], [n('na'), 'à surveiller', 'na'], [n('ok'), 'à conserver', 'ok']].filter(x => x[0]);
    return `<div class="px-sum"><span class="px-ab">${I.bell}<b>Synthèse du suivi</b></span>${parts.length ? parts.map(([c, l, k]) => `<span><i class="n ${k}">${c}</i>${l}</span>`).join('') : '<span class="muted">Aucune position suivie</span>'}<span class="muted">Un repère, jamais un ordre : rien n’est vendu automatiquement.</span></div>`;
  }

  /* ───────── données du graphique : une seule fonction, deux modes, toutes les périodes ───────── */
  async function ensureBars(ids) { for (const id of ids) if (!(id in BARS)) { try { BARS[id] = (await J.api('bars15', { params: { id } })).bars || []; } catch (e) { BARS[id] = null; } } }
  function rateOf(l) { for (let i = l.prices.length - 1; i >= 0; i--) if (isNum(l.prices[i]) && isNum(l.prices_eur[i]) && l.prices[i] > 0) return l.prices_eur[i] / l.prices[i]; return null; }
  const rebase = vals => { const b = vals.find(isNum); return vals.map(v => isNum(v) && b ? 100 * (v / b - 1) : null); };
  async function build(st, o) {
    const perso = st.mode === 'perso', per = st.per, pct = st.unit === 'pct', H = C.H;
    const out = { times: [], series: [], intraday: false, markersFrom: null, meta: { req: perName(per), res: 'quotidienne', source: '', notes: [], first: null, last: null }, empty: null, ref: '' };
    const add = (key, label, values, width, color) => out.series.push({ id: key, label, color: color || colorOf(key), width: width || 2, values });
    const nameOf = k => { const p = all().find(x => pkey(x) === k); return p ? p.symbol : k; };
    if (perso) {
      const ss = H.session;
      if (per === '1d' && ss && ss.dates && ss.dates.length > 1) {
        out.intraday = true; out.times = ss.dates; out.meta.res = '15 minutes'; out.meta.source = 'barres de 15 minutes de la séance du ' + J.date(ss.day) + ' (positions actuelles)';
        out.ref = 'Variation depuis la première barre de la séance.';
        if (o.pf) add('pf', 'Portefeuille', pct ? ss.pct : ss.gain, 4, cssv('--text'));
        o.keys.forEach(k => { const l = ss.lines.find(x => x.key === k); if (l && !l.reason) add(k, nameOf(k), pct ? l.pct : l.gain); else out.meta.notes.push(nameOf(k) + ' : ' + ((l && l.reason) || 'aucune barre de 15 minutes')); });
        if (o.pf && !out.series[0].values.some(isNum)) out.meta.notes.push('Résultat global de séance indisponible : ' + ((ss.notes || []).find(n => /ransaction/.test(n)) || 'cours manquant sur une position') + ' Les titres comparables restent affichés.');
        return out;
      }
      const w = PFM.resolveWindow(H, per === 'max' ? 'all' : per);
      if (INTRA[per]) out.meta.notes.push(per === '1d' ? 'Aucune barre de 15 minutes enregistrée : résolution quotidienne (deux derniers jours).' : 'L’historique personnel n’est pas stocké barre par barre au-delà de la dernière séance : résolution quotidienne.');
      if (per === 'max' || per === 'all') out.meta.notes.push('Votre historique personnel commence à votre première opération (' + J.date(H.dates[0]) + ') : « Max » et « Depuis le début » coïncident ici.');
      if (w.clipped) out.meta.notes.push('Historique plus court que la période demandée : il commence le ' + J.date(w.startDate) + '.');
      const metric = pct ? 'perf' : 'result', ps = o.pf ? PFM.series(H, w, 'pf', metric) : null;
      const base = ps || PFM.series(H, w, o.keys[0] || (H.lines[0] || {}).key, metric);
      out.times = base.x; out.meta.source = 'valorisation quotidienne du moteur (clôtures, change du jour)';
      out.ref = pct ? 'Portefeuille : performance hors mouvements (achats et ventes neutralisés). Titres : rendement du capital engagé. 0 % = clôture précédant la période.' : 'Résultat cumulé (€) depuis la clôture précédant la période, apports neutralisés.';
      if (ps) { if (ps.note) out.meta.notes.push(ps.note); add('pf', 'Portefeuille', ps.y, 4, cssv('--text')); }
      o.keys.forEach(k => { const q = PFM.series(H, w, k, metric); add(k, nameOf(k), q.y); if (!q.y.some(isNum)) out.meta.notes.push(nameOf(k) + ' : non détenu sur cette période.'); });
      out.markersFrom = true; return out;
    }
    /* marché : cours réels, indépendants des dates d'achat */
    const M = mk(), dates = mDates();
    const lines = o.keys.map(k => M.lines.find(l => l.key === k)).filter(Boolean);
    if (INTRA[per]) {
      const ids = lines.map(l => +l.key).filter(Boolean);
      let times = [], obs = {};
      if (per === '1d' && M.intraday && M.intraday.dates.length > 1) {
        times = M.intraday.dates; M.intraday.lines.forEach(l => { obs[l.key] = {}; M.intraday.dates.forEach((d, i) => { if (isNum(l.prices[i])) obs[l.key][d] = l.prices[i]; }); });
      } else {
        await ensureBars(ids); const days = [...new Set(ids.flatMap(id => (BARS[id] || []).map(b => b[0].slice(0, 10))))].sort(), keep = new Set(days.slice(-INTRA[per]));
        ids.forEach(id => { obs[String(id)] = {}; (BARS[id] || []).forEach(b => { if (keep.has(b[0].slice(0, 10))) obs[String(id)][b[0]] = b[1]; }); });
        times = [...new Set(Object.values(obs).flatMap(o2 => Object.keys(o2)))].sort();
      }
      if (times.length > 1) {
        out.intraday = true; out.times = times; out.meta.res = '15 minutes'; out.meta.source = 'barres de 15 minutes enregistrées (7 derniers jours au plus)';
        lines.forEach(l => {
          const raw = times.map(t => obs[l.key] && isNum(obs[l.key][t]) ? obs[l.key][t] : null);
          if (!raw.some(isNum)) { out.meta.notes.push(nameOf(l.key) + ' : aucune barre de 15 minutes sur cette période.'); return; }
          let v = raw; if (pct) v = rebase(raw); else { const r = (l.currency === 'EUR') ? 1 : rateOf(l); if (r === null) { out.meta.notes.push(nameOf(l.key) + ' : change indisponible, valeur en euros impossible.'); return; } v = raw.map(x => isNum(x) ? x * r : null); if (l.currency !== 'EUR') out.meta.notes.push(nameOf(l.key) + ' : converti au dernier change connu (' + (l.currency || '') + ').'); }
          add(l.key, nameOf(l.key), v);
        });
        out.ref = pct ? '0 % = premier cours de chaque titre dans la fenêtre. Aucun point intermédiaire n’est inventé : un trou reste un trou.' : 'Cours convertis en euros.';
        out.markersFrom = true; return out;
      }
      out.meta.notes.push(per === '1d' ? 'Aucune barre de 15 minutes pour la dernière séance : résolution quotidienne.' : 'Pas de barres de 15 minutes sur cette période : résolution quotidienne.');
    }
    const n = dates.length; if (!n) { out.empty = 'Aucun cours disponible.'; return out; }
    let i0, i1 = n - 1;
    if (per === 'all') i0 = Math.max(0, lastIdx(dates, H.dates[0])); else if (per === 'max') i0 = 0;
    else { const w = PFM.resolveWindow({ dates }, per); i0 = Math.max(0, w.i0); if (w.clipped) out.meta.notes.push('Les cours disponibles commencent le ' + J.date(dates[0]) + ', après le début demandé.'); }
        out.times = dates.slice(i0, i1 + 1); out.meta.source = 'cours de clôture ajustés des divisions (historique complet, indépendant de vos achats)';
    if (per === 'all') out.meta.notes.push('« Depuis le début » : depuis votre première opération (' + J.date(H.dates[0]) + '). « Max » remonte au plus ancien cours disponible.');
    lines.forEach(l => {
      const raw = (pct ? l.prices : l.prices_eur).slice(i0, i1 + 1);
      if (!raw.some(isNum)) { out.meta.notes.push(nameOf(l.key) + ' : aucun cours sur cette période.'); return; }
      const first = out.times[raw.findIndex(isNum)]; if (first > out.times[0]) out.meta.notes.push(nameOf(l.key) + ' : cours disponibles à partir du ' + J.date(first) + '.');
      add(l.key, nameOf(l.key), pct ? rebase(raw) : raw);
    });
    out.ref = pct ? '0 % = premier cours disponible de chaque titre dans la fenêtre (les titres plus récents partent de leur propre premier cours). Devise de cotation.' : 'Cours réels convertis en euros au change du jour.';
    out.markersFrom = true; return out;
  }
  function markersFor(out, keys, pf) {
    if (!out.markersFrom || !out.times.length) return [];
    const a = String(out.times[0]).slice(0, 10), b = String(out.times[out.times.length - 1]).slice(0, 10), ks = new Set(keys);
    return (C.H.trades || []).filter(t => !t.note && t.date >= a && t.date <= b && (pf ? ks.has(t.key) : ks.has(t.key))).map(t => ({ x: out.intraday ? String(t.trade_at).replace(' ', 'T') : t.date, kind: t.side === 'sell' ? 'sell' : 'buy', key: t.key, symbol: t.symbol, id: t.id, label: (t.side === 'sell' ? 'Vente ' : 'Achat ') + t.symbol, detail: J.num(t.quantity, 4) + ' × ' + J.num(t.unit_price, 4) + ' ' + (t.currency || '') }));
  }

  /* ───────── boîte graphique (utilisée par l'ensemble et par le détail) ───────── */
  function boxHtml(st, o) {
    return `<div class="px-box" id="${st.id}-box"><div class="px-top"><div class="px-tabs" data-box="${st.id}" data-k="mode" role="tablist" aria-label="Type de graphique">${o.modes.map(([k, l]) => `<button type="button" role="tab" data-v="${k}" aria-selected="${st.mode === k}" class="${st.mode === k ? 'on' : ''}">${l}</button>`).join('')}</div><div class="px-seg" data-box="${st.id}" data-k="unit" aria-label="Unité">${[['pct', '%'], ['eur', '€']].map(([k, l]) => `<button type="button" data-v="${k}" class="${st.unit === k ? 'on' : ''}" aria-pressed="${st.unit === k}">${l}</button>`).join('')}</div></div>
      <div class="px-per" data-box="${st.id}" data-k="per" role="group" aria-label="Période">${PER.map(([k, l]) => `<button type="button" data-v="${k}" class="${st.per === k ? 'on' : ''}" aria-pressed="${st.per === k}">${l}</button>`).join('')}</div>
      <p class="px-cur" id="${st.id}-cur"></p><div class="px-plot" id="${st.id}-plot"></div><div class="px-leg" id="${st.id}-leg"></div><details class="px-meta"><summary id="${st.id}-sum">Détails des données</summary><div id="${st.id}-meta"></div></details></div>`;
  }
  function bindBox(st, o) {
    J.$$(`[data-box="${st.id}"]`).forEach(g => g.onclick = e => {
      const b = e.target.closest('button[data-v]'); if (!b || !g.contains(b)) return;
      const k = g.dataset.k, v = b.dataset.v; if (st[k] === v) return; st[k] = v; st.view = null; st.focus = null; if (k === 'per' || k === 'mode') st.hidden.clear();
      if (st === S.main) { store(k === 'per' ? 'per' : k, v); }
      J.$$(`[data-box="${st.id}"][data-k="${k}"] button`).forEach(x => { const on = x.dataset.v === v; x.classList.toggle('on', on); x.setAttribute(k === 'mode' ? 'aria-selected' : 'aria-pressed', String(on)); });
      drawBox(st, o);
    });
    drawBox(st, o);
  }
  async function drawBox(st, o) {
    const plot = J.$('#' + st.id + '-plot'); if (!plot) return; const t = ++st.token;
    const keys = o.keys(), h = innerWidth < 600 ? 250 : 330;
    plot.style.minHeight = h + 'px'; plot.classList.add('loading');
    if (!plot.querySelector('.px-spin')) plot.insertAdjacentHTML('beforeend', '<span class="px-spin spinner" aria-label="Chargement"></span>');
    let out; try { out = await build(st, { keys, pf: o.pf && st.mode === 'perso' }); } catch (e) { if (t !== st.token) return; plot._financial && plot._financial.destroy(); plot.classList.remove('loading'); plot.innerHTML = `<div class="notice err">Impossible de charger les données : ${esc(e.message)}</div>`; return; }
    if (t !== st.token) return;
    plot.classList.remove('loading'); plot.querySelector('.px-spin')?.remove();
    const perso = st.mode === 'perso', pct = st.unit === 'pct', vis = out.series.filter(s => !st.hidden.has(s.id));
    const msg = out.empty || (!out.series.length ? (perso ? 'Aucune position détenue sur cette période : votre historique personnel commence à votre première opération.' : 'Aucun cours disponible pour ces titres sur cette période.') : (!vis.length ? 'Toutes les courbes sont masquées : cliquez sur une pastille pour en réafficher.' : (!vis.some(s => s.values.some(isNum)) ? 'Aucune valeur disponible sur cette période pour les courbes affichées.' : '')));
    J.$('#' + st.id + '-cur').innerHTML = `<b>${perName(st.per)}</b> · ${pct ? '%' : '€'} · ${perso ? 'Mon investissement' : 'Historique des cours'}`;
    if (msg && !vis.some(s => s.values.some(isNum))) { plot._financial && plot._financial.destroy(); plot.innerHTML = `<div class="px-empty" style="min-height:${h}px">${esc(msg)}</div>`; }
    else {
      if (!plot._financial) plot.innerHTML = '';
      const fmt = pct ? (v => pc(v, 2)) : (perso ? (v => sg(v)) : (v => eur(v, 2)));
      J.financialChart(plot, { times: out.times, series: vis }, { height: h, time: out.intraday, format: fmt, zero: perso || pct, markers: markersFor(out, keys, o.pf), selected: st.focus ? new Set([st.focus]) : new Set(), view: st.view,
        onRange: r => { st.view = r; }, onReset: () => { st.view = null; }, onSelect: id => { st.focus = id && id !== st.focus ? id : null; drawBox(st, o); }, onTransaction: id => C.helpers.history(id) });
    }
    const last = s => { for (let i = s.values.length - 1; i >= 0; i--) if (isNum(s.values[i])) return s.values[i]; return null; };
    J.$('#' + st.id + '-leg').innerHTML = out.series.map(s => `<button type="button" class="px-chip ${st.hidden.has(s.id) ? 'off' : ''}" data-sid="${esc(s.id)}" aria-pressed="${!st.hidden.has(s.id)}"><i style="background:${s.color}"></i>${esc(s.label)} <b class="${cl(last(s))}">${isNum(last(s)) ? (pct ? pc(last(s)) : (perso ? sg(last(s)) : eur(last(s)))) : 'n/d'}</b></button>`).join('');
    J.$$('#' + st.id + '-leg [data-sid]').forEach(b => b.onclick = () => { st.hidden.has(b.dataset.sid) ? st.hidden.delete(b.dataset.sid) : st.hidden.add(b.dataset.sid); drawBox(st, o); });
    const real = out.times.length ? [out.times[0], out.times[out.times.length - 1]] : null, fd = x => out.intraday ? J.dateTime(String(x).replace(' ', 'T')) : J.date(String(x).slice(0, 10)), pts = Math.max(0, ...out.series.map(s => s.values.filter(isNum).length));
    const full = out.series.length && out.series.every(s => s.values.filter(isNum).length >= out.times.length * 0.98) && !out.meta.notes.length;
    J.$('#' + st.id + '-sum').textContent = `Données : ${real ? fd(real[0]) + ' → ' + fd(real[1]) : 'aucune'} · ${out.meta.res} · ${pts} point${pts > 1 ? 's' : ''} · ${full ? 'complet' : 'partiel ou avec remarques'}`;
    J.$('#' + st.id + '-meta').innerHTML = `<ul><li>Période demandée : ${esc(perName(st.per))}${st.view ? ' (zoom manuel actif : double-clic pour revenir à la période)' : ''}.</li><li>Résolution : ${esc(out.meta.res)} · Source : ${esc(out.meta.source || '–')}.</li><li>${esc(out.ref)}</li>${out.meta.notes.map(n => `<li>${esc(n)}</li>`).join('')}</ul>`;
  }

  /** Estimation indicative CTO au PFU de 30 % (12,8 % impôt + 17,2 % prélèvements sociaux) : gains réalisés positifs par année + plus-value latente positive, comme si tout était vendu aujourd'hui. */
  const taxOf = (realizedYears, latent, gross, base) => { const b = realizedYears.reduce((n, v) => n + Math.max(0, Number(v) || 0), 0) + Math.max(0, Number(latent) || 0), inc = b * .128, soc = b * .172, net = isNum(gross) ? gross - inc - soc : null; return { inc, soc, net, pct: isNum(net) && base > 0 ? 100 * net / base : null }; };
  /* ───────── synthèse ───────── */
  function stats() {
    const H = C.H, wAll = PFM.resolveWindow(H, 'all'), pf = PFM.portfolio(H, wAll);
    const rows = all().map(p => { const l = lineOf(p), r = l ? PFM.position(H, l, wAll) : { result: null, sinceBuy: null, sinceBuyPct: null }; return { p, l, r, key: pkey(p), contrib: PFM.contribution(r, pf), gain: r.sinceBuy, pctv: r.sinceBuyPct, w: C.D.totals.value > 0 && p.qty > 0 ? 100 * p.value / C.D.totals.value : null, watch: watchOf(p) }; });
    const evo = [['1d', 'Aujourd’hui'], ['1w', '1 semaine'], ['1m', '1 mois'], ['1y', '1 an'], ['all', 'Depuis le début']].map(([k, l]) => { const q = PFM.portfolio(H, PFM.resolveWindow(H, k)); return { l, q }; });
    const ranked = rows.filter(r => isNum(r.contrib) && r.p.qty > 0).sort((a, b) => b.contrib - a.contrib);
    return { pf, rows, evo, best: ranked[0], worst: ranked.length > 1 ? ranked[ranked.length - 1] : null };
  }
  function synth(st) {
    const t = C.D.totals, base = t.invested_total || 0, tg = t.total_gain, tx = taxOf(Object.values(C.D.realized_by_year || {}), t.unrealized, tg, base);
    return `<section class="px-card px-syn"><div class="px-val"><span class="px-l">Valeur du portefeuille</span><strong>${eur(t.value)}</strong><span class="px-pill ${cl(tg)}">${sg(tg)}${base > 0 && isNum(tg) ? ` <small>(${pc(100 * tg / base)})</small>` : ''}</span></div>
      <dl class="px-kv"><div><dt>Capital investi</dt><dd>${eur(t.cost)}</dd></div><div><dt>Gains latents</dt><dd class="${cl(t.unrealized)}">${sg(t.unrealized)}</dd></div><div><dt>Gains réalisés</dt><dd class="${cl(t.realized)}">${sg(t.realized)}</dd></div><div><dt>Résultat total</dt><dd class="${cl(tg)}">${sg(tg)}</dd></div></dl>
      <div class="px-evo" aria-label="Évolution">${st.evo.map(({ l, q }) => `<div><span>${l}</span><b class="${cl(q.pct)}">${pc(q.pct)}</b><small class="${cl(q.result)}">${sg(q.result)}</small></div>`).join('')}</div>
      <div class="px-tax"><span>Après impôts (estimation)</span><b class="${cl(tx.net)}">${sg(tx.net)} <small>(${pc(tx.pct)})</small></b><small>Brut ${sg(tg)} · impôt ${eur(tx.inc, 0)} · prélèvements sociaux ${eur(tx.soc, 0)}. PFU 30 % supposé (compte-titres), comme si les titres ouverts étaient vendus aujourd’hui ; hors PEA, reports de pertes, dividendes et situation personnelle.</small></div><div class="px-hh"><div><span>Contribue le plus</span><b class="${cl(st.best && st.best.contrib)}">${st.best ? esc(st.best.p.symbol) + ' ' + pt(st.best.contrib) : '–'}</b></div><div><span>Pèse le plus</span><b class="${cl(st.worst && st.worst.contrib)}">${st.worst && st.worst.contrib < 0 ? esc(st.worst.p.symbol) + ' ' + pt(st.worst.contrib) : '–'}</b></div></div></section>`;
  }

  /* ───────── tableau compact des positions ───────── */
  const COLS = { title: ['Titre', r => r.p.symbol, 'l'], value: ['Valeur', r => r.p.value], gain: ['Gain/perte', r => r.gain], pct: ['Rendement', r => r.pctv], contrib: ['Contribution', r => r.contrib], w: ['Poids', r => r.w], strat: ['Stratégie', r => (r.watch.strat || r.watch.origin || '').toLowerCase(), 'l'], watch: ['Suivi', r => r.watch.rank, 'l'] };
  function sortRows(rows) {
    const f = COLS[S.sort] || COLS.value, num = !(f[2] === 'l' && S.sort !== 'watch');
    return rows.map((r, i) => [r, i]).sort((A, B) => { const x = f[1](A[0]), y = f[1](B[0]); if (!num) return S.dir * String(x).localeCompare(String(y), 'fr') || A[1] - B[1]; const kx = isNum(x), ky = isNum(y); if (kx !== ky) return kx ? -1 : 1; return (kx ? S.dir * (x - y) : 0) || A[1] - B[1]; }).map(a => a[0]);
  }
  function table(st, limit) {
    let rows = st.rows.filter(r => S.closed || r.p.qty > 0), total = rows.length; rows = sortRows(rows); if (limit) rows = rows.slice(0, limit);
    const th = k => { const c = COLS[k], on = S.sort === k; return `<th class="${c[2] === 'l' ? '' : 'num'} c-${k}" aria-sort="${on ? (S.dir > 0 ? 'ascending' : 'descending') : 'none'}"><button type="button" data-sort="${k}">${c[0]}${on ? (S.dir > 0 ? ' ▲' : ' ▼') : ''}</button></th>`; };
    const body = rows.map(r => { const { p } = r, closed = !(p.qty > 0), w = r.watch;
      return `<tr class="${closed ? 'closed' : ''}" data-open="${esc(r.key)}" tabindex="0"><td class="c-title" data-l="Titre"><b>${esc(p.symbol)}</b><span class="ell">${esc(p.name_catalogue || p.name || '')}${closed ? ' · soldé' : ''}</span>${closed ? '' : J.riskBar(J.riskWorst((C.D.lots || []).filter(lo => p.listing_id ? lo.listing_id === p.listing_id : lo.symbol === p.symbol).map(lo => lo.alert && lo.alert.risk)), { compact: true })}</td><td class="num c-value" data-l="Valeur">${closed ? '–' : eur(p.value)}</td><td class="num c-gain ${cl(r.gain)}" data-l="Gain/perte">${sg(r.gain)}</td><td class="num c-pct ${cl(r.pctv)}" data-l="Rendement">${pc(r.pctv)}</td><td class="num c-contrib ${cl(r.contrib)}" data-l="Contribution">${pt(r.contrib)}</td><td class="num c-w" data-l="Poids">${isNum(r.w) ? J.num(r.w, 1) + ' %' : '–'}</td><td class="c-strat" data-l="Stratégie"><span class="ell">${esc(w.strat || w.origin || 'Non renseignée')}</span></td><td class="c-watch" data-l="Suivi"><button type="button" class="px-w ${w.k}" data-conf="${esc(r.key)}">${I.bell}${esc(w.t)}</button></td>
        <td class="c-act"><button type="button" class="px-btn s" data-buy="${esc(r.key)}">Acheter</button><button type="button" class="px-btn s" data-sell="${esc(r.key)}" ${closed ? 'disabled' : ''}>Vendre</button>${p.listing_id ? `<a class="px-btn s" href="titre.html?id=${p.listing_id}&from=portefeuille" target="_blank" rel="noopener" aria-label="Analyse du titre ${esc(p.symbol)} (nouvel onglet)">Analyse ${I.ext}</a>` : ''}</td></tr>`; }).join('');
    return `<div class="px-tw"><table class="px-t"><thead><tr>${Object.keys(COLS).map(th).join('')}<th class="c-act">Actions</th></tr></thead><tbody>${body || '<tr><td colspan="9" class="px-note">Aucune position.</td></tr>'}</tbody></table></div>${limit && total > limit ? `<p class="px-more"><button type="button" class="px-link" data-zone="positions">Toutes les positions (${total}) ${I.chev}</button></p>` : ''}`;
  }

  /* ───────── zones ───────── */
  function zoneTabs() { return `<nav class="px-zones" role="tablist" aria-label="Zones du portefeuille">${[['overview', 'Vue d’ensemble'], ['transactions', 'Transactions']].map(([k, l]) => `<button type="button" role="tab" data-zone="${k}" aria-selected="${S.zone === k}" class="${S.zone === k ? 'on' : ''}">${l}</button>`).join('')}</nav>`; }
  function head() { return `<header class="px-head"><div><h1>${esc(C.name || 'Portefeuille')}</h1><p class="muted">${open().length} position${open().length > 1 ? 's' : ''} · valeur et résultat en euros</p></div><div class="px-ha"><button type="button" class="px-btn pri" data-add>Ajouter une opération</button></div></header>${zoneTabs()}`; }
  /* ───────── sections repliables (seul l'affichage est replié : le suivi continue d'être calculé) ───────── */
  function foldHead(key, title, count) {
    const folded = !!store('fold_' + key);
    return `<button type="button" class="px-fold" data-fold="${key}" aria-expanded="${!folded}" aria-controls="px-fb-${key}"><span class="chv">${I.chev}</span><h2>${title}${count ? ` <span>(${count})</span>` : ''}</h2><span class="hint">${folded ? 'Masqué · afficher' : 'Masquer'}</span></button>`;
  }
  /** Suivi des positions : une ligne par position ouverte (même jauge, mêmes conseils que le détail), classées par urgence de décision. */
  function suiviSection() {
    const fs = !!store('fold_suivi'), ps = open().filter(p => p.listing_id), noq = open().length - ps.length;
    let sum = '', body;
    if (!S.tr || !root.PlanSuivi) body = `<p class="px-note">${S.trErr ? esc('Suivi indisponible : ' + S.trErr) : 'Chargement du suivi…'}</p>`;
    else {
      const items = ps.map(p => ({ p, pl: planOf(p) })).filter(x => x.pl);
      const rank = x => root.PlanSuivi.STATE[root.PlanSuivi.stateOf(x.pl)].rank;
      items.sort((a, b) => rank(a) - rank(b) || (b.p.value || 0) - (a.p.value || 0));
      const cnt = k => items.filter(x => root.PlanSuivi.stateOf(x.pl) === k).length;
      sum = [['exit', 'sortie à envisager'], ['reevaluate', 'à réévaluer'], ['watch', 'à surveiller'], ['keep', 'à conserver']].filter(([k]) => cnt(k)).map(([k, l]) => `<span><i class="${k}">${cnt(k)}</i>${l}</span>`).join('');
      body = `<p class="psr-note">Un repère de surveillance, jamais un ordre de vente : rien n’est vendu automatiquement. Les couleurs de la jauge sont des zones de prix et de protection, pas une garantie de faible risque. Clique le nom d’un titre pour son détail, « Configurer » pour ses règles.</p>
        <div class="psr-list"><div class="psr-cols" aria-hidden="true"><span>Titre</span><span>Perf.</span><span>Suivi et protections</span><span>Conseil</span><span></span></div>${items.length ? items.map(x => root.PlanSuivi.row(x.pl, { key: pkey(x.p) })).join('') : '<p class="px-note">Aucune position suivie.</p>'}</div>${noq ? `<p class="px-note">${noq} position${noq > 1 ? 's' : ''} sans cotation suivie : pas de suivi possible.</p>` : ''}`;
    }
    return `<section class="px-card${fs ? ' folded' : ''}" id="px-sec-suivi"><div class="px-ph">${foldHead('suivi', 'Suivi des positions', ps.length || '')}<div class="psr-sum" aria-label="Synthèse du suivi">${sum}</div></div><div class="px-fold-body" id="px-fb-suivi" ${fs ? 'hidden' : ''}>${body}</div></section>`;
  }
  async function reloadTracking() {
    await loadTracking(); refreshPage();
    if (S.sel && J.$('#px-plan-body')) { const x = stats().rows.find(r => r.key === S.sel); if (x) renderPlan(x); }
  }
  function configureFor(lid) {
    const p = open().find(x => String(x.listing_id) === String(lid)), pl = p && planOf(p);
    if (!pl || !root.PlanSuivi) return;
    root.PlanSuivi.configure({ plan: pl, strategies: S.tr.strategies, portfolio: C.current, listing: p.listing_id, reload: reloadTracking });
  }

  function viewOverview(st) {
    const nc = st.rows.filter(r => !(r.p.qty > 0)).length;
    const fp = !!store('fold_positions');
    return `${synth(st)}${planSummary()}<section class="px-card"><h2>Évolution</h2>${boxHtml(S.main, MAIN)}</section><section class="px-card${fp ? ' folded' : ''}" id="px-sec-positions"><div class="px-ph">${foldHead('positions', 'Positions', '')}${nc ? `<label class="px-chk" id="px-closed-wrap" ${fp ? 'hidden' : ''}><input type="checkbox" id="px-closed" ${S.closed ? 'checked' : ''}> Afficher les positions soldées (${nc})</label>` : ''}</div><div class="px-fold-body" id="px-fb-positions" ${fp ? 'hidden' : ''}>${table(st, 0)}</div></section>${suiviSection()}`;
  }
  function viewTx() {
    const tr = (C.H.trades || []).filter(t => !t.note).slice().sort((a, b) => String(b.trade_at).localeCompare(String(a.trade_at))).slice(0, 12);
    return `<section class="px-card"><div class="px-ph"><h2>Transactions</h2><div class="px-ha"><button type="button" class="px-btn pri" data-add>Ajouter une opération</button><button type="button" class="px-btn" data-hist>Historique complet, lots et ventes</button></div></div>
      <div class="px-tw"><table class="px-t px-tx"><thead><tr><th>Date</th><th>Opération</th><th>Titre</th><th class="num">Quantité</th><th class="num">Prix</th></tr></thead><tbody>${tr.map(t => `<tr data-tx="${t.id}" tabindex="0"><td data-l="Date">${J.date(t.date)}</td><td data-l="Opération"><b>${t.side === 'sell' ? 'Vente' : 'Achat'}</b></td><td data-l="Titre">${esc(t.symbol)}</td><td class="num" data-l="Quantité">${J.num(t.quantity, 4)}</td><td class="num" data-l="Prix">${J.num(t.unit_price, 4)} ${esc(t.currency || '')}</td></tr>`).join('') || '<tr><td colspan="5" class="px-note">Aucune transaction.</td></tr>'}</tbody></table></div><p class="px-note">12 dernières opérations. L’historique complet permet de filtrer, modifier et régler les lots.</p></section>`;
  }
  /* ───────── détail : en-tête compact, trois onglets (Chiffres, Graphique, Plan de suivi) ───────── */
  const MAIN = { modes: [['perso', 'Mon investissement'], ['market', 'Historique des cours']], pf: true, keys: () => open().map(pkey) };
  const DETC = key => ({ modes: [['perso', 'Mon investissement'], ['market', 'Historique des cours']], pf: false, keys: () => [key] });
  const ROWS = ['1d', '2d', '5d', '1w', '2w', '1m', '3m', '6m', '1y', '2y', '3y', '5y', '10y', 'all'];
  const rowName = per => per === 'all' ? 'Depuis l’achat' : perName(per);
  /** Résultat personnel par période : uniquement sur la partie détenue ; jamais de performance avant l'achat. Apports neutralisés (résultat = variation du gain). */
  function persoRows(l) {
    const H = C.H, first = PFM.firstActive(l), fd = first == null ? null : H.dates[first];
    return ROWS.map(per => {
      const lab = rowName(per); if (first == null) return { lab, na: 'Aucun achat enregistré sur ce titre.' };
      const w = PFM.resolveWindow(H, per); if (w.i1 < first) return { lab, na: 'Titre pas encore détenu.' };
      const partial = per !== 'all' && w.i0 < first, r = PFM.position(H, l, partial ? Object.assign({}, w, { i0: -1 }) : w);
      if (!isNum(r.result)) return { lab, na: r.reason || 'Indisponible.' };
      return { lab, eur: r.result, pct: r.pct, note: partial ? 'Partiel : depuis l’achat du ' + J.date(fd) : (w.clipped ? 'Historique plus court que la période' : '') };
    });
  }
  /** Variation du cours du titre (marché) : indépendante de vos achats. € par titre au change du jour. */
  function marketRows(key, l) {
    const M = mk(), ln = M.lines.find(x => x.key === key), dates = mDates(), H = C.H, first = l ? PFM.firstActive(l) : null, fd = first == null ? null : H.dates[first];
    return ROWS.map(per => {
      const lab = rowName(per); if (!ln) return { lab, na: 'Aucun cours disponible pour ce titre.' };
      let i1 = ln.prices.length - 1; while (i1 >= 0 && !isNum(ln.prices[i1])) i1--; if (i1 < 0) return { lab, na: 'Aucun cours.' };
      let i0; if (per === 'all') { if (!fd) return { lab, na: 'Aucun achat enregistré.' }; i0 = lastIdx(dates, fd); } else { const w = PFM.resolveWindow({ dates }, per); i0 = w.i0; if (i0 < 0) return { lab, na: 'Cours disponibles seulement depuis le ' + J.date(dates[0]) + '.' }; }
      if (i0 < 0 || !isNum(ln.prices[i0])) return { lab, na: 'Cours de départ indisponible.' };
      const e0 = ln.prices_eur[i0], e1 = ln.prices_eur[i1];
      return { lab, eur: isNum(e0) && isNum(e1) ? e1 - e0 : null, pct: 100 * (ln.prices[i1] / ln.prices[i0] - 1), note: '' };
    });
  }
  function figuresHtml(x) {
    const rows = S.fig === 'market' ? marketRows(x.key, x.l) : (x.l ? persoRows(x.l) : []), mk2 = S.fig === 'market';
    return `<div class="px-tw"><table class="px-t px-fig"><thead><tr><th>Période</th><th class="num">${mk2 ? 'Variation € / titre' : 'Gain / perte €'}</th><th class="num">${mk2 ? 'Variation du cours %' : 'Performance %'}</th></tr></thead><tbody>${rows.map(r => r.na ? `<tr><td data-l="Période"><b>${r.lab}</b></td><td colspan="2" class="px-na">Indisponible : ${esc(r.na)}</td></tr>` : `<tr><td data-l="Période"><b>${r.lab}</b>${r.note ? `<small class="px-part">${esc(r.note)}</small>` : ''}</td><td class="num ${cl(r.eur)}" data-l="${mk2 ? 'Variation €' : 'Gain / perte'}">${mk2 ? sg(r.eur) : sg(r.eur)}</td><td class="num ${cl(r.pct)}" data-l="Performance">${pc(r.pct)}</td></tr>`).join('')}</tbody></table></div>
      <p class="px-note">${mk2 ? 'Variation du cours, indépendante de vos achats (cours de clôture, dernier cours connu pour la fin).' : 'Votre résultat sur la période, calculé uniquement sur la partie détenue : les apports d’argent ne sont jamais comptés comme des gains, les gains réalisés par vos ventes sont conservés. 1J à 1S : clôtures quotidiennes.'}</p>`;
  }
  function lotStrategy(lo) {
    const pl = S.tr && S.tr.positions[String(lo.listing_id)], o = pl && (pl.origins || []).find(z => z.tx === lo.tx_id && z.label);
    return o ? o.label : 'Non renseignée';
  }
  function openDetail(key, goPlan) {
    S.sel = key; S.fig = 'perso'; S.tab = goPlan ? 'suivi' : 'chiffres'; const st = stats(), x = st.rows.find(r => r.key === key); if (!x) return;
    const { p, l } = x, closed = !(p.qty > 0), cur = p.price_currency || p.currency;
    const lots = (C.D.lots || []).filter(lo => p.listing_id ? lo.listing_id === p.listing_id : lo.symbol === p.symbol), trades = (C.H.trades || []).filter(t => t.key === key && !t.note).slice().sort((a, b) => String(b.trade_at).localeCompare(String(a.trade_at)));
    const sales = (C.D.sales || []).filter(s => p.listing_id ? s.listing_id === p.listing_id : s.symbol === p.symbol), re = sales.reduce((n, s) => n + (s.gain || 0), 0), lat = closed ? 0 : p.value - p.cost, tp = taxOf([Math.max(0, re)], lat, x.gain, l ? (l.purchases[l.purchases.length - 1] || 0) : 0);
    Object.assign(S.det, { mode: 'perso', per: 'all', unit: 'pct', view: null, focus: null }); S.det.hidden.clear();
    const root = J.$('#px-drawer-root'), prev = document.activeElement, kv = (k, v) => `<div><dt>${k}</dt><dd>${v}</dd></div>`;
    root.innerHTML = `<div class="px-back" data-close></div><aside class="px-drawer" role="dialog" aria-modal="true" aria-label="Détail ${esc(p.symbol)}"><header class="px-dh"><div class="px-id"><h2>${esc(p.symbol)} <span>${esc(p.name_catalogue || p.name || '')}</span></h2><dl class="px-kv2 px-hk">${kv('Cours', closed ? '–' : J.money(p.price, cur))}${kv('Prix de revient', closed ? '–' : eur(p.avg_cost))}${kv('Résultat global', `<span class="${cl(x.gain)}">${sg(x.gain)} · ${pc(x.pctv, 1)}</span>`)}</dl></div>
      <div class="px-ha px-dact">${p.listing_id ? `<a class="px-btn" href="titre.html?id=${p.listing_id}&from=portefeuille" target="_blank" rel="noopener">Analyse du titre ${I.ext}</a>` : ''}<button type="button" class="px-btn pri" data-buy="${esc(key)}">Acheter</button><button type="button" class="px-btn" data-sell="${esc(key)}" ${closed ? 'disabled' : ''}>Vendre</button><button type="button" class="px-btn" data-close aria-label="Fermer le détail">✕</button></div></header>
      <div class="px-tabs2" role="tablist" aria-label="Détail du titre">${[['chiffres', 'Chiffres'], ['graphique', 'Graphique'], ['suivi', 'Plan de suivi']].map(([k, lb]) => `<button type="button" role="tab" data-tab="${k}" aria-selected="${S.tab === k}" class="${S.tab === k ? 'on' : ''}">${lb}</button>`).join('')}</div>
      <div class="px-db">
       <section data-panel="chiffres" ${S.tab === 'chiffres' ? '' : 'hidden'}><h3>Combien ai-je gagné ou perdu sur ce titre ?</h3>
        <dl class="px-kv2 px-origin">${kv('Depuis l’origine', `<span class="${cl(x.gain)}">${sg(x.gain)}</span>`)}${kv('dont réalisé (ventes)', `<span class="${cl(re)}">${sg(re)}</span>`)}${kv('dont latent', closed ? '–' : `<span class="${cl(lat)}">${sg(lat)}</span>`)}${kv('Après impôts (estimé)', `<span class="${cl(tp.net)}">${sg(tp.net)} · ${pc(tp.pct, 1)}</span>`)}${kv('Quantité', closed ? '0' : J.num(p.qty, 4))}</dl>
        <div class="px-seg px-figseg" id="px-figseg" aria-label="Type de chiffres"><button type="button" data-fig="perso" class="on" aria-pressed="true">Mon résultat</button><button type="button" data-fig="market" aria-pressed="false">Variation du cours</button></div>
        <div id="px-fig">${figuresHtml(x)}</div>
        <h3>Mes achats et ventes</h3><div class="px-tw"><table class="px-t px-ops"><thead><tr><th>Date</th><th>Opération</th><th class="num">Quantité</th><th class="num">Prix</th><th class="num">Frais</th><th class="num">Résultat réalisé</th></tr></thead><tbody>${trades.map(t => { const s = t.side === 'sell' ? sales.find(z => z.tx_id === t.id) : null; return `<tr><td data-l="Date">${J.date(t.date)}</td><td data-l="Opération"><b>${t.side === 'sell' ? 'Vente' : 'Achat'}</b></td><td class="num" data-l="Quantité">${J.num(t.quantity, 4)}</td><td class="num" data-l="Prix">${J.num(t.unit_price, 4)} ${esc(t.currency || '')}</td><td class="num" data-l="Frais">${eur(t.fees_eur)}</td><td class="num ${s ? cl(s.gain) : ''}" data-l="Réalisé">${s ? sg(s.gain) : '–'}</td></tr>`; }).join('') || '<tr><td colspan="6" class="px-note">Aucune opération.</td></tr>'}</tbody></table></div>
        ${lots.length ? `<details class="px-tech"><summary>Détails techniques : lots d’achat restants</summary><div class="px-list">${lots.map(lo => `<div><span>${J.date(lo.trade_at)}</span><b>${J.num(lo.remaining, 4)} titre(s)</b><span>Stratégie d’origine : ${esc(lotStrategy(lo))}</span><button type="button" class="px-btn s" data-lot="${lo.tx_id}">Régler cet achat</button></div>`).join('')}</div></details>` : ''}</section>
       <section data-panel="graphique" ${S.tab === 'graphique' ? '' : 'hidden'}>${boxHtml(S.det, DETC(key))}</section>
       <section data-panel="suivi" ${S.tab === 'suivi' ? '' : 'hidden'}><div id="px-plan-body"></div></section></div></aside>`;
    root.hidden = false; document.body.classList.add('px-lock'); let boxed = false;
    const close = () => { root.hidden = true; root.innerHTML = ''; S.sel = null; document.body.classList.remove('px-lock'); document.removeEventListener('keydown', esc2); prev && prev.focus && prev.focus(); };
    const esc2 = e => { if (e.key === 'Escape' && !document.querySelector('dialog[open]')) close(); };
    document.addEventListener('keydown', esc2);
    const showTab = k => { S.tab = k; root.querySelectorAll('[data-tab]').forEach(b => { const on = b.dataset.tab === k; b.classList.toggle('on', on); b.setAttribute('aria-selected', String(on)); }); root.querySelectorAll('[data-panel]').forEach(s => { s.hidden = s.dataset.panel !== k; }); if (k === 'graphique') { if (!boxed) { boxed = true; bindBox(S.det, DETC(key)); } else drawBox(S.det, DETC(key)); } };
    root.onclick = e => {
      if (e.target.closest('[data-close]')) return close(); const tb = e.target.closest('[data-tab]'); if (tb) return showTab(tb.dataset.tab);
      const fg = e.target.closest('[data-fig]'); if (fg) { S.fig = fg.dataset.fig; root.querySelectorAll('[data-fig]').forEach(b => { b.classList.toggle('on', b === fg); b.setAttribute('aria-pressed', String(b === fg)); }); J.$('#px-fig').innerHTML = figuresHtml(x); return; }
      const lo = e.target.closest('[data-lot]'); if (lo) return C.helpers.lot(C.D.lots.find(z => z.tx_id == lo.dataset.lot));
      const b = e.target.closest('[data-buy],[data-sell]'); if (b) return C.helpers.trade(b.dataset.buy || b.dataset.sell, b.dataset.sell ? 'sell' : 'buy');
    };
    renderPlan(x); showTab(S.tab); root.querySelector('.px-dact [data-close]').focus();
  }
  function renderPlan(x) {
    const host = J.$('#px-plan-body'), p = x.p; if (!host) return;
    if (!p.listing_id) { host.innerHTML = '<p class="px-note">Ce titre n’a pas de cotation suivie : aucun plan de suivi possible.</p>'; return; }
    if (!S.tr && !S.trErr && S.trP) { host.innerHTML = '<p class="px-note">Chargement du plan de suivi…</p>'; S.trP.then(() => { if (J.$('#px-plan-body') === host) renderPlan(x); }); return; }
    if (!S.tr || !root.PlanSuivi) { host.innerHTML = `<p class="notice err">${esc(S.trErr || 'Plan de suivi indisponible')}</p>`; return; }
    const pl = planOf(p); if (!pl) { host.innerHTML = '<p class="notice err">Plan de suivi indisponible pour ce titre.</p>'; return; }
    root.PlanSuivi.render(host, { plan: pl, strategies: S.tr.strategies, portfolio: C.current, listing: p.listing_id, reload: reloadTracking });
  }

  /* ───────── rendu ───────── */
  function refreshPage() { if (!J.$('#px-page')) return; const y = scrollY; render(true); scrollTo(0, y); }
  function render(keepScroll) {
    if (!C || !C.H) return;
    const st = stats(), body = S.zone === 'transactions' ? viewTx() : viewOverview(st);
    if (!J.$('#px-drawer-root')) C.host.innerHTML = '<div id="px-page"></div><div id="px-drawer-root" hidden></div>';
    J.$('#px-page').innerHTML = head() + body;
    if (S.zone === 'overview') bindBox(S.main, MAIN);
  }
  function onClick(e) {
    const t = e.target, z = t.closest('[data-zone]'); if (z) { e.preventDefault(); S.zone = z.dataset.zone; render(); const h = J.$('.px-zones'); h && h.scrollIntoView({ block: 'start' }); return; }
    const s = t.closest('[data-sort]'); if (s) { const k = s.dataset.sort; S.dir = S.sort === k ? -S.dir : (COLS[k][2] === 'l' ? 1 : -1); S.sort = k; store('sort', k); store('dir', S.dir); const y = scrollY; render(); scrollTo(0, y); return; }
    const f = t.closest('[data-fold]');
    if (f) { const k = f.dataset.fold, hide = f.getAttribute('aria-expanded') === 'true'; store('fold_' + k, hide); f.setAttribute('aria-expanded', String(!hide)); f.querySelector('.hint').textContent = hide ? 'Masqué · afficher' : 'Masquer';
      const b = J.$('#px-fb-' + k); if (b) b.hidden = hide; const sec = f.closest('.px-card'); if (sec) sec.classList.toggle('folded', hide);
      if (k === 'positions') { const w = J.$('#px-closed-wrap'); if (w) w.hidden = hide; } return; }
    const cf = t.closest('[data-ps-cfg]'); if (cf) return configureFor(cf.dataset.psCfg);
    const ex = t.closest('[data-ps-exp]'); if (ex) { const m = J.$('#psr-more-' + ex.dataset.psExp), o = ex.getAttribute('aria-expanded') !== 'true'; ex.setAttribute('aria-expanded', o ? 'true' : 'false'); if (m) m.hidden = !o; return; }
    if (t.closest('[data-add]')) return C.helpers.add();
    if (t.closest('[data-hist]')) return C.helpers.history();
    const b = t.closest('[data-buy],[data-sell]'); if (b && !t.closest('#px-drawer-root')) { e.stopPropagation(); return C.helpers.trade(b.dataset.buy || b.dataset.sell, b.dataset.sell ? 'sell' : 'buy'); }
    if (t.closest('a')) return;
    const c = t.closest('[data-conf]'); if (c) return openDetail(c.dataset.conf, true);
    const tx = t.closest('tr[data-tx]'); if (tx) return C.helpers.history(+tx.dataset.tx);
    const o = t.closest('[data-open]'); if (o) return openDetail(o.dataset.open);
  }
  function onChange(e) { if (e.target.id === 'px-closed') { S.closed = e.target.checked; const y = scrollY; render(); scrollTo(0, y); } }
  function onKey(e) { if (['Enter', ' '].includes(e.key) && e.target.matches('tr[data-open],tr[data-tx]')) { e.preventDefault(); e.target.click(); } }
  async function mount(host, ctx) {
    const first = !C || C.host !== host; C = Object.assign({ host }, ctx);
    if (first) { host.addEventListener('click', onClick); host.addEventListener('change', onChange); host.addEventListener('keydown', onKey); }
    if (!ctx.keep) { S.main.view = null; S.main.hidden.clear(); S.zone = 'overview'; }
    render();
    await loadTracking(); if (C.host === host) { const y = scrollY; render(); scrollTo(0, y); }
  }
  root.PFHome = { mount, state: S, ctx: () => C, build: (st, o) => build(st, o), setCtx: c => { C = Object.assign({ host: document.body }, c); } };
})(typeof window !== 'undefined' ? window : globalThis);
