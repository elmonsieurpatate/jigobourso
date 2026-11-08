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
    const slopeGain = (c, n) => c && c.slope != null ? `+${num(gain(c.slope, n), 1)} %` : null;
    const tests = s.periods.filter(p => (s.criteria[p.id] || {}).slope != null).map(p => { const c = s.criteria[p.id]; return `<li>sur <b>${E(p.label.toLowerCase())}</b> (${p.sessions} séances) : le prix doit avoir monté d’au moins environ <b>${slopeGain(c, p.sessions)}</b> (pente ${E(levelName(facts.common.slope_levels, LV_SLOPE, c.slope) || 'personnalisée')})${c.r2 != null ? `, et la courbe doit être assez droite (régularité ${E(levelName(facts.common.r2_levels, LV_R2, c.r2) || 'personnalisée')}, R² ≥ ${num(c.r2, 2)})` : ''}</li>`; }).join('');
    const cwTop = Object.entries(s.complex_weights).filter(([, v]) => v >= 15).sort((x, y) => y[1] - x[1]).map(([k, v]) => `<b>${E((COMP[k] || [k])[0])}</b> (${v} %)`).join(', ');
    const body = level === 'beginner'
      ? `<p><b>Pour qui ?</b> ${E(b[0])}</p>
         <p><b>Le tri (critères de recherche).</b> ${tests ? `Un titre est retenu seulement s’il réussit tous ces tests :</p><ul>${tests}</ul><p>Il doit donc réussir sur <b>toutes</b> les durées à la fois.` : 'Aucun seuil de pente ou de régularité : tous les titres notés sont retenus tant que leurs données existent.'}</p>
         <p><b>La note (scores).</b> Le score complexe donne le plus de poids à : ${cwTop || '—'}. Durées utilisées pour les notes : ${periods}.</p>
         <p><b>Comment ça marche, en clair.</b> ${E(b[1])}</p><p><b>À savoir.</b> ${E(b[2])}</p>`
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
    dynamics: ['Dynamique (la hausse)', 'De combien le prix a monté sur la période, comparé à une hausse « de référence ». 0 = pas de hausse ; 100 = au moins la hausse de référence.', c => `Référence du réglage standard : ${num(c.saturation.a * 1, 0)} % sur 1 semaine, ${num(c.saturation.a * Math.pow(21 / 5, c.saturation.b), 0)} % sur 1 mois, ${num(c.saturation.a * Math.pow(63 / 5, c.saturation.b), 0)} % sur 1 trimestre. Exemple : +18 % sur un mois → environ 50/100.`],
    r2: ['Régularité (R²)', 'Est-ce que la hausse suit une ligne bien droite ? Un prix qui zigzague est pénalisé.', () => '0 si le R² est de 0,5 ou moins ; 100 si 0,95 ou plus. Sur une durée très courte, cette note compte moins (elle est moins fiable).'],
    up_days: ['Séances en hausse', 'Sur 100 jours de bourse, combien ont fini en hausse ? Une hausse portée par beaucoup de petits pas vaut mieux qu’un seul gros saut.', () => '0 si 40 % des séances ou moins sont en hausse ; 100 si 80 % ou plus.'],
    concentration: ['Gains bien répartis', 'La hausse vient-elle de quelques énormes sauts, ou d’une progression régulière ? Si tout vient d’un seul jour, la hausse est fragile.', () => '100 si les plus gros sauts pèsent 10 % de la hausse ou moins ; 0 s’ils en pèsent 60 % ou plus.'],
    volatility: ['Prix peu agité (volatilité)', 'À quel point le prix bouge d’un jour à l’autre. Montagnes russes = mauvaise note.', () => '100 si le prix bouge de 1 % par jour ou moins ; 0 s’il bouge de 5 % par jour ou plus.'],
    drawdown: ['Petites chutes (drawdown)', 'La plus grosse chute depuis un sommet pendant la période. Plus elle est petite, mieux c’est.', () => '100 si aucune chute ; 0 si la chute atteint 15 % ou plus.'],
    liquidity: ['Facilité à revendre (liquidité)', 'Combien d’argent s’échange chaque jour sur ce titre. Peu d’échanges = difficile de revendre vite.', c => `Échelle logarithmique : 0 si moins de ${num(c.liquidity.floor_eur / 1e6, 0)} millions d’euros échangés par jour ; 100 à partir de ${num(c.liquidity.ceil_eur / 1e6, 0)} millions.`],
    acceleration: ['Accélération', 'La hausse est-elle en train de s’accélérer par rapport à la période d’avant ? Utile pour repérer un démarrage.', () => '50 = la vitesse n’a pas changé ; au-dessus = ça accélère ; en dessous = ça ralentit.'],
    momentum: ['Momentum (la tendance passée)', 'De combien le prix a monté sur 6 ou 12 mois, sans compter le dernier mois (pour ne pas suivre un emballement trop récent).', c => `100 si la hausse atteint ${num(c.momentum.saturation['6m'], 0)} % (6 mois) ou ${num(c.momentum.saturation['12m'], 0)} % (12 mois) ; 0 si le prix a baissé.`],
    recovery: ['Contexte de rebond', 'Le titre a-t-il peu monté (ou baissé) ces 6 derniers mois ? Si oui, un redémarrage est plus intéressant : il n’a pas déjà beaucoup progressé.', c => `100 si le semestre est à ${num(c.recovery.best, 0)} % ou moins ; 0 s’il a déjà gagné ${num(c.recovery.worst, 0)} % ou plus.`]
  };
  const gain = (slope, n) => 100 * (Math.pow(1 + slope / 100, n) - 1);
  const criteriaFacts = () => { const c = facts.common, per = ['day', 'week', 'month', 'quarter', 'half', 'year'];
    return `<div class="sui-scroll"><table class="sui-cmp"><caption class="small muted" style="text-align:left">Les durées (granularités)</caption><thead><tr><th>Durée</th><th>Nombre de séances</th></tr></thead><tbody>${per.filter(k => c.periods[k]).map(k => `<tr><th scope="row">${E(c.periods[k].label)}</th><td>${c.periods[k].sessions}</td></tr>`).join('')}</tbody></table></div>
    <div class="sui-scroll"><table class="sui-cmp"><caption class="small muted" style="text-align:left">Les niveaux de pente, et ce que ça représente si la hausse est régulière</caption><thead><tr><th>Niveau</th><th>Hausse par séance</th><th>≈ sur 1 semaine</th><th>≈ sur 1 mois</th><th>≈ sur 1 trimestre</th></tr></thead><tbody>${Object.entries(c.slope_levels).map(([k, v]) => `<tr><th scope="row">${E(LV_SLOPE[k])}</th><td>${num(v, 3)} %</td><td>+${num(gain(v, 5), 1)} %</td><td>+${num(gain(v, 21), 1)} %</td><td>+${num(gain(v, 63), 1)} %</td></tr>`).join('')}</tbody></table></div>
    <div class="sui-scroll"><table class="sui-cmp"><caption class="small muted" style="text-align:left">Les niveaux de régularité (R², de 0 à 1)</caption><thead><tr><th>Niveau</th><th>R² minimal</th></tr></thead><tbody>${Object.entries(c.r2_levels).map(([k, v]) => `<tr><th scope="row">${E(LV_R2[k])}</th><td>${num(v, 3)}</td></tr>`).join('')}</tbody></table></div>`; };
  const componentFacts = () => `<div class="sui-comps">${Object.keys(COMP).map(k => {
    const used = facts.strategies.filter(s => s.complex_weights[k] > 0);
    return `<article class="sui-comp"><h4>${E(COMP[k][0])}</h4><p>${E(COMP[k][1])}</p><p class="small"><b>Note de 0 à 100 :</b> ${E(COMP[k][2](facts.common))}</p>
      <div class="sui-chips" aria-label="Poids dans le score complexe">${used.length ? used.map(s => `<span class="sui-chip"><span>${E(s.label)}</span><b>${s.complex_weights[k]} %</b></span>`).join('') : '<span class="muted small">Poids nul dans les 7 stratégies officielles (réglable dans Mes paramètres de scores).</span>'}</div></article>`;
  }).join('')}</div>`;
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
