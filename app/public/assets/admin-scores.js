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
    ['acceleration', 'Accélération', 'Variation de pente par rapport à la fenêtre précédente (0 dans le profil de référence).']];
  const CLABEL = Object.fromEntries(COMPLEX.map(c => [c[0], c[1]]));
  const SIMPLE = [
    ['Dynamique', 'Croissance lissée de chaque période, ramenée à une échelle de saturation (17 % × (séances/5)^0,52). 100 % = croissance saturée.', 'facteur de 0 à 1'],
    ['Régularité', 'R² (pleine fiabilité dès 21 séances) × (1 − ½ × part du plus gros pic) × (½ + ½ × séances positives). Pénalise les hausses en un seul saut.', 'facteur de 0 à 1'],
    ['Accélération', 'Écart de pente avec la fenêtre précédente, pondéré par la régularité. Indisponible : facteur neutre.', 'facteur de 0,90 à 1,10']];
  const LASTDAY = 'Dernier jour : la variation de la dernière séance n’entre pas encore dans la note (intégration à valider). Le filtre facultatif « dernier jour positif » est indépendant de la notation (Profils de stratégies, mode avancé).';
  const TABS = [['config', 'Configuration du moteur'], ['profils', 'Profils de stratégies'], ['simulation', 'Simulation & exemples'], ['suivi', 'Suivi des calculs']];
  const $ = (s, r) => (r || document).querySelector(s);
  const E = s => J.esc(String(s ?? ''));
  const fmt = (v, d = 1) => v === null || v === undefined ? '—' : J.num(v, d);
  const clone = o => JSON.parse(JSON.stringify(o));

  let root, S, draft, savedJson, sel, adv = false, conf = null, confBusy = false, confFail = false, confStale = false, tab = 'config', scoreTab = 'simple', mon = null, monErr = null, sim = null, simBusy = false, simQ = '', useDraft = true, error = '';
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
    draft = { global: { kappa: S.global.kappa, threshold: S.global.threshold }, profiles: {} };
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
    skeleton(); paint();
  }

  // ───────────── mise en page ─────────────
  // Squelette posé une fois : la barre d'actions n'est jamais remplacée (un clic sur « Enregistrer » juste après une saisie ne se perd pas) ;
  // seuls l'onglet courant et l'état de la barre sont mis à jour.
  function skeleton() {
    root.innerHTML = `<div class="as">
      <div class="notice as-principle"><b>Principe V4 : un moteur unique pour toutes les stratégies.</b> Le score simple mesure la croissance et sa régularité (avec accélération) ; le score complexe ajoute risque, volatilité, concentration et liquidité. Chaque stratégie choisit ses périodes, ses seuils et ses pondérations, sans changer la méthode de calcul. Les seuils de conformité filtrent, ils n’entrent jamais dans une note.</div>
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
    if (tab === 'profils' && !conf && !confBusy && !confFail && st && st.engine === 'v4') runConf();
  }

  function paint() { if (!$('#as-body')) skeleton(); paintBody(); paintBar(); }
  const later = () => setTimeout(paint, 0);       // redessin différé quand on sort d'un champ (évite de remplacer le DOM pendant l'événement « blur »)

  function strategyPicker() {
    return `<label class="as-lbl">Stratégie sélectionnée</label><select data-a="strategy" class="as-select">
      <optgroup label="Moteur commun V4">${v4().map(s => `<option value="${E(s.name)}" ${s.name === sel ? 'selected' : ''}>${E(s.label)}</option>`).join('')}</optgroup>
      <optgroup label="Anciens moteurs (préservés, lecture seule)">${S.strategies.filter(s => s.engine === 'historic').map(s => `<option value="${E(s.name)}" ${s.name === sel ? 'selected' : ''}>${E(s.label)}</option>`).join('')}</optgroup></select>`;
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
        <div class="as-field"><label>Couverture minimale des données <span class="as-i" title="Part des mesures nécessaires pour noter un titre. En dessous, la note reste « inconnue » (jamais 0). Entre ce seuil et 100 %, elle est « partielle ».">ⓘ</span></label><input type="number" class="as-num" data-a="thr" min="0.1" max="1" step="0.05" value="${draft.global.threshold}"></div>
        <p class="as-hint">Valeur 0,1 à 1 · proposée : ${S.design.threshold}.</p></div></div>`;
  }

  function simpleView() {
    const f = S.formula;
    return `<h3 class="as-h">Score simple (croissance et régularité)</h3><p class="as-hint">Mesure la force de la tendance, sa régularité et son accélération.</p>
      <div class="as-formula">Score simple = 100 × <b>Dynamique</b> × <b>Régularité</b> × <b>facteur d’accélération</b> <span class="muted">(plafonné à 100)</span></div>
      <h3 class="as-h">Composantes (formule validée, non modifiable)</h3>
      ${SIMPLE.map(([n, d, e]) => `<div class="as-comp"><div class="row between"><b>${n}</b><span class="badge">${e}</span></div><p class="as-hint">${d}</p></div>`).join('')}
      <div class="notice warn as-lastday">${LASTDAY}</div>
      <p class="as-hint">Les périodes sont combinées avec les poids de la colonne de gauche. Une période obligatoire sans historique rend le titre « inconnu » ; une période facultative absente baisse seulement la couverture (minimum ${fmt(f.min_sessions, 0)} séances par période).</p>`;
  }

  function complexView(p) {
    const cw = p.complex_weights, total = sum(cw);
    return `<h3 class="as-h">Score complexe (qualité globale) <span class="as-i" title="Somme pondérée de notes 0-100. Ces poids sont propres au profil ; les valeurs proposées sont celles du profil de référence « Croissance rapide ».">ⓘ</span></h3>
      <div class="as-total ${Math.abs(total - 100) <= 0.05 ? 'ok' : 'ko'}">Total : <b id="cw-total">${fmt(total, 1)} %</b></div>
      ${COMPLEX.map(([k, n, d]) => `<div class="as-cw"><span title="${E(d)}">${n}</span><input type="number" class="as-num" data-a="cw" data-k="${k}" min="0" max="100" step="0.5" value="${cw[k] ?? 0}"><span class="as-bar-bg"><span class="as-bar-fg" id="cwb-${k}" style="width:${Math.min(100, cw[k] || 0)}%"></span></span><span class="as-pct" id="cwp-${k}">${fmt(cw[k], 0)} %</span></div>`).join('')}
      <div class="row gap-s" style="margin-top:10px"><button class="btn small" data-a="cw-norm">Normaliser à 100</button><button class="btn small" data-a="cw-ref">Valeurs de référence</button></div>
      <p class="as-hint">La liquidité est comptée une seule fois pour le titre, jamais par période. Le profil de référence (Dynamique 40, R² 15, séances positives 5, concentration 7, volatilité 15, drawdown 8, liquidité 10) est celui de Croissance rapide, pas forcément celui des autres stratégies.</p>`;
  }

  function historicView(st) {
    return `<div class="notice warn"><b>Moteur historique.</b> « ${E(st.label)} » utilise encore le classement par percentiles : il ne passe pas par les scores V4 et ne se règle pas ici. Aucun de ses réglages n’est modifié par cette page.</div>
      <p class="as-hint" style="margin-top:12px">Périodes actives : ${st.periods.length ? st.periods.map(i => E(labels()[i] || i)).join(', ') : 'aucune'}.</p>
      ${st.components.length ? `<div class="table-wrap"><table><thead><tr><th>Composante</th><th>Période</th><th class="num">Poids</th></tr></thead><tbody>${st.components.map(c => `<tr><td>${E(c.metric)}</td><td>${E(labels()[c.period] || c.period)}</td><td class="num">${fmt(c.weight, 2)}</td></tr>`).join('')}</tbody></table></div>` : '<p class="muted">Aucune composante de score pondérée.</p>'}`;
  }

  const PCT = (v, d = 1) => v === null || v === undefined ? '' : v;
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
      <tr class="as-group"><td colspan="6">Anciens moteurs — comportement préservé tant qu’aucune migration n’est validée</td></tr>${S.strategies.filter(s => s.engine === 'historic').map(row).join('')}</tbody></table></div>
      <p class="as-hint">Stratégies personnelles : ${pe.total ? `${pe.total} enregistrée${pe.total > 1 ? 's' : ''}, dont ${pe.common_engine} sur le moteur commun et ${pe.historic} sur un ancien moteur (non migrées).` : 'aucune enregistrée sur cette base.'}${pe.configurable.length ? ' Configurables ici : ' + pe.configurable.map(c => E(c.name)).join(', ') + '.' : ''}</p></div>
      ${p ? conformityCard(st, p) + technicalCard(p) + previewCard() : ''}`;
  }

  function conformityCard(st, p) {
    const th = (id, f, step) => { const x = p.periods[id]; return `<td><input type="number" class="as-num" data-a="thr-p" data-p="${id}" data-f="${f}" step="${step}" value="${PCT(x[f])}" ${x.enabled ? '' : 'disabled'} placeholder="aucun"></td>`; };
    const mm = (v) => v === null || v === undefined ? '' : v / 1e6;
    return `<div class="card"><div class="row between" style="flex-wrap:wrap;gap:8px"><h3 class="as-h" style="margin:0">Conformité de « ${E(st.label)} »</h3>
        <div class="row gap-s"><div class="seg"><button data-a="adv" data-v="0" class="${adv ? '' : 'on'}">Mode simple</button><button data-a="adv" data-v="1" class="${adv ? 'on' : ''}">Mode avancé</button></div></div></div>
      <div class="notice as-sep" style="margin-top:10px">Ces seuils <b>filtrent</b> les titres (conformes / écartés). Ils ne modifient <b>jamais</b> une note : les valeurs réelles de pente, R² et des autres indicateurs alimentent les deux scores, que le titre soit conforme ou non. Une case vide = <b>aucun seuil</b>.</div>
      <div class="row gap-s" style="margin:8px 0;flex-wrap:wrap"><button class="btn small" data-a="preset" data-v="balanced">Valeurs initiales « équilibré »</button><button class="btn small" data-a="preset" data-v="v1">Appliquer le préréglage de référence V1</button><span class="as-hint" style="margin:0">Un préréglage remplit les cases ; rien n’est enregistré tant que vous n’enregistrez pas.</span></div>
      <div class="table-wrap"><table class="as-conf"><thead><tr><th>Granularité</th><th>Active</th><th>Pente minimale (%/séance)</th><th>R² minimal (0–1)</th>${adv ? '<th>Rendement minimal (%)</th><th>Concentration max (0–1)</th><th>Volatilité max (%/séance)</th><th>Séances positives min (0–1)</th><th>Drawdown max (%)</th>' : ''}</tr></thead><tbody>
        ${S.scoring_periods.map(id => { const x = p.periods[id]; return `<tr class="${x.enabled ? '' : 'as-off'}"><td>${E(labels()[id])} <span class="muted">(${x.sessions} s)</span></td><td><input type="checkbox" data-a="active" data-p="${id}" ${x.enabled ? 'checked' : ''}></td>
          ${th(id, 'min_slope', 0.05)}${th(id, 'min_r2', 0.05)}${adv ? th(id, 'min_return', 0.5) + th(id, 'max_spike_share', 0.05) + th(id, 'max_volatility', 0.5) + th(id, 'min_up_fraction', 0.05) + th(id, 'max_drawdown', 1) : ''}</tr>`; }).join('')}</tbody></table></div>
      ${adv ? `<div class="as-adv"><h4 class="as-h">Dernier jour (filtre facultatif, indépendant de la notation)</h4>
        <label class="row gap-s"><input type="checkbox" data-a="day-on" ${p.day_filter.enabled ? 'checked' : ''}> Exiger un dernier jour positif : variation de la dernière séance clôturée ≥</label>
        <input type="number" class="as-num" data-a="day-min" step="0.1" value="${p.day_filter.min_return}" ${p.day_filter.enabled ? '' : 'disabled'}> %
        <p class="as-hint">Écarte le titre de la sélection sans changer sa note. La dernière séance est la dernière séance boursière clôturée.</p>
        <h4 class="as-h">Liquidité minimale (valeur échangée par jour)</h4>
        <div class="row gap-s" style="flex-wrap:wrap"><label>Hors États-Unis <input type="number" class="as-num" data-a="liq" data-f="min_turnover_eur" step="0.5" value="${mm(p.liquidity.min_turnover_eur)}" placeholder="aucun"> M€</label>
        <label>Places américaines <input type="number" class="as-num" data-a="liq" data-f="min_turnover_eur_us" step="0.5" value="${mm(p.liquidity.min_turnover_eur_us)}" placeholder="aucun"> M€</label></div></div>` : '<p class="as-hint">Mode simple : exactement deux réglages par granularité active. Les critères facultatifs (rendement, concentration, volatilité, séances positives, drawdown, dernier jour, liquidité) sont en mode avancé.</p>'}</div>`;
  }

  function technicalCard(p) {
    return `<div class="card"><h3 class="as-h">Données et exclusions techniques</h3>
      <p class="as-hint">Ce ne sont pas des critères de croissance : ils décident si un titre est <b>évaluable</b>. Un titre non évaluable est signalé « inconnu » (jamais noté 0) ; un titre simplement non conforme garde ses deux scores.</p>
      <table class="as-mini"><thead><tr><th>Période</th><th>Historique exigé (période obligatoire)</th></tr></thead><tbody>${S.scoring_periods.map(id => `<tr class="${p.periods[id].enabled ? '' : 'as-off'}"><td>${E(labels()[id])} <span class="muted">(${p.periods[id].sessions} séances)</span></td><td><input type="checkbox" data-a="req" data-p="${id}" ${p.periods[id].require_history ? 'checked' : ''} ${p.periods[id].enabled ? '' : 'disabled'}></td></tr>`).join('')}</tbody></table>
      <label class="row gap-s" style="margin-top:8px"><input type="checkbox" data-a="fresh" ${p.technical.require_fresh ? 'checked' : ''}> Exiger des cours récents (sinon le titre n’est pas évaluable)</label>
      <p class="as-hint">Couverture minimale des données : <b>${fmt(100 * draft.global.threshold, 0)} %</b> (réglage commun, onglet « Configuration du moteur »). Période obligatoire sans historique suffisant : titre non évaluable. Période facultative absente : seule la couverture baisse.</p></div>`;
  }

  function previewCard() {
    const c = conf, t = c ? c.counts : null;
    return `<div class="card"><div class="row between"><h3 class="as-h" style="margin:0">Effet sur la base actuelle</h3><button class="btn small" data-a="conf-run">${confBusy ? 'Calcul…' : 'Recalculer'}</button></div>
      ${confStale ? '<p class="as-hint" style="color:var(--warn)">Réglages modifiés depuis ce calcul : cliquez sur « Recalculer ».</p>' : ''}
      ${confBusy && !c ? '<div class="empty"><span class="spinner"></span></div>' : !c ? `<p class="muted">${confFail ? 'Calcul impossible : voir le message ci-dessus.' : 'Calcul au premier affichage.'}</p>` : c.universe === 0 ? '<div class="notice warn" style="margin-top:8px">Aucun titre dans cette base : rien à évaluer. Aucune valeur d’exemple n’est affichée.</div>' : `<div class="as-tiles as-tiles3" style="margin-top:10px">
        <div class="as-tile"><span>Conformes</span><b>${J.num(t.retained, 0)}</b><small>sur ${J.num(c.universe, 0)} titres</small></div>
        <div class="as-tile"><span>Écartés par un seuil</span><b>${J.num(t.rejected, 0)}</b><small>${J.num(c.rejected_with_both_scores, 0)} gardent leurs deux scores</small></div>
        <div class="as-tile"><span>Non évaluables</span><b>${J.num(t.unknown, 0)}</b><small>exclusion technique ou données insuffisantes</small></div></div>
        <p class="as-hint">Mesuré avec les réglages affichés (y compris les modifications non enregistrées). Les écartés restent accessibles dans la vue des écartés avec leurs scores.</p>`}</div>`;
  }

  async function runConf() {
    confBusy = true; confFail = false; confStale = false; paintBody();
    try { const body = { strategy: sel }; if (dirty()) body.draft = { global: draft.global, profile: payload() }; conf = await J.post('admin/scores/conformity', body); error = ''; }
    catch (e) { conf = null; confFail = true; error = e.message; }
    confBusy = false; paint();
  }

  // ───────────── simulation ─────────────
  function simulationView(isV4) {
    if (!isV4) return `<div class="notice warn">La simulation porte sur une stratégie V4. Choisissez-en une dans « Configuration du moteur ».</div>`;
    const chips = sim && sim.suggestions && sim.suggestions.length ? `<div class="as-chips"><span class="muted">Mieux notés :</span> ${sim.suggestions.map(c => `<button class="btn small" data-a="sim-pick" data-id="${c.id}">${E(c.symbol)} · ${fmt(c.simple, 0)}</button>`).join(' ')}</div>` : '';
    return `<div class="card"><div class="row gap-s" style="flex-wrap:wrap"><input id="as-q" class="as-search" placeholder="Symbole, nom ou ISIN d’un titre noté" value="${E(simQ)}"><button class="btn primary" data-a="sim-run">Décomposer</button>
        <label class="row gap-s as-chk"><input type="checkbox" data-a="use-draft" ${useDraft ? 'checked' : ''}> avec mes modifications non enregistrées</label></div>${chips}</div>
      <div id="as-sim">${simBusy ? '<div class="empty"><span class="spinner"></span></div>' : simBody()}</div>`;
  }

  function simBody() {
    if (!sim) return '<div class="empty">Lancez une décomposition pour un titre réel, ou laissez vide pour voir les titres les mieux notés.</div>';
    if (sim.empty) return `<div class="card"><div class="notice warn"><b>Aucune donnée à décomposer.</b> ${E(sim.reason)} Rien n’est remplacé par des exemples fictifs.</div></div>`;
    if (sim.not_found) return '<div class="card"><div class="notice warn">Aucun titre noté ne correspond à cette recherche.</div></div>';
    if (!sim.result) return `<div class="card"><p class="muted">${sim.candidates && sim.candidates.length ? 'Plusieurs titres correspondent.' : 'Choisissez un titre parmi les mieux notés ci-dessus.'}</p></div>`;
    const r = sim.result, ids = sim.periods.map(x => x.id), L = labels();
    const sc = (o, cls) => `<div class="as-score ${cls}"><span>${cls === 's' ? 'Score simple' : 'Score complexe'}</span><b>${o.score === null ? 'inconnu' : fmt(o.score, 1)}</b>${o.score === null ? '' : ' / 100'}<small>${o.status === 'ok' ? 'données complètes' : o.status === 'partiel' ? 'données partielles' : E(o.why || '')} · couverture ${fmt(100 * (o.coverage || 0), 0)} %</small></div>`;
    const cell = (c, key, unit, d) => { if (!c) return '<td class="num muted">—</td>'; const raw = c.raw || {}; const val = key === 'growth' ? c.growth : raw[key]; const note = c[key === 'growth' ? 'dynamics' : { r2: 'r2', up_fraction: 'up_days', spike_share: 'concentration', accel: 'acceleration', volatility: 'volatility', drawdown: 'drawdown' }[key]];
      return `<td class="num">${val === null || val === undefined ? '<span class="muted">indisponible</span>' : fmt(unit === '%' ? val * (['up_fraction', 'spike_share'].includes(key) ? 100 : 1) : val, d) + (unit ? ' ' + unit : '')}${note === null || note === undefined ? '' : `<br><small class="muted">note ${fmt(note, 0)}</small>`}</td>`; };
    const rows = [['Croissance (Dynamique)', 'growth', '%', 2], ['Régularité (R²)', 'r2', '', 2], ['Séances positives', 'up_fraction', '%', 0], ['Plus gros pic ÷ hausse nette', 'spike_share', '%', 0], ['Accélération (écart de pente)', 'accel', '', 3], ['Volatilité (par séance)', 'volatility', '%', 2], ['Drawdown', 'drawdown', '%', 1]];
    const s = r.simple, c = r.complex, liq = r.liquidity || {};
    return `<div class="card"><div class="row between" style="flex-wrap:wrap;gap:12px"><div><h3 class="as-h" style="margin:0">${E(sim.title.name)}</h3><span class="muted">${E(sim.title.symbol)} · ${E(sim.title.mic)} · ${sim.title.kind === 'etf' ? 'ETF' : 'Action'}</span></div><div class="row gap-s">${sc(s, 's')}${sc(c, 'c')}</div></div>
      <div class="table-wrap"><table class="as-dec"><thead><tr><th>Mesure</th>${ids.map(i => `<th class="num">${E(L[i])}<br><small class="muted">poids ${fmt(100 * (r.weights[i] || 0), 1)} %</small></th>`).join('')}</tr></thead><tbody>
        ${rows.map(([n, k, u, d]) => `<tr><td>${n}</td>${ids.map(i => cell(r.periods[i], k, u, d)).join('')}</tr>`).join('')}</tbody></table></div>
      <div class="as-two"><div><h4 class="as-h">Score simple (produit)</h4>${s.score === null ? `<p class="muted">${E(s.why || '')}</p>` : `<p>100 × Dynamique <b>${fmt(s.dynamics, 2)}</b> × Régularité <b>${fmt(s.quality, 2)}</b> × accélération <b>${fmt(s.acceleration_factor, 2)}</b> = <b>${fmt(s.score, 1)}</b></p><p class="as-hint">Chaque facteur est un multiplicateur : un seul maillon faible tire tout le score vers le bas.</p>`}</div>
        <div><h4 class="as-h">Score complexe (somme pondérée)</h4>${c.score === null ? `<p class="muted">${E(c.why || '')}</p>` : `<table class="as-mini"><tbody>${Object.entries(c.contributions).map(([k, v]) => `<tr><td>${E(CLABEL[k] || k)}</td><td class="num">poids ${fmt(100 * v.weight, 1)} %</td><td class="num">note ${fmt(v.value, 0)}</td><td class="num"><b>+${fmt(v.points, 1)}</b></td></tr>`).join('')}</tbody></table><p class="as-hint">Total ${fmt(c.raw_total, 1)} × ancrage récent ${fmt(c.anchor, 2)} = <b>${fmt(c.score, 1)}</b></p>`}</div></div>
      <p class="as-hint">Liquidité : ${liq.turnover_eur ? fmt(liq.turnover_eur / 1e6, 1) + ' M€/jour (' + (liq.source === 'daily' ? 'volumes quotidiens réels' : 'estimée, moyenne trimestrielle') + ') · note ' + fmt(liq.note, 0) : 'indisponible'}. ${r.missing && (r.missing.secondary.length || r.missing.optional_periods.length) ? 'Mesures absentes : ' + E(r.missing.optional_periods.concat(r.missing.secondary).join(', ')) + '.' : ''}</p></div>`;
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
    const stat = k => `<div class="as-tile"><span>${k === 'simple' ? 'Score simple' : 'Score complexe'}</span><b>${J.num(m.counts[k].ok + m.counts[k].partiel, 0)}</b><small>notés · ${J.num(m.counts[k].ok, 0)} complets · ${J.num(m.counts[k].partiel, 0)} partiels · ${J.num(m.counts[k].inconnu, 0)} inconnus</small></div>`;
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
    if (a === 'strategy') { sel = t.value; sim = null; conf = null; later(); }
    else if (a === 'active') {
      const on = t.checked, q = prof();
      if (!on && active(q).length <= 1) { t.checked = true; J.toast('Au moins une granularité doit rester active'); return; }
      q.periods[t.dataset.p].enabled = on;
      if (q.weights_mode === 'custom') { if (on) q.weights[t.dataset.p] = 0; else delete q.weights[t.dataset.p]; }
      later();
    } else if (a === 'req') { p.periods[t.dataset.p].require_history = t.checked; confStale = true; paintBar(); }
    else if (a === 'pw') {
      p.weights[t.dataset.p] = +t.value || 0;
      const tot = sum(Object.fromEntries(active(p).map(i => [i, p.weights[i]]))), el = $('#pw-total');
      if (el) { el.className = 'as-total ' + (Math.abs(tot - 100) <= 0.05 ? 'ok' : 'ko'); el.innerHTML = `Pondération totale : <b>${fmt(tot, 1)} %</b>${Math.abs(tot - 100) > 0.05 ? ' — doit faire 100 %' : ''}`; }
      paintBar();
    }
    else if (a === 'cw') { p.complex_weights[t.dataset.k] = +t.value || 0; paintBar(); }
    else if (a === 'kappa') { draft.global.kappa = +t.value; paintBar(); later(); }
    else if (a === 'thr') { draft.global.threshold = +t.value; paintBar(); }
    else if (a === 'thr-p') { p.periods[t.dataset.p][t.dataset.f] = t.value === '' ? null : +t.value; confStale = true; paintBar(); }
    else if (a === 'day-on') { p.day_filter.enabled = t.checked; confStale = true; paint(); }
    else if (a === 'day-min') { p.day_filter.min_return = +t.value || 0; confStale = true; paintBar(); }
    else if (a === 'liq') { p.liquidity[t.dataset.f] = t.value === '' ? null : Math.round(+t.value * 1e6); confStale = true; paintBar(); }
    else if (a === 'fresh') { p.technical.require_fresh = t.checked; confStale = true; paintBar(); }
    else if (a === 'use-draft') { useDraft = t.checked; }
  }

  function applyPreset(kind) {
    const ref = clone(S.references[kind]), p = prof(), before = active(p).join();
    S.scoring_periods.forEach(id => { Object.assign(p.periods[id], ref.periods[id], { sessions: p.periods[id].sessions }); });
    p.day_filter = ref.day_filter; p.liquidity = ref.liquidity; p.technical = ref.technical;
    if (before !== active(p).join()) { p.weights_mode = 'auto'; p.weights = {}; }
    conf = null; J.toast(kind === 'v1' ? 'Préréglage V1 appliqué (non enregistré)' : 'Valeurs initiales appliquées (non enregistrées)'); paint();
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
    else if (a === 'cw-ref') { prof().complex_weights = clone(S.design.complex_weights); paint(); }
    else if (a === 'open') { sel = v; tab = 'profils'; sim = null; conf = null; paint(); }
    else if (a === 'adv') { adv = v === '1'; paint(); }
    else if (a === 'preset') { applyPreset(v); }
    else if (a === 'conf-run') { runConf(); }
    else if (a === 'cancel') { reset(); conf = null; paint(); }
    else if (a === 'save') save();
    else if (a === 'restore') restore();
    else if (a === 'sim-run') { simQ = ($('#as-q') || {}).value || ''; runSim(null); }
    else if (a === 'sim-pick') runSim(+t.dataset.id);
    else if (a === 'mon-refresh') { mon = null; monErr = null; paint(); }
  }

  async function save() {
    try {
      const before = savedProfiles(), changed = v4().map(s => s.name).filter(n => JSON.stringify(draft.profiles[n]) !== JSON.stringify(before[n]));
      if (!changed.length) S = await J.post('admin/scores/save', { global: draft.global });
      for (const [i, n] of changed.entries()) S = await J.post('admin/scores/save', i === 0 ? { global: draft.global, profile: payloadFor(n) } : { profile: payloadFor(n) });
      reset(); Object.keys(autoCache).forEach(k => delete autoCache[k]); mon = null; sim = null; conf = null; J.toast('Configuration enregistrée');
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
        try { S = await J.post('admin/scores/save', scope === 'profile' ? { reset: 'profile', name: st && st.engine === 'v4' ? sel : v4()[0].name } : { reset: scope }); reset(); Object.keys(autoCache).forEach(k => delete autoCache[k]); sim = null; conf = null; J.toast('Valeurs par défaut rétablies'); } catch (e) { J.toast(e.message); }
        paint(); } }] });
  }

  window.AdminScores = { render };
})();
