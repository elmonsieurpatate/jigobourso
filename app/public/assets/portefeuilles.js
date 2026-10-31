/* Page Portefeuilles */
(async () => {
  const user = await J.init('portefeuilles'); if (!user) return;
  const page = J.$('#page');
  let list = (await J.api('portfolios')).portfolios;
  let current = +new URLSearchParams(location.search).get('id') || (list.find(p => p.is_default) || list[0] || {}).id;
  const NAMES = { regular: 'Croissance régulière', fast: 'Croissance rapide', recovery: 'Rebond', low_volatility: 'Hausse calme', momentum: 'Momentum 6 mois (essai)', momentum12: 'Momentum 12 mois (essai)' };

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
  async function render() {
    list = (await J.api('portfolios')).portfolios;
    if (!list.length) { page.innerHTML = `<h1>Portefeuilles</h1><div class="card empty"><p>Vous n’avez pas encore de portefeuille.</p><button class="btn primary" id="first">Créer mon premier portefeuille</button></div>`; J.$('#first').onclick = createPf; return; }
    if (!list.find(p => p.id === current)) current = list[0].id;
    const d = await J.api('portfolio', { params: { id: current } }), t = d.totals;
    history.replaceState(null, '', '?id=' + current);
    page.innerHTML = `${d.integrity && !d.integrity.ok ? `<div class="notice err">${d.integrity.issues.map(x => 'Transaction n° ' + x.transaction_id + ' : ' + J.esc(x.message)).join('<br>')}</div>` : ''}<div class="row between"><h1>Portefeuilles</h1><div class="row"><button class="btn" id="new-pf">Nouveau portefeuille</button></div></div>
    <div class="tabs" id="pf-tabs">${list.map(p => `<button data-id="${p.id}" class="${p.id === current ? 'on' : ''}">${J.esc(p.name)}${p.is_default ? ' ★' : ''}</button>`).join('')}</div>
    <div class="grid cols-4">
      <div class="card kpi"><span class="l">Valeur actuelle</span><span class="v">${J.eur(t.value, 0)}</span></div>
      <div class="card kpi"><span class="l">Plus-value latente</span><span class="v ${J.cls(t.unrealized)}">${J.eur(t.unrealized, 0)}</span><span class="small ${J.cls(t.unrealized)}">${J.pct(t.unrealized_pct)}</span></div>
      <div class="card kpi"><span class="l">Plus-value réalisée</span><span class="v ${J.cls(t.realized)}">${J.eur(t.realized, 0)}</span></div>
      <div class="card kpi"><span class="l">Investi (positions ouvertes)</span><span class="v">${J.eur(t.cost, 0)}</span><span class="small muted">frais cumulés ${J.eur(t.fees)}</span></div></div>
    ${t.unpriced ? `<div class="notice warn" style="margin-top:14px">${t.unpriced} position${t.unpriced > 1 ? 's' : ''} sans cours disponible : la valeur totale est sous-estimée.</div>` : ''}
    ${splitNotice(d.positions)}
    ${JEtf.portfolio(d.etf_analysis)}
    <div class="card" style="margin-top:16px"><div class="row between"><h2 style="margin:0">Positions</h2><div class="row"><button class="btn primary small" id="add-tx">Ajouter une transaction</button></div></div>
      <div class="table-wrap"><table><thead><tr><th>Titre</th><th class="num">Quantité</th><th class="num">Prix de revient</th><th class="num">Cours</th><th class="num">Valeur</th><th class="num">+/− value</th><th class="num">Poids</th><th>Garde-fous</th></tr></thead><tbody>
      ${d.positions.map(p => `<tr><td>${p.linked ? `<a href="titre.html?id=${p.listing_id}"><b>${J.esc(p.name_catalogue || p.name || p.symbol)}</b></a>` : `<b>${J.esc(p.name || p.symbol)}</b>`}<div class="small muted">${J.esc(p.symbol)} ${p.catalogue_status === 'excluded' ? `<span class="badge ko help" title="${J.esc(p.excluded_reason || '')}">Hors sélection</span>` : ''}${!p.linked ? '<span class="badge wait help" title="Titre saisi à la main, sans cours">Sans cours</span>' : ''}</div></td>
        <td class="num">${J.num(p.qty, 4)}</td><td class="num">${J.eur(p.avg_cost)}</td><td class="num">${p.price_eur !== null ? J.eur(p.price_eur) + `<div class="small muted">${J.priceLabel(p)} · ${J.ago(p.price_time)}</div>` : '–'}</td>
        <td class="num"><b>${J.eur(p.value)}</b></td><td class="num ${J.cls(p.unrealized)}">${p.unrealized !== null ? J.eur(p.unrealized) + `<div class="small">${J.pct(p.unrealized_pct, 1)}</div>` : '–'}</td><td class="num">${p.weight !== null ? J.pct(p.weight, 1, false) : '–'}</td><td>${levelCell(p)}</td></tr>`).join('') || '<tr><td colspan="7" class="empty">Aucune position ouverte.</td></tr>'}</tbody></table></div></div>
    <div class="card"><div class="row between"><h2 style="margin:0">Transactions <span class="muted small">(${d.transactions_list.length})</span></h2><a class="btn small" href="api.php?r=export&id=${current}">Exporter en CSV</a></div>
      <div class="table-wrap"><table><thead><tr><th>Date</th><th>Sens</th><th>Titre</th><th class="num">Quantité</th><th class="num">Prix</th><th class="num">Frais</th><th></th></tr></thead><tbody>
      ${d.transactions_list.map(x => `<tr><td>${J.date(x.trade_at)}</td><td><span class="badge ${x.side === 'buy' ? 'ok' : 'wait'}">${x.side === 'buy' ? 'Achat' : 'Vente'}</span></td><td>${J.esc(x.name || x.symbol)} <span class="muted small">${J.esc(x.symbol)}</span></td><td class="num">${J.num(+x.quantity, 4)}</td><td class="num">${J.money(+x.unit_price, x.currency)}</td><td class="num">${x.fees ? J.eur(+x.fees) : '–'}</td>
        <td class="num"><button class="btn small" data-edit="${x.id}">Modifier</button> <button class="btn small danger" data-del="${x.id}" aria-label="Supprimer">✕</button></td></tr>`).join('') || '<tr><td colspan="7" class="empty">Aucune transaction.</td></tr>'}</tbody></table></div></div>
    <div class="card"><h2>Réglages du portefeuille</h2><div class="row">
      <button class="btn small" id="rename">Renommer</button>${d.portfolio.is_default ? '' : '<button class="btn small" id="mk-default">Définir par défaut</button>'}<button class="btn small danger" id="del-pf">Supprimer</button></div>
      <p class="small muted" style="margin-bottom:0">Stratégie enregistrée : <b>${d.portfolio.strategy ? (NAMES[d.portfolio.strategy.name] || 'Personnalisée') : 'aucune (Croissance régulière par défaut)'}</b>. Elle se règle depuis l’Explorer (affichage avancé).</p></div>`;
    J.$$('#pf-tabs button').forEach(b => b.onclick = () => { current = +b.dataset.id; render(); });
    J.$('#new-pf').onclick = createPf;
    J.$$('[data-lv]').forEach(b => b.onclick = () => { const p = d.positions.find(x => x.listing_id == b.dataset.lv), L = p.levels || {}, cur = p.price_currency || p.currency;
      J.dialog({ title: 'Garde-fous · ' + (p.name_catalogue || p.name || p.symbol), body: `<p class="small muted">Prix dans la devise de la cotation (${J.esc(cur || '')}). Ce sont des repères personnels : rien n’est vendu automatiquement. Cours actuel : ${px(p.price, cur)} · prix de revient moyen : ${J.eur(p.avg_cost)}.</p>${J.field('Filet de sécurité (stop)', `<input id="lv-stop" inputmode="decimal" value="${L.stop ?? ''}">`)}${J.field('Objectif', `<input id="lv-target" inputmode="decimal" value="${L.target ?? ''}">`)}`,
        actions: [{ label: 'Annuler', run: () => { } }, { label: 'Enregistrer', cls: 'primary', run: async dlg => { const n = i => J.$(i, dlg).value.trim().replace(',', '.'); try { await J.post('position/levels', { portfolio_id: current, listing_id: p.listing_id, stop: n('#lv-stop'), target: n('#lv-target') }); } catch (e) { J.formError(dlg, e.message); return true; } render(); } }] }); });
    J.$$('[data-chart]').forEach(b => b.onclick = async () => { const p = d.positions.find(x => x.listing_id == b.dataset.chart), s = await J.api('sheet', { params: { id: p.listing_id } }), since = (p.first_buy || '').slice(0, 10);
      const dly = s.daily.map((x, i) => [x[0], x[1], s.daily_volume[i]]), from = Math.max(0, dly.findIndex(x => x[0] >= since) - 1), n = dly.length - from;
      const dlg = J.dialog({ title: (p.name_catalogue || p.name || p.symbol) + ' · depuis l’achat', body: '<div id="pc"></div><p class="small muted" id="pc-n"></p>', actions: [{ label: 'Fermer', run: () => { } }] });
      const r = J.priceChart(J.$('#pc', dlg), dly, { sessions: Math.max(5, n), ma20: false, ma50: false, volume: false, unit: s.currency });
      J.$('#pc-n', dlg).textContent = r ? `Premier achat le ${J.date(since)} · ${J.pct(r.perf, 1)} depuis cette date (cours du titre, hors frais et change).` : 'Historique insuffisant.'; });
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
