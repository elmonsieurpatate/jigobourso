/* Page Portefeuilles */
(async () => {
  const user = await J.init('portefeuilles'); if (!user) return;
  const page = J.$('#page');
  let list = (await J.api('portfolios')).portfolios;
  let current = +new URLSearchParams(location.search).get('id') || (list.find(p => p.is_default) || list[0] || {}).id;
  const NAMES = { regular: 'Croissance régulière', fast: 'Croissance rapide', recovery: 'Rebond', low_volatility: 'Hausse calme', momentum: 'Momentum 6 mois (essai)', momentum12: 'Momentum 12 mois (essai)', momentum_risk: 'Momentum ajusté du risque (essai)' };

  const px = (v, c) => v === null || v === undefined ? '–' : J.money(v, c || 'EUR');
  const splitNotice = positions => positions.filter(p => p.splits_applied && p.splits_applied.length).map(p => `<div class="notice" style="margin-top:14px"><b>${J.esc(p.name_catalogue || p.name || p.symbol)}</b> : ${p.splits_applied.map(a => a.ratio >= 1 ? `split ${J.num(a.ratio, 2)} pour 1` : `regroupement ${J.num(1 / a.ratio, 2)} pour 1`).join(', ')} pris en compte automatiquement (Yahoo a ajusté ses cours) : la quantité affichée est celle d’aujourd’hui, le prix de revient total est inchangé.</div>`).join('');
  function levelCell(p) {
    if (!p.linked) return '<span class="muted small">–</span>';
    const cur = p.price_currency || p.currency, L = p.levels || {}, price = p.price;
    let state = '', gauge = '';
    if (price !== null && L.stop !== null && L.stop !== undefined && price <= L.stop) state = '<span class="badge ko">Filet atteint</span>';
    else if (price !== null && L.target !== null && L.target !== undefined && price >= L.target) state = '<span class="badge ok">Objectif atteint</span>';
    if (price !== null && L.stop && L.target) { const pos = Math.max(0, Math.min(100, 100 * (price - L.stop) / (L.target - L.stop))); gauge = `<div class="bar" style="width:120px;margin:4px 0" title="Cours entre le filet de sécurité et l’objectif"><i style="width:${pos}%"></i></div>`; }
    return `<div class="small">${L.stop || L.target ? `Filet ${px(L.stop, cur)}<br>Objectif ${px(L.target, cur)}` : '<span class="muted">non défini</span>'}</div>${gauge}${state}<div style="margin-top:4px"><button class="btn small" data-lv="${p.listing_id}">Régler</button> <button class="btn small" data-chart="${p.listing_id}">Graphique</button></div>`;
  }
  /* ── Évolution du portefeuille (ventes comprises), historique des ventes, blocs repliables ── */
  const PAL = ['#4f46e5', '#0d9488', '#d97706', '#db2777', '#2563eb', '#65a30d', '#9333ea', '#dc2626', '#0891b2', '#ca8a04', '#475569', '#16a34a'];
  const store = (k, v) => { try { if (v === undefined) return JSON.parse(localStorage.getItem('jigo_pf_' + k)); localStorage.setItem('jigo_pf_' + k, JSON.stringify(v)); } catch (e) { return null; } };
  const EVO = { mode: store('evo_mode') || 'value', per: store('evo_per') || 'all' };
  const PERIODS = [['1m', '1 M', 31], ['3m', '3 M', 92], ['6m', '6 M', 183], ['1y', '1 an', 366], ['all', 'Tout', 0]];
  function evoCard() {
    const seg = (id, items, cur) => `<span class="seg" id="${id}">${items.map(([k, l]) => `<button type="button" data-v="${k}" class="${k === cur ? 'on' : ''}">${l}</button>`).join('')}</span>`;
    return `<div class="card" data-fold="evo" id="evo" style="margin-top:16px"><div class="row between"><h2 style="margin:0">Évolution du portefeuille</h2></div>
      <div class="seg-row">${seg('evo-mode', [['value', 'Valeur et apports'], ['gain', 'Gain ou perte'], ['titles', 'Par titre']], EVO.mode)}${seg('evo-per', PERIODS.map(p => [p[0], p[1]]), EVO.per)}</div>
      <div id="evo-chart"><div class="empty"><span class="spinner"></span></div></div><p class="small muted" id="evo-note"></p></div>`;
  }
  function drawEvo(h) {
    const host = J.$('#evo-chart'); if (!host) return;
    if (!h || !h.dates || !h.dates.length) { host.innerHTML = '<div class="empty">Aucune transaction : rien à tracer.</div>'; return; }
    const per = PERIODS.find(p => p[0] === EVO.per) || PERIODS[4], since = per[2] ? new Date(Date.now() - per[2] * 864e5).toISOString().slice(0, 10) : '';
    const i0 = Math.max(0, h.dates.findIndex(d => d >= since)), cut = a => a.slice(i0 === -1 ? 0 : i0), dates = cut(h.dates);
    const trades = (h.trades || []).filter(t => t.date >= dates[0] && !t.note).map(t => ({ date: t.date, label: (t.side === 'buy' ? 'Achat ' : 'Vente ') + t.symbol, cls: t.side }));
    const eur = v => J.eur(v, 0);
    let series, note;
    if (EVO.mode === 'gain') {
      const g = cut(h.gain), up = g[g.length - 1] >= 0;
      series = [{ label: 'Gain ou perte cumulé (latent + réalisé)', values: g, color: up ? 'var(--up)' : 'var(--down)', area: true }];
      note = 'Gain ou perte = valeur du portefeuille − argent investi net (achats + frais − produit des ventes). Les ventes ne font pas disparaître le gain : il reste dans la courbe.';
    } else if (EVO.mode === 'titles') {
      series = h.lines.map((l, k) => ({ label: l.symbol, values: cut(l.values), color: PAL[k % PAL.length], width: 1.6 }));
      note = 'Valeur de chaque titre en euros (0 quand il n’est plus détenu).';
    } else {
      series = [{ label: 'Valeur du portefeuille', values: cut(h.value), color: 'var(--accent)', area: true }, { label: 'Argent investi net', values: cut(h.net_in), color: 'var(--muted)', dash: '6 4' }];
      note = 'Valeur = titres détenus au cours de clôture du jour. Argent investi net = achats + frais − produit des ventes. L’écart entre les deux courbes est votre gain ou perte.';
    }
    J.lineChart(host, dates, series, { format: eur, zeroLine: EVO.mode === 'gain', marks: EVO.mode === 'titles' ? [] : trades });
    const last = h.dates.length - 1;
    J.$('#evo-note').innerHTML = `${note} Aujourd’hui : valeur <b>${eur(h.value[last])}</b>, investi net <b>${eur(h.net_in[last])}</b>, gain ou perte <b class="${J.cls(h.gain[last])}">${eur(h.gain[last])}</b>.${(h.notes || []).length ? ' ' + h.notes.map(J.esc).join(' ') : ''} Barres verticales : achats (bleu) et ventes (rouge).`;
  }
  function salesCard(d) {
    const s = d.sales || [];
    if (!s.length) return '';
    const total = s.reduce((a, x) => a + (x.gain || 0), 0);
    return `<div class="card" data-fold="sales"><div class="row between"><h2 style="margin:0">Ventes réalisées <span class="muted small">(${s.length})</span></h2><span class="${J.cls(total)}"><b>${J.eur(total, 0)}</b> au total</span></div>
      <div class="table-wrap"><table><thead><tr><th>Date</th><th>Titre</th><th class="num">Quantité</th><th class="num">Produit net</th><th class="num">Prix de revient</th><th class="num">Gain ou perte</th></tr></thead><tbody>
      ${s.map(x => `<tr><td>${J.date(x.trade_at)}</td><td>${x.listing_id ? `<a href="titre.html?id=${x.listing_id}" target="_blank" rel="noopener"><b>${J.esc(x.name || x.symbol)}</b></a>` : `<b>${J.esc(x.name || x.symbol)}</b>`} <span class="muted small">${J.esc(x.symbol)}</span></td><td class="num">${J.num(x.quantity, 4)}</td><td class="num">${J.eur(x.proceeds)}</td><td class="num">${J.eur(x.cost)}</td><td class="num ${J.cls(x.gain)}">${J.eur(x.gain)}<div class="small">${J.pct(x.gain_pct, 1)}</div></td></tr>`).join('')}</tbody></table></div>
      <p class="small muted">Gain ou perte = produit de la vente (frais déduits) − prix de revient moyen des titres vendus.</p></div>`;
  }
  /* Blocs repliables : un clic sur le titre replie ou déplie le bloc ; le choix est mémorisé dans ce navigateur. */
  function folds() {
    const etf = J.$$('#page .card').find(c => (c.querySelector('h2') || {}).textContent === 'Diversification des ETF'); if (etf) etf.dataset.fold = 'etf';
    const saved = store('folds') || { etf: true };
    J.$$('#page .card[data-fold]').forEach(c => {
      const head = c.firstElementChild; if (!head) return;
      head.classList.add('fold-head'); c.classList.toggle('folded', !!saved[c.dataset.fold]);
      head.addEventListener('click', e => { if (e.target.closest('button, a, input, select')) return; c.classList.toggle('folded'); const f = store('folds') || { etf: true }; f[c.dataset.fold] = c.classList.contains('folded'); store('folds', f); });
    });
  }
  /* Alertes de vente achat par achat (rien n'est vendu automatiquement). Niveaux : info < watch (surveiller, réexaminer) < act (alléger, vente à envisager). */
  const LEVEL = { info: ['info', 'Info'], watch: ['wait', 'À surveiller'], act: ['ko', 'À examiner'] };
  const lotBadge = a => a && a.level ? `<span class="badge ${LEVEL[a.level][0]}" title="${J.esc(a.alerts.map(x => x.message).join(' '))}">${LEVEL[a.level][1]}</span>` : '';
  function worstFor(lots, listingId) {
    const order = ['info', 'watch', 'act'];
    return (lots || []).filter(l => l.listing_id == listingId && l.alert && l.alert.level).map(l => l.alert).sort((a, b) => order.indexOf(b.level) - order.indexOf(a.level))[0] || null;
  }
  /* Courbe de la position depuis son plus ancien achat encore détenu : une barre par achat, couleur selon la hausse ou la baisse depuis ce premier achat. */
  function posCurve(c, listingId) {
    if (!c || !c.points || c.points.length < 2) return '<span class="muted small">–</span>';
    const w = 170, h = 46, v = c.points.map(p => p[1]), min = Math.min(...v), max = Math.max(...v), span = max - min || 1, n = v.length;
    const X = i => i * w / (n - 1), Y = x => h - 3 - (x - min) / span * (h - 6), up = v[n - 1] >= v[0];
    const d = v.map((x, i) => (i ? 'L' : 'M') + X(i).toFixed(1) + ' ' + Y(x).toFixed(1)).join('');
    const marks = c.buys.map(b => { const i = c.points.findIndex(p => p[0] >= b); return i < 0 ? '' : `<line x1="${X(i).toFixed(1)}" x2="${X(i).toFixed(1)}" y1="0" y2="${h}" class="buy"/>`; }).join('');
    const pct = 100 * (v[n - 1] / v[0] - 1);
    return `<button type="button" class="pos-curve" data-chart="${listingId}" title="Agrandir la courbe depuis l’achat"><svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" style="color:var(--${up ? 'up' : 'down'})"><line x1="0" x2="${w}" y1="${Y(v[0]).toFixed(1)}" y2="${Y(v[0]).toFixed(1)}" class="base"/>${marks}<path class="area" d="${d}L${w} ${h}L0 ${h}Z"/><path d="${d}" class="ln"/></svg><span class="small ${J.cls(pct)}">${J.pct(pct, 1)} depuis le ${J.date(c.buys[0])}</span></button>`;
  }
  function lotsCard(d) {
    const lots = d.lots || [];
    if (!lots.length) return '';
    const rule = a => { const r = a.rules || {}; if (r.off) return '<span class="muted">alertes désactivées</span>';
      return [r.days ? `${r.days} j → ${J.esc(r.days_action)}` : '', r.drop ? `−${J.num(r.drop, 0)} % du plus haut → ${J.esc(r.drop_action)}` : '', r.exit === 'momentum_negative' ? 'momentum 6 mois négatif → vente à envisager' : r.exit === 'below_ma50' ? 'sous la moyenne 50 j → vente à envisager' : ''].filter(Boolean).join('<br>') + (r.personal ? ' <span class="badge accent">perso</span>' : ''); };
    const rows = lots.map(l => { const a = l.alert || {}; const m = a.measures || {}; const held = Math.floor((Date.now() - new Date(l.trade_at.replace(' ', 'T') + 'Z')) / 864e5);
      return `<tr><td>${J.date(l.trade_at)}<div class="small muted">${held} j</div></td><td><b>${J.esc(l.name || l.symbol)}</b><div class="small muted">${J.esc(l.symbol)} · ${J.num(l.remaining, 4)} détenu${l.remaining < l.quantity - 1e-9 ? ` sur ${J.num(l.quantity, 4)}` : ''}</div></td>
        <td>${J.esc(a.strategy_label || '–')}${a.own_strategy ? ' <span class="badge accent">choisie</span>' : ''}</td><td class="small">${a.rules ? rule(a) : '–'}</td>
        <td class="num">${m.drop_pct !== undefined && m.drop_pct !== null ? `<span class="${m.drop_pct > 0 ? 'neg' : ''}">−${J.num(m.drop_pct, 1)} %</span><div class="small muted">du plus haut</div>` : '–'}</td>
        <td class="lot-alerts">${(a.alerts || []).map(x => `<span class="badge ${LEVEL[x.level][0]}" title="${J.esc(x.message)}">${J.esc(x.action)}</span>`).join('') || '<span class="muted small">aucune</span>'}${(a.alerts || []).length ? `<div class="small muted">${(a.alerts || []).map(x => J.esc(x.message)).join('<br>')}</div>` : ''}</td>
        <td class="num"><button class="btn small" data-lot="${l.tx_id}">Régler</button></td></tr>`; }).join('');
    return `<div class="card" id="lots" data-fold="lots"><div class="row between"><h2 style="margin:0">Mes achats et alertes</h2></div>
      <details class="help"><summary>Comment sont réglées les alertes ?</summary><p class="small muted">Chaque achat garde sa stratégie (celle du portefeuille, sauf si vous en choisissez une autre) et ses alertes. Ce sont des repères, rien n’est vendu automatiquement. Réglages par défaut tirés du test historique des règles de sortie : conserver plus longtemps a rapporté plus, d’où un rappel vers 6 mois ; un recul de 20 % depuis le plus haut signale les pires cas ; pour le Momentum, la meilleure sortie testée est un momentum 6 mois devenu négatif.</p></details>
      <div class="table-wrap"><table><thead><tr><th>Achat</th><th>Titre</th><th>Stratégie</th><th>Alertes prévues</th><th class="num">Recul</th><th>Alertes</th><th></th></tr></thead><tbody>${rows}</tbody></table></div></div>`;
  }
  function lotDialog(d, l) {
    const s = l.settings || {}, a = l.alert || {}, strategies = d.lot_strategies || {};
    const opts = `<option value="">Celle du portefeuille</option>` + Object.entries(strategies).map(([k, v]) => `<option value="${k}" ${s.strategy === k ? 'selected' : ''}>${J.esc(v)}</option>`).join('');
    J.dialog({ title: 'Achat du ' + J.date(l.trade_at) + ' · ' + (l.name || l.symbol), body: `<p class="small muted">Laissez un champ vide pour garder la valeur par défaut de la stratégie${a.rules ? ` (actuellement : ${a.rules.days ? a.rules.days + ' jours' : 'pas de durée'}, ${a.rules.drop ? '−' + a.rules.drop + ' %' : 'pas de seuil de recul'})` : ''}.</p>
      ${J.field('Stratégie de cet achat', `<select id="lt-st">${opts}</select>`)}${J.field('Rappel après (jours de détention)', `<input id="lt-days" inputmode="numeric" value="${s.alert_days ?? ''}" placeholder="défaut de la stratégie">`)}${J.field('Alerte si recul depuis le plus haut (%)', `<input id="lt-drop" inputmode="decimal" value="${s.alert_drop_pct ?? ''}" placeholder="défaut de la stratégie">`)}
      <label class="check"><input type="checkbox" id="lt-off" ${s.alerts_off ? 'checked' : ''}> Désactiver les alertes de cet achat</label>`,
      actions: [{ label: 'Annuler', run: () => { } }, { label: 'Enregistrer', cls: 'primary', run: async dlg => { const v = i => J.$(i, dlg).value.trim().replace(',', '.'); try { await J.post('lot/settings', { tx_id: l.tx_id, strategy: v('#lt-st'), alert_days: v('#lt-days'), alert_drop_pct: v('#lt-drop'), alerts_off: J.$('#lt-off', dlg).checked }); } catch (e) { J.formError(dlg, e.message); return true; } render(); } }] });
  }
  /* Répartition par zone (stratégie prudente) : valeur actuelle par zone, cible, montant à acheter (+) ou vendre (−) pour revenir à la cible. Rien n'est exécuté. */
  function allocationCard(a) {
    if (!a || !a.rows) return '';
    const head = a.target ? `<p class="small muted">Cible enregistrée : ${a.rows.filter(r => r.zone !== 'other').map(r => `${J.esc(r.label)} ${J.num(r.target_pct, 0)} %`).join(' · ')}. Rééquilibrage conseillé une fois par an, ou quand une zone s’écarte d’au moins ${J.num(a.tolerance, 0)} points.</p>`
      : '<p class="small muted">Aucune répartition cible. La stratégie prudente répartit des ETF larges et peu chers : 50 % États-Unis, 25 % Europe, 25 % émergents, rééquilibrés une fois par an.</p>';
    const rows = a.rows.filter(r => r.value_eur > 0 || (a.target && r.zone !== 'other')).map(r => `<tr><td>${J.esc(r.label)}</td><td class="num">${J.eur(r.value_eur, 0)}</td><td class="num">${r.current_pct === null ? '–' : J.pct(r.current_pct, 1, false)}</td>
      ${a.target ? `<td class="num">${r.target_pct === null ? '–' : J.pct(r.target_pct, 0, false)}</td><td class="num ${r.off_target ? 'neg' : ''}">${r.gap_eur === null ? '–' : (r.gap_eur >= 0 ? 'acheter ' : 'vendre ') + J.eur(Math.abs(r.gap_eur), 0)}</td>` : ''}</tr>`).join('');
    const links = ['us', 'eu', 'emerging'].map(z => `<a class="btn small" href="index.html?kind=large_etf&geo_region=${z}&max_fee=0.3">Gros ETF ${z === 'us' ? 'États-Unis' : z === 'eu' ? 'Europe' : 'émergents'}</a>`).join(' ');
    return `<div class="card" id="alloc" data-fold="alloc" style="margin-top:16px"><div class="row between"><h2 style="margin:0">Répartition par zone</h2><div class="row">${a.target ? '<button class="btn small" id="alloc-edit">Modifier la cible</button><button class="btn small" id="alloc-off">Retirer la cible</button>' : '<button class="btn small primary" id="alloc-prudent">Utiliser la répartition prudente 50 / 25 / 25</button><button class="btn small" id="alloc-edit">Autre répartition…</button>'}</div></div>
      ${head}${a.rebalance_suggested ? '<div class="notice warn">Une zone s’écarte de la cible : un rééquilibrage peut être envisagé.</div>' : ''}
      ${rows ? `<div class="table-wrap"><table><thead><tr><th>Zone</th><th class="num">Valeur</th><th class="num">Part</th>${a.target ? '<th class="num">Cible</th><th class="num">Pour revenir à la cible</th>' : ''}</tr></thead><tbody>${rows}</tbody></table></div>` : ''}
      <p class="small muted">Zone d’une action : pays de l’entreprise. Zone d’un ETF : sa catégorie géographique ; un ETF « Monde » ou sans catégorie compte dans « Autre ou inconnue ».${a.unpriced ? ` ${a.unpriced} position(s) sans cours ne sont pas comptées.` : ''}</p>
      <div class="row">${links}</div></div>`;
  }
  function allocationDialog(a) {
    const t = (a && a.target) || { us: 50, eu: 25, emerging: 25 };
    J.dialog({ title: 'Répartition cible par zone', body: `<p class="small muted">Trois parts en %, total 100.</p>${J.field('États-Unis (%)', `<input id="al-us" inputmode="decimal" value="${t.us}">`)}${J.field('Europe (%)', `<input id="al-eu" inputmode="decimal" value="${t.eu}">`)}${J.field('Émergents (%)', `<input id="al-em" inputmode="decimal" value="${t.emerging}">`)}`,
      actions: [{ label: 'Annuler', run: () => { } }, { label: 'Enregistrer', cls: 'primary', run: async dlg => { const n = i => J.$(i, dlg).value.trim().replace(',', '.'); try { await J.post('portfolio/target', { id: current, target: { us: n('#al-us'), eu: n('#al-eu'), emerging: n('#al-em') } }); } catch (e) { J.formError(dlg, e.message); return true; } render(); } }] });
  }
  async function render() {
    list = (await J.api('portfolios')).portfolios;
    if (!list.length) { page.innerHTML = `<h1>Portefeuilles</h1><div class="card empty"><p>Vous n’avez pas encore de portefeuille.</p><button class="btn primary" id="first">Créer mon premier portefeuille</button></div>`; J.$('#first').onclick = createPf; return; }
    if (!list.find(p => p.id === current)) current = list[0].id;
    const d = await J.api('portfolio', { params: { id: current } }), t = d.totals;
    // Estimation indicative CTO/PFU : les gains latents sont taxés comme si les titres ouverts étaient vendus aujourd'hui.
    const realizedTaxBase = Object.values(d.realized_by_year || {}).reduce((sum, gain) => sum + Math.max(0, Number(gain) || 0), 0);
    const latentTaxBase = Math.max(0, Number(t.unrealized) || 0), taxBase = realizedTaxBase + latentTaxBase;
    const estimatedIncomeTax = taxBase * .128, estimatedSocialTax = taxBase * .172;
    const estimatedNetGain = t.total_gain === null || t.total_gain === undefined ? null : t.total_gain - estimatedIncomeTax - estimatedSocialTax;
    const estimatedNetPct = estimatedNetGain === null || !(t.invested_total > 0) ? null : 100 * estimatedNetGain / t.invested_total;
    history.replaceState(null, '', '?id=' + current);
    page.innerHTML = `${d.integrity && !d.integrity.ok ? `<div class="notice err">${d.integrity.issues.map(x => 'Transaction n° ' + x.transaction_id + ' : ' + J.esc(x.message)).join('<br>')}</div>` : ''}<div class="row between"><h1>Portefeuilles</h1><div class="row"><button class="btn" id="new-pf">Nouveau portefeuille</button></div></div>
    <div class="tabs" id="pf-tabs">${list.map(p => `<button data-id="${p.id}" class="${p.id === current ? 'on' : ''}">${J.esc(p.name)}${p.is_default ? ' ★' : ''}</button>`).join('')}</div>
    <div class="grid portfolio-kpis">
      <div class="card kpi"><span class="l">Valeur actuelle</span><span class="v">${J.eur(t.value, 0)}</span></div>
      <div class="card kpi"><span class="l">Plus-value latente</span><span class="v ${J.cls(t.unrealized)}">${J.eur(t.unrealized, 0)}</span><span class="small ${J.cls(t.unrealized)}">${J.pct(t.unrealized_pct)}</span></div>
      <div class="card kpi"><span class="l">Plus-value réalisée</span><span class="v ${J.cls(t.realized)}">${J.eur(t.realized, 0)}</span></div>
      <div class="card kpi"><span class="l">Investi (positions ouvertes)</span><span class="v">${J.eur(t.cost, 0)}</span><span class="small muted">frais cumulés ${J.eur(t.fees)}</span></div>
      <div class="card kpi"><span class="l">Gain net estimé · si vente aujourd’hui</span><span class="v ${J.cls(estimatedNetGain)}">${J.eur(estimatedNetGain, 0)}</span><span class="small ${J.cls(estimatedNetPct)}">${J.pct(estimatedNetPct, 1)} du coût cumulé des achats</span><span class="small muted">Brut ${J.eur(t.total_gain, 0)} · impôt ${J.eur(estimatedIncomeTax, 0)} · sociaux ${J.eur(estimatedSocialTax, 0)}</span></div></div>
    <details class="help tax-estimate-note"><summary>Comment est estimé le gain net ?</summary><p class="small muted">Estimation indicative pour un compte-titres au PFU supposé de 30 % (12,8 % d’impôt sur le revenu + 17,2 % de prélèvements sociaux) : gains réalisés positifs par année et plus-value latente positive comme si les titres étaient vendus aujourd’hui. Hors PEA, reports de pertes, dividendes et situation fiscale personnelle ; les gains réalisés ont pu être imposés auparavant. Ce n’est pas un calcul déclaratif.${t.partial ? ' Estimation partielle : certaines positions sont exclues du calcul des gains.' : ''}</p></details>
    ${t.unpriced ? `<div class="notice warn" style="margin-top:14px">${t.unpriced} position${t.unpriced > 1 ? 's' : ''} sans cours disponible : la valeur totale est sous-estimée.</div>` : ''}
    ${splitNotice(d.positions)}
    ${evoCard()}
    ${JEtf.portfolio(d.etf_analysis)}
    ${allocationCard(d.allocation)}
    <div class="card" data-fold="positions" style="margin-top:16px"><div class="row between"><h2 style="margin:0">Positions</h2><div class="row"><button class="btn primary small" id="add-tx">Ajouter une transaction</button></div></div>
      <div class="table-wrap"><table><thead><tr><th>Titre</th><th class="num">Quantité</th><th class="num">Prix de revient</th><th class="num">Cours</th><th class="num">Valeur</th><th class="num">+/− value</th><th class="num">Poids</th><th>Depuis l’achat</th><th>Garde-fous</th></tr></thead><tbody>
      ${d.positions.map(p => `<tr><td>${p.linked ? `<a href="titre.html?id=${p.listing_id}" target="_blank" rel="noopener"><b>${J.esc(p.name_catalogue || p.name || p.symbol)}</b></a>` : `<b>${J.esc(p.name || p.symbol)}</b>`}<div class="small muted">${J.esc(p.symbol)} ${p.catalogue_status === 'excluded' ? `<span class="badge ko help" title="${J.esc(p.excluded_reason || '')}">Hors sélection</span>` : ''}${!p.linked ? '<span class="badge wait help" title="Titre saisi à la main, sans cours">Sans cours</span>' : ''} ${lotBadge(worstFor(d.lots, p.listing_id))}</div></td>
        <td class="num">${J.num(p.qty, 4)}</td><td class="num">${J.eur(p.avg_cost)}</td><td class="num">${p.price_eur !== null ? J.eur(p.price_eur) + `<div class="small muted">${J.priceLabel(p)} · ${J.ago(p.price_time)}</div>` : '–'}</td>
        <td class="num"><b>${J.eur(p.value)}</b></td><td class="num ${J.cls(p.unrealized)}">${p.unrealized !== null ? J.eur(p.unrealized) + `<div class="small">${J.pct(p.unrealized_pct, 1)}</div>` : '–'}</td><td class="num">${p.weight !== null ? J.pct(p.weight, 1, false) : '–'}</td><td>${p.listing_id ? posCurve((d.curves || {})[p.listing_id], p.listing_id) : '–'}</td><td>${levelCell(p)}</td></tr>`).join('') || '<tr><td colspan="9" class="empty">Aucune position ouverte.</td></tr>'}</tbody></table></div></div>
    ${lotsCard(d)}
    ${salesCard(d)}
    <div class="card" data-fold="tx"><div class="row between"><h2 style="margin:0">Transactions <span class="muted small">(${d.transactions_list.length})</span></h2><a class="btn small" href="api.php?r=export&id=${current}">Exporter en CSV</a></div>
      <div class="table-wrap"><table><thead><tr><th>Date</th><th>Sens</th><th>Titre</th><th class="num">Quantité</th><th class="num">Prix</th><th class="num">Frais</th><th></th></tr></thead><tbody>
      ${d.transactions_list.map(x => `<tr><td>${J.date(x.trade_at)}</td><td><span class="badge ${x.side === 'buy' ? 'ok' : 'wait'}">${x.side === 'buy' ? 'Achat' : 'Vente'}</span></td><td>${J.esc(x.name || x.symbol)} <span class="muted small">${J.esc(x.symbol)}</span></td><td class="num">${J.num(+x.quantity, 4)}</td><td class="num">${J.money(+x.unit_price, x.currency)}</td><td class="num">${x.fees ? J.eur(+x.fees) : '–'}</td>
        <td class="num"><button class="btn small" data-edit="${x.id}">Modifier</button> <button class="btn small danger" data-del="${x.id}" aria-label="Supprimer">✕</button></td></tr>`).join('') || '<tr><td colspan="7" class="empty">Aucune transaction.</td></tr>'}</tbody></table></div></div>
    <div class="card"><h2>Réglages du portefeuille</h2><div class="row">
      <button class="btn small" id="rename">Renommer</button>${d.portfolio.is_default ? '' : '<button class="btn small" id="mk-default">Définir par défaut</button>'}<button class="btn small danger" id="del-pf">Supprimer</button></div>
      <p class="small muted" style="margin-bottom:0">Stratégie enregistrée : <b>${d.portfolio.strategy ? (NAMES[d.portfolio.strategy.name] || 'Personnalisée') : 'aucune (Croissance régulière par défaut)'}</b>. Elle se règle depuis l’Explorer (affichage avancé).</p></div>`;
    J.$$('#pf-tabs button').forEach(b => b.onclick = () => { current = +b.dataset.id; render(); });
    J.$('#new-pf').onclick = createPf;
    folds();
    J.$$('#evo-mode button, #evo-per button').forEach(b => b.onclick = () => { const k = b.parentElement.id === 'evo-mode' ? 'mode' : 'per'; EVO[k] = b.dataset.v; store('evo_' + k, EVO[k]); J.$$('#' + b.parentElement.id + ' button').forEach(x => x.classList.toggle('on', x === b)); drawEvo(hist); });
    let hist = null; const pid = current;
    J.api('portfolio/history', { params: { id: pid } }).then(h => { if (pid !== current) return; hist = h; drawEvo(h); }).catch(e => { const c = J.$('#evo-chart'); if (c) c.innerHTML = `<div class="notice err">${J.esc(e.message)}</div>`; });
    J.$$('[data-lot]').forEach(b => b.onclick = () => lotDialog(d, d.lots.find(x => x.tx_id == b.dataset.lot)));
    const ap = J.$('#alloc-prudent'); if (ap) ap.onclick = async () => { await J.post('portfolio/target', { id: current, target: { us: 50, eu: 25, emerging: 25 } }); render(); };
    const ae = J.$('#alloc-edit'); if (ae) ae.onclick = () => allocationDialog(d.allocation);
    const ao = J.$('#alloc-off'); if (ao) ao.onclick = async () => { await J.post('portfolio/target', { id: current, target: null }); render(); };
    J.$$('[data-lv]').forEach(b => b.onclick = () => { const p = d.positions.find(x => x.listing_id == b.dataset.lv), L = p.levels || {}, cur = p.price_currency || p.currency;
      J.dialog({ title: 'Garde-fous · ' + (p.name_catalogue || p.name || p.symbol), body: `<p class="small muted">Prix dans la devise de la cotation (${J.esc(cur || '')}). Ce sont des repères personnels : rien n’est vendu automatiquement. Cours actuel : ${px(p.price, cur)} · prix de revient moyen : ${J.eur(p.avg_cost)}.</p>${J.field('Filet de sécurité (stop)', `<input id="lv-stop" inputmode="decimal" value="${L.stop ?? ''}">`)}${J.field('Objectif', `<input id="lv-target" inputmode="decimal" value="${L.target ?? ''}">`)}`,
        actions: [{ label: 'Annuler', run: () => { } }, { label: 'Enregistrer', cls: 'primary', run: async dlg => { const n = i => J.$(i, dlg).value.trim().replace(',', '.'); try { await J.post('position/levels', { portfolio_id: current, listing_id: p.listing_id, stop: n('#lv-stop'), target: n('#lv-target') }); } catch (e) { J.formError(dlg, e.message); return true; } render(); } }] }); });
    J.$$('[data-chart]').forEach(b => b.onclick = async () => { const p = d.positions.find(x => x.listing_id == b.dataset.chart), s = await J.api('sheet', { params: { id: p.listing_id } }), since = (p.first_buy || '').slice(0, 10);
      const dly = s.daily.map((x, i) => [x[0], x[1], s.daily_volume[i]]), from = Math.max(0, dly.findIndex(x => x[0] >= since) - 1), n = dly.length - from;
      const GR = [['buy', 'Depuis l’achat'], ['1m', '1 M'], ['3m', '3 M'], ['6m', '6 M'], ['1y', '1 an'], ['all', 'Tout'], ['15m', '15 min']], SESS = { '1m': 21, '3m': 63, '6m': 126, '1y': 252, all: 0 };
      let gr = store('chart_gr') || 'buy';
      const dlg = J.dialog({ title: (p.name_catalogue || p.name || p.symbol), body: `<div class="seg-row"><span class="seg" id="pc-gr">${GR.map(([k, l]) => `<button type="button" data-v="${k}">${l}</button>`).join('')}</span></div><div id="pc"></div><p class="small muted" id="pc-n"></p>`, actions: [{ label: 'Fermer', run: () => { } }] });
      const buys = d.transactions_list.filter(x => x.side === 'buy' && x.listing_id == p.listing_id).map(x => ({ date: x.trade_at.slice(0, 10), label: 'Achat ' + J.date(x.trade_at) }));
      const open = (d.lots || []).filter(l => l.listing_id == p.listing_id && l.alert && l.alert.measures), first = open[0], lv = [];
      if (p.levels && p.levels.stop) lv.push({ value: +p.levels.stop, label: 'Filet de sécurité' });
      if (first && first.alert.rules && first.alert.rules.drop && !first.alert.rules.off) lv.push({ value: first.alert.measures.high * (1 - first.alert.rules.drop / 100), label: `Alerte −${J.num(first.alert.rules.drop, 0)} % du plus haut` }, { value: first.alert.measures.high, label: 'Plus haut depuis l’achat', cls: 'high' });
      const draw = () => {
        J.$$('#pc-gr button', dlg).forEach(x => x.classList.toggle('on', x.dataset.v === gr));
        if (gr === '15m') { J.$('#pc-n', dlg).textContent = 'Barres de 15 minutes des deux dernières séances.'; J.intradayPanel(J.$('#pc', dlg), p.listing_id); return; }
        const r = J.priceChart(J.$('#pc', dlg), dly, { sessions: gr === 'buy' ? Math.max(5, n) : SESS[gr], ma20: false, ma50: false, volume: false, unit: s.currency, marks: buys, levels: lv });
        J.$('#pc-n', dlg).textContent = r ? (gr === 'buy' ? `Premier achat le ${J.date(since)} · ${J.pct(r.perf, 1)} depuis cette date (cours du titre, hors frais et change).` : `${J.pct(r.perf, 1)} du ${J.date(r.from)} au ${J.date(r.to)} (cours du titre).`) : 'Historique insuffisant.';
      };
      J.$$('#pc-gr button', dlg).forEach(x => x.onclick = () => { gr = x.dataset.v; store('chart_gr', gr); draw(); });
      draw(); });
    J.$('#add-tx').onclick = () => J.txDialog({ portfolios: list, portfolioId: current, onDone: render });
    J.$$('[data-edit]').forEach(b => b.onclick = () => J.txDialog({ portfolios: list, portfolioId: current, tx: d.transactions_list.find(x => x.id == b.dataset.edit), onDone: render }));
    J.$$('[data-del]').forEach(b => b.onclick = async () => { if (await J.confirm('Supprimer la transaction', 'Cette transaction sera supprimée définitivement.', 'Supprimer')) { await J.post('tx/delete', { id: +b.dataset.del }); render(); } });
    J.$('#rename').onclick = () => J.dialog({ title: 'Renommer', body: J.field('Nom', `<input id="nm" value="${J.esc(d.portfolio.name)}">`), actions: [{ label: 'Annuler', run: () => { } }, { label: 'Enregistrer', cls: 'primary', run: async dlg => { await J.post('portfolio/rename', { id: current, name: J.$('#nm', dlg).value }); render(); } }] });
    const mk = J.$('#mk-default'); if (mk) mk.onclick = async () => { await J.post('portfolio/default', { id: current }); render(); };
    J.$('#del-pf').onclick = () => J.dialog({ title: 'Supprimer le portefeuille', body: `<p>Supprimer « ${J.esc(d.portfolio.name)} » et ses ${d.transactions_list.length} transactions ? Cette action est définitive.</p>${d.transactions_list.length ? J.field('Pour confirmer, tapez le nom du portefeuille', '<input id="cf">') : ''}`, actions: [{ label: 'Annuler', run: () => { } }, { label: 'Supprimer', cls: 'danger', run: async dlg => { await J.post('portfolio/delete', { id: current, confirm: J.$('#cf', dlg)?.value || '' }); render(); } }] });
  }
  function createPf() { J.dialog({ title: 'Nouveau portefeuille', body: J.field('Nom', '<input id="nm" maxlength="100" autofocus>'), actions: [{ label: 'Annuler', run: () => { } }, { label: 'Créer', cls: 'primary', run: async d => { const r = await J.post('portfolio/create', { name: J.$('#nm', d).value }); current = r.id; render(); } }] }); }
  render();
})();
