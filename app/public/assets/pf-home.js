/* Accueil du Portefeuille V4 : synthèse, graphique global, tableau des positions, détail d'une position. Calculs dans pf-math.js, tracé dans pf-chart.js. */
(function (root) {
  'use strict';
  const PFM = root.PFM, PFC = root.PFChart;
  const PAL = ['#2563eb', '#f97316', '#16a34a', '#9333ea', '#e11d48', '#0891b2', '#ca8a04', '#db2777', '#4f46e5', '#65a30d', '#0d9488', '#b45309'];
  const store = (k, v) => { try { if (v === undefined) return JSON.parse(localStorage.getItem('jigo_pfh_' + k)); localStorage.setItem('jigo_pfh_' + k, JSON.stringify(v)); } catch (e) { return null; } };
  const S = { per: 'all', zoom: null, unit: store('unit') || 'eur', metric: store('metric') || null, scope: 'open', chartClosed: false, onlyPf: false, hidden: new Set(), sort: store('sort') || 'result_desc', sel: null, dmetric: 'result', cols: store('cols') || {} };
  let C = null;                                    // contexte : {D,H,host,helpers}
  const isNum = PFM.isNum;
  const pkey = p => p.listing_id ? String(p.listing_id) : 'S' + String(p.symbol).toUpperCase();
  const eur = (v, d = 2) => isNum(v) ? J.eur(v, d) : '–';
  const sg = v => isNum(v) ? (v > 0 ? '+' : v < 0 ? '−' : '') + J.eur(Math.abs(v), 2) : '–';
  const pc = (v, d = 1) => isNum(v) ? (v > 0 ? '+' : v < 0 ? '−' : '') + J.num(Math.abs(v), d) + ' %' : '–';
  const pts = v => isNum(v) ? (v > 0 ? '+' : v < 0 ? '−' : '') + J.num(Math.abs(v), 2) + ' pt' : '–';
  const cl = v => isNum(v) ? (v > 0.0049 ? 'up' : v < -0.0049 ? 'down' : '') : 'muted';
  const info = t => `<button type="button" class="pf-i" aria-label="Explication" data-tip="${J.esc(t)}">i</button>`;
  const metricsFor = u => u === 'eur' ? [['result', 'Résultat'], ['value', 'Valeur']] : [['perf', 'Performance personnelle'], ['market', 'Cours rebasé']];
  const metric = () => { const m = metricsFor(S.unit).map(x => x[0]); return m.includes(S.metric) ? S.metric : m[0]; };
  const unitFmt = m => m === 'value' || m === 'result' ? (v => J.eur(v, 2)) : (v => pc(v, 2));

  function all() { return [...C.D.positions, ...C.D.closed]; }
  function lineOf(p) { return C.H.lines.find(l => l.key === pkey(p)); }
  function inScope(p) { const closed = !(p.qty > 0); return S.scope === 'all' || (S.scope === 'open' ? !closed : closed); }
  function win() { return PFM.resolveWindow(C.H, S.per, S.zoom); }
  const perLabel = w => w.zoom ? 'Zoom ' + PFC.fr(w.startDate) + ' → ' + PFC.fr(w.endDate) : (PFM.PERIODS.find(x => x[0] === S.per) || [0, ''])[1];

  /* ── Données de la page ── */
  function rows(w, pf) {
    return all().filter(inScope).map(p => {
      const l = lineOf(p), r = l ? PFM.position(C.H, l, w) : { result: null, reason: 'Aucune ligne dans l’historique.' };
      const ins = (C.D.insights || {})[p.key] || { status: 'unknown', label: 'Données insuffisantes' };
      const active = l && w.i1 >= 0 && PFM.firstActive(l) !== null && PFM.firstActive(l) <= w.i1;
      return { p, l, r, ins, key: pkey(p), contrib: PFM.contribution(r, pf), dd: l ? PFM.drawdownFromHigh(C.H, l) : null, active, first: l ? (C.H.dates[PFM.firstActive(l)] || null) : null };
    });
  }

  /* ── Synthèse ── */
  function overview(w, pf) {
    const t = C.D.totals, tx = C.D.transactions_list || [];
    const buys = tx.filter(x => x.side === 'buy').reduce((n, x) => n + (+x.quantity * +x.unit_price * +x.fx_to_eur + +x.fees), 0);
    const sells = (C.D.sales || []).reduce((n, x) => n + (x.proceeds || 0), 0);
    const totalGain = t.total_gain, base = t.invested_total || 0;
    const card = (cls, label, big, sub, tip) => `<div class="pf-card ${cls || ''}"><span class="pf-l">${label}${tip ? info(tip) : ''}</span><strong>${big}</strong><small>${sub || ''}</small></div>`;
    const approx = pf.approxEnd ? ' · dernière valorisation fiable' : '';
    return `<section class="pf-cards" aria-label="Synthèse">
      ${card('', 'Valeur totale', eur(t.value), 'Titres détenus, valorisés au dernier cours', 'Valeur de marché des titres encore détenus, convertie en euros. Les liquidités ne sont pas gérées.')}
      ${card('', 'Capital investi', eur(t.cost), `Achats cumulés ${eur(buys, 0)} · Ventes encaissées ${eur(sells, 0)}`, 'Capital engagé = prix de revient (PMP, frais compris) des positions ouvertes. Achats cumulés : tout ce qui a été acheté depuis le début. Ventes : produit net encaissé.')}
      ${card(cl(t.unrealized), 'Gains latents', sg(t.unrealized), 'Positions ouvertes, non encaissé', 'Valeur actuelle moins prix de revient des positions ouvertes (frais et change inclus).')}
      ${card(cl(t.realized), 'Gains réalisés', sg(t.realized), 'Ventes déjà faites', 'Produit net des ventes moins le prix de revient moyen pondéré des titres vendus, frais compris.')}
      ${card(cl(totalGain), 'Gain total', sg(totalGain), `Rendement sur achats cumulés : <b>${pc(base > 0 && isNum(totalGain) ? 100 * totalGain / base : null)}</b>`, 'Gain total = latent + réalisé. Rendement = gain total ÷ achats cumulés (' + eur(base, 0) + ', frais compris). Ce n’est pas une performance annualisée.')}
      ${card(cl(pf.result), 'Résultat · ' + perLabel(w), sg(pf.result), `Performance hors mouvements : <b class="${cl(pf.pct)}">${isNum(pf.pct) ? pc(pf.pct, 2) : 'indisponible'}</b>${approx}`, 'Résultat de la période = gain à la fin moins gain au début : les apports et retraits ne comptent pas. Performance hors mouvements : rendements quotidiens chaînés (Dietz modifié), neutre vis-à-vis des achats et ventes. ' + (pf.pctReason || ''))}
    </section>${w.clipped ? `<p class="pf-note">La période demandée commence avant votre première opération : les chiffres couvrent ${PFC.fr(w.startDate)} → ${PFC.fr(w.endDate)}.</p>` : ''}${isNum(pf.pct) || !pf.pctReason ? '' : `<p class="pf-note">${J.esc(pf.pctReason)}</p>`}`;
  }

  /* ── Graphique ── */
  function seriesSet(w, rs) {
    const m = metric(), out = [], notes = [];
    if (m !== 'market') { const s = PFM.series(C.H, w, 'pf', m); if (s.note) notes.push(s.note); out.push({ id: 'pf', label: 'Portefeuille', color: '#0b1f44', width: 3.4, x: s.x, y: s.y }); }
    else notes.push('Le portefeuille n’a pas de cours de marché unique : seuls les titres sont tracés.');
    if (!S.onlyPf) {
      const want = all().filter(p => { const closed = !(p.qty > 0); return closed ? S.chartClosed : true; }).filter(p => S.scope === 'all' || S.scope === 'closed' || p.qty > 0 || S.chartClosed);
      want.forEach((p, k) => {
        const l = lineOf(p); if (!l) return; const s = PFM.series(C.H, w, l.key, m);
        const n = s.y.filter(isNum).length;
        out.push({ id: l.key, label: p.symbol, name: p.name_catalogue || p.name || p.symbol, color: PAL[k % PAL.length], width: 1.7, x: s.x, y: s.y, closed: !(p.qty > 0), empty: !n });
        if (!n) { const r = PFM.firstActive(l); notes.push(p.symbol + ' : ' + (r !== null && r > w.i1 ? 'acheté après la fin de la période affichée.' : (PFM.reasonFor(C.H, l)))); }
        else if (s.note) notes.push(p.symbol + ' : ' + s.note);
      });
    }
    return { out, notes };
  }
  function chartBlock() { return `<section class="pf-box" aria-label="Évolution"><div class="pf-bar"><h2>Évolution</h2><div class="pf-seg" id="pfh-unit" role="group" aria-label="Unité"><button data-u="eur">€</button><button data-u="pct">%</button></div><div class="pf-seg" id="pfh-metric" role="group" aria-label="Mesure"></div>${info('€ : résultat cumulé de la période (gain moins gain de départ) ou valeur des titres. % : performance personnelle (résultat ÷ capital engagé) ou cours de marché rebasé à 0 % au début. Un cours en € n’est jamais mélangé à la valeur du portefeuille.')}</div><div class="pf-bar small" id="pfh-leg-tools"></div><div id="pfh-chart" class="pfc"></div><div class="pf-legend" id="pfh-legend"></div><p class="pf-note" id="pfh-notes" role="status"></p></section>`; }
  function drawChart(w, rs) {
    const { out, notes } = seriesSet(w, rs), H = C.H, m = metric();
    const dates = out.length ? out[0].x : [];
    const base = out.find(s => s.x.length) || out[0];
    const dd = base ? base.x : [];
    const series = out.map(s => ({ id: s.id, label: s.label, color: s.color, width: s.width, y: s.x.length === dd.length ? s.y : dd.map(d => { const i = s.x.indexOf(d); return i < 0 ? null : s.y[i]; }), hidden: S.hidden.has(s.id), dim: s.closed }));
    const mk = (H.trades || []).filter(t => !t.note && dd.length && t.date >= dd[0] && t.date <= dd[dd.length - 1]).map(t => ({ date: t.date, sid: m === 'market' ? t.key : (S.onlyPf ? 'pf' : t.key), side: t.side, label: (t.side === 'sell' ? 'Vente ' : 'Achat ') + t.symbol + ' · ' + J.num(t.quantity, 4) + ' titre(s)' }));
    PFC.draw(J.$('#pfh-chart'), { dates: dd, series, markers: mk, fmt: unitFmt(m), tick: m === 'value' || m === 'result' ? (v => J.eur(v, 0)) : (v => J.num(v, 0) + ' %'), onZoom: (a, b) => { S.zoom = { from: a, to: b }; redraw(); }, emptyText: 'Aucune donnée valorisable sur cette période.' });
    J.$('#pfh-legend').innerHTML = out.map(s => `<button type="button" class="pf-chip ${S.hidden.has(s.id) ? 'off' : ''} ${s.empty ? 'na' : ''}" data-sid="${J.esc(s.id)}" aria-pressed="${!S.hidden.has(s.id)}"><i style="background:${s.color}"></i>${J.esc(s.label)}${s.closed ? ' <small>soldé</small>' : ''}${s.empty ? ' <small>n/d</small>' : ''}</button>`).join('');
    J.$$('#pfh-legend [data-sid]').forEach(b => b.onclick = () => { S.hidden.has(b.dataset.sid) ? S.hidden.delete(b.dataset.sid) : S.hidden.add(b.dataset.sid); drawChart(w, rs); });
    J.$('#pfh-leg-tools').innerHTML = `<button class="btn small" id="pfh-all">Tout afficher</button><button class="btn small ${S.onlyPf ? 'primary' : ''}" id="pfh-only">Portefeuille seul</button><label class="chk"><input type="checkbox" id="pfh-closed" ${S.chartClosed ? 'checked' : ''}> Inclure les titres soldés</label>${S.zoom ? '<button class="btn small primary" id="pfh-reset">Réinitialiser le zoom</button>' : '<span class="small muted">Glissez sur le graphique pour zoomer.</span>'}`;
    J.$('#pfh-all').onclick = () => { S.hidden.clear(); S.onlyPf = false; redraw(); };
    J.$('#pfh-only').onclick = () => { S.onlyPf = !S.onlyPf; redraw(); };
    J.$('#pfh-closed').onchange = e => { S.chartClosed = e.target.checked; redraw(); };
    J.$('#pfh-reset')?.addEventListener('click', () => { S.zoom = null; redraw(); });
    const per = `Période affichée : ${perLabel(w)} (${PFC.fr(w.startDate)} → ${PFC.fr(w.endDate)}), identique au tableau et aux chiffres.`;
    J.$('#pfh-notes').innerHTML = J.esc([per, ...notes, ...(C.H.notes || [])].join(' '));
  }

  /* ── Tableau ── */
  const SORTS = { result_desc: ['Meilleurs résultats', r => r.r.result, -1], result_asc: ['Pires résultats', r => r.r.result, 1], perf_desc: ['Meilleure performance', r => r.r.pct, -1], perf_asc: ['Pire performance', r => r.r.pct, 1], contrib_desc: ['Plus forte contribution +', r => r.contrib, -1], contrib_asc: ['Plus forte contribution −', r => r.contrib, 1], weight: ['Poids', r => r.p.weight, -1], alpha: ['Ordre alphabétique', r => null, 0] };
  function sorted(list) { const [, f, dir] = SORTS[S.sort] || SORTS.result_desc; return list.slice().sort((a, b) => { if (!dir) return a.p.symbol.localeCompare(b.p.symbol); const x = f(a), y = f(b), kx = isNum(x), ky = isNum(y); return kx !== ky ? (kx ? -1 : 1) : kx ? dir * (x - y) || a.p.symbol.localeCompare(b.p.symbol) : a.p.symbol.localeCompare(b.p.symbol); }); }
  const COLS = [['first', 'Premier achat'], ['qty', 'Quantité'], ['pru', 'PRU'], ['price', 'Cours'], ['value', 'Valeur'], ['weight', 'Poids'], ['period', 'Période'], ['since', 'Depuis l’achat'], ['contrib', 'Contribution'], ['dd', 'Recul / plus haut'], ['alert', 'Alerte']];
  const colOn = k => S.cols[k] !== false;
  function tableBlock(rs, w, pf) {
    const counts = { open: all().filter(p => p.qty > 0).length, closed: all().filter(p => !(p.qty > 0)).length };
    const eu = S.unit === 'eur';
    const head = `<div class="pf-bar"><h2>Mes positions</h2><div class="pf-seg" id="pfh-scope" role="group"><button data-s="open">Ouvertes <b>${counts.open}</b></button><button data-s="closed">Soldées <b>${counts.closed}</b></button><button data-s="all">Toutes <b>${counts.open + counts.closed}</b></button></div><label class="small">Trier <select id="pfh-sort">${Object.entries(SORTS).map(([k, v]) => `<option value="${k}" ${S.sort === k ? 'selected' : ''}>${v[0]}</option>`).join('')}</select></label><details class="pf-cols"><summary>Colonnes</summary><div>${COLS.map(([k, l]) => `<label><input type="checkbox" data-col="${k}" ${colOn(k) ? 'checked' : ''}> ${l}</label>`).join('')}</div></details></div>`;
    const th = (k, l, cls) => colOn(k) ? `<th class="${cls || ''}">${l}</th>` : '';
    const body = sorted(rs).map(x => {
      const { p, r, ins } = x, cur = p.price_currency || p.currency, closed = !(p.qty > 0);
      const periodCell = eu ? sg(r.result) : pc(r.pct, 1), sinceCell = eu ? sg(r.sinceBuy) : pc(r.sinceBuyPct, 1), conCell = eu ? sg(r.result) : pts(x.contrib);
      const td = (k, label, v, cls) => colOn(k) ? `<td data-label="${label}" class="num ${cls || ''}">${v}</td>` : '';
      return `<tr data-key="${J.esc(x.key)}" class="${S.sel === x.key ? 'sel' : ''} ${closed ? 'closed' : ''}" tabindex="0"><td class="tt"><b>${J.esc(p.symbol)}</b> <span>${J.esc(p.name_catalogue || p.name || '')}</span>${closed ? ' <span class="badge">Soldé</span>' : ''}${x.r.result === null && x.r.reason ? `<small class="muted">${J.esc(x.r.reason)}</small>` : ''}</td>
        ${td('first', 'Premier achat', x.first ? J.date(x.first) : '–')}${td('qty', 'Quantité', closed ? '0' : J.num(p.qty, 4))}${td('pru', 'PRU', closed ? '–' : eur(p.avg_cost))}${td('price', 'Cours', closed ? '–' : J.money(p.price, cur))}${td('value', 'Valeur', closed ? '–' : eur(p.value))}${td('weight', 'Poids', closed ? '–' : J.num(p.weight, 1) + ' %')}
        ${td('period', 'Période', periodCell, cl(eu ? r.result : r.pct))}${td('since', 'Depuis l’achat', sinceCell, cl(r.sinceBuy))}${td('contrib', 'Contribution', conCell, cl(x.contrib))}${td('dd', 'Recul / plus haut', isNum(x.dd) && !closed ? pc(x.dd, 1) : '–', cl(x.dd))}
        ${colOn('alert') ? `<td data-label="Alerte">${closed ? '–' : `<span class="badge ${({ normal: 'ok', watch: 'wait', act: 'ko' })[ins.status] || ''}">${J.esc(ins.label || 'Données insuffisantes')}</span>`}</td>` : ''}
        <td class="act"><a class="btn small" href="${p.listing_id ? 'titre.html?id=' + p.listing_id + '&from=portefeuille' : '#'}" ${p.listing_id ? '' : 'hidden'} title="Ouvrir la même analyse que dans l’Explorer">Analyse du titre</a> <button class="btn small" data-buy="${J.esc(x.key)}">Acheter</button> <button class="btn small" data-sell="${J.esc(x.key)}" ${closed ? 'disabled' : ''}>Vendre</button></td></tr>`;
    }).join('') || `<tr><td colspan="14" class="empty">Aucune position dans ce filtre.</td></tr>`;
    const wp = eu ? 'Résultat sur la période' : 'Rendement sur la période';
    return `<section class="pf-box" aria-label="Positions">${head}<div class="pf-tw"><table class="pf-table"><thead><tr><th>Titre</th>${th('first', 'Premier achat')}${th('qty', 'Qté', 'num')}${th('pru', 'PRU', 'num')}${th('price', 'Cours', 'num')}${th('value', 'Valeur', 'num')}${th('weight', 'Poids', 'num')}${th('period', wp + ' · ' + perLabel(w), 'num')}${th('since', 'Depuis l’achat', 'num')}${th('contrib', eu ? 'Contribution (€)' : 'Contribution (pts)', 'num')}${th('dd', 'Recul', 'num')}${colOn('alert') ? '<th>Alerte</th>' : ''}<th></th></tr></thead><tbody>${body}</tbody></table></div><p class="pf-note">${eu ? 'Les résultats en euros s’additionnent : la somme des positions vaut le résultat du portefeuille.' : 'Rendement d’une position = résultat ÷ (valeur de départ + achats de la période). Contribution en points = résultat de la position ÷ capital engagé du portefeuille.'} Recul : écart au plus haut cours depuis le premier achat.</p></section>`;
  }

  /* ── Détail d'une position ── */
  function detailBlock(rs, w, pf) {
    const x = rs.find(r => r.key === S.sel) || (all().filter(p => pkey(p) === S.sel).map(p => ({ p, l: lineOf(p), key: S.sel, r: lineOf(p) ? PFM.position(C.H, lineOf(p), w) : {}, ins: (C.D.insights || {})[p.key] || {}, contrib: null, dd: null }))[0]);
    if (!x || !x.l) return '';
    const { p, l, r, ins } = x, closed = !(p.qty > 0), cur = p.price_currency || p.currency, peak = PFM.personalPeak(l), m = ins.market || {};
    const trades = (C.H.trades || []).filter(t => t.key === l.key && !t.note);
    const lots = (C.D.lots || []).filter(lo => p.listing_id ? lo.listing_id === p.listing_id : lo.symbol === p.symbol);
    const pr = (C.D.sales || []).filter(s => p.listing_id ? s.listing_id === p.listing_id : s.symbol === p.symbol).reduce((n, s) => n + (s.gain || 0), 0);
    const stat = (k, v) => `<div><dt>${k}</dt><dd>${v}</dd></div>`;
    const trend = { strong: 'hausse forte', steady: 'hausse soutenue', gentle: 'hausse douce', flat: 'pas de tendance nette', down: 'baisse' }[m.trend] || 'non mesurée';
    return `<section class="pf-box pf-detail" id="pfh-detail" aria-label="Détail de la position"><div class="pf-bar"><h2>${J.esc(p.symbol)} · ${J.esc(p.name_catalogue || p.name || '')}</h2><span class="badge">${J.esc(p.kind === 'etf' ? 'ETF' : 'Action')}</span>${p.listing_id ? `<a class="btn small primary" href="titre.html?id=${p.listing_id}&from=portefeuille">Analyse du titre</a>` : ''}<button class="btn small" id="pfh-close">Fermer</button></div>
      <dl class="pf-facts">${stat('Cours', closed ? '–' : J.money(p.price, cur))}${stat('Quantité', closed ? '0 (soldé)' : J.num(p.qty, 4))}${stat('Valeur', closed ? '–' : eur(p.value))}${stat('Gain total', `<b class="${cl(r.sinceBuy)}">${sg(r.sinceBuy)}</b>`)}${stat('Résultat · ' + perLabel(w), `<b class="${cl(r.result)}">${sg(r.result)} · ${pc(r.pct, 1)}</b>`)}</dl>
      <div class="pf-bar small"><div class="pf-seg" id="pfh-dm" role="group">${[['result', 'Résultat'], ['value', 'Valeur'], ['perf', 'Perf. %'], ['market', 'Cours rebasé']].map(([k, lb]) => `<button data-m="${k}" class="${S.dmetric === k ? 'on' : ''}">${lb}</button>`).join('')}</div></div><div id="pfh-dchart" class="pfc"></div><p class="pf-note" id="pfh-dnote"></p>
      <div class="pf-two"><div><h3>Mon résultat</h3><dl class="pf-facts col">${stat('Coût restant (PMP)', closed ? '–' : eur(p.cost))}${stat('Gain latent', closed ? '–' : sg(p.value - p.cost))}${stat('Gain réalisé', sg(pr))}${stat('Meilleur résultat observé', `${sg(peak.peak)}${peak.idx !== null ? ' le ' + PFC.fr(C.H.dates[peak.idx]) : ''}`)}${stat('Recul depuis ce maximum', `<b class="${cl(peak.drop)}">${sg(peak.drop)}</b>`)}${stat('Recul du cours depuis le plus haut', isNum(x.dd) ? pc(x.dd, 1) : '–')}</dl></div>
      <div><h3>État du titre</h3>${!m.reliable && !closed ? '<p class="small muted">Données anciennes ou incomplètes : indicateurs non fiables.</p>' : ''}<dl class="pf-facts col">${stat('Tendance 1 mois', closed ? '–' : trend)}${stat('Momentum 6 mois', closed ? '–' : pc(m.momentum_6m, 1))}${stat('Volatilité 3 mois', closed || !isNum(m.volatility) ? '–' : J.num(m.volatility, 2) + ' %/séance')}${stat('Cours / moyenne 50 j', closed || !isNum(m.close) ? '–' : (m.close >= m.ma50 ? 'au-dessus' : 'sous') + ' (' + J.money(m.ma50, cur) + ')')}${stat('Statut de surveillance', J.esc(ins.label || 'Données insuffisantes'))}</dl></div></div>
      <h3>Transactions et lots</h3><div class="pf-tw"><table class="pf-table"><thead><tr><th>Date</th><th>Opération</th><th class="num">Quantité</th><th class="num">Prix</th><th class="num">Frais</th></tr></thead><tbody>${trades.map(t => `<tr><td>${J.date(t.date)}</td><td>${t.side === 'sell' ? 'Vente' : t.first_buy ? 'Premier achat' : 'Achat'}</td><td class="num">${J.num(t.quantity, 4)}</td><td class="num">${J.num(t.unit_price, 4)} ${J.esc(t.currency || '')}</td><td class="num">${eur(t.fees_eur)}</td></tr>`).join('') || '<tr><td colspan="5">Aucune transaction.</td></tr>'}</tbody></table></div>
      ${lots.length ? `<p class="small muted">Lots ouverts (ordre d’arrivée, pour les alertes) : ${lots.map(lo => `${J.date(lo.trade_at)} · ${J.num(lo.remaining, 4)} titre(s) <button class="btn small" data-lot="${lo.tx_id}">Régler</button>`).join(' · ')}</p>` : ''}
      <p class="small muted">Gain réalisé et prix de revient : méthode du prix de revient moyen pondéré. Les lots servent aux alertes et au suivi.</p></section>`;
  }
  function drawDetail(w) {
    const x = all().filter(p => pkey(p) === S.sel)[0]; if (!x) return; const l = lineOf(x); if (!l) return;
    const s = PFM.series(C.H, w, l.key, S.dmetric), fmt = unitFmt(S.dmetric);
    const mk = (C.H.trades || []).filter(t => !t.note && t.key === l.key && s.x.length && t.date >= s.x[0] && t.date <= s.x[s.x.length - 1]).map(t => ({ date: t.date, sid: l.key, side: t.side, label: (t.side === 'sell' ? 'Vente ' : 'Achat ') + J.num(t.quantity, 4) + ' titre(s)' }));
    PFC.draw(J.$('#pfh-dchart'), { dates: s.x, series: [{ id: l.key, label: x.symbol, color: '#2563eb', width: 2.4, y: s.y }], markers: mk, fmt, tick: S.dmetric === 'value' || S.dmetric === 'result' ? (v => J.eur(v, 0)) : (v => J.num(v, 0) + ' %'), onZoom: (a, b) => { S.zoom = { from: a, to: b }; redraw(); }, emptyText: 'Position non valorisable sur cette période.' });
    J.$('#pfh-dnote').textContent = (s.note ? s.note + ' ' : '') + (S.dmetric === 'market' ? 'Cours du titre dans sa devise, base 0 % au début : hors frais et change.' : 'Période : ' + perLabel(w) + '. Les flèches marquent vos achats (vert) et ventes (rouge).');
    J.$$('#pfh-dm [data-m]').forEach(b => b.onclick = () => { S.dmetric = b.dataset.m; redraw(); });
    J.$('#pfh-close').onclick = () => { S.sel = null; redraw(); };
    J.$$('#pfh-detail [data-lot]').forEach(b => b.onclick = () => C.helpers.lot(C.D.lots.find(lo => lo.tx_id == b.dataset.lot)));
  }

  /* ── Montage ── */
  function periodBar() { return `<div class="pf-bar pf-period" role="group" aria-label="Période commune">${PFM.PERIODS.map(([k, l]) => `<button type="button" data-p="${k}" class="${!S.zoom && S.per === k ? 'on' : ''}">${l}</button>`).join('')}${S.zoom ? `<button type="button" class="on" id="pfh-unz">Zoom actif · réinitialiser</button>` : ''}</div>`; }
  function redraw() {
    if (!C || !C.H) return;
    const w = win(), pf = PFM.portfolio(C.H, w), rs = rows(w, pf);
    C.host.innerHTML = `${periodBar()}${overview(w, pf)}${chartBlock()}${tableBlock(rs, w, pf)}${S.sel ? detailBlock(rs, w, pf) : ''}`;
    J.$$('.pf-period [data-p]').forEach(b => b.onclick = () => { S.per = b.dataset.p; S.zoom = null; redraw(); });
    J.$('#pfh-unz')?.addEventListener('click', () => { S.zoom = null; redraw(); });
    J.$$('#pfh-unit button').forEach(b => { b.classList.toggle('on', b.dataset.u === S.unit); b.onclick = () => { S.unit = b.dataset.u; S.metric = null; store('unit', S.unit); redraw(); }; });
    J.$('#pfh-metric').innerHTML = metricsFor(S.unit).map(([k, l]) => `<button data-m="${k}" class="${metric() === k ? 'on' : ''}">${l}</button>`).join('');
    J.$$('#pfh-metric button').forEach(b => b.onclick = () => { S.metric = b.dataset.m; store('metric', S.metric); redraw(); });
    J.$$('#pfh-scope button').forEach(b => { b.classList.toggle('on', b.dataset.s === S.scope); b.onclick = () => { S.scope = b.dataset.s; redraw(); }; });
    J.$('#pfh-sort').onchange = e => { S.sort = e.target.value; store('sort', S.sort); redraw(); };
    J.$$('[data-col]').forEach(c => c.onchange = () => { S.cols[c.dataset.col] = c.checked; store('cols', S.cols); redraw(); });
    J.$$('.pf-table tbody tr[data-key]').forEach(tr => { const open = () => { S.sel = tr.dataset.key; redraw(); const d = J.$('#pfh-detail'); d && d.scrollIntoView({ block: 'nearest', behavior: 'smooth' }); }; tr.onclick = e => { if (!e.target.closest('a,button')) open(); }; tr.onkeydown = e => { if (e.target === tr && ['Enter', ' '].includes(e.key)) { e.preventDefault(); open(); } }; });
    J.$$('[data-buy],[data-sell]').forEach(b => b.onclick = e => { e.stopPropagation(); C.helpers.trade(b.dataset.buy || b.dataset.sell, b.dataset.sell ? 'sell' : 'buy'); });
    J.$$('.pf-i').forEach(b => b.onclick = e => { e.stopPropagation(); J.dialog({ title: 'Définition', body: `<p>${J.esc(b.dataset.tip)}</p>`, actions: [{ label: 'Fermer', run: () => { } }] }); });
    drawChart(w, rs); if (S.sel) drawDetail(w);
  }
  function mount(host, ctx) { C = Object.assign({ host }, ctx); if (!ctx.keep) { S.zoom = null; S.hidden.clear(); } redraw(); }
  root.PFHome = { mount, redraw, state: S };
})(typeof window !== 'undefined' ? window : globalThis);
