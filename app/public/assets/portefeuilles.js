/* Page Portefeuilles — l'essentiel d'abord : valeur et gain, courbe compacte, ce qui fait bouger, positions ; le reste replié. */
(async () => {
  const user = await J.init('portefeuilles'); if (!user) return;
  const page = J.$('#page');
  let list = (await J.api('portfolios')).portfolios;
  let current = +new URLSearchParams(location.search).get('id') || (list.find(p => p.is_default) || list[0] || {}).id;
  const NAMES = { regular: 'Croissance régulière', fast: 'Croissance rapide', recovery: 'Rebond', low_volatility: 'Hausse calme', momentum: 'Momentum 6 mois (essai)', momentum12: 'Momentum 12 mois (essai)', momentum_risk: 'Momentum ajusté du risque (essai)' };
  const PAL = ['#6366f1', '#14b8a6', '#f59e0b', '#ec4899', '#3b82f6', '#84cc16', '#a855f7', '#ef4444', '#06b6d4', '#eab308', '#64748b', '#22c55e'];
  const store = (k, v) => { try { if (v === undefined) return JSON.parse(localStorage.getItem('jigo_pf_' + k)); localStorage.setItem('jigo_pf_' + k, JSON.stringify(v)); } catch (e) { return null; } };
  const EVO = { mode: ['value', 'gain', 'titles'].includes(store('evo_mode')) ? store('evo_mode') : 'value', per: store('evo_per') || 'all', hidden: new Set(store('evo_hidden') || []) };
  const PERIODS = [['1d', '1 J', 0], ['1w', '1 S', 8], ['1m', '1 M', 31], ['3m', '3 M', 92], ['6m', '6 M', 183], ['1y', '1 A', 366], ['all', 'Tout', 0]];
  const px = (v, c) => v === null || v === undefined ? '–' : J.money(v, c || 'EUR');
  const eur0 = v => J.eur(v, 0), sgn = v => (v > 0 ? '+' : v < 0 ? '−' : '') + J.eur(Math.abs(v), 0);
  const pills = (id, items, cur) => `<div class="pills" id="${id}">${items.map(([k, l]) => `<button type="button" data-v="${k}" class="${k === cur ? 'on' : ''}">${l}</button>`).join('')}</div>`;
  const splitNotice = positions => positions.filter(p => p.splits_applied && p.splits_applied.length).map(p => `<div class="notice" style="margin-top:12px"><b>${J.esc(p.name_catalogue || p.name || p.symbol)}</b> : ${p.splits_applied.map(a => a.ratio >= 1 ? `split ${J.num(a.ratio, 2)} pour 1` : `regroupement ${J.num(1 / a.ratio, 2)} pour 1`).join(', ')} pris en compte automatiquement : la quantité affichée est celle d’aujourd’hui, le prix de revient total est inchangé.</div>`).join('');
  const LEVEL = { info: ['info', 'Info'], watch: ['wait', 'À surveiller'], act: ['ko', 'À examiner'] };
  const worstFor = (lots, lid) => (lots || []).filter(l => l.listing_id == lid && l.alert && l.alert.level).map(l => l.alert).sort((a, b) => ['info', 'watch', 'act'].indexOf(b.level) - ['info', 'watch', 'act'].indexOf(a.level))[0] || null;
  let D = null, H = null;                       // données du portefeuille affiché, et son évolution (chargée à part)

  /* ── Blocs repliables : un clic sur l'en-tête ; choix mémorisé dans ce navigateur. Par défaut, seuls l'essentiel et les positions sont ouverts. ── */
  const FOLD_DEFAULT = { etf: true, alloc: true, lots: true, sales: true, tx: true, settings: true };
  const section = (id, title, extra, body, cls = '') => `<section class="card fold ${cls}" data-fold="${id}"><header class="fold-h"><h2>${title}</h2><div class="fold-x">${extra || ''}</div><span class="chev" aria-hidden="true"></span></header><div class="fold-b">${body}</div></section>`;
  function folds() {
    const saved = Object.assign({}, FOLD_DEFAULT, store('folds2') || {});
    J.$$('#page [data-fold]').forEach(c => {
      c.classList.toggle('folded', !!saved[c.dataset.fold]);
      const h = c.querySelector('.fold-h') || c.firstElementChild; if (!h) return;
      h.classList.add('fold-h');
      h.addEventListener('click', e => { if (e.target.closest('button, a, input, select, .pills')) return; c.classList.toggle('folded'); const f = Object.assign({}, FOLD_DEFAULT, store('folds2') || {}); f[c.dataset.fold] = c.classList.contains('folded'); store('folds2', f); if (c.dataset.fold === 'hero' && !c.classList.contains('folded')) drawEvo(); });
    });
  }

  /* ── En-tête : valeur, gain total, variation du jour ── */
  function hero(d) {
    const t = d.totals, gain = t.total_gain, base = t.invested_total || 0;
    const realizedTaxBase = Object.values(d.realized_by_year || {}).reduce((s, g) => s + Math.max(0, Number(g) || 0), 0), taxBase = realizedTaxBase + Math.max(0, Number(t.unrealized) || 0);
    const net = gain === null || gain === undefined ? null : gain - taxBase * .3;
    const stat = (l, v, cls = '', tip = '') => `<div class="hs"${tip ? ` title="${J.esc(tip)}"` : ''}><span>${l}</span><b class="${cls}">${v}</b></div>`;
    return `<section class="card hero2" data-fold="hero"><header class="fold-h hero-top">
        <div class="hero-main"><span class="hero-l">Valeur du portefeuille</span><span class="hero-v">${eur0(t.value)}</span>
          <span class="hero-g ${J.cls(gain)}">${gain === null ? '–' : sgn(gain)}${base > 0 && gain !== null ? ` <small>(${J.pct(100 * gain / base, 1)})</small>` : ''} <em>gain total, ventes comprises</em></span>
          <span class="hero-day" id="hero-day"></span></div>
        <div class="hero-stats">${stat('Plus-value latente', J.eur(t.unrealized, 0), J.cls(t.unrealized), 'Sur les titres encore détenus')}${stat('Réalisé (ventes)', J.eur(t.realized, 0), J.cls(t.realized))}${stat('Investi', eur0(t.cost), '', 'Prix de revient des titres encore détenus')}${stat('Net d’impôt estimé', J.eur(net, 0), J.cls(net), 'Si tout était vendu aujourd’hui, compte-titres au taux forfaitaire de 30 % (12,8 % impôt + 17,2 % prélèvements sociaux). Indicatif : hors PEA, pertes reportables et dividendes.')}</div>
        <span class="chev" aria-hidden="true"></span></header>
      <div class="fold-b"><div class="hero-tools">${pills('evo-mode', [['value', 'Valeur'], ['gain', 'Gain'], ['titles', 'Par titre']], EVO.mode)}${pills('evo-per', PERIODS.map(p => [p[0], p[1]]), EVO.per)}</div>
        <div class="hero-grid"><div id="evo-chart"><div class="lc-empty"><span class="spinner"></span></div></div><aside class="movers" id="movers"></aside></div></div></section>`;
  }
  function periodStart(h) {
    const per = PERIODS.find(p => p[0] === EVO.per) || PERIODS[PERIODS.length - 1];
    if (!per[2]) return 0;
    const since = new Date(Date.now() - per[2] * 864e5).toISOString().slice(0, 10);
    const i = h.dates.findIndex(d => d >= since);
    return i <= 0 ? 0 : i - 1;                                   // départ : la dernière valeur connue avant la période
  }
  function drawEvo() {
    const host = J.$('#evo-chart'), mv = J.$('#movers'), h = H; if (!host || !h) return;
    if (!h.dates || !h.dates.length) { host.innerHTML = '<div class="lc-empty">Ajoutez une transaction pour voir l’évolution.</div>'; mv.innerHTML = ''; return; }
    const last = h.dates.length - 1, toggle = id => { EVO.hidden.has(id) ? EVO.hidden.delete(id) : EVO.hidden.add(id); store('evo_hidden', [...EVO.hidden]); drawEvo(); };
    const height = innerWidth < 700 ? 190 : 230;
    // Jour : valeur du portefeuille actuel barre par barre (15 min)
    if (EVO.per === '1d') {
      const it = h.intraday || { t: [], value: [] };
      J.lineChart(host, it.t, [{ id: 'v', label: 'Valeur', values: it.value, color: '#6366f1', area: true }], { height, format: eur0, time: true });
      if (it.t.length < 2) host.querySelector('.lc-empty').textContent = 'Pas de cotations de 15 minutes enregistrées aujourd’hui pour vos titres.';
      const d0 = it.value[0], d1 = it.value[it.value.length - 1];
      mv.innerHTML = it.t.length > 1 ? `<h3>Aujourd’hui</h3><p class="mv-big ${J.cls(d1 - d0)}">${sgn(d1 - d0)}</p><p class="small muted">Valeur des titres détenus aujourd’hui, de ${J.dateTime(it.t[0])} à ${J.dateTime(it.t[it.t.length - 1])}.</p>` : '';
      return;
    }
    const i0 = periodStart(h), cut = a => a.slice(i0), xs = cut(h.dates), from = i0 === 0 ? 0 : h.gain[i0];
    const markers = (h.trades || []).filter(t => t.date >= xs[0] && !t.note).map(t => ({ x: t.date, kind: t.side, label: (t.side === 'buy' ? 'Achat ' : 'Vente ') + t.symbol }));
    let series;
    if (EVO.mode === 'gain') {
      const g = cut(h.gain).map(v => v - from);
      series = [{ id: 'gain', label: 'Gain sur la période', values: g, color: g[g.length - 1] >= 0 ? '#16a34a' : '#dc2626', area: true }]
        .concat(h.lines.map((l, k) => ({ id: 't:' + l.key, label: l.symbol, values: cut(l.gain).map(v => v - (i0 === 0 ? 0 : l.gain[i0])), color: PAL[k % PAL.length], width: 1.4 })));
      if (!store('evo_hidden_init')) { h.lines.forEach(l => EVO.hidden.add('t:' + l.key)); store('evo_hidden_init', 1); store('evo_hidden', [...EVO.hidden]); }
    } else if (EVO.mode === 'titles') {
      series = h.lines.map((l, k) => ({ id: 'v:' + l.key, label: l.symbol, values: cut(l.values), color: PAL[k % PAL.length], width: 1.8 }));
    } else {
      series = [{ id: 'value', label: 'Valeur', values: cut(h.value), color: '#6366f1', area: true }, { id: 'net', label: 'Argent investi', values: cut(h.net_in), color: '#94a3b8', dash: '5 5', width: 1.6 }];
    }
    J.lineChart(host, xs, series, { height, format: eur0, zeroLine: EVO.mode === 'gain', markers: EVO.mode === 'titles' ? [] : markers, hidden: EVO.hidden, onToggle: toggle });
    // Ce qui fait bouger le portefeuille sur la période
    const moves = h.lines.map(l => ({ l, d: l.gain[last] - (i0 === 0 ? 0 : l.gain[i0]) })).filter(m => Math.abs(m.d) >= .5).sort((a, b) => b.d - a.d);
    const total = h.gain[last] - from, m = Math.max(1, ...moves.map(x => Math.abs(x.d)));
    const per = PERIODS.find(p => p[0] === EVO.per) || PERIODS[PERIODS.length - 1];
    mv.innerHTML = `<h3>${per[0] === 'all' ? 'Depuis le début' : 'Sur ' + ({ '1w': 'la semaine', '1m': 'le mois', '3m': '3 mois', '6m': '6 mois', '1y': 'un an' })[per[0]]}</h3>
      <p class="mv-big ${J.cls(total)}">${sgn(total)}</p><p class="small muted mv-sub">Ce qui a fait monter ou baisser votre portefeuille :</p>
      <div class="mv-list">${moves.map(x => `<div class="mv-row" title="${J.esc(x.l.name)}"><span class="mv-s">${J.esc(x.l.symbol)}</span><span class="mv-bar"><i class="${x.d >= 0 ? 'up' : 'down'}" style="width:${Math.max(3, 100 * Math.abs(x.d) / m).toFixed(0)}%"></i></span><span class="mv-v ${J.cls(x.d)}">${sgn(x.d)}</span></div>`).join('') || '<p class="small muted">Rien n’a bougé.</p>'}</div>`;
    const dd = h.dates.length > 1 ? h.value[last] - h.value[last - 1] - (h.net_in[last] - h.net_in[last - 1]) : null;
    const hd = J.$('#hero-day'); if (hd && dd !== null) hd.innerHTML = `<span class="${J.cls(dd)}">${sgn(dd)}</span> depuis la clôture du ${J.date(h.dates[last - 1])}`;
  }

  /* ── Positions : une ligne lisible par titre ── */
  function spark(c, up) {
    if (!c || !c.points || c.points.length < 2) return '';
    const w = 120, hh = 34, v = c.points.map(p => p[1]), min = Math.min(...v), max = Math.max(...v), span = max - min || 1, n = v.length;
    const X = i => i * w / (n - 1), Y = x => hh - 2 - (x - min) / span * (hh - 4), d = v.map((x, i) => (i ? 'L' : 'M') + X(i).toFixed(1) + ' ' + Y(x).toFixed(1)).join('');
    return `<svg class="sp" viewBox="0 0 ${w} ${hh}" preserveAspectRatio="none" style="color:var(--${up ? 'up' : 'down'})"><path class="a" d="${d}L${w} ${hh}L0 ${hh}Z"/><path class="l" d="${d}"/></svg>`;
  }
  function positionsTable(d) {
    const rows = d.positions.map(p => {
      const c = (d.curves || {})[p.listing_id], w = worstFor(d.lots, p.listing_id), name = J.esc(p.name_catalogue || p.name || p.symbol), L = p.levels || {};
      const sinceBuy = c && c.points && c.points.length > 1 ? 100 * (c.points[c.points.length - 1][1] / c.points[0][1] - 1) : null;
      const filet = p.price !== null && L.stop && p.price <= L.stop ? '<span class="badge ko">Filet atteint</span>' : p.price !== null && L.target && p.price >= L.target ? '<span class="badge ok">Objectif atteint</span>' : '';
      return `<tr class="pos-row" data-open="${p.listing_id || ''}">
        <td class="pt">${p.linked ? `<a href="titre.html?id=${p.listing_id}" target="_blank" rel="noopener" class="pn">${name}</a>` : `<span class="pn">${name}</span>`}
          <div class="ps">${J.esc(p.symbol)} · ${J.num(p.qty, p.qty % 1 ? 4 : 0)} × ${p.price !== null ? px(p.price, p.price_currency) : '–'} ${w ? `<span class="badge ${LEVEL[w.level][0]}" title="${J.esc(w.alerts.map(x => x.message).join(' '))}">${LEVEL[w.level][1]}</span>` : ''}${filet}${p.catalogue_status === 'excluded' ? ` <span class="badge ko" title="${J.esc(p.excluded_reason || '')}">Hors sélection</span>` : ''}${!p.linked ? ' <span class="badge wait">Sans cours</span>' : ''}</div></td>
        <td class="pc hide-s">${p.listing_id ? `<button type="button" class="sp-btn" data-chart="${p.listing_id}" title="Ouvrir la courbe">${spark(c, (sinceBuy || 0) >= 0)}</button>` : ''}</td>
        <td class="num"><b>${J.eur(p.value, 0)}</b><div class="ps">${p.weight !== null ? J.pct(p.weight, 0, false) + ' du total' : ''}</div></td>
        <td class="num ${J.cls(p.unrealized)}"><b>${p.unrealized !== null ? sgn(p.unrealized) : '–'}</b><div class="ps">${J.pct(p.unrealized_pct, 1)}</div></td>
        <td class="num act hide-s"><button type="button" class="ib" data-chart="${p.listing_id || ''}" title="Courbe" ${p.listing_id ? '' : 'disabled'}>📈</button><button type="button" class="ib" data-lv="${p.listing_id || ''}" title="Filet de sécurité et objectif" ${p.linked ? '' : 'disabled'}>🛡️</button></td></tr>`; }).join('');
    return `<div class="table-wrap"><table class="pos-t"><thead><tr><th>Titre</th><th class="hide-s">Depuis l’achat</th><th class="num">Valeur</th><th class="num">Gain</th><th class="hide-s"></th></tr></thead><tbody>${rows || '<tr><td colspan="5" class="empty">Aucune position ouverte.</td></tr>'}</tbody></table></div>`;
  }

  /* ── Alertes, ventes, répartition, transactions : repliés par défaut ── */
  function lotsBody(d) {
    const rule = a => { const r = a.rules || {}; if (r.off) return '<span class="muted">désactivées</span>';
      return [r.days ? `${r.days} j → ${J.esc(r.days_action)}` : '', r.drop ? `−${J.num(r.drop, 0)} % du plus haut → ${J.esc(r.drop_action)}` : '', r.exit === 'momentum_negative' ? 'momentum 6 mois négatif → vente à envisager' : r.exit === 'below_ma50' ? 'sous la moyenne 50 j → vente à envisager' : ''].filter(Boolean).join('<br>') + (r.personal ? ' <span class="badge accent">perso</span>' : ''); };
    const rows = d.lots.map(l => { const a = l.alert || {}, held = Math.floor((Date.now() - new Date(l.trade_at.replace(' ', 'T') + 'Z')) / 864e5);
      return `<tr><td>${J.date(l.trade_at)}<div class="ps">${held} j</div></td><td><b>${J.esc(l.name || l.symbol)}</b><div class="ps">${J.esc(l.symbol)} · ${J.num(l.remaining, 4)} détenu(s) · ${J.esc(a.strategy_label || '–')}${a.own_strategy ? ' <span class="badge accent">choisie</span>' : ''}</div></td>
        <td class="small hide-s">${a.rules ? rule(a) : '–'}</td><td class="lot-alerts">${(a.alerts || []).map(x => `<span class="badge ${LEVEL[x.level][0]}" title="${J.esc(x.message)}">${J.esc(x.action)}</span>`).join('') || '<span class="muted small">aucune</span>'}</td>
        <td class="num"><button class="btn small" data-lot="${l.tx_id}">Régler</button></td></tr>`; }).join('');
    return `<p class="small muted">Rien n’est vendu automatiquement. Par défaut : rappel à 6 mois, alerte si le cours recule de 20 % depuis son plus haut depuis l’achat, et pour le Momentum quand sa hausse sur 6 mois devient négative (meilleure règle du test historique). Survolez une pastille pour le détail.</p>
      <div class="table-wrap"><table><thead><tr><th>Achat</th><th>Titre</th><th class="hide-s">Alertes prévues</th><th>Alertes</th><th></th></tr></thead><tbody>${rows}</tbody></table></div>`;
  }
  function salesBody(d) {
    return `<div class="table-wrap"><table><thead><tr><th>Date</th><th>Titre</th><th class="num">Produit net</th><th class="num hide-s">Prix de revient</th><th class="num">Gain</th></tr></thead><tbody>
      ${d.sales.map(x => `<tr><td>${J.date(x.trade_at)}</td><td>${x.listing_id ? `<a href="titre.html?id=${x.listing_id}" target="_blank" rel="noopener"><b>${J.esc(x.name || x.symbol)}</b></a>` : `<b>${J.esc(x.name || x.symbol)}</b>`}<div class="ps">${J.esc(x.symbol)} · ${J.num(x.quantity, 4)} vendu(s)</div></td><td class="num">${J.eur(x.proceeds)}</td><td class="num hide-s">${J.eur(x.cost)}</td><td class="num ${J.cls(x.gain)}"><b>${sgn(x.gain)}</b><div class="ps">${J.pct(x.gain_pct, 1)}</div></td></tr>`).join('')}</tbody></table></div>`;
  }
  function allocBody(a) {
    const rows = a.rows.filter(r => r.value_eur > 0 || (a.target && r.zone !== 'other')).map(r => `<tr><td>${J.esc(r.label)}</td><td class="num">${J.eur(r.value_eur, 0)}</td><td class="num">${r.current_pct === null ? '–' : J.pct(r.current_pct, 0, false)}</td>${a.target ? `<td class="num">${r.target_pct === null ? '–' : J.pct(r.target_pct, 0, false)}</td><td class="num ${r.off_target ? 'neg' : ''}">${r.gap_eur === null ? '–' : (r.gap_eur >= 0 ? 'acheter ' : 'vendre ') + J.eur(Math.abs(r.gap_eur), 0)}</td>` : ''}</tr>`).join('');
    return `<p class="small muted">${a.target ? `Cible : ${a.rows.filter(r => r.zone !== 'other').map(r => `${J.esc(r.label)} ${J.num(r.target_pct, 0)} %`).join(' · ')}. Rééquilibrer une fois par an, ou quand une zone s’écarte de ${J.num(a.tolerance, 0)} points.` : 'Stratégie prudente : des ETF larges et peu chers, 50 % États-Unis, 25 % Europe, 25 % émergents, rééquilibrés une fois par an.'}</p>
      ${a.rebalance_suggested ? '<div class="notice warn">Une zone s’écarte de la cible : un rééquilibrage peut être envisagé.</div>' : ''}
      ${rows ? `<div class="table-wrap"><table><thead><tr><th>Zone</th><th class="num">Valeur</th><th class="num">Part</th>${a.target ? '<th class="num">Cible</th><th class="num">Pour y revenir</th>' : ''}</tr></thead><tbody>${rows}</tbody></table></div>` : ''}
      <div class="row" style="margin-top:8px">${a.target ? '<button class="btn small" id="alloc-edit">Modifier la cible</button><button class="btn small" id="alloc-off">Retirer la cible</button>' : '<button class="btn small primary" id="alloc-prudent">Utiliser 50 / 25 / 25</button><button class="btn small" id="alloc-edit">Autre répartition…</button>'}
        ${['us', 'eu', 'emerging'].map(z => `<a class="btn small" href="index.html?kind=large_etf&geo_region=${z}&max_fee=0.3" target="_blank" rel="noopener">Gros ETF ${z === 'us' ? 'US' : z === 'eu' ? 'Europe' : 'émergents'}</a>`).join('')}</div>`;
  }
  function txBody(d) {
    return `<div class="row" style="justify-content:flex-end;margin-bottom:6px"><a class="btn small" href="api.php?r=export&id=${current}">Exporter en CSV</a></div><div class="table-wrap"><table><thead><tr><th>Date</th><th>Titre</th><th class="num">Quantité</th><th class="num">Prix</th><th class="num hide-s">Frais</th><th></th></tr></thead><tbody>
      ${d.transactions_list.map(x => `<tr><td>${J.date(x.trade_at)}</td><td><span class="badge ${x.side === 'buy' ? 'ok' : 'wait'}">${x.side === 'buy' ? 'Achat' : 'Vente'}</span> ${J.esc(x.name || x.symbol)} <span class="muted small">${J.esc(x.symbol)}</span></td><td class="num">${J.num(+x.quantity, 4)}</td><td class="num">${J.money(+x.unit_price, x.currency)}</td><td class="num hide-s">${x.fees ? J.eur(+x.fees) : '–'}</td>
        <td class="num"><button class="btn small" data-edit="${x.id}">Modifier</button> <button class="btn small danger" data-del="${x.id}" aria-label="Supprimer">✕</button></td></tr>`).join('') || '<tr><td colspan="6" class="empty">Aucune transaction.</td></tr>'}</tbody></table></div>`;
  }

  async function render() {
    list = (await J.api('portfolios')).portfolios;
    if (!list.length) { page.innerHTML = `<h1>Portefeuilles</h1><div class="card empty"><p>Vous n’avez pas encore de portefeuille.</p><button class="btn primary" id="first">Créer mon premier portefeuille</button></div>`; J.$('#first').onclick = createPf; return; }
    if (!list.find(p => p.id === current)) current = list[0].id;
    const d = D = await J.api('portfolio', { params: { id: current } });
    H = null;
    history.replaceState(null, '', '?id=' + current);
    const nAlerts = (d.lots || []).filter(l => l.alert && (l.alert.level === 'act' || l.alert.level === 'watch')).length;
    const etfHtml = JEtf.portfolio(d.etf_analysis);
    page.innerHTML = `${d.integrity && !d.integrity.ok ? `<div class="notice err">${d.integrity.issues.map(x => 'Transaction n° ' + x.transaction_id + ' : ' + J.esc(x.message)).join('<br>')}</div>` : ''}
    <div class="pf-bar"><div class="pf-tabs" id="pf-tabs">${list.map(p => `<button data-id="${p.id}" class="${p.id === current ? 'on' : ''}">${J.esc(p.name)}${p.is_default ? ' ★' : ''}</button>`).join('')}<button class="add" id="new-pf" title="Nouveau portefeuille">＋</button></div>
      <button class="btn primary" id="add-tx">＋ Transaction</button></div>
    ${d.totals.unpriced ? `<div class="notice warn">${d.totals.unpriced} position(s) sans cours : la valeur totale est sous-estimée.</div>` : ''}${splitNotice(d.positions)}
    ${hero(d)}
    ${section('positions', `Positions <span class="cnt">${d.positions.length}</span>`, '', positionsTable(d))}
    ${d.lots && d.lots.length ? section('lots', `Alertes ${nAlerts ? `<span class="cnt warn">${nAlerts}</span>` : '<span class="cnt">0</span>'}`, '', lotsBody(d)) : ''}
    ${d.sales && d.sales.length ? section('sales', `Ventes réalisées <span class="cnt">${d.sales.length}</span>`, `<span class="${J.cls(d.sales.reduce((a, x) => a + (x.gain || 0), 0))}">${sgn(d.sales.reduce((a, x) => a + (x.gain || 0), 0))}</span>`, salesBody(d)) : ''}
    ${d.allocation && d.allocation.rows ? section('alloc', 'Répartition par zone', d.allocation.rebalance_suggested ? '<span class="badge wait">à rééquilibrer</span>' : '', allocBody(d.allocation)) : ''}
    ${etfHtml ? section('etf', 'Secteurs de vos ETF', '', etfHtml.replace(/^<div class="card">\s*<h2>[^<]*<\/h2>/, '<div>')) : ''}
    ${section('tx', `Transactions <span class="cnt">${d.transactions_list.length}</span>`, '', txBody(d))}
    ${section('settings', 'Réglages du portefeuille', '', `<div class="row"><button class="btn small" id="rename">Renommer</button>${d.portfolio.is_default ? '' : '<button class="btn small" id="mk-default">Définir par défaut</button>'}<button class="btn small danger" id="del-pf">Supprimer</button></div>
      <p class="small muted" style="margin-bottom:0">Stratégie : <b>${d.portfolio.strategy ? (NAMES[d.portfolio.strategy.name] || 'Personnalisée') : 'aucune (Croissance régulière par défaut)'}</b>. Elle se règle depuis l’Explorer (affichage avancé).</p>`)}`;
    folds();
    J.$$('#pf-tabs button[data-id]').forEach(b => b.onclick = () => { current = +b.dataset.id; render(); });
    J.$('#new-pf').onclick = createPf;
    J.$$('#evo-mode button, #evo-per button').forEach(b => b.onclick = e => { e.stopPropagation(); const k = b.parentElement.id === 'evo-mode' ? 'mode' : 'per'; EVO[k] = b.dataset.v; store('evo_' + k, EVO[k]); J.$$('#' + b.parentElement.id + ' button').forEach(x => x.classList.toggle('on', x === b)); drawEvo(); });
    const pid = current;
    J.api('portfolio/history', { params: { id: pid } }).then(h => { if (pid !== current) return; H = h; drawEvo(); }).catch(e => { const c = J.$('#evo-chart'); if (c) c.innerHTML = `<div class="notice err">${J.esc(e.message)}</div>`; });
    J.$$('[data-lot]').forEach(b => b.onclick = () => lotDialog(d, d.lots.find(x => x.tx_id == b.dataset.lot)));
    const ap = J.$('#alloc-prudent'); if (ap) ap.onclick = async () => { await J.post('portfolio/target', { id: current, target: { us: 50, eu: 25, emerging: 25 } }); render(); };
    const ae = J.$('#alloc-edit'); if (ae) ae.onclick = () => allocationDialog(d.allocation);
    const ao = J.$('#alloc-off'); if (ao) ao.onclick = async () => { await J.post('portfolio/target', { id: current, target: null }); render(); };
    J.$$('[data-lv]').forEach(b => b.onclick = e => { e.stopPropagation(); levelsDialog(d.positions.find(x => x.listing_id == b.dataset.lv)); });
    J.$$('[data-chart]').forEach(b => b.onclick = e => { e.stopPropagation(); e.preventDefault(); chartDialog(d, d.positions.find(x => x.listing_id == b.dataset.chart)); });
    J.$$('tr.pos-row').forEach(r => r.onclick = e => { if (e.target.closest('a, button') || !r.dataset.open) return; chartDialog(d, d.positions.find(x => x.listing_id == r.dataset.open)); });
    J.$('#add-tx').onclick = () => J.txDialog({ portfolios: list, portfolioId: current, onDone: render });
    J.$$('[data-edit]').forEach(b => b.onclick = () => J.txDialog({ portfolios: list, portfolioId: current, tx: d.transactions_list.find(x => x.id == b.dataset.edit), onDone: render }));
    J.$$('[data-del]').forEach(b => b.onclick = async () => { if (await J.confirm('Supprimer la transaction', 'Cette transaction sera supprimée définitivement.', 'Supprimer')) { await J.post('tx/delete', { id: +b.dataset.del }); render(); } });
    J.$('#rename').onclick = () => J.dialog({ title: 'Renommer', body: J.field('Nom', `<input id="nm" value="${J.esc(d.portfolio.name)}">`), actions: [{ label: 'Annuler', run: () => { } }, { label: 'Enregistrer', cls: 'primary', run: async dlg => { await J.post('portfolio/rename', { id: current, name: J.$('#nm', dlg).value }); render(); } }] });
    const mk = J.$('#mk-default'); if (mk) mk.onclick = async () => { await J.post('portfolio/default', { id: current }); render(); };
    J.$('#del-pf').onclick = () => J.dialog({ title: 'Supprimer le portefeuille', body: `<p>Supprimer « ${J.esc(d.portfolio.name)} » et ses ${d.transactions_list.length} transactions ? Cette action est définitive.</p>${d.transactions_list.length ? J.field('Pour confirmer, tapez le nom du portefeuille', '<input id="cf">') : ''}`, actions: [{ label: 'Annuler', run: () => { } }, { label: 'Supprimer', cls: 'danger', run: async dlg => { await J.post('portfolio/delete', { id: current, confirm: J.$('#cf', dlg)?.value || '' }); render(); } }] });
  }

  /* ── Courbe d'un titre : instantanée pour les périodes en jours (série déjà chargée), 15 min pour 1 J et 1 S ── */
  function chartDialog(d, p) {
    if (!p || !p.listing_id) return;
    const c = (d.curves || {})[p.listing_id] || {}, dly = (c.daily || []).map(x => [x[0], x[1], null]), since = (p.first_buy || '').slice(0, 10), from = Math.max(0, dly.findIndex(x => x[0] >= since) - 1), n = dly.length - from;
    const GR = [['1d', '1 J'], ['1w', '1 S'], ['buy', 'Depuis l’achat'], ['1m', '1 M'], ['3m', '3 M'], ['6m', '6 M'], ['1y', '1 A'], ['all', 'Tout']], SESS = { '1m': 21, '3m': 63, '6m': 126, '1y': 252, all: 0 };
    let gr = store('chart_gr') || 'buy'; if (!GR.find(g => g[0] === gr)) gr = 'buy';
    const cur = p.price_currency || p.currency;
    const dlg = J.dialog({ title: p.name_catalogue || p.name || p.symbol, body: `${pills('pc-gr', GR, gr)}<div id="pc" class="pc-box"></div><p class="small muted" id="pc-n"></p>
      <p class="small"><a href="titre.html?id=${p.listing_id}" target="_blank" rel="noopener">Ouvrir la fiche complète ↗</a> · <a href="#" id="pc-lv">Filet de sécurité et objectif</a></p>`, actions: [{ label: 'Fermer', run: () => { } }] });
    dlg.classList && dlg.classList.add('wide');
    const buys = d.transactions_list.filter(x => x.side === 'buy' && x.listing_id == p.listing_id).map(x => ({ date: x.trade_at.slice(0, 10), label: 'Achat ' + J.date(x.trade_at) }));
    const open = (d.lots || []).filter(l => l.listing_id == p.listing_id && l.alert && l.alert.measures), first = open[0], lv = [];
    if (p.levels && p.levels.stop) lv.push({ value: +p.levels.stop, label: 'Filet de sécurité' });
    if (first && first.alert.rules && first.alert.rules.drop && !first.alert.rules.off) lv.push({ value: first.alert.measures.high * (1 - first.alert.rules.drop / 100), label: `Alerte −${J.num(first.alert.rules.drop, 0)} %` });
    const host = () => J.$('#pc', dlg), note = t => { J.$('#pc-n', dlg).textContent = t; };
    const draw = () => {
      J.$$('#pc-gr button', dlg).forEach(x => x.classList.toggle('on', x.dataset.v === gr));
      if (gr === '1d') { note('Les deux dernières séances, barre par barre (15 minutes).'); J.intradayPanel(host(), p.listing_id); return; }
      if (gr === '1w') { host().innerHTML = '<div class="lc-empty"><span class="spinner"></span></div>'; J.api('bars15', { params: { id: p.listing_id } }).then(w => { if (gr !== '1w') return;
          const r = w.bars.length > 1 ? J.priceChart(host(), w.bars, { sessions: 0, intraday: true, ma20: false, ma50: false, volume: false, unit: cur, levels: lv }) : (host().innerHTML = '<div class="lc-empty">Pas de barres de 15 minutes enregistrées cette semaine pour ce titre.</div>', null);
          note(r ? `${J.pct(r.perf, 1)} sur la semaine.` : ''); }).catch(e => { host().innerHTML = `<div class="notice err">${J.esc(e.message)}</div>`; }); return; }
      if (dly.length < 2) { host().innerHTML = '<div class="lc-empty">Pas d’historique pour ce titre.</div>'; note(''); return; }
      const r = J.priceChart(host(), dly, { sessions: gr === 'buy' ? Math.max(5, n) : SESS[gr], ma20: false, ma50: false, volume: false, unit: cur, marks: buys, levels: lv });
      note(r ? (gr === 'buy' ? `${J.pct(r.perf, 1)} depuis votre premier achat (${J.date(since)}), cours du titre hors frais et change.` : `${J.pct(r.perf, 1)} du ${J.date(r.from)} au ${J.date(r.to)}.`) : '');
    };
    J.$$('#pc-gr button', dlg).forEach(x => x.onclick = () => { gr = x.dataset.v; store('chart_gr', gr); draw(); });
    J.$('#pc-lv', dlg).onclick = e => { e.preventDefault(); dlg.close(); levelsDialog(p); };
    draw();
  }
  function levelsDialog(p) {
    if (!p) return;
    const L = p.levels || {}, cur = p.price_currency || p.currency;
    J.dialog({ title: 'Filet et objectif · ' + (p.name_catalogue || p.name || p.symbol), body: `<p class="small muted">Prix dans la devise du titre (${J.esc(cur || '')}). Repères personnels : rien n’est vendu automatiquement. Cours : ${px(p.price, cur)} · prix de revient moyen : ${J.eur(p.avg_cost)}.</p>${J.field('Filet de sécurité (stop)', `<input id="lv-stop" inputmode="decimal" value="${L.stop ?? ''}">`)}${J.field('Objectif', `<input id="lv-target" inputmode="decimal" value="${L.target ?? ''}">`)}`,
      actions: [{ label: 'Annuler', run: () => { } }, { label: 'Enregistrer', cls: 'primary', run: async dlg => { const n = i => J.$(i, dlg).value.trim().replace(',', '.'); try { await J.post('position/levels', { portfolio_id: current, listing_id: p.listing_id, stop: n('#lv-stop'), target: n('#lv-target') }); } catch (e) { J.formError(dlg, e.message); return true; } render(); } }] });
  }
  function lotDialog(d, l) {
    const s = l.settings || {}, a = l.alert || {}, strategies = d.lot_strategies || {};
    const opts = `<option value="">Celle du portefeuille</option>` + Object.entries(strategies).map(([k, v]) => `<option value="${k}" ${s.strategy === k ? 'selected' : ''}>${J.esc(v)}</option>`).join('');
    J.dialog({ title: 'Achat du ' + J.date(l.trade_at) + ' · ' + (l.name || l.symbol), body: `<p class="small muted">Laissez vide pour garder la valeur par défaut de la stratégie${a.rules ? ` (actuellement : ${a.rules.days ? a.rules.days + ' jours' : 'pas de durée'}, ${a.rules.drop ? '−' + a.rules.drop + ' %' : 'pas de seuil de recul'})` : ''}.</p>
      ${J.field('Stratégie de cet achat', `<select id="lt-st">${opts}</select>`)}${J.field('Rappel après (jours de détention)', `<input id="lt-days" inputmode="numeric" value="${s.alert_days ?? ''}" placeholder="défaut de la stratégie">`)}${J.field('Alerte si recul depuis le plus haut (%)', `<input id="lt-drop" inputmode="decimal" value="${s.alert_drop_pct ?? ''}" placeholder="défaut de la stratégie">`)}
      <label class="check"><input type="checkbox" id="lt-off" ${s.alerts_off ? 'checked' : ''}> Désactiver les alertes de cet achat</label>`,
      actions: [{ label: 'Annuler', run: () => { } }, { label: 'Enregistrer', cls: 'primary', run: async dlg => { const v = i => J.$(i, dlg).value.trim().replace(',', '.'); try { await J.post('lot/settings', { tx_id: l.tx_id, strategy: v('#lt-st'), alert_days: v('#lt-days'), alert_drop_pct: v('#lt-drop'), alerts_off: J.$('#lt-off', dlg).checked }); } catch (e) { J.formError(dlg, e.message); return true; } render(); } }] });
  }
  function allocationDialog(a) {
    const t = (a && a.target) || { us: 50, eu: 25, emerging: 25 };
    J.dialog({ title: 'Répartition cible par zone', body: `<p class="small muted">Trois parts en %, total 100.</p>${J.field('États-Unis (%)', `<input id="al-us" inputmode="decimal" value="${t.us}">`)}${J.field('Europe (%)', `<input id="al-eu" inputmode="decimal" value="${t.eu}">`)}${J.field('Émergents (%)', `<input id="al-em" inputmode="decimal" value="${t.emerging}">`)}`,
      actions: [{ label: 'Annuler', run: () => { } }, { label: 'Enregistrer', cls: 'primary', run: async dlg => { const n = i => J.$(i, dlg).value.trim().replace(',', '.'); try { await J.post('portfolio/target', { id: current, target: { us: n('#al-us'), eu: n('#al-eu'), emerging: n('#al-em') } }); } catch (e) { J.formError(dlg, e.message); return true; } render(); } }] });
  }
  function createPf() { J.dialog({ title: 'Nouveau portefeuille', body: J.field('Nom', '<input id="nm" maxlength="100" autofocus>'), actions: [{ label: 'Annuler', run: () => { } }, { label: 'Créer', cls: 'primary', run: async d => { const r = await J.post('portfolio/create', { name: J.$('#nm', d).value }); current = r.id; render(); } }] }); }
  let rs; addEventListener('resize', () => { clearTimeout(rs); rs = setTimeout(drawEvo, 150); });
  render();
})();
