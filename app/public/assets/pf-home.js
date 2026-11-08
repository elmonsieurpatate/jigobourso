/* Portefeuille V4 : un seul espace, quatre zones (Vue d'ensemble, Positions, Transactions, Surveillance), détail en panneau.
   Calculs : pf-math.js. Tracé : J.financialChart (financial-chart.js, moteur partagé). Surveillance : alert-panel.js. Couleurs : variables du thème. */
(function (root) {
  'use strict';
  const PFM = root.PFM, isNum = PFM.isNum;
  const store = (k, v) => { try { if (v === undefined) return JSON.parse(localStorage.getItem('jigo_pfx_' + k)); localStorage.setItem('jigo_pfx_' + k, JSON.stringify(v)); } catch (e) { return null; } };
  const PER = PFM.PERIODS, PERKEYS = PER.map(p => p[0]);
  const perName = k => (PER.find(x => x[0] === k) || [0, ''])[1];
  const INTRA = { '1d': 1, '2d': 2, '5d': 5, '1w': 7 };               // séances d'historique 15 min recherchées ; 2S et au-delà : quotidien
  const mkBox = (id, mode) => ({ id, mode, per: 'all', unit: 'pct', view: null, hidden: new Set(), focus: null, token: 0 });
  const S = { zone: 'overview', sort: store('sort') || 'value', dir: store('dir') || -1, closed: false, sel: null, al: null, alErr: null,
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
  const pal = () => ['--accent', '--warn', '--up', '--down'].map(cssv).concat(['#7c3aed', '#0891b2', '#db2777', '#65a30d', '#ca8a04', '#4f46e5', '#059669', '#9333ea']);
  const pkey = p => p.listing_id ? String(p.listing_id) : 'S' + String(p.symbol).toUpperCase();
  const all = () => [...C.D.positions, ...C.D.closed];
  const open = () => C.D.positions.filter(p => p.qty > 0);
  const lineOf = p => C.H.lines.find(l => l.key === pkey(p));
  const mk = () => C.H.market && C.H.market.dates ? C.H.market : { dates: [], lines: [], intraday: { dates: [], lines: [] } };
  const mDates = () => mk().dates.map(d => d.slice(0, 10));
  const lastIdx = (a, d) => { let r = -1; for (let i = 0; i < a.length; i++) { if (a[i] <= d) r = i; else break; } return r; };
  const colorOf = key => { const i = open().findIndex(p => pkey(p) === key); return pal()[(i < 0 ? 0 : i) % pal().length]; };
  const I = { chev: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 5l7 7-7 7" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>', ext: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 17L17 7M9 7h8v8" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>', bell: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 17h12l-1.5-2V10a4.5 4.5 0 00-9 0v5zM10 20h4" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>' };

  /* ───────── surveillance (état lu dans alerts/state) ───────── */
  async function loadAlerts() { try { S.al = await J.api('alerts/state', { params: { portfolio: C.current } }); S.alErr = null; } catch (e) { S.al = null; S.alErr = e.message || 'indisponible'; } }
  function watchOf(p) {
    const A = S.al; if (!A || !p.listing_id) return { k: 'na', t: A ? 'Sans cotation' : S.alErr ? 'Indisponible' : 'Chargement…', rules: 0, trig: 0, strat: null, origin: null, last: null };
    const ap = A.positions.find(x => x.listing_id === p.listing_id), rs = A.rules.filter(r => r.listing_id === p.listing_id), on = rs.filter(r => r.enabled);
    const trig = on.filter(r => r.state === 'triggered' && !r.acked_at).length, bad = on.filter(r => r.state === 'insufficient' || r.state === 'error').length, never = on.filter(r => r.state === null).length;
    const last = rs.map(r => r.last_eval_at).filter(Boolean).sort().pop() || null;
    const origin = ap && ap.origins.find(o => o.strategy) ? ap.origins.find(o => o.strategy).label : ap && ap.lot_strategies[0] ? ap.lot_strategies[0].label : null;
    let k, t;
    if (!rs.length) [k, t] = ['none', 'Sans surveillance']; else if (!on.length) [k, t] = ['off', 'Désactivée']; else if (trig) [k, t] = ['ko', trig + ' déclenchée' + (trig > 1 ? 's' : '')];
    else if (bad) [k, t] = ['na', 'Données insuffisantes']; else if (never === on.length) [k, t] = ['na', 'Pas encore évaluée']; else [k, t] = ['ok', 'Normale'];
    return { k, t, rules: on.length, trig, strat: ap && ap.watch ? ap.watch.label : null, origin, last };
  }
  function alertSummary(tag) {
    tag = tag || 'a'; const att = tag === 'a' ? ' data-zone="surveillance" href="#"' : '';
    const A = S.al; if (!A) return `<${tag} class="px-sum"${att}><span class="px-ab">${I.bell}<b>Surveillance</b></span><span class="muted">${S.alErr ? 'Indisponible : ' + esc(S.alErr) : 'Chargement…'}</span></${tag}>`;
    const ws = open().filter(p => p.listing_id).map(watchOf), n = k => ws.filter(w => w.k === k).length, last = A.rules.map(r => r.last_eval_at).filter(Boolean).sort().pop();
    const parts = [[n('ko'), 'déclenchée', 'ko'], [n('na'), 'à vérifier', 'na'], [n('none'), 'sans surveillance', 'none']].filter(x => x[0]);
    return `<${tag} class="px-sum"${att}><span class="px-ab">${I.bell}<b>Surveillance</b></span>${parts.length ? parts.map(([c, l, k]) => `<span><i class="n ${k}">${c}</i>${l}${c > 1 && k !== 'none' && k !== 'na' ? 's' : ''}</span>`).join('') : '<span><i class="n ok">✓</i>Tout est normal</span>'}<span class="muted">${last ? 'Dernière vérification : ' + J.dateTime(String(last).replace(' ', 'T')) : 'Jamais évaluée'}</span>${tag === 'a' ? I.chev : ''}</${tag}>`;
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
        if (o.pf) add('pf', 'Portefeuille', pct ? ss.pct : ss.gain, 3.2, cssv('--accent'));
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
      if (ps) { if (ps.note) out.meta.notes.push(ps.note); add('pf', 'Portefeuille', ps.y, 3.2, cssv('--accent')); }
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

  /* ───────── synthèse ───────── */
  function stats() {
    const H = C.H, wAll = PFM.resolveWindow(H, 'all'), pf = PFM.portfolio(H, wAll);
    const rows = all().map(p => { const l = lineOf(p), r = l ? PFM.position(H, l, wAll) : { result: null, sinceBuy: null, sinceBuyPct: null }; return { p, l, r, key: pkey(p), contrib: PFM.contribution(r, pf), gain: r.sinceBuy, pctv: r.sinceBuyPct, w: C.D.totals.value > 0 && p.qty > 0 ? 100 * p.value / C.D.totals.value : null, watch: watchOf(p) }; });
    const evo = [['1d', 'Aujourd’hui'], ['1w', '1 semaine'], ['1m', '1 mois'], ['1y', '1 an'], ['all', 'Depuis le début']].map(([k, l]) => { const q = PFM.portfolio(H, PFM.resolveWindow(H, k)); return { l, q }; });
    const ranked = rows.filter(r => isNum(r.contrib) && r.p.qty > 0).sort((a, b) => b.contrib - a.contrib);
    return { pf, rows, evo, best: ranked[0], worst: ranked.length > 1 ? ranked[ranked.length - 1] : null };
  }
  function synth(st) {
    const t = C.D.totals, base = t.invested_total || 0, tg = t.total_gain;
    return `<section class="px-card px-syn"><div class="px-val"><span class="px-l">Valeur du portefeuille</span><strong>${eur(t.value)}</strong><span class="px-pill ${cl(tg)}">${sg(tg)}${base > 0 && isNum(tg) ? ` <small>(${pc(100 * tg / base)})</small>` : ''}</span></div>
      <dl class="px-kv"><div><dt>Capital investi</dt><dd>${eur(t.cost)}</dd></div><div><dt>Gains latents</dt><dd class="${cl(t.unrealized)}">${sg(t.unrealized)}</dd></div><div><dt>Gains réalisés</dt><dd class="${cl(t.realized)}">${sg(t.realized)}</dd></div><div><dt>Résultat total</dt><dd class="${cl(tg)}">${sg(tg)}</dd></div></dl>
      <div class="px-evo" aria-label="Évolution">${st.evo.map(({ l, q }) => `<div><span>${l}</span><b class="${cl(q.pct)}">${pc(q.pct)}</b><small class="${cl(q.result)}">${sg(q.result)}</small></div>`).join('')}</div>
      <div class="px-hh"><div><span>Contribue le plus</span><b class="${cl(st.best && st.best.contrib)}">${st.best ? esc(st.best.p.symbol) + ' ' + pt(st.best.contrib) : '–'}</b></div><div><span>Pèse le plus</span><b class="${cl(st.worst && st.worst.contrib)}">${st.worst && st.worst.contrib < 0 ? esc(st.worst.p.symbol) + ' ' + pt(st.worst.contrib) : '–'}</b></div></div></section>`;
  }

  /* ───────── tableau compact des positions ───────── */
  const COLS = { title: ['Titre', r => r.p.symbol, 'l'], value: ['Valeur', r => r.p.value], gain: ['Gain/perte', r => r.gain], pct: ['Rendement', r => r.pctv], contrib: ['Contribution', r => r.contrib], w: ['Poids', r => r.w], strat: ['Stratégie', r => (r.watch.strat || r.watch.origin || '').toLowerCase(), 'l'], watch: ['Surveillance', r => ({ ko: 0, na: 1, none: 2, off: 3, ok: 4 }[r.watch.k]), 'l'] };
  function sortRows(rows) {
    const f = COLS[S.sort] || COLS.value, num = !(f[2] === 'l' && S.sort !== 'watch');
    return rows.map((r, i) => [r, i]).sort((A, B) => { const x = f[1](A[0]), y = f[1](B[0]); if (!num) return S.dir * String(x).localeCompare(String(y), 'fr') || A[1] - B[1]; const kx = isNum(x), ky = isNum(y); if (kx !== ky) return kx ? -1 : 1; return (kx ? S.dir * (x - y) : 0) || A[1] - B[1]; }).map(a => a[0]);
  }
  function table(st, limit) {
    let rows = st.rows.filter(r => S.closed || r.p.qty > 0), total = rows.length; rows = sortRows(rows); if (limit) rows = rows.slice(0, limit);
    const th = k => { const c = COLS[k], on = S.sort === k; return `<th class="${c[2] === 'l' ? '' : 'num'} c-${k}" aria-sort="${on ? (S.dir > 0 ? 'ascending' : 'descending') : 'none'}"><button type="button" data-sort="${k}">${c[0]}${on ? (S.dir > 0 ? ' ▲' : ' ▼') : ''}</button></th>`; };
    const body = rows.map(r => { const { p } = r, closed = !(p.qty > 0), w = r.watch;
      return `<tr class="${closed ? 'closed' : ''}" data-open="${esc(r.key)}" tabindex="0"><td class="c-title" data-l="Titre"><b>${esc(p.symbol)}</b><span class="ell">${esc(p.name_catalogue || p.name || '')}${closed ? ' · soldé' : ''}</span></td><td class="num c-value" data-l="Valeur">${closed ? '–' : eur(p.value)}</td><td class="num c-gain ${cl(r.gain)}" data-l="Gain/perte">${sg(r.gain)}</td><td class="num c-pct ${cl(r.pctv)}" data-l="Rendement">${pc(r.pctv)}</td><td class="num c-contrib ${cl(r.contrib)}" data-l="Contribution">${pt(r.contrib)}</td><td class="num c-w" data-l="Poids">${isNum(r.w) ? J.num(r.w, 1) + ' %' : '–'}</td><td class="c-strat" data-l="Stratégie"><span class="ell">${esc(w.strat || w.origin || 'Non renseignée')}</span></td><td class="c-watch" data-l="Surveillance"><button type="button" class="px-w ${w.k}" data-conf="${esc(r.key)}">${I.bell}${esc(w.t)}</button></td>
        <td class="c-act"><button type="button" class="px-btn s" data-buy="${esc(r.key)}">Acheter</button><button type="button" class="px-btn s" data-sell="${esc(r.key)}" ${closed ? 'disabled' : ''}>Vendre</button>${p.listing_id ? `<a class="px-btn s" href="titre.html?id=${p.listing_id}&from=portefeuille" target="_blank" rel="noopener" aria-label="Analyse du titre ${esc(p.symbol)} (nouvel onglet)">Analyse ${I.ext}</a>` : ''}</td></tr>`; }).join('');
    return `<div class="px-tw"><table class="px-t"><thead><tr>${Object.keys(COLS).map(th).join('')}<th class="c-act">Actions</th></tr></thead><tbody>${body || '<tr><td colspan="9" class="px-note">Aucune position.</td></tr>'}</tbody></table></div>${limit && total > limit ? `<p class="px-more"><button type="button" class="px-link" data-zone="positions">Toutes les positions (${total}) ${I.chev}</button></p>` : ''}`;
  }

  /* ───────── zones ───────── */
  function zoneTabs() { return `<nav class="px-zones" role="tablist" aria-label="Zones du portefeuille">${[['overview', 'Vue d’ensemble'], ['positions', 'Positions'], ['transactions', 'Transactions'], ['surveillance', 'Surveillance']].map(([k, l]) => `<button type="button" role="tab" data-zone="${k}" aria-selected="${S.zone === k}" class="${S.zone === k ? 'on' : ''}">${l}</button>`).join('')}</nav>`; }
  function head() { return `<header class="px-head"><div><h1>${esc(C.name || 'Portefeuille')}</h1><p class="muted">${open().length} position${open().length > 1 ? 's' : ''} · valeur et résultat en euros</p></div><div class="px-ha"><button type="button" class="px-btn pri" data-add>Ajouter une opération</button></div></header>${zoneTabs()}`; }
  function viewOverview(st) {
    return `${synth(st)}${alertSummary()}<section class="px-card"><h2>Évolution</h2>${boxHtml(S.main, MAIN)}</section><section class="px-card"><div class="px-ph"><h2>Positions</h2></div>${table(st, 8)}</section>
      <section class="px-card px-links"><button type="button" class="px-link" data-zone="transactions">Transactions et lots ${I.chev}</button><a class="px-link" href="alertes.html?portfolio=${C.current}">Centre d’alertes ${I.chev}</a></section>`;
  }
  function viewPositions(st) { const nc = st.rows.filter(r => !(r.p.qty > 0)).length; return `<section class="px-card"><div class="px-ph"><h2>Positions <span>(${open().length})</span></h2>${nc ? `<label class="px-chk"><input type="checkbox" id="px-closed" ${S.closed ? 'checked' : ''}> Afficher les positions soldées (${nc})</label>` : ''}</div>${table(st, 0)}<p class="px-note">Gain, rendement et contribution : depuis l’achat (réalisé et latent). Cliquez une ligne pour le détail.</p></section>`; }
  function viewTx() {
    const tr = (C.H.trades || []).filter(t => !t.note).slice().sort((a, b) => String(b.trade_at).localeCompare(String(a.trade_at))).slice(0, 12);
    return `<section class="px-card"><div class="px-ph"><h2>Transactions</h2><div class="px-ha"><button type="button" class="px-btn pri" data-add>Ajouter une opération</button><button type="button" class="px-btn" data-hist>Historique complet, lots et ventes</button></div></div>
      <div class="px-tw"><table class="px-t px-tx"><thead><tr><th>Date</th><th>Opération</th><th>Titre</th><th class="num">Quantité</th><th class="num">Prix</th></tr></thead><tbody>${tr.map(t => `<tr data-tx="${t.id}" tabindex="0"><td data-l="Date">${J.date(t.date)}</td><td data-l="Opération"><b>${t.side === 'sell' ? 'Vente' : 'Achat'}</b></td><td data-l="Titre">${esc(t.symbol)}</td><td class="num" data-l="Quantité">${J.num(t.quantity, 4)}</td><td class="num" data-l="Prix">${J.num(t.unit_price, 4)} ${esc(t.currency || '')}</td></tr>`).join('') || '<tr><td colspan="5" class="px-note">Aucune transaction.</td></tr>'}</tbody></table></div><p class="px-note">12 dernières opérations. L’historique complet permet de filtrer, modifier et régler les lots.</p></section>`;
  }
  function viewSurv(st) {
    const A = S.al; if (!A) return `<section class="px-card"><h2>Surveillance</h2><p class="notice err">${S.alErr ? esc(S.alErr) : 'Chargement…'}</p></section>`;
    const rows = st.rows.filter(r => r.p.qty > 0 && r.p.listing_id);
    return `<section class="px-card"><div class="px-ph"><h2>Surveillance des positions</h2><div class="px-ha"><button type="button" class="px-btn" id="px-eval">Évaluer maintenant</button><a class="px-btn" href="alertes.html?portfolio=${C.current}">Centre d’alertes</a></div></div>${alertSummary('div')}
      <div class="px-tw"><table class="px-t px-sv"><thead><tr><th>Titre</th><th>Stratégie de surveillance</th><th>État</th><th class="num">Règles actives</th><th class="num">Déclenchées</th><th>Dernière évaluation</th><th></th></tr></thead><tbody>${rows.map(r => { const w = r.watch; return `<tr data-open="${esc(r.key)}" tabindex="0"><td data-l="Titre"><b>${esc(r.p.symbol)}</b><span class="ell">${esc(r.p.name_catalogue || r.p.name || '')}</span></td><td data-l="Stratégie"><span class="ell">${esc(w.strat || 'Aucune')}</span></td><td data-l="État"><span class="px-w ${w.k}">${esc(w.t)}</span></td><td class="num" data-l="Règles actives">${w.rules}</td><td class="num" data-l="Déclenchées">${w.trig}</td><td data-l="Dernière évaluation">${w.last ? J.dateTime(String(w.last).replace(' ', 'T')) : '–'}</td><td><button type="button" class="px-btn s" data-conf="${esc(r.key)}">Configurer</button></td></tr>`; }).join('') || '<tr><td colspan="7" class="px-note">Aucune position avec cotation.</td></tr>'}</tbody></table></div>
      <p class="px-note">Une alerte informe, elle ne vend jamais à votre place. Évaluation à chaque passage automatique (toutes les 5 minutes en séance pour les cours, une fois par jour pour les tendances).</p></section>`;
  }

  /* ───────── détail en panneau ───────── */
  const MAIN = { modes: [['perso', 'Mon investissement'], ['market', 'Historique des cours']], pf: true, keys: () => open().map(pkey) };
  let DET = null;
  function openDetail(key, section) {
    S.sel = key; const st = stats(), x = st.rows.find(r => r.key === key); if (!x) return;
    const { p, l, r } = x, closed = !(p.qty > 0), cur = p.price_currency || p.currency, w = x.watch, peak = l ? PFM.personalPeak(l) : {}, dd = l ? PFM.drawdownFromHigh(C.H, l) : null;
    const lots = (C.D.lots || []).filter(lo => p.listing_id ? lo.listing_id === p.listing_id : lo.symbol === p.symbol), trades = (C.H.trades || []).filter(t => t.key === key && !t.note);
    const re = (C.D.sales || []).filter(s => p.listing_id ? s.listing_id === p.listing_id : s.symbol === p.symbol).reduce((n, s) => n + (s.gain || 0), 0), kv = (k, v) => `<div><dt>${k}</dt><dd>${v}</dd></div>`;
    DET = Object.assign(S.det, { mode: 'perso', per: 'all', unit: 'pct', view: null, focus: null }); DET.hidden.clear();
    const root = J.$('#px-drawer-root'), prev = document.activeElement;
    root.innerHTML = `<div class="px-back" data-close></div><aside class="px-drawer" role="dialog" aria-modal="true" aria-label="Détail ${esc(p.symbol)}"><header class="px-dh"><div><h2>${esc(p.symbol)} <span>${esc(p.name_catalogue || p.name || '')}</span></h2><small>${p.kind === 'etf' ? 'ETF' : 'Action'}${p.country ? ' · ' + esc(p.country) : ''}${closed ? ' · position soldée' : ''}</small></div><div class="px-ha">${p.listing_id ? `<a class="px-btn" href="titre.html?id=${p.listing_id}&from=portefeuille" target="_blank" rel="noopener">Analyse du titre ${I.ext}</a>` : ''}<button type="button" class="px-btn" data-close aria-label="Fermer le détail">✕</button></div></header>
      <div class="px-db"><section><h3>Synthèse financière</h3><dl class="px-kv2">${kv('Cours', closed ? '–' : J.money(p.price, cur))}${kv('Valeur', closed ? 'soldé' : eur(p.value))}${kv('Quantité', closed ? '0' : J.num(p.qty, 4))}${kv('Prix de revient moyen', closed ? '–' : eur(p.avg_cost))}${kv('Gain latent', closed ? '–' : `<span class="${cl(p.value - p.cost)}">${sg(p.value - p.cost)}</span>`)}${kv('Gain réalisé', `<span class="${cl(re)}">${sg(re)}</span>`)}${kv('Résultat total', `<span class="${cl(x.gain)}">${sg(x.gain)} · ${pc(x.pctv, 1)}</span>`)}${kv('Contribution', `<span class="${cl(x.contrib)}">${pt(x.contrib)}</span>`)}${kv('Meilleur résultat atteint', sg(peak.peak))}${kv('Recul depuis le plus haut cours', isNum(dd) ? pc(dd, 1) : '–')}</dl></section>
      <section><h3>Évolution</h3>${boxHtml(S.det, DETC(key))}</section>
      <section><h3>Stratégies</h3><dl class="px-kv2">${kv('Stratégie d’origine', esc(w.origin || 'Stratégie d’origine non renseignée'))}${kv('Stratégie de surveillance', esc(w.strat || 'Aucune'))}${kv('État de la surveillance', `<span class="px-w ${w.k}">${esc(w.t)}</span>`)}</dl></section>
      <section id="px-surv"><h3>Surveillance</h3><div id="px-surv-body"></div></section>
      <section><h3>Transactions et lots</h3><div class="px-list">${trades.map(t => `<div><span>${J.date(t.date)}</span><b>${t.side === 'sell' ? 'Vente' : 'Achat'}</b><span>${J.num(t.quantity, 4)} × ${J.num(t.unit_price, 4)} ${esc(t.currency || '')}</span><button type="button" class="px-btn s" data-tx="${t.id}">Voir</button></div>`).join('') || '<p class="px-note">Aucune transaction.</p>'}${lots.map(lo => `<div><span>${J.date(lo.trade_at)}</span><b>${J.num(lo.remaining, 4)} titre(s)</b><span>${esc((lo.alert && lo.alert.strategy_label) || 'Stratégie non renseignée')}</span><button type="button" class="px-btn s" data-lot="${lo.tx_id}">Régler</button></div>`).join('')}</div></section>
      <section class="px-act"><button type="button" class="px-btn pri" data-buy="${esc(key)}">Acheter</button><button type="button" class="px-btn" data-sell="${esc(key)}" ${closed ? 'disabled' : ''}>Vendre</button></section></div></aside>`;
    root.hidden = false; document.body.classList.add('px-lock');
    const close = () => { root.hidden = true; root.innerHTML = ''; S.sel = null; document.body.classList.remove('px-lock'); document.removeEventListener('keydown', esc2); prev && prev.focus && prev.focus(); };
    const esc2 = e => { if (e.key === 'Escape' && !document.querySelector('dialog[open]')) close(); };
    document.addEventListener('keydown', esc2);
    root.onclick = e => { if (e.target.closest('[data-close]')) return close(); const b = e.target.closest('[data-buy],[data-sell]'); if (b) C.helpers.trade(b.dataset.buy || b.dataset.sell, b.dataset.sell ? 'sell' : 'buy'); const t = e.target.closest('[data-tx]'); if (t) { close(); C.helpers.history(+t.dataset.tx, key); } const lo = e.target.closest('[data-lot]'); if (lo) C.helpers.lot(C.D.lots.find(z => z.tx_id == lo.dataset.lot)); };
    bindBox(S.det, DETC(key)); renderSurv(p);
    root.querySelector('[data-close].px-btn').focus();
    if (section) setTimeout(() => { const el = J.$('#px-surv'), sc = J.$('.px-db'); if (el && sc) sc.scrollTop = el.offsetTop - 8; }, 30);
  }
  const DETC = key => ({ modes: [['perso', 'Mon investissement'], ['market', 'Historique des cours']], pf: false, keys: () => [key] });
  function renderSurv(p) {
    const host = J.$('#px-surv-body'); if (!host) return;
    if (!p.listing_id) { host.innerHTML = '<p class="px-note">Ce titre n’a pas de cotation suivie : aucune surveillance possible.</p>'; return; }
    if (!S.al || !root.AlertPanel) { host.innerHTML = `<p class="notice err">${esc(S.alErr || 'Surveillance indisponible')}</p>`; return; }
    root.AlertPanel.render(host, { S: S.al, pid: C.current, listing: p.listing_id, reload: async () => { await loadAlerts(); renderSurv(p); refreshPage(); } });
  }

  /* ───────── rendu ───────── */
  function refreshPage() { if (!J.$('#px-page')) return; const y = scrollY; render(true); scrollTo(0, y); }
  function render(keepScroll) {
    if (!C || !C.H) return;
    const st = stats(), body = S.zone === 'positions' ? viewPositions(st) : S.zone === 'transactions' ? viewTx() : S.zone === 'surveillance' ? viewSurv(st) : viewOverview(st);
    if (!J.$('#px-drawer-root')) C.host.innerHTML = '<div id="px-page"></div><div id="px-drawer-root" hidden></div>';
    J.$('#px-page').innerHTML = head() + body;
    if (S.zone === 'overview') bindBox(S.main, MAIN);
  }
  function onClick(e) {
    const t = e.target, z = t.closest('[data-zone]'); if (z) { e.preventDefault(); S.zone = z.dataset.zone; render(); const h = J.$('.px-zones'); h && h.scrollIntoView({ block: 'start' }); return; }
    const s = t.closest('[data-sort]'); if (s) { const k = s.dataset.sort; S.dir = S.sort === k ? -S.dir : (COLS[k][2] === 'l' ? 1 : -1); S.sort = k; store('sort', k); store('dir', S.dir); const y = scrollY; render(); scrollTo(0, y); return; }
    if (t.closest('[data-add]')) return C.helpers.add();
    if (t.closest('[data-hist]')) return C.helpers.history();
    const b = t.closest('[data-buy],[data-sell]'); if (b && !t.closest('#px-drawer-root')) { e.stopPropagation(); return C.helpers.trade(b.dataset.buy || b.dataset.sell, b.dataset.sell ? 'sell' : 'buy'); }
    if (t.closest('a')) return;
    const c = t.closest('[data-conf]'); if (c) return openDetail(c.dataset.conf, true);
    const tx = t.closest('tr[data-tx]'); if (tx) return C.helpers.history(+tx.dataset.tx);
    const o = t.closest('[data-open]'); if (o) return openDetail(o.dataset.open);
    if (t.id === 'px-eval') { t.disabled = true; J.post('alerts/refresh', {}).then(() => loadAlerts()).then(() => { render(); J.toast('Évaluation terminée'); }).catch(x => { t.disabled = false; J.toast(x.message); }); }
  }
  function onChange(e) { if (e.target.id === 'px-closed') { S.closed = e.target.checked; const y = scrollY; render(); scrollTo(0, y); } }
  function onKey(e) { if (['Enter', ' '].includes(e.key) && e.target.matches('tr[data-open],tr[data-tx]')) { e.preventDefault(); e.target.click(); } }
  async function mount(host, ctx) {
    const first = !C || C.host !== host; C = Object.assign({ host }, ctx);
    if (first) { host.addEventListener('click', onClick); host.addEventListener('change', onChange); host.addEventListener('keydown', onKey); }
    if (!ctx.keep) { S.main.view = null; S.main.hidden.clear(); S.zone = 'overview'; }
    render();
    await loadAlerts(); if (C.host === host) { const y = scrollY; render(); scrollTo(0, y); }
  }
  root.PFHome = { mount, state: S, ctx: () => C, build: (st, o) => build(st, o), setCtx: c => { C = Object.assign({ host: document.body }, c); } };
})(typeof window !== 'undefined' ? window : globalThis);
