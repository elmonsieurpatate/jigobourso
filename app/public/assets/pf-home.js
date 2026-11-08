/* Accueil du Portefeuille V4 (maquette) : synthèse, alertes, graphique à deux modes, positions en cartes, détail. Calculs : pf-math.js ; tracé : pf-chart.js. */
(function (root) {
  'use strict';
  const PFM = root.PFM, PFC = root.PFChart;
  const PAL = ['#2dd4bf', '#a78bfa', '#fb923c', '#60a5fa', '#f472b6', '#facc15', '#34d399', '#f87171', '#38bdf8', '#c084fc', '#a3e635', '#fbbf24'];
  const store = (k, v) => { try { if (v === undefined) return JSON.parse(localStorage.getItem('jigo_pfx_' + k)); localStorage.setItem('jigo_pfx_' + k, JSON.stringify(v)); } catch (e) { return null; } };
  const S = { mode: store('mode') || 'perso', per: store('per') || 'all', zoom: null, unit: store('unit') || 'pct', hidden: new Set(), sort: store('sort') || 'result_desc', sel: null };
  let C = null;
  const isNum = PFM.isNum;
  const pkey = p => p.listing_id ? String(p.listing_id) : 'S' + String(p.symbol).toUpperCase();
  const eur = (v, d = 2) => isNum(v) ? J.eur(v, d) : '–';
  const sg = v => isNum(v) ? (v > 0 ? '+' : v < 0 ? '−' : '') + J.eur(Math.abs(v), 2) : '–';
  const pc = (v, d = 2) => isNum(v) ? (v > 0 ? '+' : v < 0 ? '−' : '') + J.num(Math.abs(v), Math.abs(v) >= 1000 ? 0 : d) + ' %' : '–';
  const pt = v => isNum(v) ? (v > 0 ? '+' : v < 0 ? '−' : '') + J.num(Math.abs(v), 2) + ' pt' : '–';
  const cl = v => isNum(v) ? (v > 0.0049 ? 'up' : v < -0.0049 ? 'down' : '') : '';
  const I = { up: '<svg viewBox="0 0 24 24"><path d="M3 17l6-6 4 4 8-8M15 7h6v6" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>', bars: '<svg viewBox="0 0 24 24"><path d="M5 20V10M11 20V4M17 20v-8M22 20H2" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>', pie: '<svg viewBox="0 0 24 24"><path d="M12 3v9h9A9 9 0 1112 3z" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/></svg>', down: '<svg viewBox="0 0 24 24"><path d="M3 7l6 6 4-4 8 8M15 17h6v-6" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>', bell: '<svg viewBox="0 0 24 24"><path d="M6 17h12l-1.5-2V10a4.5 4.5 0 00-9 0v5zM10 20h4" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>', chev: '<svg viewBox="0 0 24 24"><path d="M9 5l7 7-7 7" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>', list: '<svg viewBox="0 0 24 24"><path d="M6 3h9l4 4v14H6zM9 12h7M9 16h7" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>', ext: '<svg viewBox="0 0 24 24"><path d="M7 17L17 7M9 7h8v8" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>' };
  const all = () => [...C.D.positions, ...C.D.closed];
  const lineOf = p => C.H.lines.find(l => l.key === pkey(p));
  const open = () => C.D.positions.filter(p => p.qty > 0);
  const PER = [['1d', '1J'], ['1w', '1S'], ['1m', '1M'], ['3m', '3M'], ['6m', '6M'], ['1y', '1A'], ['2y', '2A'], ['3y', '3A'], ['5y', '5A'], ['all', 'Depuis le début']];
  const perName = k => (PER.find(x => x[0] === k) || [0, ''])[1];
  const perShort = k => k === 'all' ? 'totale' : perName(k);

  /* fenêtres : perso = historique du portefeuille ; marché = cours complets, indépendants des achats */
  const mk = () => C.H.market && C.H.market.dates ? C.H.market : { dates: [], lines: [] };
  const mDates = () => mk().dates.map(d => d.slice(0, 10));
  function win() { return S.mode === 'perso' ? PFM.resolveWindow(C.H, S.per, S.zoom) : PFM.resolveWindow({ dates: mDates() }, S.per, S.zoom); }
  function marketSeries(key, w) {
    const l = mk().lines.find(x => x.key === key); if (!l) return null;
    const ds = mDates(), pr = S.unit === 'pct' ? l.prices : (l.prices_eur || []), start = Math.max(0, w.i0), xs = [], ys = [];
    let base = null;
    if (S.unit === 'pct') for (let i = start; i <= w.i1; i++) if (isNum(l.prices[i])) { base = l.prices[i]; break; }
    for (let i = start; i <= w.i1; i++) { xs.push(ds[i]); const p = pr[i]; ys.push(!isNum(p) ? null : S.unit === 'pct' ? (base ? 100 * (p / base - 1) : null) : p); }
    return { x: xs, y: ys };
  }
  function strategyOf(p) { const lots = (C.D.lots || []).filter(l => p.listing_id ? l.listing_id === p.listing_id : l.symbol === p.symbol), set = [...new Set(lots.map(l => (l.alert && l.alert.strategy_label) || '').filter(Boolean))]; return set.length ? set : []; }
  const alertOf = p => { const i = (C.D.insights || {})[p.key] || {}; const t = p.levels && isNum(+p.levels.target) && +p.levels.target > 0 && p.price >= +p.levels.target; return t ? ['goal', 'Objectif atteint'] : i.status === 'act' ? ['act', 'À traiter'] : i.status === 'watch' ? ['watch', 'Vigilance'] : i.status === 'normal' ? ['ok', 'Normal'] : ['na', 'Données insuffisantes']; };

  function stats(w) {
    const H = C.H, pf = PFM.portfolio(H, w), t = C.D.totals, op = open();
    const rows = all().map(p => { const l = lineOf(p), r = l ? PFM.position(H, l, w) : { result: null }; return { p, l, r, key: pkey(p), contrib: PFM.contribution(r, pf), alert: alertOf(p), strat: strategyOf(p), first: l ? H.dates[PFM.firstActive(l)] : null }; });
    const best = rows.filter(r => isNum(r.contrib)).sort((a, b) => b.contrib - a.contrib)[0];
    const s = PFM.series(H, PFM.resolveWindow(H, 'all'), 'pf', 'perf'); let peak = 0, dd = 0; s.y.forEach(v => { if (isNum(v)) { const g = 1 + v / 100; peak = Math.max(peak, g); dd = Math.min(dd, g / peak - 1); } });
    return { pf, rows, best, dd: s.y.some(isNum) ? 100 * dd : null, t };
  }
  const alertCounts = rows => ({ act: rows.filter(r => r.p.qty > 0 && r.alert[0] === 'act').length, watch: rows.filter(r => r.p.qty > 0 && r.alert[0] === 'watch').length, goal: rows.filter(r => r.p.qty > 0 && r.alert[0] === 'goal').length });

  function head(st, w) {
    const { t, pf } = st, tg = t.total_gain, base = t.invested_total || 0;
    const hasP = isNum(pf.result) && S.mode === 'perso';
    return `<section class="px-hero"><div class="px-val"><span class="px-l">Valeur du portefeuille <button class="px-i" data-tip="Valeur de marché des titres détenus, en euros. Les liquidités ne sont pas gérées.">i</button></span><strong>${eur(t.value)}</strong><span class="px-pill ${cl(tg)}">${I.up}${sg(tg)} <small>(${pc(base > 0 && isNum(tg) ? 100 * tg / base : null)})</small></span></div>
      <dl class="px-kv"><div><dt>Capital investi</dt><dd>${eur(t.cost)}</dd></div><div><dt>Gains latents</dt><dd class="${cl(t.unrealized)}">${sg(t.unrealized)}</dd></div><div><dt>Gains réalisés</dt><dd class="${cl(t.realized)}">${sg(t.realized)}</dd></div><div><dt>Résultat total</dt><dd class="${cl(tg)}">${sg(tg)}</dd></div></dl></section>
      <section class="px-mini"><div class="px-m g">${I.up}<span>Perf. ${perName(S.per) === 'Depuis le début' ? 'depuis le début' : perName(S.per)}<b class="${cl(pf.pct)}">${pc(pf.pct)}</b></span></div><div class="px-m b">${I.bars}<span>Perf. depuis achat<b class="${cl(tg)}">${pc(base > 0 && isNum(tg) ? 100 * tg / base : null)}</b></span></div><div class="px-m p">${I.pie}<span>Meilleure contribution<b class="${cl(st.best && st.best.contrib)}">${st.best ? J.esc(st.best.p.symbol) + ' ' + pt(st.best.contrib) : '–'}</b></span></div><div class="px-m r">${I.down}<span>Recul max.<b class="down">${isNum(st.dd) ? pc(st.dd, 1) : '–'}</b></span></div></section>`;
  }
  function alertStrip(rows) {
    const c = alertCounts(rows);
    return `<a class="px-alerts" href="alertes.html?portfolio=${C.current}"><span class="px-ab">${I.bell}<b>Mes alertes</b></span><span><i class="n r">${c.act}</i>À traiter</span><span><i class="n o">${c.watch}</i>Vigilance</span><span><i class="n g">${c.goal}</i>Objectif atteint</span>${I.chev}</a>`;
  }

  /* graphique */
  function series(w, st) {
    const out = [], notes = []; let k = 0;
    if (S.mode === 'perso') {
      const s = PFM.series(C.H, w, 'pf', S.unit === 'pct' ? 'perf' : 'result'); if (s.note) notes.push(s.note);
      out.push({ id: 'pf', label: 'Portefeuille', color: '#2dd4bf', width: 3.2, x: s.x, y: s.y });
      open().forEach(p => { const l = lineOf(p); if (!l) return; const q = PFM.series(C.H, w, l.key, S.unit === 'pct' ? 'perf' : 'result'); out.push({ id: l.key, label: p.symbol, color: PAL[++k % PAL.length], width: 1.8, x: q.x, y: q.y, empty: !q.y.some(isNum) }); });
    } else open().forEach(p => { const q = marketSeries(pkey(p), w); if (!q) return; out.push({ id: pkey(p), label: p.symbol, color: PAL[k++ % PAL.length], width: 2, x: q.x, y: q.y, empty: !q.y.some(isNum) }); });
    return { out, notes };
  }
  function chartBlock(w, st) {
    const perso = S.mode === 'perso';
    return `<section class="px-box"><div class="px-top"><div class="px-tabs" id="px-mode"><button data-m="perso">${I.up}Performance personnelle</button><button data-m="market">${I.bars}Historique des cours</button></div><div class="px-seg" id="px-unit"><button data-u="eur">€</button><button data-u="pct">%</button></div></div>
      <div class="px-per" id="px-per">${PER.map(([k, l]) => `<button data-p="${k}" class="${!S.zoom && S.per === k ? 'on' : ''}">${l}</button>`).join('')}</div>
      <div id="px-chart" class="pfc"></div><div class="px-leg" id="px-leg"></div>
      <p class="px-note" id="px-note"></p></section>`;
  }
  function drawChart(w, st) {
    const { out, notes } = series(w, st), perso = S.mode === 'perso', unitEur = S.unit === 'eur';
    const base = out.slice().sort((a, b) => b.x.length - a.x.length)[0], dd = base ? base.x : [];
    const ser = out.map(s => ({ id: s.id, label: s.label, color: s.color, width: s.width, hidden: S.hidden.has(s.id), y: dd.map(d => { const i = s.x.indexOf(d); return i < 0 ? null : s.y[i]; }) }));
    const markers = perso ? (C.H.trades || []).filter(t => !t.note && dd.length && t.date >= dd[0] && t.date <= dd[dd.length - 1]).map(t => ({ date: t.date, sid: t.key, side: t.side, label: (t.side === 'sell' ? 'Vente ' : 'Achat ') + t.symbol })) : (C.H.trades || []).filter(t => !t.note && dd.length && t.date >= dd[0] && t.date <= dd[dd.length - 1]).map(t => ({ date: t.date, sid: t.key, side: t.side, label: (t.side === 'sell' ? 'Vente ' : 'Achat ') + t.symbol }));
    const fmt = unitEur ? (v => J.eur(v, 2)) : (v => pc(v, 2));
    PFC.draw(J.$('#px-chart'), { dates: dd, series: ser, markers, fmt, tick: unitEur ? (v => J.eur(v, 0)) : (v => J.num(v, 0) + ' %'), zero: !(!perso && unitEur), onZoom: (a, b) => { S.zoom = { from: a, to: b }; redraw(); }, emptyText: perso ? 'Votre historique personnel commence à votre première opération.' : 'Aucun cours disponible sur cette période.' });
    const last = s => { for (let i = s.y.length - 1; i >= 0; i--) if (isNum(s.y[i])) return s.y[i]; return null; };
    J.$('#px-leg').innerHTML = ser.map((s, i) => `<button type="button" class="px-chip ${s.hidden ? 'off' : ''}" data-sid="${J.esc(s.id)}"><i style="background:${s.color}"></i>${J.esc(s.label)} <b class="${cl(last(s))}">${isNum(last(s)) ? (unitEur ? J.eur(last(s), 2) : pc(last(s), 2)) : 'n/d'}</b></button>`).join('') + (S.zoom ? '<button class="px-chip on" id="px-reset">Réinitialiser le zoom</button>' : '');
    J.$$('#px-leg [data-sid]').forEach(b => b.onclick = () => { S.hidden.has(b.dataset.sid) ? S.hidden.delete(b.dataset.sid) : S.hidden.add(b.dataset.sid); drawChart(w, st); });
    J.$('#px-reset')?.addEventListener('click', () => { S.zoom = null; redraw(); });
    const span = w.startDate ? `${PFC.fr(w.startDate)} → ${PFC.fr(w.endDate)}` : '';
    const first = S.per === 'all' ? (perso ? ' « Depuis le début » = votre première opération.' : ' « Depuis le début » = premier cours disponible, avant vos achats.') : '';
    const unit = perso ? (unitEur ? 'Résultat cumulé en euros (gain moins gain de départ), achats et ventes neutralisés.' : 'Performance hors mouvements (portefeuille) et rendement du capital engagé (titres).') : (unitEur ? 'Cours réels convertis en euros au change du jour.' : 'Cours normalisés à 0 % au début de la période, dans la devise de chaque titre.');
    const miss = out.filter(s => s.empty).map(s => s.label + (perso ? ' : acheté après la période' : ' : pas de cours sur la période'));
    J.$('#px-note').textContent = [span && 'Période : ' + span + '.', first.trim(), unit, ...notes, ...miss].filter(Boolean).join(' ');
  }

  /* positions */
  const SORTS = { result_desc: ['Meilleurs résultats', r => r.r.result, -1], result_asc: ['Pires résultats', r => r.r.result, 1], perf_desc: ['Meilleure perf.', r => r.r.pct, -1], contrib_desc: ['Contribution +', r => r.contrib, -1], contrib_asc: ['Contribution −', r => r.contrib, 1], value: ['Valeur', r => r.p.value, -1], alpha: ['Alphabétique', () => null, 0] };
  function sorted(rows) { const [, f, dir] = SORTS[S.sort]; return rows.slice().sort((a, b) => { if (!dir) return a.p.symbol.localeCompare(b.p.symbol); const x = f(a), y = f(b), kx = isNum(x), ky = isNum(y); return kx !== ky ? (kx ? -1 : 1) : kx ? dir * (x - y) : 0; }); }
  function posBlock(st) {
    const rows = st.rows.filter(r => r.p.qty > 0), n = rows.length, closed = st.rows.length - n, eu = S.unit === 'eur';
    const bestK = st.best && st.best.key, worst = rows.filter(r => isNum(r.contrib)).sort((a, b) => a.contrib - b.contrib)[0];
    return `<section class="px-pos"><div class="px-ph"><h2>Mes positions <span>(${n})</span></h2><label>Trier : <select id="px-sort">${Object.entries(SORTS).map(([k, v]) => `<option value="${k}" ${S.sort === k ? 'selected' : ''}>${v[0]}</option>`).join('')}</select></label></div>
      <div class="px-cards">${sorted(rows).map((r, i) => { const { p } = r, color = PAL[(open().indexOf(p) + 1) % PAL.length], t = p.kind === 'etf' ? 'ETF' : 'Action', badge = r.key === bestK ? '<span class="px-tag up">Meilleur contributeur</span>' : worst && r.key === worst.key && worst.contrib < 0 ? '<span class="px-tag down">Pire contributeur</span>' : '';
        return `<article class="px-card" data-key="${J.esc(r.key)}" style="--c:${color}" tabindex="0"><div class="px-id"><b>${J.esc(p.symbol)}</b>${badge}<span>${J.esc(p.name_catalogue || p.name || '')}</span><small>${t}${p.country ? ' · ' + J.esc(p.country) : ''}</small>${p.listing_id ? `<a class="px-an" href="titre.html?id=${p.listing_id}&from=portefeuille" target="_blank" rel="noopener">Analyse du titre ${I.ext}</a>` : ''}</div>
        <div class="px-n"><span>Valeur</span><b>${eur(p.value)}</b></div><div class="px-n"><span>${eu ? 'Gain ' + perShort(S.per) : 'Perf. ' + perShort(S.per)}</span><b class="${cl(r.r.result)}">${eu ? sg(r.r.result) : pc(r.r.pct)}</b></div><div class="px-n"><span>Contribution</span><b class="${cl(r.contrib)}">${pt(r.contrib)}</b></div>
        <div class="px-s"><span>Stratégie</span>${r.strat.length ? r.strat.map(x => `<em class="px-st">${J.esc(x)}</em>`).join('') : '<em class="px-st na">Non renseignée</em>'}<em class="px-al ${r.alert[0]}">${I.bell}${r.alert[1]}</em></div>${I.chev}</article>`; }).join('') || '<p class="px-note">Aucune position ouverte.</p>'}</div>${closed ? `<p class="px-note">${closed} position(s) soldée(s) : gains réalisés conservés dans le résultat ; historique dans « Historique des transactions ».</p>` : ''}</section>`;
  }

  /* détail */
  function detail(st, w) {
    const x = st.rows.find(r => r.key === S.sel); if (!x || !x.l) return '';
    const { p, l, r } = x, closed = !(p.qty > 0), cur = p.price_currency || p.currency, peak = PFM.personalPeak(l), dd = PFM.drawdownFromHigh(C.H, l);
    const trades = (C.H.trades || []).filter(t => t.key === l.key && !t.note), lots = (C.D.lots || []).filter(lo => p.listing_id ? lo.listing_id === p.listing_id : lo.symbol === p.symbol);
    const re = (C.D.sales || []).filter(s => p.listing_id ? s.listing_id === p.listing_id : s.symbol === p.symbol).reduce((n, s) => n + (s.gain || 0), 0), kv = (k, v) => `<div><dt>${k}</dt><dd>${v}</dd></div>`;
    return `<section class="px-box px-detail" id="px-detail"><div class="px-ph"><h2>${J.esc(p.symbol)} <span>${J.esc(p.name_catalogue || p.name || '')}</span></h2><button class="px-x" id="px-close" aria-label="Fermer">✕</button></div>
      <div class="px-act">${p.listing_id ? `<a class="px-btn pri" href="titre.html?id=${p.listing_id}&from=portefeuille" target="_blank" rel="noopener">Analyse du titre ${I.ext}</a>` : ''}<button class="px-btn" data-buy="${J.esc(x.key)}">Acheter</button><button class="px-btn" data-sell="${J.esc(x.key)}" ${closed ? 'disabled' : ''}>Vendre</button><a class="px-btn" href="alertes.html?portfolio=${C.current}&listing=${p.listing_id || ''}">Alertes ${I.bell}</a></div>
      <dl class="px-kv2">${kv('Cours', closed ? '–' : J.money(p.price, cur))}${kv('Valeur', closed ? 'soldé' : eur(p.value))}${kv('Quantité', closed ? '0' : J.num(p.qty, 4))}${kv('PRU', closed ? '–' : eur(p.avg_cost))}${kv('Latent', closed ? '–' : `<span class="${cl(p.value - p.cost)}">${sg(p.value - p.cost)}</span>`)}${kv('Réalisé', `<span class="${cl(re)}">${sg(re)}</span>`)}${kv('Résultat · ' + perName(S.per), `<span class="${cl(r.result)}">${sg(r.result)} · ${pc(r.pct, 1)}</span>`)}${kv('Meilleur résultat', `${sg(peak.peak)}`)}${kv('Recul / sommet du cours', isNum(dd) ? pc(dd, 1) : '–')}${kv('Stratégie', x.strat.length ? x.strat.map(J.esc).join(', ') : 'Non renseignée')}</dl>
      <div class="px-per" id="px-dm">${[['result', 'Résultat'], ['perf', 'Perf. %'], ['market', 'Cours']].map(([k, lb]) => `<button data-m="${k}" class="${(S.dm || 'result') === k ? 'on' : ''}">${lb}</button>`).join('')}</div><div id="px-dchart" class="pfc"></div><p class="px-note" id="px-dnote"></p>
      <h3>Achats et ventes</h3><div class="px-list">${trades.map(t => `<div><span>${J.date(t.date)}</span><b>${t.side === 'sell' ? 'Vente' : 'Achat'}</b><span>${J.num(t.quantity, 4)} × ${J.num(t.unit_price, 4)} ${J.esc(t.currency || '')}</span><span>frais ${eur(t.fees_eur)}</span></div>`).join('') || '<p class="px-note">Aucune transaction.</p>'}</div>
      ${lots.length ? `<h3>Lots ouverts (FIFO)</h3><div class="px-list">${lots.map(lo => `<div><span>${J.date(lo.trade_at)}</span><b>${J.num(lo.remaining, 4)} titre(s)</b><span>${J.esc((lo.alert && lo.alert.strategy_label) || 'Stratégie non renseignée')}</span><button class="px-btn s" data-lot="${lo.tx_id}">Régler</button></div>`).join('')}</div>` : ''}</section>`;
  }
  function drawDetail(st) {
    const x = st.rows.find(r => r.key === S.sel); if (!x || !x.l) return; const dm = S.dm || 'result';
    const w = PFM.resolveWindow(C.H, S.per, S.zoom); let s, fmt = dm === 'result' ? (v => J.eur(v, 2)) : (v => pc(v, 2));
    if (dm === 'market') { const ww = PFM.resolveWindow({ dates: mDates() }, S.per, S.zoom), q = marketSeries(x.key, Object.assign({}, ww)); const keep = S.unit; S.unit = 'pct'; const q2 = marketSeries(x.key, ww); S.unit = keep; s = q2 || { x: [], y: [] }; } else s = PFM.series(C.H, w, x.l.key, dm);
    const mkr = (C.H.trades || []).filter(t => !t.note && t.key === x.l.key && s.x.length && t.date >= s.x[0] && t.date <= s.x[s.x.length - 1]).map(t => ({ date: t.date, sid: x.l.key, side: t.side, label: (t.side === 'sell' ? 'Vente ' : 'Achat ') + J.num(t.quantity, 4) }));
    PFC.draw(J.$('#px-dchart'), { dates: s.x, series: [{ id: x.l.key, label: x.p.symbol, color: '#2dd4bf', width: 2.4, y: s.y }], markers: mkr, fmt, tick: dm === 'result' ? (v => J.eur(v, 0)) : (v => J.num(v, 0) + ' %'), onZoom: (a, b) => { S.zoom = { from: a, to: b }; redraw(); }, emptyText: 'Aucune donnée sur cette période.' });
    J.$('#px-dnote').textContent = (dm === 'market' ? 'Cours du titre indépendant de vos achats, base 0 % au début. ' : 'Votre résultat personnel. ') + 'Période : ' + perName(S.per) + '.';
    J.$$('#px-dm [data-m]').forEach(b => b.onclick = () => { S.dm = b.dataset.m; redraw(); });
    J.$('#px-close').onclick = () => { S.sel = null; redraw(); };
    J.$$('#px-detail [data-lot]').forEach(b => b.onclick = () => C.helpers.lot(C.D.lots.find(lo => lo.tx_id == b.dataset.lot)));
  }

  function redraw() {
    if (!C || !C.H) return;
    const w = win(), st = stats(PFM.resolveWindow(C.H, S.mode === 'perso' ? S.per : S.per, S.mode === 'perso' ? S.zoom : null));
    C.host.innerHTML = `${head(st, w)}${alertStrip(st.rows)}${chartBlock(w, st)}${posBlock(st)}${detail(st, w)}<div class="px-links"><button class="px-link" id="px-hist">${I.list}<b>Historique des transactions</b>${I.chev}</button><a class="px-link" href="alertes.html?portfolio=${C.current}">${I.bell}<b>Centre d’alertes</b>${I.chev}</a></div>`;
    J.$$('#px-mode button').forEach(b => { b.classList.toggle('on', b.dataset.m === S.mode); b.onclick = () => { S.mode = b.dataset.m; S.zoom = null; store('mode', S.mode); redraw(); }; });
    J.$$('#px-unit button').forEach(b => { b.classList.toggle('on', b.dataset.u === S.unit); b.onclick = () => { S.unit = b.dataset.u; store('unit', S.unit); redraw(); }; });
    J.$$('#px-per [data-p]').forEach(b => b.onclick = () => { S.per = b.dataset.p; S.zoom = null; store('per', S.per); redraw(); });
    J.$('#px-sort').onchange = e => { S.sort = e.target.value; store('sort', S.sort); redraw(); };
    J.$$('.px-card').forEach(c => { const go = () => { S.sel = c.dataset.key; redraw(); const d = J.$('#px-detail'); d && d.scrollIntoView({ block: 'start', behavior: 'smooth' }); }; c.onclick = e => { if (!e.target.closest('a,button')) go(); }; c.onkeydown = e => { if (e.target === c && ['Enter', ' '].includes(e.key)) { e.preventDefault(); go(); } }; });
    J.$$('[data-buy],[data-sell]').forEach(b => b.onclick = e => { e.stopPropagation(); C.helpers.trade(b.dataset.buy || b.dataset.sell, b.dataset.sell ? 'sell' : 'buy'); });
    J.$$('.px-i').forEach(b => b.onclick = e => { e.preventDefault(); J.dialog({ title: 'Définition', body: `<p>${J.esc(b.dataset.tip)}</p>`, actions: [{ label: 'Fermer', run: () => { } }] }); });
    J.$('#px-hist').onclick = () => C.helpers.history();
    drawChart(w, st); if (S.sel) drawDetail(st);
  }
  function mount(host, ctx) { C = Object.assign({ host }, ctx); if (!ctx.keep) { S.zoom = null; S.hidden.clear(); } redraw(); }
  root.PFHome = { mount, redraw, state: S };
})(typeof window !== 'undefined' ? window : globalThis);
