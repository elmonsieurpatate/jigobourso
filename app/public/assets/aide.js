/* Centre d'aide : rubriques (help-content.js), fiches des 7 stratégies générées depuis les faits du moteur (help/facts), recherche, mode Débutant / Expert (préférence par utilisateur). */
(async () => {
  const me = await J.init('aide'); if (!me) return;
  const E = J.esc, main = J.$('#help-main'), nav = J.$('#help-nav'), q = J.$('#help-q');
  let level = (me.prefs || {}).help_level === 'expert' ? 'expert' : 'beginner', facts = null, factsErr = null;
  const pct = (v, d = 1) => (v == null ? '—' : (+v).toLocaleString('fr-FR', { maximumFractionDigits: d }) + ' %');
  const num = (v, d = 3) => (v == null ? '—' : (+v).toLocaleString('fr-FR', { maximumFractionDigits: d }));
  const LV_SLOPE = { gentle: 'douce', moderate: 'modérée', strong: 'forte', very_strong: 'très forte' }, LV_R2 = { flexible: 'souple', balanced: 'équilibré', strict: 'strict' };
  const levelName = (map, labels, v) => { for (const [k, x] of Object.entries(map)) if (Math.abs(x - v) < 1e-9) return labels[k]; return null; };
  const BEGIN = {
    fast: ['Vous voulez repérer ce qui monte vite en ce moment.', 'Une hausse forte à la semaine ET au mois.', 'Ne dit rien de la régularité : un titre peut monter par à-coups.'],
    regular: ['Vous préférez une progression solide et constante.', 'Une hausse moyenne modérée, sur un mois et un trimestre, avec une courbe assez régulière.', 'Plus lente à réagir que Croissance rapide.'],
    calm: ['Vous voulez monter sans trop de secousses.', 'Une hausse douce sur un mois et un trimestre ; la faible volatilité et le faible repli comptent beaucoup dans la note.', 'Les gains sont souvent plus modestes.'],
    rebound: ['Vous cherchez un titre qui redémarre après une période calme ou en baisse.', 'Semaine et mois qui repartent ; le semestre sert de contexte : moins il a progressé, meilleure est la note de rebond.', 'Un rebond peut être éphémère.'],
    mom6: ['Vous misez sur la tendance des six derniers mois.', 'Aucun seuil de recherche : tous les titres notés sont classés selon leur variation sur six mois (hors dernier mois).', 'Stratégie marquée « expérimentale » dans le moteur.'],
    mom12: ['Vous misez sur la tendance de l’année écoulée.', 'Aucun seuil de recherche : classement selon la variation sur douze mois (hors dernier mois).', 'Stratégie marquée « expérimentale » dans le moteur.'],
    momrisk: ['Vous voulez du momentum, mais en tenant compte du risque.', 'Aucun seuil de recherche : moyenne des momentums 6 et 12 mois, corrigée par la volatilité et le repli.', 'Stratégie marquée « expérimentale » dans le moteur.']
  };
  const VIGIL = {
    fast: ['Aucun seuil de R² dans ses critères de recherche : seule la pente compte (semaine et mois). Le R² n’intervient que dans le score complexe.'],
    regular: [], calm: ['La volatilité et le repli ne sont pas des critères de recherche : ils pèsent seulement dans le score complexe.'],
    rebound: ['Le semestre est activé avec un poids automatique nul : il sert uniquement au contexte de rebond, sans critère.'],
    mom6: ['Aucun critère de recherche : tous les titres notés sont « retenus » tant que les données existent.'], mom12: ['Aucun critère de recherche : tous les titres notés sont « retenus » tant que les données existent.'],
    momrisk: ['Aucun critère de recherche. Le filtre « au-dessus de la moyenne 200 jours » de l’ancien profil n’est pas une notation : il reste un filtre d’affichage.']
  };
  async function loadFacts() { try { facts = await J.api('help/facts'); } catch (e) { factsErr = e.message; } try { SUI.setMeta((await J.api('classement-test/strategies')).meta); } catch (e) { /* présentation par défaut */ } }
  const critCell = (s, pid) => { const c = (s.criteria || {})[pid]; if (!c) return '—'; const parts = []; const cm = facts.common;
    if (c.slope != null) parts.push(`pente ≥ ${num(c.slope, 4)} %/séance (${levelName(cm.slope_levels, LV_SLOPE, c.slope) || 'personnalisée'})`);
    if (c.r2 != null) parts.push(`R² ≥ ${num(c.r2, 3)} (${levelName(cm.r2_levels, LV_R2, c.r2) || 'personnalisé'})`);
    return parts.length ? parts.join(' ; ') : 'aucun seuil'; };
  const fiche = s => {
    const id = s.id, b = BEGIN[id] || ['', '', ''];
    const periods = s.periods.map(p => `${E(p.label)} (${p.sessions} séances) : ${pct(p.weight)}`).join(' · ');
    const crit = s.periods.map(p => `<tr><th scope="row">${E(p.label)}</th><td>${E(critCell(s, p.id))}</td><td>${pct(p.weight)}</td></tr>`).join('');
    const cw = Object.entries(s.complex_weights).filter(([, v]) => v > 0).map(([k, v]) => `${E(facts.common.complex_labels[k] || k)} ${pct(v, 0)}`).join(' · ');
    const t = s.tuning || {}, tune = [t.sat_a != null ? `saturation de dynamique A = ${num(t.sat_a, 2)} %` : '', t.accel_ref != null ? `référence d’accélération k = ${num(t.accel_ref, 2)}` : '', t.momentum_horizon ? `horizon de momentum : ${E(t.momentum_horizon)}` : '', t.vol_mode ? `volatilité : mode ${E(t.vol_mode)}` : ''].filter(Boolean).join(' · ');
    const vig = (VIGIL[id] || []).map(x => `<div class="help-note">${E(x)}</div>`).join('');
    const body = level === 'beginner'
      ? `<p><b>Pour qui ?</b> ${E(b[0])}</p><p><b>Comment ça marche ?</b> ${E(b[1])}</p><p><b>À savoir.</b> ${E(b[2])}</p><p class="small muted">Périodes observées : ${periods}.</p>`
      : `<div class="sui-scroll"><table class="sui-cmp"><thead><tr><th>Granularité</th><th>Critère de recherche</th><th>Poids du score</th></tr></thead><tbody>${crit}</tbody></table></div>
         <p><b>Poids du score complexe :</b> ${cw}.</p><p><b>Réglages :</b> ${tune || '—'}. Mode des poids de périodes : ${s.weights_mode === 'auto' ? 'automatique (κ = ' + num(facts.common.kappa, 2) + ')' : 'personnalisé'}. Tri par défaut : score ${s.sort === 'complex' ? 'complexe' : 'simple'}.</p>${vig}`;
    return `<article class="sui-card" id="strategie-${E(id)}" style="margin-bottom:12px"><div class="sui-head">${SUI.ico(id)}<div><h3>${E(s.label)}</h3><div class="small muted">${E(SUI.desc(id))}</div></div></div>${body}</article>`;
  };
  const compare = () => {
    const rows = facts.strategies.map(s => `<tr><th scope="row">${E(s.label)}</th><td>${s.periods.map(p => E(p.label)).join(', ')}</td><td>${s.periods.map(p => E(critCell(s, p.id)).replace(/ \(.*?\)/g, '')).filter(x => x !== '—').join(' / ') || 'aucun seuil'}</td><td>${Object.entries(s.complex_weights).filter(([, v]) => v >= 20).map(([k, v]) => E((facts.common.complex_labels[k] || k) + ' ' + v + ' %')).join(', ')}</td></tr>`).join('');
    return `<h3>Comparatif des 7 stratégies</h3><div class="sui-scroll"><table class="sui-cmp"><thead><tr><th>Stratégie</th><th>Granularités</th><th>Critères de recherche</th><th>Composantes dominantes du score complexe (≥ 20 %)</th></tr></thead><tbody>${rows}</tbody></table></div>`;
  };
  const formulas = () => { const c = facts.common; return `<div class="prose"><p>Constantes lues dans le moteur :</p><ul>
    <li>Dynamique : croissance lissée sur n séances comparée à A·(n/5)<sup>${num(c.saturation.b, 2)}</sup> % (A = ${num(c.saturation.a, 0)} par défaut, réglable par stratégie) ; la note vaut 100 à saturation.</li>
    <li>Garde-fou : sous une note de dynamique de ${num(c.gate_floor, 0)}, régularité et risque de la période sont amortis.</li>
    <li>Fiabilité du R² : poids min(1, n/${c.reliability_sessions}) ; aucun R² ni volatilité sous ${c.min_sessions} séances.</li>
    <li>Accélération : référence k × saturation(n)/n ; régularité requise : facteur min(R², R²<sub>préc.</sub>)/${num(c.accel.r2, 1)}.</li>
    <li>Contexte de rebond : rendement du semestre ≤ ${num(c.recovery.best, 0)} % → 100, ≥ ${num(c.recovery.worst, 0)} % → 0.</li>
    <li>Momentum : variation J−126→J−21 (6 mois, saturation ${num(c.momentum.saturation['6m'], 0)} %) ou J−252→J−21 (12 mois, saturation ${num(c.momentum.saturation['12m'], 0)} %) ; négatif : 0.</li>
    <li>Liquidité : valeur échangée par jour de ${num(c.liquidity.floor_eur / 1e6, 0)} à ${num(c.liquidity.ceil_eur / 1e6, 0)} M€, échelle logarithmique 0 → 100.</li>
    <li>Volatilité (mode relatif) : rapport volatilité/pente ≤ ${num(c.vol.ratio_best, 0)} → 100, ≥ ${num(c.vol.ratio_worst, 0)} → 0 ; plancher de pente ${num(c.vol.slope_floor, 1)} %/séance.</li>
    <li>Réglages communs (administration) : κ = ${num(c.kappa, 2)}, seuil de couverture = ${num(c.threshold, 2)}, ancrage = ${num(c.anchor, 2)}.</li></ul></div>`; };
  const COMP = {
    dynamics: ['Dynamique', 'La force de la hausse : croissance lissée sur chaque durée, comparée à une croissance de référence au-delà de laquelle la note vaut 100.'],
    r2: ['Régularité (R²)', 'Le degré auquel la hausse suit une ligne droite. Un R² faible (zigzags) est pénalisé ; il compte moins sur les durées très courtes (peu fiable).'],
    up_days: ['Séances positives', 'La part des séances de hausse sur la dernière période : une hausse portée par beaucoup de séances vaut mieux qu’une hausse portée par quelques-unes.'],
    concentration: ['Concentration des gains', 'Mesure si la hausse vient de quelques séances seulement (pics). Moins les gains sont concentrés, meilleure est la note.'],
    volatility: ['Volatilité', 'L’ampleur des variations quotidiennes. Plus elles sont faibles, meilleure est la note (échelle : voir les formules en mode Expert).'],
    drawdown: ['Drawdown (repli maximal)', 'La plus forte baisse depuis un sommet sur la période. Plus le repli est faible, meilleure est la note.'],
    liquidity: ['Liquidité', 'Le montant échangé par jour (en euros), sur une échelle logarithmique : un titre très peu échangé est difficile à acheter et à revendre.'],
    acceleration: ['Accélération', 'Si la pente s’améliore par rapport à la période précédente, avec un garde-fou de régularité. Utilisée par Rebond.'],
    momentum: ['Momentum (6/12 mois)', 'La variation du cours sur 6 ou 12 mois, sans le dernier mois (pour ne pas suivre un emballement récent). Utilisé par les stratégies Momentum.'],
    recovery: ['Contexte de rebond', 'Plus le semestre a peu progressé (ou reculé), plus la note est haute : le titre n’a pas déjà beaucoup monté. Utilisé par Rebond.']
  };
  const criteriaFacts = () => { const c = facts.common, per = ['day', 'week', 'month', 'quarter', 'half', 'year'];
    return `<div class="sui-scroll"><table class="sui-cmp"><caption class="small muted" style="text-align:left">Granularités</caption><thead><tr><th>Granularité</th><th>Séances</th></tr></thead><tbody>${per.filter(k => c.periods[k]).map(k => `<tr><th scope="row">${E(c.periods[k].label)}</th><td>${c.periods[k].sessions}</td></tr>`).join('')}</tbody></table></div>
    <div class="sui-scroll"><table class="sui-cmp"><caption class="small muted" style="text-align:left">Niveaux de pente (hausse moyenne par séance)</caption><thead><tr><th>Niveau</th><th>Seuil minimal</th></tr></thead><tbody>${Object.entries(c.slope_levels).map(([k, v]) => `<tr><th scope="row">${E(LV_SLOPE[k])}</th><td>${num(v, 4)} % par séance</td></tr>`).join('')}</tbody></table></div>
    <div class="sui-scroll"><table class="sui-cmp"><caption class="small muted" style="text-align:left">Niveaux de régularité (R², de 0 à 1)</caption><thead><tr><th>Niveau</th><th>Seuil minimal</th></tr></thead><tbody>${Object.entries(c.r2_levels).map(([k, v]) => `<tr><th scope="row">${E(LV_R2[k])}</th><td>${num(v, 3)}</td></tr>`).join('')}</tbody></table></div>`; };
  const componentFacts = () => { const labels = facts.common.complex_labels;
    const head = facts.strategies.map(s => `<th>${E(s.label)}</th>`).join('');
    const rows = Object.keys(COMP).map(k => `<tr><th scope="row">${E(COMP[k][0])}</th><td>${E(COMP[k][1])}</td>${facts.strategies.map(s => { const v = s.complex_weights[k]; return `<td>${v ? v + ' %' : '—'}</td>`; }).join('')}</tr>`).join('');
    return `<div class="sui-scroll"><table class="sui-cmp"><caption class="small muted" style="text-align:left">Poids de chaque point dans le score complexe, par stratégie (— = non utilisé)</caption><thead><tr><th>Point noté</th><th>Ce qu’il mesure</th>${head}</tr></thead><tbody>${rows}</tbody></table></div>`; };
  const personal = () => `<article class="sui-card" id="strategie-personnelles">${`<div class="sui-head">${SUI.ico('x', 'personal')}<div><h3>Stratégies personnelles</h3><div class="small muted">${E(SUI.SHORT.personal)}</div></div></div>`}<p>Créez-les depuis <a href="mes-strategies.html">Mes stratégies</a> (copie d’une stratégie existante, ou nouveau réglage depuis l’Explorer). Elles ne sont jamais distribuées aux autres comptes ni modifiées par une mise à jour des références.</p></article>`;
  function sectionHtml(sec) {
    let h = `<section id="${E(sec.id)}" class="card"><h2>${J.icon(sec.icon || 'book', 'sui-ic')} ${E(sec.title)}</h2><div class="prose">${level === 'expert' ? sec.e : sec.b}</div>`;
    if (sec.dynamic === 'strategies') {
      if (factsErr) h += `<div class="notice err">Faits indisponibles : ${E(factsErr)}</div>`;
      else if (facts) h += `<div style="margin-top:12px">${facts.strategies.map(fiche).join('')}</div>${compare()}`;
    }
    if (sec.id === 'adaptees') h += personal();
    h += '</section>';
    return h;
  }
  const visible = () => HELP.filter(s => !s.admin || me.is_admin);
  function paint() {
    const term = q.value.trim().toLowerCase(), list = visible();
    const text = s => (s.title + ' ' + (level === 'expert' ? s.e : s.b) + (s.dynamic && facts ? ' ' + facts.strategies.map(x => x.label).join(' ') : '')).replace(/<[^>]+>/g, ' ').toLowerCase();
    const shown = term ? list.filter(s => text(s).includes(term)) : list;
    nav.innerHTML = list.map(s => `<a href="#${E(s.id)}" ${shown.includes(s) ? '' : 'style="opacity:.4"'}>${J.icon(s.icon || 'book', 'sui-ic')}<span>${E(s.title)}</span></a>`).join('');
    main.innerHTML = shown.length ? shown.map(sectionHtml).join('').replace(/<div data-facts="(formulas|criteria|components)"><\/div>/g, (m, k) => !facts ? '' : k === 'formulas' ? formulas() : k === 'criteria' ? criteriaFacts() : componentFacts()) : '<div class="empty">Aucun résultat. Essayez un autre mot.</div>';
    J.$$('[data-mode]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.mode === level)));
    markNav();
  }
  function markNav() { const h = location.hash.slice(1); J.$$('a', nav).forEach(a => a.removeAttribute('aria-current')); const a = nav.querySelector(`a[href="#${CSS.escape(h)}"]`); if (a) a.setAttribute('aria-current', 'true'); }
  J.$$('[data-mode]').forEach(b => b.onclick = async () => { level = b.dataset.mode; paint(); scrollToHash(); try { me.prefs = (await J.post('auth/prefs', { help_level: level })).prefs; } catch (e) { } });
  q.oninput = paint;
  const scrollToHash = () => { const h = decodeURIComponent(location.hash.slice(1)); if (!h) return; const el = document.getElementById(h); if (el) el.scrollIntoView(); markNav(); };
  addEventListener('hashchange', scrollToHash);
  await loadFacts(); paint(); scrollToHash();
})();
