/* Administration → Scores (V4) : un moteur de notation commun, des profils de stratégie, une simulation sur titres réels, le suivi des calculs.
   Toutes les valeurs viennent du moteur (admin/scores*). Aucune donnée d'exemple : sans données, les écrans le disent. */
(function () {
  const COMPLEX = [
    ['dynamics', 'Dynamique', 'Croissance lissée de la période, ramenée à l’échelle de saturation.'],
    ['r2', 'Régularité (R²)', 'Part de la trajectoire expliquée par une tendance régulière.'],
    ['up_days', 'Séances positives', 'Proportion de séances en hausse.'],
    ['concentration', 'Concentration des gains', 'Poids du plus gros pic dans la hausse (moins c’est concentré, mieux c’est).'],
    ['volatility', 'Volatilité', 'Amplitude des variations quotidiennes (plus c’est calme, mieux c’est).'],
    ['drawdown', 'Drawdown (recul max)', 'Pire recul depuis un sommet sur la période.'],
    ['liquidity', 'Liquidité', 'Valeur échangée par jour, comptée une seule fois pour tout le titre.'],
    ['acceleration', 'Accélération', 'Variation de pente par rapport à la fenêtre précédente (0 dans le profil de référence).'],
    ['momentum', 'Momentum (6/12 mois)', 'Variation du cours hors dernier mois (J−126 ou J−252 → J−21), comptée une seule fois pour le titre (0 dans le profil de référence).'],
    ['recovery', 'Contexte de rebond', 'Le semestre n’a presque pas progressé : 100 si le rendement 6 mois est ≤ −10 %, 0 s’il est ≥ +20 % (0 dans le profil de référence).']];
  const TUNING = [
    ['sat_a', 'Saturation de la dynamique', '% sur 5 séances', 'Croissance (en % sur 5 séances ; (séances/5)^0,52 pour les autres périodes) à laquelle la note de dynamique atteint 100. Plus elle est haute, plus il faut une hausse violente pour saturer : à 17 une semaine à +17 % vaut déjà 100, à 40 il faut +40 %. Sert au score simple et au score complexe.'],
    ['accel_ref', 'Référence d’accélération', 'coefficient', 'Écart de pente (par séance) pour lequel la note d’accélération vaut 100 : saturation(n) ÷ n × ce coefficient. Plus il est haut, plus il faut une accélération forte pour saturer. Le garde-fou de régularité reste actif : la note est multipliée par min(R², R² précédent) ÷ 0,6 (plafonné à 1).'],
    ['vol_mode', 'Notation de la volatilité', 'méthode', 'Absolue : 100 à 1 %/séance, 0 à 5 %/séance. Relative à la pente : rapport volatilité ÷ pente (plancher de pente 0,3 %), 100 à 1 et 0 à 4 : une forte hausse peu heurtée n’est plus écrasée, une pente nulle ou négative reste à 0. Le drawdown et la liquidité restent notés à part.'],
    ['momentum_horizon', 'Horizon du momentum', 'horizon', 'Variation du cours hors dernier mois : 6 mois (100 à +60 %), 12 mois (100 à +100 %) ou moyenne des deux. Sans effet tant que le poids « Momentum » est à 0.']];
  const VOLMODES = { absolute: 'Absolue (1 % → 5 %/séance)', relative: 'Relative à la pente' };
  const HORIZONS = { '6m': '6 mois', '12m': '12 mois', blend: 'Moyenne 6 et 12 mois' };
  const CLABEL = Object.fromEntries(COMPLEX.map(c => [c[0], c[1]]));
  const SIMPLE = [
    ['Dynamique', 'Pente de chaque période, ramenée à une croissance sur la période puis à une échelle de saturation (A % × (séances/5)^0,52 ; A = réglage de la stratégie, 17 par défaut). 100 % = croissance saturée. Moyenne pondérée des périodes mesurables.', 'facteur de 0 à 1'],
    ['Régularité', 'R² de chaque période, chacun pesant min(1, séances/21) car un R² sur peu de séances est bruité. Moyenne pondérée des périodes où le R² est mesuré.', 'facteur de 0 à 1']];
  const LASTDAY = 'Dernier jour : aucun coefficient propre. La dernière séance compte comme les autres séances dans les mesures de chaque période.';
  const TABS = [['config', 'Configuration du moteur'], ['profils', 'Profils de stratégies'], ['simulation', 'Simulation & exemples'], ['suivi', 'Suivi des calculs']];
  const $ = (s, r) => (r || document).querySelector(s);
  const E = s => J.esc(String(s ?? ''));
  const fmt = (v, d = 1) => v === null || v === undefined ? '—' : J.num(v, d);
  const clone = o => JSON.parse(JSON.stringify(o));

  let root, S, draft, savedJson, sel, rkWhich = 'simple', rkCat = null, rkMore = false, rank = null, confBusy = false, confFail = false, confStale = false, tab = 'config', scoreTab = 'simple', mon = null, monErr = null, sim = null, simWin = 0, simBusy = false, simQ = '', useDraft = true, error = '';
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
      J.post('admin/scores/preview', { kappa: draft.global.kappa, periods: ids }).then(r => { autoCache[key] = r.weights; paint(); }).catch(() => { });
    }
    const st = strat();
    return st && JSON.stringify(Object.keys(st.auto_weights).sort()) === JSON.stringify(ids.slice().sort()) && draft.global.kappa === S.global.kappa ? st.auto_weights : null;
  }
  const weightsOf = p => p.weights_mode === 'custom' ? p.weights : autoWeights(p);
  const sum = o => Object.values(o).reduce((a, b) => a + (+b || 0), 0);

  async function load() {
    S = await J.api('admin/scores');
    if (!sel || !S.strategies.find(s => s.name === sel)) sel = (v4()[0] || S.strategies[0]).name;
    reset();
  }

  async function render(page) {
    root = page;
    root.innerHTML = '<div class="empty"><span class="spinner"></span></div>';
    await load();
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
    $('#as-tabs').innerHTML = TABS.map(([k, t]) => `<button data-a="tab" data-v="${k}" class="${tab === k ? 'on' : ''}">${t}</button>`).join('');
    $('#as-err').innerHTML = error ? `<div class="notice err" style="margin-bottom:12px">${E(error)}</div>` : '';
    $('#as-body').innerHTML = tab === 'config' ? configView(st, isV4) : tab === 'profils' ? profilesView() : tab === 'simulation' ? simulationView(isV4) : monitorView();
    if (tab === 'suivi' && !mon && !monErr) loadMonitor();
    if (tab === 'profils' && !rank && !confBusy && !confFail && st && st.engine === 'v4') runConf();
  }

  function paint() { if (!$('#as-body')) skeleton(); paintBody(); paintBar(); }
  const later = () => setTimeout(paint, 0);       // redessin différé quand on sort d'un champ (évite de remplacer le DOM pendant l'événement « blur »)

  function strategyPicker() {
    return `<label class="as-lbl">Stratégie sélectionnée</label><select data-a="strategy" class="as-select">
      <optgroup label="Moteur commun V4">${v4().map(s => `<option value="${E(s.name)}" ${s.name === sel ? 'selected' : ''}>${E(s.label)}</option>`).join('')}</optgroup></select>`;
  }

  function configView(st, isV4) {
    if (!isV4) return `<div class="as-grid"><div class="card">${strategyPicker()}</div><div class="card as-span2">${historicView(st)}</div></div>`;
    const p = prof(), w = weightsOf(p), ids = active(p), custom = p.weights_mode === 'custom';
    const total = custom ? sum(p.weights) : (w ? sum(w) : 0);
    return `<div class="as-grid">
      <div class="card">${strategyPicker()}
        <div class="seg as-seg"><button data-a="mode" data-v="auto" class="${custom ? '' : 'on'}">Automatique</button><button data-a="mode" data-v="custom" class="${custom ? 'on' : ''}">Personnalisé</button></div>
        <p class="as-hint">${custom ? 'Vous fixez vous-même le poids de chaque période (total 100 %).' : 'Les poids des périodes sont calculés automatiquement : les périodes courtes comptent davantage (réglable plus bas).'}</p>
        <h3 class="as-h">Périodes (granularités) actives</h3>
        ${S.scoring_periods.map(id => {
          const x = p.periods[id], on = x.enabled;
          return `<div class="as-period"><label><input type="checkbox" data-a="active" data-p="${id}" ${on ? 'checked' : ''}> ${E(labels()[id])} <span class="muted">(${x.sessions} séances)</span></label>
            ${!on ? '<span class="as-w muted">—</span>' : custom ? `<span class="as-w"><input type="number" class="as-num" data-a="pw" data-p="${id}" min="0" max="100" step="0.1" value="${p.weights[id] ?? 0}"> %</span>` : `<span class="as-w as-pill">${w && w[id] !== undefined ? fmt(w[id], 1) + ' %' : '…'}</span>`}</div>`; }).join('')}
        <div class="as-total ${Math.abs(total - 100) <= 0.05 ? 'ok' : 'ko'}" id="pw-total">Pondération totale : <b>${fmt(total, 1)} %</b>${Math.abs(total - 100) > 0.05 && ids.length ? ' — doit faire 100 %' : ''}</div>
        ${custom ? '<button class="btn small" data-a="pw-auto">Répartir automatiquement</button>' : ''}
        <p class="as-hint">${ids.length} période${ids.length > 1 ? 's' : ''} active${ids.length > 1 ? 's' : ''} sur ${S.scoring_periods.length}. Le « dernier jour » ne se note pas : il faut au moins ${S.formula.min_sessions} séances pour mesurer R² et volatilité.</p></div>
      <div class="card"><div class="row between"><div class="seg"><button data-a="score" data-v="simple" class="${scoreTab === 'simple' ? 'on' : ''}">Score simple</button><button data-a="score" data-v="complex" class="${scoreTab === 'complex' ? 'on' : ''}">Score complexe</button></div><span class="badge accent">Note sur 100</span></div>
        ${scoreTab === 'simple' ? simpleView() : complexView(p)}</div>
      <div class="card"><h3 class="as-h">Paramètres généraux (moteur commun)</h3>
        <div class="as-field"><label>Priorité aux périodes courtes <span class="as-i" title="Symbole κ. À 0, chaque séance pèse pareil donc les longues périodes dominent. Plus la valeur est haute, plus la semaine et le mois pèsent. Ne sert qu’aux poids automatiques.">ⓘ</span></label><input type="number" class="as-num" data-a="kappa" min="0" max="0.95" step="0.05" value="${draft.global.kappa}"></div>
        <p class="as-hint">Valeur 0 à 0,95 · proposée : ${S.design.kappa}. Commun à toutes les stratégies.</p>
        <div class="as-field"><label>Seuil de fiabilité (couverture) <span class="as-i" title="Information seulement : sous ce seuil, la note est calculée mais signalée « peu fiable ». Elle n’est jamais supprimée et ce seuil ne change aucune note.">ⓘ</span></label><input type="number" class="as-num" data-a="thr" min="0.1" max="1" step="0.05" value="${draft.global.threshold}"></div>
        <p class="as-hint">Valeur 0,1 à 1 · proposée : ${S.design.threshold}. Information seulement.</p>
        <div class="as-field"><label>Ancrage récent du score complexe <span class="as-i" title="Pénalise progressivement le score complexe quand la période la plus courte est faible : note × (1 − λ × (1 − vigueur de la période courte)). 0 = neutralisé, 0,5 = valeur actuelle, 1 = maximal. Ne touche pas au score simple.">ⓘ</span></label><input type="number" class="as-num" data-a="anchor" min="0" max="1" step="0.05" value="${draft.global.anchor}"></div>
        <p class="as-hint">Valeur 0 à 1 · proposée : ${S.design.anchor}. À 0, aucune pénalité. Détail dans l’onglet « Score complexe ».</p></div></div>`;
  }

  function simpleView() {
    const f = S.formula;
    return `<h3 class="as-h">Score simple (croissance et régularité)</h3><p class="as-hint">Mesure la force de la tendance (pente) et sa régularité (R²) sur les périodes sélectionnées. Rien d’autre.</p>
      <div class="as-formula">Score simple = 100 × <b>Dynamique</b> (pente) × <b>Régularité</b> (R²) <span class="muted">(plafonné à 100)</span></div>
      <h3 class="as-h">Composantes (formule validée, non modifiable)</h3>
      ${SIMPLE.map(([n, d, e]) => `<div class="as-comp"><div class="row between"><b>${n}</b><span class="badge">${e}</span></div><p class="as-hint">${d}</p></div>`).join('')}
      <div class="notice warn as-lastday">${LASTDAY}</div>
      <p class="as-hint">Les périodes sont combinées avec les poids de la colonne de gauche. Si une période n’a pas assez d’historique, la note est calculée sur les périodes disponibles (poids renormalisés) et marquée « données incomplètes » : le titre reste classé (minimum ${fmt(f.min_sessions, 0)} séances par période).</p>`;
  }

  function complexView(p) {
    const cw = p.complex_weights, total = sum(cw);
    return `<h3 class="as-h">Score complexe (qualité globale) <span class="as-i" title="Somme pondérée de notes 0-100. Ces poids sont propres au profil ; les valeurs proposées sont celles du profil de référence « Croissance rapide ».">ⓘ</span></h3>
      <div class="as-total ${Math.abs(total - 100) <= 0.05 ? 'ok' : 'ko'}">Total : <b id="cw-total">${fmt(total, 1)} %</b></div>
      ${COMPLEX.map(([k, n, d]) => `<div class="as-cw"><span title="${E(d)}">${n}</span><input type="number" class="as-num" data-a="cw" data-k="${k}" min="0" max="100" step="0.5" value="${cw[k] ?? 0}"><span class="as-bar-bg"><span class="as-bar-fg" id="cwb-${k}" style="width:${Math.min(100, cw[k] || 0)}%"></span></span><span class="as-pct" id="cwp-${k}">${fmt(cw[k], 0)} %</span></div>`).join('')}
      <div class="row gap-s" style="margin-top:10px"><button class="btn small" data-a="cw-norm">Normaliser à 100</button><button class="btn small" data-a="cw-ref">Valeurs de référence</button></div>
      ${tuningCard(p)}
      <h3 class="as-h" style="margin-top:14px">Ancrage récent (λ = ${fmt(draft.global.anchor, 2)})</h3>
      <div class="as-formula">Note finale = somme pondérée × <b>(1 − λ × (1 − g))</b>, où g = min(1, dynamique de la période la plus courte ÷ 32), entre 0 et 1.</div>
      <p class="as-hint">Si la période courte (la semaine) garde une dynamique d’au moins 32 sur 100, g = 1 et rien n’est retiré. Plus elle faiblit, plus la note baisse, jusqu’à −λ (−50 % à λ = 0,5) pour une semaine plate ou négative. <b>λ = 0 neutralise l’ancrage.</b> Réglage commun à toutes les stratégies (onglet « Configuration du moteur »). Il ne concerne pas le score simple.</p>
      <p class="as-hint">Sur la base actuelle, la semaine faible pèse déjà dans la dynamique et dans les composantes amorties par g : l’ancrage s’y ajoute. Pour un titre à semaine plate, les deux premiers canaux retirent environ 35 % de la note et l’ancrage 0,5 porte la perte totale à environ 68 %. Le classement reste stable (corrélation de rang 0,996 entre λ = 0 et λ = 0,5, 93 titres communs sur le top 100) : l’ancrage sert surtout à départager les titres encore actifs de ceux qui ont calé.</p>
      <p class="as-hint">La liquidité est comptée une seule fois pour le titre, jamais par période. Le profil de référence (Dynamique 40, R² 15, séances positives 5, concentration 7, volatilité 15, drawdown 8, liquidité 10) est celui de Croissance rapide, pas forcément celui des autres stratégies.</p>`;
  }

  function tuningCard(p) {
    const t = p.tuning || S.design.tuning, d = S.design.tuning, R = S.design.tuning_ranges;
    const field = ([k, n, unit, help]) => {
      const dflt = d[k], cur = t[k], same = cur === dflt;
      const input = k === 'vol_mode' ? `<select class="as-select as-tsel" data-a="tune" data-k="${k}">${S.design.vol_modes.map(v => `<option value="${v}" ${v === cur ? 'selected' : ''}>${E(VOLMODES[v])}</option>`).join('')}</select>`
        : k === 'momentum_horizon' ? `<select class="as-select as-tsel" data-a="tune" data-k="${k}">${S.design.momentum_horizons.map(v => `<option value="${v}" ${v === cur ? 'selected' : ''}>${E(HORIZONS[v])}</option>`).join('')}</select>`
        : `<input type="number" class="as-num" data-a="tune" data-k="${k}" min="${R[k][0]}" max="${R[k][1]}" step="${k === 'sat_a' ? 1 : 0.05}" value="${cur}"> <span class="muted as-unit">${unit}</span>`;
      const shown = k === 'vol_mode' ? VOLMODES[dflt] : k === 'momentum_horizon' ? HORIZONS[dflt] : dflt;
      return `<div class="as-tune"><div class="as-tune-head"><b>${n}</b> <span class="as-i" title="${E(help)}">ⓘ</span></div><div class="as-tune-ctl">${input}</div>
        <p class="as-hint">${E(help)}</p><p class="as-hint as-tune-def">Valeur par défaut : <b>${E(shown)}</b>${k in R ? ` · bornes ${R[k][0]} à ${R[k][1]}` : ''} ${same ? '' : `<button class="btn small" data-a="tune-reset" data-k="${k}">Valeur par défaut</button>`}</p></div>`;
    };
    return `<h3 class="as-h" style="margin-top:14px">Normalisations de cette stratégie (réglages avancés)</h3>
      <p class="as-hint">Propres à la stratégie sélectionnée : elles changent les notes de cette stratégie et d’aucune autre.</p>${TUNING.map(field).join('')}`;
  }

  function historicView(st) {
    return `<div class="notice warn"><b>Moteur historique.</b> « ${E(st.label)} » utilise encore le classement par percentiles : il ne passe pas par les scores V4 et ne se règle pas ici. Aucun de ses réglages n’est modifié par cette page.</div>
      <p class="as-hint" style="margin-top:12px">Périodes actives : ${st.periods.length ? st.periods.map(i => E(labels()[i] || i)).join(', ') : 'aucune'}.</p>
      ${st.components.length ? `<div class="table-wrap"><table><thead><tr><th>Composante</th><th>Période</th><th class="num">Poids</th></tr></thead><tbody>${st.components.map(c => `<tr><td>${E(c.metric)}</td><td>${E(labels()[c.period] || c.period)}</td><td class="num">${fmt(c.weight, 2)}</td></tr>`).join('')}</tbody></table></div>` : '<p class="muted">Aucune composante de score pondérée.</p>'}`;
  }

  function profilesView() {
    const row = s => {
      if (s.engine === 'v4') {
        const p = draft.profiles[s.name], ids = active(p), w = p.weights_mode === 'custom' ? p.weights : (s.name === sel ? autoWeights(p) : s.auto_weights);
        return `<tr><td><b>${E(s.label)}</b><br><small class="muted">${E(s.note)}</small></td><td><span class="badge ok">Moteur commun V4</span></td><td>${ids.map(i => `${E(labels()[i])}${w && w[i] !== undefined ? ' <b>' + fmt(w[i], 1) + ' %</b>' : ''}`).join('<br>') || '—'}</td><td>${p.weights_mode === 'custom' ? 'Personnalisée' : 'Automatique'}</td><td>${s.customised ? '<span class="badge wait">Modifié</span>' : 'Valeurs initiales'}</td><td class="num"><button class="btn small" data-a="open" data-v="${E(s.name)}">Configurer</button></td></tr>`;
      }
      return `<tr class="as-legacy"><td>${E(s.label)}</td><td><span class="badge">Ancien moteur</span></td><td>${s.periods.map(i => E(labels()[i] || i)).join('<br>') || '—'}</td><td>Percentiles</td><td>Préservé</td><td></td></tr>`;
    };
    const pe = S.personal, st = strat(), p = st && st.engine === 'v4' ? prof() : null;
    return `<div class="card"><h3 class="as-h">Profils de stratégies</h3>
      <div class="table-wrap"><table><thead><tr><th>Stratégie</th><th>Moteur</th><th>Granularités et poids</th><th>Pondération</th><th>État</th><th></th></tr></thead><tbody>
      <tr class="as-group"><td colspan="6">Moteur commun V4 — mêmes calculs de score, seuls les réglages changent</td></tr>${v4().map(row).join('')}
</tbody></table></div>
      <p class="as-hint">Stratégies personnelles : ${pe.total ? `${pe.total} enregistrée${pe.total > 1 ? 's' : ''}, dont ${pe.common_engine} sur le moteur commun et ${pe.historic} sur un ancien moteur (non migrées).` : 'aucune enregistrée sur cette base.'}${pe.configurable.length ? ' Configurables ici : ' + pe.configurable.map(c => E(c.name)).join(', ') + '.' : ''}</p></div>
      ${p ? technicalCard(p) + previewCard() : ''}`;
  }

  function technicalCard(p) {
    return `<div class="card"><h3 class="as-h">Données et exclusions techniques</h3>
      <p class="as-hint">Politique des données manquantes (moteur V4.2), sans effet de seuil :</p>
      <ul class="as-hint as-list"><li><b>Historique suffisant</b> : note normale.</li>
        <li><b>Données incomplètes ou historique réduit</b> (une période, une mesure ou la liquidité manque) : la note est calculée sur les composantes disponibles, dont les poids sont renormalisés — sans bonus ni pénalité. Le titre est classé et marqué « incomplet » avec sa couverture.</li>
        <li><b>Calcul impossible</b> (aucune période mesurable, ou aucune régularité mesurable) : note « indisponible » avec la raison ; jamais un zéro ni une note favorable inventés.</li></ul>
      <label class="row gap-s" style="margin-top:8px"><input type="checkbox" data-a="fresh" ${p.technical.require_fresh ? 'checked' : ''}> Exiger des cours récents (contrôle technique : un cours périmé rend le titre non évaluable)</label>
      <p class="as-hint">Seuil de fiabilité : <b>${fmt(100 * draft.global.threshold, 0)} %</b> de couverture (réglage commun, onglet « Configuration du moteur »). En dessous, la note est calculée mais signalée « peu fiable » ; aucun titre n’est supprimé.</p></div>`;
  }

  function dist(d) {
    const max = Math.max(1, ...d.histogram);
    return `<div class="as-hist">${d.histogram.map((n, i) => `<span title="${i * 10}–${i * 10 + 10} : ${n} titres"><i style="height:${Math.round(100 * n / max)}%"></i><small>${i * 10}</small></span>`).join('')}</div>
      <p class="as-hint">Médiane <b>${fmt(d.median, 1)}</b> · quartiles ${fmt(d.p25, 1)} – ${fmt(d.p75, 1)} · 90e centile ${fmt(d.p90, 1)} · maximum ${fmt(d.max, 1)}</p>`;
  }

  function rankTop(rows) {
    return rows.length ? `<table class="as-mini"><tbody>${rows.map(r => `<tr><td class="num">${r.rank}</td><td><b>${E(r.symbol)}</b> <span class="muted">${E(r.name)}</span></td><td class="num">${fmt(r.score, 1)}</td><td>${r.status === 'partiel' ? '<span class="badge wait">incomplet</span>' : ''}</td></tr>`).join('')}</tbody></table>` : '<p class="muted">Aucun titre noté.</p>';
  }

  // Courbe de cours : points réels uniquement, rien d'interpolé. Vert si la période finit au-dessus de son début, rouge sinon.
  function spark(vals, w = 96, h = 26) {
    if (!vals || vals.length < 2) return `<span class="as-nocurve muted" title="Historique insuffisant">—</span>`;
    const lo = Math.min(...vals), hi = Math.max(...vals), span = hi - lo || 1, n = vals.length - 1;
    const pts = vals.map((v, i) => `${(i * (w - 2) / n + 1).toFixed(1)},${(h - 2 - (v - lo) / span * (h - 4)).toFixed(1)}`).join(' ');
    const up = vals[vals.length - 1] >= vals[0], chg = vals[0] ? (vals[n] / vals[0] - 1) * 100 : null;
    const tip = `${n} séances : ${fmt(vals[0], 2)} → ${fmt(vals[n], 2)}${chg === null ? '' : ' (' + (chg >= 0 ? '+' : '') + fmt(chg, 1) + ' %)'}`;
    return `<svg class="as-spark ${up ? 'up' : 'dn'}" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" role="img" aria-label="${tip}"><title>${tip}</title><polyline points="${pts}" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/></svg>`;
  }
  // Graphique interactif : cours réels, axes datés, fenêtre au choix (granularités de notation), lecture au survol ou au toucher.
  let chart = null;
  const dFull = d => new Date(d + 'T00:00:00').toLocaleDateString('fr-FR', { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' });
  const dShort = d => new Date(d + 'T00:00:00').toLocaleDateString('fr-FR', { day: 'numeric', month: 'short' });
  const winSessions = () => { const w = (sim.windows || []), act = w.filter(x => x.active).map(x => x.sessions); return w.some(x => x.sessions === simWin) ? simWin : (act.length ? Math.max(...act) : (w.length ? w[w.length - 1].sessions : 0)); };
  function chartCard() {
    const all = sim.curve || [], wins = sim.windows || [], L = labels();
    if (all.length < 2) return '<p class="muted">Pas assez d’historique pour tracer la courbe.</p>';
    const n = Math.min(winSessions(), all.length - 1), pts = all.slice(-(n + 1)), W = Math.max(260, Math.floor(((root && $('#as-body')) ? $('#as-body').clientWidth : 360) - 40)), H = W < 480 ? 210 : 250;
    const m = { l: 50, r: 10, t: 14, b: 26 }, iw = W - m.l - m.r, ih = H - m.t - m.b;
    const ps = pts.map(x => x.p), lo0 = Math.min(...ps), hi0 = Math.max(...ps), pad = (hi0 - lo0) * 0.08 || hi0 * 0.01 || 1, lo = lo0 - pad, hi = hi0 + pad;
    const X = i => m.l + i * iw / (pts.length - 1), Y = v => m.t + (hi - v) / (hi - lo) * ih;
    const yt = [0, 1, 2, 3].map(k => lo + (hi - lo) * k / 3), nt = Math.min(pts.length, W < 480 ? 3 : 5);
    const xt = [...new Set(Array.from({ length: nt }, (_, j) => Math.round(j * (pts.length - 1) / Math.max(1, nt - 1))))];
    const up = ps[ps.length - 1] >= ps[0], chg = ps[0] ? (ps[ps.length - 1] / ps[0] - 1) * 100 : null;
    const marks = wins.filter(x => x.active && x.sessions < n).map(x => ({ i: pts.length - 1 - x.sessions, lab: L[x.id] || x.id }));
    chart = { pts, X, Y, m, W, H, ih, first: ps[0] };
    const line = pts.map((x, i) => `${X(i).toFixed(1)},${Y(x.p).toFixed(1)}`).join(' ');
    return `<div class="as-chart"><div class="as-win" role="group" aria-label="Fenêtre du graphique">${wins.map(x => `<button class="${x.sessions === n ? 'on' : ''}" data-a="sim-win" data-v="${x.sessions}">${E(L[x.id] || x.id)}<small>${x.sessions} séances${x.active ? ' · stratégie' : ''}</small></button>`).join('')}</div>
      <div class="as-read" id="as-read" aria-live="polite">${readout(pts.length - 1)}</div>
      <svg id="as-ch" class="as-ch ${up ? 'up' : 'dn'}" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" role="img" aria-label="Courbe des cours sur ${n} séances">
        ${yt.map(v => `<line class="g" x1="${m.l}" x2="${W - m.r}" y1="${Y(v).toFixed(1)}" y2="${Y(v).toFixed(1)}"/><text class="t" x="${m.l - 6}" y="${(Y(v) + 4).toFixed(1)}" text-anchor="end">${fmt(v, hi - lo < 5 ? 2 : hi - lo < 50 ? 1 : 0)}</text>`).join('')}
        ${marks.map(k => `<line class="mk" x1="${X(k.i).toFixed(1)}" x2="${X(k.i).toFixed(1)}" y1="${m.t}" y2="${m.t + ih}"/><text class="t mkt" x="${(X(k.i) + 3).toFixed(1)}" y="${m.t + 10}">début ${E(k.lab.toLowerCase())}</text>`).join('')}
        ${xt.map((i, k) => `<text class="t" x="${X(i).toFixed(1)}" y="${H - 7}" text-anchor="${i === 0 ? 'start' : i === pts.length - 1 ? 'end' : 'middle'}">${dShort(pts[i].d)}</text>`).join('')}
        <polyline points="${line}" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/>
        <line id="as-cur" class="cur" x1="0" x2="0" y1="${m.t}" y2="${m.t + ih}" style="display:none"/><circle id="as-dot" r="4.5" cx="0" cy="0" style="display:none"/>
        <rect id="as-hit" x="${m.l}" y="${m.t}" width="${iw}" height="${ih}" fill="transparent"/></svg>
      <p class="as-hint">Cours de clôture réels sur les ${n} dernières séances (du ${dShort(pts[0].d)} au ${dShort(pts[pts.length - 1].d)})${chg === null ? '' : ' · <b>' + (chg >= 0 ? '+' : '') + fmt(chg, 1) + ' %</b>'}. Survolez ou touchez le graphique pour lire le cours de chaque séance.</p></div>`;
  }
  function readout(i) {
    if (!chart) return '';
    const x = chart.pts[i], prev = chart.pts[i - 1], since = chart.first ? (x.p / chart.first - 1) * 100 : null, day = prev && prev.p ? (x.p / prev.p - 1) * 100 : null, sg = v => (v >= 0 ? '+' : '') + fmt(v, 1) + ' %';
    return `<b>${E(dFull(x.d))}</b> · cours <b>${fmt(x.p, 2)}</b>${since === null ? '' : ` · <span class="${since >= 0 ? 'pos' : 'neg'}">${sg(since)}</span> depuis le début`}${day === null ? '' : ` · <span class="${day >= 0 ? 'pos' : 'neg'}">${sg(day)}</span> sur la séance`}`;
  }
  function chartMove(e) {
    const hit = e.target.closest && e.target.closest('#as-hit'); if (!hit || !chart) return;
    const r = hit.getBoundingClientRect(), f = Math.min(1, Math.max(0, (e.clientX - r.left) / r.width)), i = Math.round(f * (chart.pts.length - 1));
    const cur = $('#as-cur'), dot = $('#as-dot'), x = chart.X(i), y = chart.Y(chart.pts[i].p);
    cur.setAttribute('x1', x); cur.setAttribute('x2', x); dot.setAttribute('cx', x); dot.setAttribute('cy', y); cur.style.display = dot.style.display = '';
    $('#as-read').innerHTML = readout(i);
  }
  function chartLeave() { if (!chart || !$('#as-cur')) return; $('#as-cur').style.display = $('#as-dot').style.display = 'none'; $('#as-read').innerHTML = readout(chart.pts.length - 1); }
  const scoreCell = (v, st, main) => `<span class="as-sc ${main ? 'main' : ''}">${v === null || v === undefined ? '<span class="muted">inconnu</span>' : `<b>${fmt(v, 1)}</b>`}<span class="as-flag" ${st === 'partiel' ? 'title="Note calculée sur des données incomplètes (une période ou une mesure manque) : les poids restent répartis sur les composantes disponibles." aria-label="données incomplètes"' : 'aria-hidden="true"'}>${st === 'partiel' ? '*' : ''}</span></span>`;
  // Une ligne de classement : rang, nom, courbe, scores à droite. `which` met en avant le score qui sert au classement.
  function rowHtml(r, which, pick) {
    return `<div class="as-rk ${pick ? 'pick' : ''}" ${pick ? `data-a="sim-pick" data-id="${r.id}" tabindex="0" role="button"` : ''}><span class="as-rk-n">${r.rank ?? '—'}</span>
      <span class="as-rk-name"><b>${E(r.symbol)}</b> <span class="muted">${E(r.name)}</span></span>${spark(r.curve)}
      <span class="as-rk-sc"><span class="as-rk-l">Simple</span>${scoreCell(r.simple, r.simple_status, which === 'simple')}<span class="as-rk-l">Complexe</span>${scoreCell(r.complex, r.complex_status, which === 'complex')}</span></div>`;
  }
  const stratPicker = () => `<select data-a="strategy" class="as-select" aria-label="Stratégie">${v4().map(s => `<option value="${E(s.name)}" ${s.name === sel ? 'selected' : ''}>${E(s.label)}</option>`).join('')}</select>`;
  const granText = g => g ? `${(g.periods || []).map(x => E(labels()[x.id] || x.id)).join(' + ')} — courbes sur ${g.sessions} séances` : '';

  function previewCard() {
    const c = rank, s = c ? c.summary : null, st = strat();
    const block = (key, label) => { const x = s[key], rel = c.compared && c.compared[key]; return `<div class="as-rankcol"><h4 class="as-h">${label}</h4>
        <div class="as-tiles as-tiles3"><div class="as-tile"><span>Notés et classés</span><b>${J.num(x.ranked, 0)}</b><small>sur ${J.num(s.universe, 0)} titres</small></div>
          <div class="as-tile"><span>Note indisponible</span><b>${J.num(x.unavailable, 0)}</b><small>calcul impossible ou mesures absentes</small></div>
          <div class="as-tile"><span>Données incomplètes</span><b>${J.num(x.reduced_history, 0)}</b><small>${J.num(x.unreliable, 0)} sous le seuil de fiabilité</small></div></div>
        ${dist(x.distribution)}
        ${rel ? `<p class="as-hint"><b>Effet de vos modifications :</b> ${J.num(rel.score_changed, 0)} notes changent ; rang médian déplacé de ${J.num(rel.median_shift, 0)} ; ${J.num(rel.moved_over_10, 0)} titres bougent de plus de 10 places ; dans le top ${rel.top} : ${rel.top_entered} entrée${rel.top_entered > 1 ? 's' : ''}, ${rel.top_left} sortie${rel.top_left > 1 ? 's' : ''}.</p>` : ''}</div>`; };
    return `<div class="card"><div class="row between" style="flex-wrap:wrap;gap:8px"><h3 class="as-h" style="margin:0">Classement général sur la base actuelle</h3><button class="btn small" data-a="conf-run">${confBusy ? 'Calcul…' : 'Recalculer'}</button></div>
      <div class="row gap-s" style="flex-wrap:wrap;margin:8px 0"><span class="muted">Stratégie :</span> ${stratPicker()}<span class="as-hint" style="margin:0">${c ? granText(c.granularity) : ''}</span></div>
      ${confStale ? '<p class="as-hint" style="color:var(--warn)">Réglages modifiés depuis ce calcul : cliquez sur « Recalculer ».</p>' : ''}
      ${confBusy && !c ? '<div class="empty"><span class="spinner"></span></div>' : !c ? `<p class="muted">${confFail ? 'Calcul impossible : voir le message ci-dessus.' : 'Calcul au premier affichage.'}</p>` : s.universe === 0 ? '<div class="notice warn" style="margin-top:8px">Aucun titre dans cette base : rien à noter. Aucune valeur d’exemple n’est affichée.</div>' : `
        <p class="as-hint">Stratégie « ${E(st ? st.label : '')} » : ${granText(c.granularity)}. Tous les titres évaluables sont notés et classés, du meilleur au moins bon. Le rang est le rang général : choisir une catégorie ne le change pas.</p>
        <div class="row between" style="flex-wrap:wrap;gap:8px"><div class="seg"><button data-a="rk-which" data-v="simple" class="${rkWhich === 'simple' ? 'on' : ''}">Classé par score simple</button><button data-a="rk-which" data-v="complex" class="${rkWhich === 'complex' ? 'on' : ''}">Classé par score complexe</button></div></div>
        <div class="as-chips" style="margin:8px 0"><button class="btn small ${rkCat ? '' : 'primary'}" data-a="rk-cat" data-v="">Toutes <b>${J.num(c.listing.categories.reduce((a, x) => a + x.count, 0), 0)}</b></button>
          ${c.listing.categories.map(k => `<button class="btn small ${rkCat === k.id ? 'primary' : ''}" data-a="rk-cat" data-v="${E(k.id)}"><i class="as-dot" style="background:${E(k.color || '#999')}"></i> ${E(k.name)} <b>${J.num(k.count, 0)}</b></button>`).join('')}</div>
        <div class="as-rklist">${c.listing.rows.length ? c.listing.rows.map(r => rowHtml(r, rkWhich)).join('') : '<p class="muted">Aucun titre dans cette catégorie.</p>'}</div>
        <p class="as-hint">* note calculée sur des données incomplètes. Ce classement porte sur tous les titres notés ; la page Classement n’affiche par défaut que ceux admis par les seuils de la stratégie, avec exactement les mêmes rangs et les mêmes notes (« Titres hors stratégie » affiche le reste).</p>
        ${c.listing.rows.length < c.listing.total ? `<div style="margin-top:8px"><button class="btn small" data-a="rk-more" ${rkMore ? 'disabled' : ''}>${rkMore ? 'Chargement…' : `Afficher la suite (${c.listing.rows.length} sur ${J.num(c.listing.total, 0)})`}</button></div>` : `<p class="as-hint">${J.num(c.listing.total, 0)} titre${c.listing.total > 1 ? 's' : ''}.</p>`}
        <div class="as-ranks" style="margin-top:14px">${block('simple', 'Score simple')}${block('complex', 'Score complexe')}</div>
        ${s.unavailable_reasons.length ? `<p class="as-hint"><b>Pourquoi une note est indisponible :</b> ${s.unavailable_reasons.map(r => `${E(r.reason)} (${J.num(r.count, 0)})`).join(' · ')}${s.no_inputs ? ` · ${J.num(s.no_inputs, 0)} titres sans mesures de score calculées` : ''}.</p>` : s.no_inputs ? `<p class="as-hint">${J.num(s.no_inputs, 0)} titres sans mesures de score calculées.</p>` : ''}
        <p class="as-hint">Moteur de notation version ${c.engine_version}. Poids réels des périodes : ${c.weights.map(w => `${E(labels()[w.id])} <b>${fmt(100 * w.weight, 1)} %</b>`).join(' · ')} (κ = ${fmt(c.kappa, 2)}${c.weights.some(w => w.custom) ? ', poids personnalisés' : ', automatiques'}).</p>`}</div>`;
  }

  const rankBody = (extra) => { const body = { strategy: sel, which: rkWhich, category: rkCat, limit: 25, ...extra }; if (dirty()) body.draft = { global: draft.global, profile: payload() }; return body; };
  async function runConf(keepCat) {
    confBusy = true; confFail = false; confStale = false; if (!keepCat) rkCat = null; paintBody();
    try { rank = await J.post('admin/scores/ranking', rankBody({ offset: 0 })); error = ''; }
    catch (e) { rank = null; confFail = true; error = e.message; }
    confBusy = false; paint();
  }
  async function rankMore() {
    rkMore = true; paintBody();
    try { const r = await J.post('admin/scores/ranking', rankBody({ offset: rank.listing.rows.length })); rank.listing.rows = rank.listing.rows.concat(r.listing.rows); rank.listing.total = r.listing.total; }
    catch (e) { error = e.message; }
    rkMore = false; paint();
  }

  // ───────────── simulation ─────────────
  function simulationView(isV4) {
    if (!isV4) return `<div class="notice warn">La simulation porte sur une stratégie V4. Choisissez-en une ci-dessous.<div style="margin-top:8px">${stratPicker()}</div></div>`;
    const cands = sim && sim.candidates && sim.candidates.length > 1 ? `<div class="as-chips"><span class="muted">Autres correspondances :</span> ${sim.candidates.map(c => `<button class="btn small" data-a="sim-pick" data-id="${c.id}">${E(c.symbol)} <span class="muted">${E(c.name)}</span></button>`).join(' ')}</div>` : '';
    return `<div class="card"><div class="row gap-s" style="flex-wrap:wrap;margin-bottom:8px"><span class="muted">Stratégie :</span> ${stratPicker()}</div>
        ${sim && sim.granularity ? `<p class="as-hint" style="margin:0 0 8px">${granText({ periods: sim.periods, sessions: sim.granularity })}</p>` : ''}
        <div class="as-searchrow"><input id="as-q" class="as-search" type="search" enterkeyhint="search" placeholder="Symbole, nom ou ISIN d’un titre noté" value="${E(simQ)}"><button class="btn primary" data-a="sim-run">Décomposer</button></div>
        <label class="row gap-s as-chk" style="margin-top:8px"><input type="checkbox" data-a="use-draft" ${useDraft ? 'checked' : ''}> avec mes modifications non enregistrées</label>${cands}</div>
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
    const cell = (c, key, unit, d) => { if (!c) return '<td class="num muted">—</td>'; const raw = c.raw || {}; const val = key === 'growth' ? c.growth : raw[key]; const note = c[key === 'growth' ? 'dynamics' : { r2: 'r2', up_fraction: 'up_days', spike_share: 'concentration', accel: 'acceleration', volatility: 'volatility', drawdown: 'drawdown' }[key]];
      return `<td class="num">${val === null || val === undefined ? '<span class="muted">indisponible</span>' : fmt(unit === '%' ? val * (['up_fraction', 'spike_share'].includes(key) ? 100 : 1) : val, d) + (unit ? ' ' + unit : '')}${note === null || note === undefined ? '' : `<br><small class="muted">note ${fmt(note, 0)}</small>`}</td>`; };
    const rows = [['Croissance (Dynamique)', 'growth', '%', 2], ['Régularité (R²)', 'r2', '', 2], ['Séances positives', 'up_fraction', '%', 0], ['Plus gros pic ÷ hausse nette', 'spike_share', '%', 0], ['Accélération (écart de pente)', 'accel', '', 3], ['Volatilité (par séance)', 'volatility', '%', 2], ['Drawdown', 'drawdown', '%', 1]];
    const s = r.simple, c = r.complex, liq = r.liquidity || {};
    return `<div class="card"><div class="row between" style="flex-wrap:wrap;gap:12px"><div><h3 class="as-h" style="margin:0">${E(sim.title.name)}</h3><span class="muted">${E(sim.title.symbol)} · ${E(sim.title.mic)} · ${sim.title.kind === 'etf' ? 'ETF' : 'Action'}</span></div><div class="as-scores">${sc(s, 's')}${sc(c, 'c')}</div></div>
      ${sim.tuning ? `<p class="as-hint">Normalisations utilisées par le calcul : saturation de dynamique <b>${fmt(sim.tuning.sat_a, 1)}</b> · référence d’accélération <b>${fmt(sim.tuning.accel_ref, 2)}</b> · volatilité <b>${E(VOLMODES[sim.tuning.vol_mode] || sim.tuning.vol_mode)}</b> · momentum <b>${E(HORIZONS[sim.tuning.momentum_horizon] || sim.tuning.momentum_horizon)}</b>.</p>` : ''}
      ${chartCard()}
      <div class="table-wrap"><table class="as-dec"><thead><tr><th>Mesure</th>${ids.map(i => `<th class="num">${E(L[i])}<br><small class="muted">poids réel ${fmt(100 * ((r.weights_effective || {})[i] || 0), 1)} %${r.periods[i] ? '' : ' (période sans données)'}</small></th>`).join('')}</tr></thead><tbody>
        ${rows.map(([n, k, u, d]) => `<tr><td>${n}</td>${ids.map(i => cell(r.periods[i], k, u, d)).join('')}</tr>`).join('')}</tbody></table></div>
      <div class="as-two"><div><h4 class="as-h">Score simple (pente × R²)</h4>${s.score === null ? `<p class="muted">${E(s.why || '')}</p>` : `<p>100 × Dynamique <b>${fmt(s.dynamics, 2)}</b> × Régularité <b>${fmt(s.quality, 2)}</b> = <b>${fmt(s.score, 1)}</b></p>
          <table class="as-mini"><thead><tr><th>Période</th><th class="num">Poids réel</th><th class="num">Pente</th><th class="num">R²</th><th class="num">Fiabilité R²</th></tr></thead><tbody>${Object.entries(s.parts || {}).map(([k, v]) => `<tr><td>${E(L[k] || k)}</td><td class="num">${fmt(100 * v.weight, 1)} %</td><td class="num">${fmt(v.slope, 2)} %/s</td><td class="num">${v.r2 === null ? '<span class="muted">indisponible</span>' : fmt(v.r2, 2)}</td><td class="num">${v.r2_reliability === null ? '—' : fmt(100 * v.r2_reliability, 0) + ' %'}</td></tr>`).join('')}</tbody></table>
          <p class="as-hint">Complétude : couverture ${fmt(100 * (s.coverage || 0), 0)} % ${s.status === 'ok' ? '(pente et R² mesurés sur toutes les périodes)' : '(une période n’a pas de R² ou de pente : elle sort du calcul, poids renormalisés)'}.</p>`}</div>
        <div><h4 class="as-h">Score complexe (somme pondérée)</h4>${c.score === null ? `<p class="muted">${E(c.why || '')}</p>` : `<table class="as-mini"><tbody>${Object.entries(c.contributions).map(([k, v]) => `<tr><td>${E(CLABEL[k] || k)}</td><td class="num">${v.value === null ? '<span class="muted">indisponible — hors calcul</span>' : `poids ${fmt(100 * v.weight, 1)} %${Math.abs(v.weight_effective - v.weight) > 0.0005 ? ' → réel ' + fmt(100 * v.weight_effective, 1) + ' %' : ''}`}</td><td class="num">${v.value === null ? '' : 'note ' + fmt(v.value, 0)}</td><td class="num">${v.points === null ? '' : '<b>+' + fmt(v.points_effective, 1) + '</b>'}</td></tr>`).join('')}</tbody></table><p class="as-hint">Total ${fmt(c.raw_total, 1)} × ancrage récent ${fmt(c.anchor, 2)} (λ = ${fmt(c.anchor_lambda, 2)}, vigueur de la période courte ${fmt(100 * (c.anchor_gate ?? 0), 0)} %) = <b>${fmt(c.score, 1)}</b>. Complétude : couverture ${fmt(100 * (c.coverage || 0), 0)} %${c.status === 'ok' ? '' : ' — score partiel, composantes absentes hors calcul'}.</p>`}</div></div>
      <p class="as-hint">Liquidité : ${liq.turnover_eur != null ? fmt(liq.turnover_eur / 1e6, 1) + ' M€/jour (' + (liq.source === 'daily' ? 'volumes quotidiens réels' : 'estimée, moyenne trimestrielle') + ') · note ' + fmt(liq.note, 0) : 'indisponible'}. ${r.missing && (r.missing.secondary.length || r.missing.optional_periods.length || r.missing.required_periods.length) ? '<b>Qualité des données :</b> périodes sans historique : ' + (E(r.missing.required_periods.concat(r.missing.optional_periods).join(', ')) || 'aucune') + ' · mesures indisponibles : ' + (E(r.missing.secondary.join(', ')) || 'aucune') + '. Elles sortent du calcul et les poids restants sont renormalisés (ni bonus ni pénalité).' : '<b>Qualité des données :</b> complète.'}</p></div>`;
  }

  async function runSim(id) {
    simBusy = true; paint();
    try {
      const body = { strategy: sel, q: id ? '' : simQ, listing_id: id || null };
      if (useDraft && dirty() && strat().engine === 'v4') body.draft = { global: draft.global, profile: payload() };
      sim = await J.post('admin/scores/simulate', body);
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
    return `${n === 0 ? '<div class="notice warn" style="margin-bottom:12px"><b>Aucun titre noté.</b> Les mesures de score se remplissent au calcul nocturne ; cette base n’en contient pas encore. Aucune valeur d’exemple n’est affichée.</div>' : ''}
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
      <div class="card"><div class="row between"><h3 class="as-h" style="margin:0">Erreurs de calcul récentes</h3><button class="btn small" data-a="mon-refresh">Actualiser</button></div>
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
    else if (a === 'rk-which') { rkWhich = v; rkCat = null; runConf(true); }
    else if (a === 'rk-cat') { rkCat = v || null; runConf(true); }
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
      if (!changed.length) S = await J.post('admin/scores/save', { global: draft.global });
      for (const [i, n] of changed.entries()) S = await J.post('admin/scores/save', i === 0 ? { global: draft.global, profile: payloadFor(n) } : { profile: payloadFor(n) });
      reset(); Object.keys(autoCache).forEach(k => delete autoCache[k]); mon = null; sim = null; rank = null; J.toast('Configuration enregistrée');
    } catch (e) { error = e.message; J.toast(e.message); }
    paint();
  }

  function restore() {
    const st = strat(), name = st && st.engine === 'v4' ? st.label : 'la stratégie';
    J.dialog({ title: 'Restaurer les valeurs par défaut', body: `<p class="as-hint">Choisissez ce qui revient aux valeurs proposées. Les modifications non enregistrées seront perdues.</p>
      <label class="as-rad"><input type="radio" name="rs" value="profile" checked> Le profil « ${E(name)} » (périodes, seuils, poids)</label>
      <label class="as-rad"><input type="radio" name="rs" value="global"> Les réglages communs (priorité aux périodes courtes, couverture minimale)</label>
      <label class="as-rad"><input type="radio" name="rs" value="all"> Tout (communs et tous les profils V4)</label>`,
      actions: [{ label: 'Annuler', run: () => { } }, { label: 'Restaurer', cls: 'primary', run: async d => {
        const scope = ($('input[name=rs]:checked', d) || {}).value || 'profile';
        try { S = await J.post('admin/scores/save', scope === 'profile' ? { reset: 'profile', name: st && st.engine === 'v4' ? sel : v4()[0].name } : { reset: scope }); reset(); Object.keys(autoCache).forEach(k => delete autoCache[k]); sim = null; rank = null; J.toast('Valeurs par défaut rétablies'); } catch (e) { J.toast(e.message); }
        paint(); } }] });
  }

  window.AdminScores = { render };
})();
