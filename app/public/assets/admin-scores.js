/* Administration → Scores (V4) : un moteur de notation commun, des profils de stratégie, une simulation sur titres réels, le suivi des calculs.
   Toutes les valeurs viennent du moteur (admin/scores*). Aucune donnée d'exemple : sans données, les écrans le disent. */
(function () {
  const TABS = [['config', 'Configuration du moteur'], ['profils', 'Profils de stratégies'], ['simulation', 'Simulation & exemples'], ['suivi', 'Suivi des calculs']];
  const $ = J.$;
  const E = J.esc;
  const fmt = (v, d = 1) => J.num(v, d);
  const clone = o => JSON.parse(JSON.stringify(o));

  let MINE = false;
  const P = () => MINE ? 'my/scores' : 'admin/scores';
  let root, S, draft, savedJson, sel, rkWhich = 'simple', rkCat = null, rkVerdict = 'all', rkSorts = [], tl = null, rkMore = false, rank = null, confBusy = false, confFail = false, confStale = false, tab = 'config', scoreTab = 'simple', mon = null, monErr = null, sim = null, simWin = 0, simBusy = false, simQ = '', useDraft = true, error = '';
  const autoCache = {};

  const v4 = () => S.strategies.filter(s => s.engine === 'v4');
  const strat = () => S.strategies.find(s => s.name === sel);
  const prof = () => draft.profiles[sel];
  const labels = () => S.period_labels;
  const active = p => S.scoring_periods.filter(id => p.periods[id].enabled);
  const dirty = () => JSON.stringify(draft) !== savedJson;
  const payloadFor = name => { const p = clone(draft.profiles[name]); Object.values(p.periods).forEach(x => delete x.sessions); return { name, ...p }; };
  const payload = () => payloadFor(sel);
  const savedProfiles = () => JSON.parse(savedJson).profiles;

  // Gabarits HTML : admin-scores-view.js lit l'état courant par ces accesseurs et renvoie du HTML (jamais d'écriture dans la page).
  const ctx = { get S() { return S; }, get draft() { return draft; }, get sel() { return sel; }, get tab() { return tab; }, get scoreTab() { return scoreTab; }, get rank() { return rank; }, get rkWhich() { return rkWhich; }, get rkCat() { return rkCat; }, get rkVerdict() { return rkVerdict; }, get rkMore() { return rkMore; }, get confBusy() { return confBusy; }, get confFail() { return confFail; }, get confStale() { return confStale; }, get sim() { return sim; }, get simWin() { return simWin; }, get root() { return root; }, get useDraft() { return useDraft; }, get MINE() { return MINE; }, get chart() { return chart; }, set chart(v) { chart = v; },
    v4: () => v4(), strat: () => strat(), prof: () => prof(), labels: () => labels(), active: p => active(p), weightsOf: p => weightsOf(p), autoWeights: p => autoWeights(p), sum: o => sum(o), rankTable: rows => rankTable(rows) };
  const { chartCard, CLABEL, configView, granText, HORIZONS, profilesView, readout, scoreCell, spark, statusBadge, stratPicker, VOLMODES } = AdminScoresView(ctx);

  function reset() {
    draft = { global: { kappa: S.global.kappa, threshold: S.global.threshold, anchor: S.global.anchor }, profiles: {} };
    v4().forEach(s => { draft.profiles[s.name] = clone(s.current); });
    savedJson = JSON.stringify(draft);
    error = '';
  }

  // Poids automatiques des périodes actives, calculés par le moteur (jamais recopiés ici).
  function autoWeights(p) {
    const ids = active(p), key = draft.global.kappa + '|' + ids.join(',');
    if (autoCache[key]) return autoCache[key];
    if (!autoCache['?' + key]) {
      autoCache['?' + key] = true;
      J.post(P() + '/preview', { kappa: draft.global.kappa, periods: ids }).then(r => { autoCache[key] = r.weights; paint(); }).catch(() => { });
    }
    const st = strat();
    return st && JSON.stringify(Object.keys(st.auto_weights).sort()) === JSON.stringify(ids.slice().sort()) && draft.global.kappa === S.global.kappa ? st.auto_weights : null;
  }
  const weightsOf = p => p.weights_mode === 'custom' ? p.weights : autoWeights(p);
  const sum = o => Object.values(o).reduce((a, b) => a + (+b || 0), 0);

  async function load() {
    S = await J.api(P());
    tl = await TableLayout.load();
    if (!sel || !S.strategies.find(s => s.name === sel)) sel = (v4()[0] || S.strategies[0]).name;
    reset();
  }

  async function render(page, opts) {
    MINE = !!(opts && opts.mine);
    root = page;
    root.innerHTML = '<div class="empty"><span class="spinner"></span></div>';
    await load();
    initRank();
    root.onchange = onChange; root.oninput = onInput; root.onclick = onClick;
    root.onpointermove = chartMove; root.onpointerdown = chartMove; root.onpointerleave = chartLeave; root.onpointerup = e => { if (e.pointerType === 'touch') setTimeout(chartLeave, 2500); };
    root.onkeydown = e => { if (e.key === 'Enter' && e.target.id === 'as-q') { simQ = e.target.value; runSim(null); } };
    if (!window.__asResize) { window.__asResize = true; let tm; window.addEventListener('resize', () => { clearTimeout(tm); tm = setTimeout(() => { if (tab === 'simulation' && sim && sim.result && $('#as-ch')) { const w = $('#as-body').clientWidth; if (chart && Math.abs(w - 40 - chart.W) > 8) paint(); } }, 200); }); }
    skeleton(); paint();
  }

  // ───────────── mise en page ─────────────
  // Squelette posé une fois : la barre d'actions n'est jamais remplacée (un clic sur « Enregistrer » juste après une saisie ne se perd pas) ;
  // seuls l'onglet courant et l'état de la barre sont mis à jour.
  function skeleton() {
    root.innerHTML = `<div class="as">
      <div class="notice as-principle"><b>Principe V4 : un moteur unique pour toutes les stratégies.</b> Le score simple mesure uniquement la pente et le R² des périodes sélectionnées ; le score complexe ajoute séances positives, concentration, volatilité, drawdown, liquidité et l’ancrage récent. Chaque stratégie choisit ses périodes, ses seuils et ses pondérations, sans changer la méthode de calcul. Tous les titres évaluables sont notés et classés ; les filtres d’affichage (page « Filtres et catégories ») n’entrent jamais dans une note.</div>
      <div class="tabs as-tabs" id="as-tabs"></div><div id="as-err"></div><div id="as-body"></div>
      <div class="as-bar"><div id="as-status"></div><div class="row gap-s">
        <button class="btn" data-a="cancel">Annuler les modifications</button>
        <button class="btn" data-a="restore">Restaurer les valeurs par défaut…</button>
        <button class="btn primary" data-a="save">Enregistrer les modifications</button></div></div></div>`;
  }

  function paintBar() {
    const st = strat(), d = dirty(), at = (st && st.saved_at) || S.global.saved_at;
    $('#as-status').innerHTML = d ? '<span class="as-dirty">● Modifications non enregistrées</span>'
      : at ? `<span class="as-saved">✓ Configuration enregistrée le ${E(J.dateTime(at))}</span>` : '<span class="as-saved">✓ Valeurs par défaut en vigueur</span>';
    $('[data-a=cancel]', root).disabled = !d;
    $('[data-a=save]', root).disabled = !(d && isV4Valid());
  }

  function paintBody() {
    const st = strat(), isV4 = st && st.engine === 'v4';
    $('#as-tabs').innerHTML = TABS.filter(t => !(MINE && t[0] === 'suivi')).map(([k, t]) => `<button data-a="tab" data-v="${k}" class="${tab === k ? 'on' : ''}">${t}</button>`).join('');
    $('#as-err').innerHTML = error ? `<div class="notice err mb-3">${E(error)}</div>` : '';
    $('#as-body').innerHTML = tab === 'config' ? configView(st, isV4) : tab === 'profils' ? profilesView() : tab === 'simulation' ? simulationView(isV4) : monitorView();
    if (MINE && tab === 'config') {       // réglages communs : propres à l'administration, lecture seule pour un utilisateur
      $('#as-body').insertAdjacentHTML('afterbegin', '<div class="notice mb-3">Les réglages communs (priorité aux périodes courtes, seuil de fiabilité, ancrage) sont fixés par l’administration. Vos adaptations se font dans « Profils de stratégies » et ne concernent que votre compte.</div>');
      document.querySelectorAll('#as-body [data-a=kappa],#as-body [data-a=anchor],#as-body [data-a=thr]').forEach(e => { e.disabled = true; });
    }
    if (tab === 'suivi' && !mon && !monErr && !MINE) loadMonitor();
    if (tab === 'profils' && !rank && !confBusy && !confFail && st && st.engine === 'v4') runConf();
  }

  function paint() { if (!$('#as-body')) skeleton(); paintBody(); paintBar(); }
  const later = () => setTimeout(paint, 0);       // redessin différé quand on sort d'un champ (évite de remplacer le DOM pendant l'événement « blur »)

  // Graphique interactif : cours réels, axes datés, fenêtre au choix (granularités de notation), lecture au survol ou au toucher.
  let chart = null;
  function chartMove(e) {
    const hit = e.target.closest && e.target.closest('#as-hit'); if (!hit || !chart) return;
    const r = hit.getBoundingClientRect(), f = Math.min(1, Math.max(0, (e.clientX - r.left) / r.width)), i = Math.round(f * (chart.pts.length - 1));
    const cur = $('#as-cur'), dot = $('#as-dot'), x = chart.X(i), y = chart.Y(chart.pts[i].p);
    cur.setAttribute('x1', x); cur.setAttribute('x2', x); dot.setAttribute('cx', x); dot.setAttribute('cy', y); cur.style.display = dot.style.display = '';
    $('#as-read').innerHTML = readout(i);
  }
  function chartLeave() { if (!chart || !$('#as-cur')) return; $('#as-cur').style.display = $('#as-dot').style.display = 'none'; $('#as-read').innerHTML = readout(chart.pts.length - 1); }

  // Colonnes, tri et statut initiaux : Administration → Colonnes (configuration « scores » de l'affichage courant). Le choix fait ensuite dans le tableau reste prioritaire.
  const SC_FALLBACK = () => ['rank', 'name', 'status', 'trend', 'simple', 'complex'].map(id => [id, true]);
  const layoutNow = () => TableLayout.get(tl, 'scores', TableLayout.device(), SC_FALLBACK());
  function initRank() {
    const l = layoutNow();
    rkVerdict = (l.filters && l.filters.verdict) || 'all';
    rkSorts = (l.sort || []).map(x => ({ ...x }));
    if (rkSorts[0] && ['simple', 'complex'].includes(rkSorts[0].key)) rkWhich = rkSorts[0].key;
    if (!window.__asLayoutWatch) { window.__asLayoutWatch = true; TableLayout.onChange(() => { if (rank && $('#as-rktable')) paintBody(); }); }
  }
  const SC_COLS = {
    rank: { cell: r => r.rank == null ? '—' : r.rank, cls: 'as-c-rank', dir: 'asc' },
    name: { cell: r => `<b>${E(r.symbol)}</b> <span class="muted">${E(r.name)}</span>`, cls: 'as-c-name', dir: 'asc' },
    status: { cell: r => statusBadge(r.status), dir: 'asc' },
    kind: { cell: r => r.kind === 'etf' ? 'ETF' : 'Action', dir: 'asc' },
    market: { cell: r => E(r.mic), dir: 'asc' },
    change: { cell: r => r.change == null ? '—' : `<span class="${r.change > 0 ? 'up' : r.change < 0 ? 'down' : ''}">${r.change > 0 ? '+' : ''}${J.num(r.change, 2)} %</span>`, cls: 'as-c-num' },
    trend: { cell: r => spark(r.curve), nosort: true },
    simple: { cell: r => scoreCell(r.simple, r.simple_status, rkWhich === 'simple'), cls: 'as-c-num' },
    complex: { cell: r => scoreCell(r.complex, r.complex_status, rkWhich === 'complex'), cls: 'as-c-num' },
  };
  function rankTable(rows) {
    const l = layoutNow(), cat = l.catalog || Object.keys(SC_COLS).map(id => ({ id, label: id }));
    const label = id => (cat.find(c => c.id === id) || {}).label || id;
    const hint = id => (cat.find(c => c.id === id) || {}).hint || '';
    const cols = l.columns.filter(c => SC_COLS[c.id] && c.visible);
    const prim = rkSorts[0] || { key: rkWhich, dir: 'desc' };
    const w = c => c.width ? ` style="width:${c.width}px;min-width:${c.width}px"` : '';
    return `<div class="as-rkwrap"><table class="dense as-rktable" id="as-rktable">${J.table.head(cols.map(c => ({ label: E(label(c.id)), cls: SC_COLS[c.id].cls || '', scope: 'col', title: hint(c.id) || '', width: c.width, sort: SC_COLS[c.id].nosort ? '' : c.id })), prim)}
      <tbody>${rows.map(r => `<tr>${cols.map(c => `<td class="${SC_COLS[c.id].cls || ''}"${w(c)} data-label="${E(label(c.id))}">${SC_COLS[c.id].cell(r)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
  }
  const rankBody = (extra) => { const body = { strategy: sel, which: rkWhich, category: rkCat, verdict: rkVerdict, sort: rkSorts, limit: 25, ...extra }; if (dirty()) body.draft = { global: draft.global, profile: payload() }; return body; };
  async function runConf(keepCat) {
    confBusy = true; confFail = false; confStale = false; if (!keepCat) rkCat = null; paintBody();
    try { rank = await J.post(P() + '/ranking', rankBody({ offset: 0 })); error = ''; }
    catch (e) { rank = null; confFail = true; error = e.message; }
    confBusy = false; paint();
  }
  async function rankMore() {
    rkMore = true; paintBody();
    try { const r = await J.post(P() + '/ranking', rankBody({ offset: rank.listing.rows.length })); rank.listing.rows = rank.listing.rows.concat(r.listing.rows); rank.listing.total = r.listing.total; }
    catch (e) { error = e.message; }
    rkMore = false; paint();
  }

  // ───────────── simulation ─────────────
  function simulationView(isV4) {
    if (!isV4) return `<div class="notice warn">La simulation porte sur une stratégie V4. Choisissez-en une ci-dessous.<div class="mt-2">${stratPicker()}</div></div>`;
    const cands = sim && sim.candidates && sim.candidates.length > 1 ? `<div class="as-chips"><span class="muted">Autres correspondances :</span> ${sim.candidates.map(c => `<button class="btn sm" data-a="sim-pick" data-id="${c.id}">${E(c.symbol)} <span class="muted">${E(c.name)}</span></button>`).join(' ')}</div>` : '';
    return `<div class="card"><div class="row gap-s" style="flex-wrap:wrap;margin-bottom:8px"><span class="muted">Stratégie :</span> ${stratPicker()}</div>
        ${sim && sim.granularity ? `<p class="as-hint mb-2">${granText({ periods: sim.periods, sessions: sim.granularity })}</p>` : ''}
        <div class="as-searchrow"><input id="as-q" class="as-search" type="search" enterkeyhint="search" placeholder="Symbole, nom ou ISIN d’un titre noté" value="${E(simQ)}"><button class="btn primary" data-a="sim-run">Décomposer</button></div>
        <label class="row gap-s as-chk mt-2"><input type="checkbox" data-a="use-draft" ${useDraft ? 'checked' : ''}> avec mes modifications non enregistrées</label>${cands}</div>
      <div id="as-sim">${simBusy ? '<div class="empty"><span class="spinner"></span></div>' : simBody()}</div>`;
  }

  function simBody() {
    if (!sim) return '<div class="empty">Cherchez un titre réel (symbole, nom ou ISIN) puis cliquez sur « Décomposer ».</div>';
    if (sim.empty) return `<div class="card"><div class="notice warn"><b>Aucune donnée à décomposer.</b> ${E(sim.reason)} Rien n’est remplacé par des exemples fictifs.</div></div>`;
    if (sim.not_found) return '<div class="card"><div class="notice warn">Aucun titre noté ne correspond à cette recherche.</div></div>';
    if (!sim.result) return '<div class="empty">Cherchez un titre réel (symbole, nom ou ISIN) puis cliquez sur « Décomposer ».</div>';
    const r = sim.result, ids = sim.periods.map(x => x.id), L = labels();
    const rk = sim.ranks || {}, rkOf = cls => { const x = rk[cls === 's' ? 'simple' : 'complex']; return x && x.rank ? `rang <b>${x.rank}</b> sur ${J.num(x.of, 0)} · ` : ''; };
    const sc = (o, cls) => `<div class="as-score ${cls}"><span>${cls === 's' ? 'Score simple' : 'Score complexe'}</span><b>${o.score === null ? 'inconnu' : fmt(o.score, 1)}</b>${o.score === null ? '' : ' / 100'}<small>${rkOf(cls)}${o.status === 'ok' ? 'données complètes' : o.status === 'partiel' ? 'données incomplètes' : E(o.why || '')} · couverture ${fmt(100 * (o.coverage || 0), 0)} %${o.score !== null && o.reliable === false ? ' · peu fiable' : ''}</small></div>`;
    const cell = (c, key, unit, d, pid) => { if (!c) return '<td class="num muted">—</td>'; if (pid === 'day' && key !== 'growth') return '<td class="num muted" title="Une seule séance : cette mesure n’existe pas">sans objet</td>'; const raw = c.raw || {}; const val = key === 'growth' ? c.growth : raw[key]; const note = c[key === 'growth' ? 'dynamics' : { r2: 'r2', up_fraction: 'up_days', spike_share: 'concentration', accel: 'acceleration', volatility: 'volatility', drawdown: 'drawdown' }[key]];
      return `<td class="num">${val === null || val === undefined ? '<span class="muted">indisponible</span>' : fmt(unit === '%' ? val * (['up_fraction', 'spike_share'].includes(key) ? 100 : 1) : val, d) + (unit ? ' ' + unit : '')}${note === null || note === undefined ? '' : `<br><small class="muted">note ${fmt(note, 0)}</small>`}</td>`; };
    const rows = [['Croissance (Dynamique)', 'growth', '%', 2], ['Régularité (R²)', 'r2', '', 2], ['Séances positives', 'up_fraction', '%', 0], ['Plus gros pic ÷ hausse nette', 'spike_share', '%', 0], ['Accélération (écart de pente)', 'accel', '', 3], ['Volatilité (par séance)', 'volatility', '%', 2], ['Drawdown', 'drawdown', '%', 1]];
    const s = r.simple, c = r.complex, liq = r.liquidity || {};
    return `<div class="card"><div class="row between" style="flex-wrap:wrap;gap:12px"><div><h3 class="as-h m-0">${E(sim.title.name)}</h3><span class="muted">${E(sim.title.symbol)} · ${E(sim.title.mic)} · ${sim.title.kind === 'etf' ? 'ETF' : 'Action'}</span></div><div class="as-scores">${sc(s, 's')}${sc(c, 'c')}</div></div>
      ${sim.tuning ? `<p class="as-hint">Normalisations utilisées par le calcul : saturation de dynamique <b>${fmt(sim.tuning.sat_a, 1)}</b> · référence d’accélération <b>${fmt(sim.tuning.accel_ref, 2)}</b> · volatilité <b>${E(VOLMODES[sim.tuning.vol_mode] || sim.tuning.vol_mode)}</b> · momentum <b>${E(HORIZONS[sim.tuning.momentum_horizon] || sim.tuning.momentum_horizon)}</b>.</p>` : ''}
      ${chartCard()}
      <div class="table-wrap"><table class="as-dec">${J.table.head(['Mesure', ...ids.map(i => ({ label: `${E(L[i])}<br><small class="muted">poids réel ${fmt(100 * ((r.weights_effective || {})[i] || 0), 1)} %${r.periods[i] ? '' : ' (période sans données)'}</small>`, num: true }))])}<tbody>
        ${rows.map(([n, k, u, d]) => `<tr><td>${n}</td>${ids.map(i => cell(r.periods[i], k, u, d, i)).join('')}</tr>`).join('')}</tbody></table></div>
      <div class="as-two"><div><h4 class="as-h">Score simple (pente × R²)</h4>${s.score === null ? `<p class="muted">${E(s.why || '')}</p>` : `<p>100 × Dynamique <b>${fmt(s.dynamics, 2)}</b> × Régularité <b>${fmt(s.quality, 2)}</b> = <b>${fmt(s.score, 1)}</b></p>
          <table class="as-mini">${J.table.head(["Période", ["Poids réel", 'num'], ["Pente", 'num'], ["R²", 'num'], ["Fiabilité R²", 'num']])}<tbody>${Object.entries(s.parts || {}).map(([k, v]) => `<tr><td>${E(L[k] || k)}</td><td class="num">${fmt(100 * v.weight, 1)} %</td><td class="num">${fmt(v.slope, 2)} %/s</td><td class="num">${v.r2 === null ? '<span class="muted">indisponible</span>' : fmt(v.r2, 2)}</td><td class="num">${v.r2_reliability === null ? '—' : fmt(100 * v.r2_reliability, 0) + ' %'}</td></tr>`).join('')}</tbody></table>
          <p class="as-hint">Complétude : couverture ${fmt(100 * (s.coverage || 0), 0)} % ${s.status === 'ok' ? '(pente et R² mesurés sur toutes les périodes)' : '(une période n’a pas de R² ou de pente : elle sort du calcul, poids renormalisés)'}.</p>`}</div>
        <div><h4 class="as-h">Score complexe (somme pondérée)</h4>${c.score === null ? `<p class="muted">${E(c.why || '')}</p>` : `<table class="as-mini"><tbody>${Object.entries(c.contributions).map(([k, v]) => `<tr><td>${E(CLABEL[k] || k)}</td><td class="num">${v.value === null ? '<span class="muted">indisponible — hors calcul</span>' : `poids ${fmt(100 * v.weight, 1)} %${Math.abs(v.weight_effective - v.weight) > 0.0005 ? ' → réel ' + fmt(100 * v.weight_effective, 1) + ' %' : ''}`}</td><td class="num">${v.value === null ? '' : 'note ' + fmt(v.value, 0)}</td><td class="num">${v.points === null ? '' : '<b>+' + fmt(v.points_effective, 1) + '</b>'}</td></tr>`).join('')}</tbody></table><p class="as-hint">Total ${fmt(c.raw_total, 1)} × ancrage récent ${fmt(c.anchor, 2)} (λ = ${fmt(c.anchor_lambda, 2)}, vigueur de la période courte ${fmt(100 * (c.anchor_gate ?? 0), 0)} %) = <b>${fmt(c.score, 1)}</b>. Complétude : couverture ${fmt(100 * (c.coverage || 0), 0)} %${c.status === 'ok' ? '' : ' — score partiel, composantes absentes hors calcul'}.</p>`}</div></div>
      <p class="as-hint">Liquidité : ${liq.turnover_eur != null ? fmt(liq.turnover_eur / 1e6, 1) + ' M€/jour (' + (liq.source === 'daily' ? 'volumes quotidiens réels' : 'estimée, moyenne trimestrielle') + ') · note ' + fmt(liq.note, 0) : 'indisponible'}. ${r.missing && (r.missing.secondary.length || r.missing.optional_periods.length || r.missing.required_periods.length) ? '<b>Qualité des données :</b> périodes sans historique : ' + (E(r.missing.required_periods.concat(r.missing.optional_periods).join(', ')) || 'aucune') + ' · mesures indisponibles : ' + (E(r.missing.secondary.join(', ')) || 'aucune') + '. Elles sortent du calcul et les poids restants sont renormalisés (ni bonus ni pénalité).' : '<b>Qualité des données :</b> complète.'}</p></div>`;
  }

  async function runSim(id) {
    simBusy = true; paint();
    try {
      const body = { strategy: sel, q: id ? '' : simQ, listing_id: id || null };
      if (useDraft && dirty() && strat().engine === 'v4') body.draft = { global: draft.global, profile: payload() };
      sim = await J.post(P() + '/simulate', body);
    } catch (e) { sim = null; error = e.message; }
    simBusy = false; paint();
  }

  // ───────────── suivi ─────────────
  async function loadMonitor() {
    try { mon = await J.api('admin/scores/monitor'); monErr = null; } catch (e) { monErr = e.message; }
    paint();
  }
  function monitorView() {
    if (monErr) return `<div class="notice err">${E(monErr)}</div>`;
    if (!mon) return '<div class="empty"><span class="spinner"></span></div>';
    const m = mon, l = m.liquidity, n = m.rated, pct = (a, b) => b ? fmt(100 * a / b, 0) + ' %' : '—';
    const stat = k => `<div class="as-tile"><span>${k === 'simple' ? 'Score simple' : 'Score complexe'}</span><b>${J.num(m.counts[k].ok + m.counts[k].partiel, 0)}</b><small>notés et classés · ${J.num(m.counts[k].ok, 0)} complets · ${J.num(m.counts[k].partiel, 0)} incomplets · ${J.num(m.counts[k].inconnu + Math.max(0, l.universe - n), 0)} indisponibles</small></div>`;
    return `${n === 0 ? '<div class="notice warn mb-3"><b>Aucun titre noté.</b> Les mesures de score se remplissent au calcul nocturne ; cette base n’en contient pas encore. Aucune valeur d’exemple n’est affichée.</div>' : ''}
      <div class="as-tiles"><div class="as-tile"><span>Titres notés</span><b>${J.num(n, 0)}</b><small>sur ${J.num(l.universe, 0)} titres recommandables</small></div>${stat('simple')}${stat('complex')}
        <div class="as-tile"><span>Couverture des données</span><b>${m.coverage.median === null ? '—' : fmt(100 * m.coverage.median, 0) + ' %'}</b><small>médiane · minimum ${m.coverage.min === null ? '—' : fmt(100 * m.coverage.min, 0) + ' %'} · ${J.num(m.coverage.full, 0)} complets</small></div></div>
      <div class="as-grid2"><div class="card"><h3 class="as-h">Fraîcheur des données</h3><table class="as-mini"><tbody>
        <tr><td>Dernier cours connu</td><td class="num">${m.freshness.last_close ? E(m.freshness.last_close) : '—'}</td></tr>
        <tr><td>Dernier calcul des indicateurs</td><td class="num">${m.freshness.computed_at ? E(J.dateTime(m.freshness.computed_at)) : '—'}</td></tr>
        <tr><td>Dernier traitement réussi</td><td class="num">${m.last_success ? E(m.last_success.type) + ' · ' + E(J.dateTime(m.last_success.at)) : 'aucun'}</td></tr>
        <tr><td>Titres au dernier cours ancien (&gt; 5 jours)</td><td class="num">${J.num(m.freshness.stale_titles, 0)}</td></tr></tbody></table></div>
        <div class="card"><h3 class="as-h">Liquidité : volumes réels ou estimés</h3><table class="as-mini"><tbody>
        <tr><td>Volumes quotidiens réels</td><td class="num">${J.num(l.daily, 0)}</td><td class="num">${pct(l.daily, l.universe)}</td></tr>
        <tr><td>Estimée (moyenne trimestrielle)</td><td class="num">${J.num(l.estimated, 0)}</td><td class="num">${pct(l.estimated, l.universe)}</td></tr>
        <tr><td>Inconnue</td><td class="num">${J.num(l.unknown, 0)}</td><td class="num">${pct(l.unknown, l.universe)}</td></tr></tbody></table>
        <p class="as-hint">Collecte des volumes quotidiens : <b>${m.volume_collection ? 'activée' : 'désactivée'}</b> · dernière vérification : ${l.volume_checked_at ? E(J.dateTime(l.volume_checked_at)) : 'jamais'}. L’estimation surestime d’environ 12 % en médiane.</p></div></div>
      <div class="card"><div class="row between"><h3 class="as-h m-0">Erreurs de calcul récentes</h3><button class="btn sm" data-a="mon-refresh">Actualiser</button></div>
        ${m.problems.length ? `<table class="as-mini"><tbody>${m.problems.map(p => `<tr><td>${E(J.dateTime(p.at))}</td><td>${E(p.type)}</td><td><span class="badge ${p.status === 'failed' ? 'ko' : 'wait'}">${E(p.status)}</span></td><td>${p.errors ? J.num(p.errors, 0) + ' erreur(s)' : ''} ${E(p.summary || '')}</td></tr>`).join('')}</tbody></table>` : '<p class="muted">Aucune erreur récente enregistrée.</p>'}</div>`;
  }

  // ───────────── actions ─────────────
  function isV4Valid() {
    return v4().every(s => { const p = draft.profiles[s.name]; const ids = active(p); if (!ids.length) return false;
      if (p.weights_mode === 'custom' && Math.abs(sum(Object.fromEntries(ids.map(i => [i, p.weights[i]]))) - 100) > 0.05) return false;
      return Math.abs(sum(p.complex_weights) - 100) <= 0.05; });
  }

  function onInput(e) {
    const t = e.target;
    if (t.dataset.a === 'cw') {
      const k = t.dataset.k; prof().complex_weights[k] = +t.value || 0; paintBar();
      const tot = sum(prof().complex_weights); const el = $('#cw-total'); if (el) { el.textContent = fmt(tot, 1) + ' %'; el.parentElement.className = 'as-total ' + (Math.abs(tot - 100) <= 0.05 ? 'ok' : 'ko'); }
      const b = $('#cwb-' + k), pc = $('#cwp-' + k); if (b) b.style.width = Math.min(100, +t.value || 0) + '%'; if (pc) pc.textContent = fmt(+t.value || 0, 0) + ' %';
    } else if (t.id === 'as-q') simQ = t.value;
  }

  function onChange(e) {
    const t = e.target, a = t.dataset.a, p = sel && draft.profiles[sel];
    if (a === 'strategy') { const keep = tab === 'simulation' && sim && sim.title ? sim.title.id : null; sel = t.value; rank = null; if (keep) { runSim(keep); return; } sim = null; later(); }
    else if (a === 'active') {
      const on = t.checked, q = prof();
      if (!on && active(q).length <= 1) { t.checked = true; J.toast('Au moins une granularité doit rester active'); return; }
      q.periods[t.dataset.p].enabled = on;
      if (q.weights_mode === 'custom') { if (on) q.weights[t.dataset.p] = 0; else delete q.weights[t.dataset.p]; }
      later();
    }
    else if (a === 'req') { p.periods[t.dataset.p].require_history = t.checked; confStale = true; paintBar(); }
    else if (a === 'pw') {
      p.weights[t.dataset.p] = +t.value || 0;
      const tot = sum(Object.fromEntries(active(p).map(i => [i, p.weights[i]]))), el = $('#pw-total');
      if (el) { el.className = 'as-total ' + (Math.abs(tot - 100) <= 0.05 ? 'ok' : 'ko'); el.innerHTML = `Pondération totale : <b>${fmt(tot, 1)} %</b>${Math.abs(tot - 100) > 0.05 ? ' — doit faire 100 %' : ''}`; }
      paintBar();
    }
    else if (a === 'cw') { p.complex_weights[t.dataset.k] = +t.value || 0; paintBar(); }
    else if (a === 'tune') { const k = t.dataset.k, R = S.design.tuning_ranges[k]; p.tuning = p.tuning || clone(S.design.tuning); p.tuning[k] = R ? Math.min(R[1], Math.max(R[0], +t.value || S.design.tuning[k])) : t.value; confStale = true; paintBar(); later(); }
    else if (a === 'kappa') { draft.global.kappa = +t.value; paintBar(); later(); }
    else if (a === 'anchor') { draft.global.anchor = Math.min(1, Math.max(0, +t.value || 0)); paintBar(); }
    else if (a === 'thr') { draft.global.threshold = +t.value; paintBar(); }
    else if (a === 'thr-p') { p.periods[t.dataset.p][t.dataset.f] = t.value === '' ? null : +t.value; confStale = true; paintBar(); }
    else if (a === 'day-on') { p.day_filter.enabled = t.checked; confStale = true; paint(); }
    else if (a === 'day-min') { p.day_filter.min_return = +t.value || 0; confStale = true; paintBar(); }
    else if (a === 'liq') { p.liquidity[t.dataset.f] = t.value === '' ? null : Math.round(+t.value * 1e6); confStale = true; paintBar(); }
    else if (a === 'fresh') { p.technical.require_fresh = t.checked; confStale = true; paintBar(); }
    else if (a === 'use-draft') { useDraft = t.checked; }
  }

  function toCustom() {
    const p = prof(), w = autoWeights(p) || {}, ids = active(p); let acc = 0;
    p.weights = {}; ids.forEach((i, n) => { const v = n === ids.length - 1 ? Math.round((100 - acc) * 10) / 10 : Math.round((w[i] || 0) * 10) / 10; p.weights[i] = v; acc += v; });
    p.weights_mode = 'custom';
  }

  async function onClick(e) {
    const sb = e.target.closest('[data-sort]');
    if (sb) { const v = sb.dataset.sort; rkSorts = [J.table.nextSort(rkSorts[0], v, SC_COLS[v].dir || 'desc')]; if (['simple', 'complex'].includes(v)) { rkWhich = v; rkCat = null; } return runConf(true); }
    const t = e.target.closest('[data-a]'); if (!t || t.tagName === 'INPUT' || t.tagName === 'SELECT') return;
    const a = t.dataset.a, v = t.dataset.v;
    if (a === 'tab') { tab = v; error = ''; paint(); }
    else if (a === 'score') { scoreTab = v; paint(); }
    else if (a === 'mode') { if (v === 'custom') toCustom(); else { prof().weights_mode = 'auto'; prof().weights = {}; } paint(); }
    else if (a === 'pw-auto') { prof().weights_mode = 'auto'; prof().weights = {}; paint(); }
    else if (a === 'cw-norm') { const p = prof(), tot = sum(p.complex_weights) || 1; let acc = 0; const keys = Object.keys(p.complex_weights); keys.forEach((k, i) => { const x = i === keys.length - 1 ? Math.round((100 - acc) * 10) / 10 : Math.round(p.complex_weights[k] / tot * 1000) / 10; p.complex_weights[k] = x; acc += x; }); paint(); }
    else if (a === 'tune-reset') { prof().tuning = prof().tuning || clone(S.design.tuning); prof().tuning[t.dataset.k] = S.design.tuning[t.dataset.k]; confStale = true; paint(); }
    else if (a === 'cw-ref') { prof().complex_weights = clone(S.design.complex_weights); paint(); }
    else if (a === 'open') { sel = v; tab = 'profils'; sim = null; rank = null; paint(); }
    else if (a === 'conf-run') { runConf(true); }
    else if (a === 'rk-which') { rkWhich = v; rkSorts = [{ key: v, dir: 'desc' }]; rkCat = null; runConf(true); }
    else if (a === 'rk-cat') { rkCat = v || null; runConf(true); }
    else if (a === 'rk-verdict') { rkVerdict = v; runConf(true); }
    else if (a === 'rk-more') rankMore();
    else if (a === 'cancel') { reset(); rank = null; paint(); }
    else if (a === 'save') save();
    else if (a === 'restore') restore();
    else if (a === 'sim-run') { simQ = ($('#as-q') || {}).value || ''; runSim(null); }
    else if (a === 'sim-pick') runSim(+t.dataset.id);
    else if (a === 'sim-win') { simWin = +v; paint(); }
    else if (a === 'mon-refresh') { mon = null; monErr = null; paint(); }
  }

  async function save() {
    try {
      const before = savedProfiles(), changed = v4().map(s => s.name).filter(n => JSON.stringify(draft.profiles[n]) !== JSON.stringify(before[n]));
      if (!changed.length && !MINE) S = await J.post(P() + '/save', { global: draft.global });
      for (const [i, n] of changed.entries()) S = await J.post(P() + '/save', i === 0 && !MINE ? { global: draft.global, profile: payloadFor(n) } : { profile: payloadFor(n) });
      reset(); Object.keys(autoCache).forEach(k => delete autoCache[k]); mon = null; sim = null; rank = null; J.toast('Configuration enregistrée');
    } catch (e) { error = e.message; J.toast(e.message); }
    paint();
  }

  function restore() {
    const st = strat(), name = st && st.engine === 'v4' ? st.label : 'la stratégie';
    J.dialog({ title: 'Restaurer les valeurs par défaut', body: `<p class="as-hint">Choisissez ce qui revient aux valeurs proposées. Les modifications non enregistrées seront perdues.</p>
      <label class="as-rad"><input type="radio" name="rs" value="profile" checked> Le profil « ${E(name)} » (périodes, seuils, poids)</label>
      ${MINE ? '' : `<label class="as-rad"><input type="radio" name="rs" value="global"> Les réglages communs (priorité aux périodes courtes, couverture minimale)</label>
      <label class="as-rad"><input type="radio" name="rs" value="all"> Tout (communs et tous les profils V4)</label>`}`,
      actions: [{ label: 'Annuler', run: () => { } }, { label: 'Restaurer', cls: 'primary', run: async d => {
        const scope = ($('input[name=rs]:checked', d) || {}).value || 'profile';
        try { S = await J.post(P() + '/save', scope === 'profile' ? { reset: 'profile', name: st && st.engine === 'v4' ? sel : v4()[0].name } : { reset: scope }); reset(); Object.keys(autoCache).forEach(k => delete autoCache[k]); sim = null; rank = null; J.toast('Valeurs par défaut rétablies'); } catch (e) { J.toast(e.message); }
        paint(); } }] });
  }

  window.AdminScores = { render };
})();
