/* Chapitres : les 7 stratégies officielles. Les chiffres (critères, durées, poids, réglages) viennent du moteur via help/facts ; les courbes illustrent un comportement type (fictives). */
(function () {
  const I = n => J.icon(n), L = (window.HELP_CHAPTERS = window.HELP_CHAPTERS || []);
  const f = (v, d = 1) => HC.f1(v, d), pc = (v, d = 1) => (v > 0 ? '+' : '') + f(v, d) + ' %';
  const LV = { gentle: 'douce', moderate: 'modérée', strong: 'forte', very_strong: 'très forte' }, LR = { flexible: 'souple', balanced: 'équilibrée', strict: 'stricte' };
  const levelName = (map, labels, v) => { for (const [k, x] of Object.entries(map || {})) if (x != null && Math.abs(x - v) < 1e-9) return labels[k]; return null; };
  const growth = (s, n) => 100 * (Math.pow(1 + s / 100, n) - 1);
  const COLORS = ['#2563eb', '#f97316', '#16a34a', '#9333ea', '#e11d48', '#0891b2', '#ca8a04', '#db2777', '#4f46e5', '#65a30d'];
  const KEYS = ['dynamics', 'r2', 'up_days', 'concentration', 'volatility', 'drawdown', 'liquidity', 'acceleration', 'momentum', 'recovery'];

  const DEF = {
    fast: { icon: 'rocket', color: '#ea580c', lead: 'Pour repérer ce qui monte vite en ce moment.', goal: 'Trouver les titres dont le prix grimpe nettement, à la semaine et au mois.',
      path: [[0, 100], [200, 102], [231, 108], [252, 134]], noise: 0.004,
      behaviour: 'Un titre qui somnolait, puis qui accélère : la dernière semaine et le dernier mois montrent une forte hausse.',
      pros: ['Détecte tôt les accélérations.', 'Critère simple : seule la pente compte.'], cons: ['Aucune exigence de régularité : un titre peut monter par à-coups.', 'Fenêtres courtes : sensibles au bruit.'],
      fake: ['Un seul jour exceptionnel (annonce, rumeur) peut suffire à passer le filtre.', 'Quand le titre est repéré, la hausse est parfois déjà épuisée.'],
      vs: [['regular', 'Croissance régulière exige une courbe droite sur mois et trimestre ; Croissance rapide ne regarde que la vitesse, sur des durées plus courtes.'], ['calm', 'Hausse calme privilégie le titre paisible ; Croissance rapide accepte les secousses.']] },
    regular: { icon: 'trending-up', color: '#16a34a', lead: 'Pour une progression solide et constante.', goal: 'Trouver les titres qui montent de façon soutenue ET régulière sur un mois et un trimestre.',
      path: null, series: [252, 36, 0.006, 4, 100, 0.002, 21],
      behaviour: 'Une montée assez droite, sans grand trou : la courbe colle à sa droite de tendance.',
      pros: ['Deux durées doivent confirmer : moins de coups de chance.', 'La régularité est exigée, pas seulement la vitesse.'], cons: ['Plus lente à réagir que Croissance rapide.', 'Exclut les hausses brutales mais irrégulières.'],
      fake: ['Une belle régularité passée ne garantit pas qu’elle continue.', 'Une courbe lisse peut aussi venir d’un titre peu échangé (voir liquidité).'],
      vs: [['fast', 'Plus lente mais plus fiable que Croissance rapide.'], ['calm', 'Hausse calme demande une pente plus faible mais note davantage le risque.']] },
    calm: { icon: 'waves', color: '#0891b2', lead: 'Pour monter sans trop de secousses.', goal: 'Trouver les titres qui progressent doucement, avec des variations quotidiennes discrètes.',
      path: null, series: [252, 24, 0.004, 3, 100, 0.0015, 17],
      behaviour: 'Une pente douce mais très régulière, avec des secousses quotidiennes petites.',
      pros: ['Les titres retenus sont plutôt paisibles à suivre.', 'La volatilité et le repli pèsent dans la note.'], cons: ['Les gains sont souvent plus modestes.', 'Peut écarter des titres qui montent vite mais avec des secousses.'],
      fake: ['Un titre calme peut le rester jusqu’à une mauvaise surprise : le calme passé n’est pas une assurance.', 'Un titre peu échangé peut sembler calme faute d’échanges.'],
      vs: [['regular', 'Plus douce et plus attentive au risque que Croissance régulière.']] },
    rebound: { icon: 'refresh-cw', color: '#ca8a04', lead: 'Pour un titre qui repart après une pause ou une baisse.', goal: 'Trouver les titres qui repartent à la hausse (semaine et mois) alors que le semestre n’a pas ou peu progressé.',
      path: [[0, 100], [110, 82], [200, 84], [232, 88], [252, 100]], noise: 0.004,
      behaviour: 'Une longue période de baisse ou de stagnation, puis un redémarrage récent.',
      pros: ['Cherche l’inverse du « déjà beaucoup monté ».', 'Le contexte du semestre entre dans la note de rebond.'], cons: ['Un rebond peut être éphémère.', 'Les titres sont souvent en phase de redressement fragile.'],
      fake: ['Un « rebond » de quelques jours dans une baisse qui continue.', 'Un titre qui baisse parce que l’entreprise va mal ne rebondit pas forcément.'],
      vs: [['fast', 'Croissance rapide aime ce qui monte déjà ; Rebond aime ce qui repart après n’avoir pas monté.']] },
    mom6: { icon: 'hourglass', color: '#7c3aed', lead: 'Pour miser sur l’élan des six derniers mois.', goal: 'Classer les titres selon leur hausse de J−126 à J−21, dernier mois écarté.',
      path: [[0, 100], [105, 140], [126, 150], [252, 160]], noise: 0.005,
      behaviour: 'Une belle hausse sur le semestre, sans compter le tout dernier mois.',
      pros: ['Simple à comprendre : l’élan du semestre.', 'Écarte le dernier mois, souvent trompeur.'], cons: ['Aucun critère de recherche : tous les titres notés sont retenus.', 'Marquée « expérimentale » dans le moteur.'],
      fake: ['Un retournement brutal du marché peut casser l’élan d’un coup.', 'Une grosse hausse due à un seul événement n’est pas un élan durable.'],
      vs: [['mom12', 'Momentum 12 mois regarde une durée plus longue : moins réactif, moins nerveux.']] },
    mom12: { icon: 'calendar-days', color: '#4f46e5', lead: 'Pour miser sur la tendance de l’année écoulée.', goal: 'Classer les titres selon leur hausse de J−252 à J−21, dernier mois écarté.',
      path: [[0, 100], [200, 150], [252, 158]], noise: 0.005,
      behaviour: 'Une hausse installée sur toute l’année.',
      pros: ['Plus stable car plus long.', 'Dernier mois écarté.'], cons: ['Aucun critère de recherche.', 'Lent à voir un changement de tendance.', 'Marquée « expérimentale » dans le moteur.'],
      fake: ['Un titre déjà très haut peut avoir épuisé sa hausse.', 'Demande un historique d’un an : sinon pas de note.'],
      vs: [['mom6', 'Momentum 6 mois est plus réactif.']] },
    momrisk: { icon: 'shield-check', color: '#0f766e', lead: 'Pour l’élan, mais en tenant compte du risque.', goal: 'Moyenne des élans de 6 et 12 mois, corrigée par la volatilité et le repli.',
      path: [[0, 100], [126, 130], [252, 165]], noise: 0.003,
      behaviour: 'Un élan solide ET peu de secousses.',
      pros: ['Ajoute le risque à l’élan.', 'Évite de privilégier des titres très nerveux.'], cons: ['Aucun critère de recherche.', 'Marquée « expérimentale » dans le moteur.'],
      fake: ['La correction par le risque est passée : un titre calme peut devenir nerveux.', 'Un élan, même corrigé, peut s’inverser.'],
      vs: [['mom6', 'Même idée que Momentum 6 mois mais avec une correction du risque.'], ['mom12', 'Idem pour 12 mois.']] }
  };
  const ORDER = ['fast', 'regular', 'calm', 'rebound', 'mom6', 'mom12', 'momrisk'];
  const series = d => d.path ? HM.path(d.path, d.noise || 0, 5) : HM.series.apply(null, d.series);
  const critLines = (s, c) => s.periods.filter(p => s.criteria[p.id] && (s.criteria[p.id].slope != null || s.criteria[p.id].r2 != null)).map(p => { const k = s.criteria[p.id]; const parts = [];
    if (k.slope != null) parts.push(`le prix doit monter d’au moins <b>${pc(growth(k.slope, p.sessions))}</b> si la hausse est régulière (pente ≥ ${f(k.slope, 3)} %/séance, niveau ${levelName(c.slope_levels, LV, k.slope) || 'personnalisé'})`);
    if (k.r2 != null) parts.push(`la courbe doit être assez droite (R² ≥ ${f(k.r2, 2)}, régularité ${levelName(c.r2_levels, LR, k.r2) || 'personnalisée'})`);
    return `<li>Sur <b>${p.label.toLowerCase()}</b> (${p.sessions} séances) : ${parts.join(' ; ')}.</li>`; }).join('');
  const weightsStack = (s, c) => { const e = Object.entries(s.complex_weights).filter(([, v]) => v > 0); return HC.stack(e.map(([k, v], i) => ({ label: c.complex_labels[k] || k, value: v, color: COLORS[KEYS.indexOf(k) % COLORS.length] })), { alt: 'Poids du score complexe' }) + `<div class="hc-legend">${e.map(([k, v]) => `<span><i style="background:${COLORS[KEYS.indexOf(k) % COLORS.length]}"></i>${HC.esc(c.complex_labels[k] || k)} ${f(v, 0)}</span>`).join('')}</div>`; };
  const tuneLine = s => { const t = s.tuning || {}; return [t.sat_a != null ? `saturation A = ${f(t.sat_a, 2)} %` : '', t.accel_ref != null ? `accélération k = ${f(t.accel_ref, 2)}` : '', t.momentum_horizon ? `horizon de momentum « ${t.momentum_horizon} »` : '', t.vol_mode ? `volatilité en mode ${t.vol_mode === 'relative' ? 'relatif (rapportée à la pente)' : 'absolu'}` : ''].filter(Boolean).join(' · '); };

  /* Explication détaillée de Croissance rapide, avec les vrais seuils du moteur */
  function fastDeep(H, s, c) {
    const wk = s.criteria.week || {}, mo = s.criteria.month || {}, a = (s.tuning || {}).sat_a || c.saturation.a, sat = n => a * Math.pow(n / 5, c.saturation.b);
    const gw = growth(wk.slope, 5), gm = growth(mo.slope, 21), pw = s.periods.find(p => p.id === 'week'), pm = s.periods.find(p => p.id === 'month');
    return `<h2>Comment Croissance rapide fonctionne, pas à pas</h2>
    <p>Imaginez que vous cherchiez, parmi des milliers de titres, ceux qui « décollent » en ce moment. Croissance rapide pose <b>deux questions</b>, et seulement deux :</p>
    ${H.steps([
      ['Sur la dernière semaine (5 séances), le prix monte-t-il vite ?', `<p>On trace la droite qui résume le mieux la semaine. Sa <b>pente</b> doit être d’au moins <b>${f(wk.slope, 4)} % par séance</b>. Traduit en clair : si la hausse était régulière, le titre aurait gagné environ <b>${pc(gw)}</b> sur la semaine.</p>`],
      ['Sur le dernier mois (21 séances), est-ce toujours vrai ?', `<p>Même question, sur une durée plus longue : pente d’au moins <b>${f(mo.slope, 4)} % par séance</b>, soit environ <b>${pc(gm)}</b> sur le mois si la hausse est régulière.</p>`],
      ['Les deux « oui » ? Le titre est retenu', '<p>Un seul « non » et le titre est exclu. La semaine dit « ça accélère maintenant », le mois dit « ce n’est pas un simple coup d’un jour ».</p>'],
      ['Les titres retenus sont notés puis classés', `<p>Chaque titre retenu reçoit un score de 0 à 100. Il tient compte de la hausse sur ${pw && pm ? `la semaine (poids ${f(100 * pw.weight, 0)} %) et le mois (poids ${f(100 * pm.weight, 0)} %)` : 'les durées actives'}, mais aussi de la régularité, du risque et de la liquidité (voir plus bas).</p>`]])}
    <h3>Que veut dire « ${f(wk.slope, 4)} % par séance » ?</h3>
    <p>C’est le niveau « <b>très forte</b> » de Jigobourso : la vitesse qui <b>doublerait</b> le prix en un an (252 séances) si elle durait. Sur une semaine ou un mois, cela représente peu en pourcentage (${pc(gw)} et ${pc(gm)}) : ce n’est donc pas un seuil démesuré, c’est la barre du « ça monte nettement ».</p>
    <h3>Pourquoi la pente et pas simplement la performance ?</h3>
    <p>La performance ne regarde que le premier et le dernier prix : un seul bon jour la fait bondir. La pente utilise <b>tous les prix</b> de la période, ce qui réduit l’effet d’un jour isolé. Mais elle ne vérifie pas que la courbe est <b>droite</b> : voilà pourquoi Croissance rapide laisse passer des titres qui montent par à-coups (voir « Tendance, pente et régularité »).</p>
    <h3>Essayez : qui est retenu ?</h3>
    <div class="hdemo" data-demo="fastdemo"></div>
    <h3>Dans la note, comment la hausse compte-t-elle ?</h3>
    <p>La note de dynamique compare la hausse du titre à une hausse « de référence » qui vaut 100/100. Ici, avec A = ${f(a, 1)} % : <b>${f(sat(5), 1)} %</b> sur 5 séances, <b>${f(sat(21), 1)} %</b> sur 21 séances. Un titre qui gagne la moitié de la référence a 50/100 en dynamique ; il plafonne à 100 au-delà.</p>
    ${H.warn('<p>Croissance rapide <b>ne demande aucune régularité</b> pour être retenu. Un titre qui monte de +8 % en un seul jour hier peut passer le filtre de la semaine. C’est pourquoi il faut regarder la fiche : courbe, régularité, liquidité.</p>', 'Le piège principal')}
    <h3>Quand l’utiliser ?</h3>
    <ul><li>Pour <b>repérer des accélérations</b>, pas pour constituer un choix final.</li><li>Si la liste est trop longue ou trop nerveuse : montez vers <a href="#/strat-regular">Croissance régulière</a>.</li><li>Si elle est vide : le marché est calme, c’est normal ; ou baissez le niveau de pente dans Mes critères de recherche.</li></ul>`;
  }
  function fastMount(el, { facts, HM, HC }) {
    const d = el.querySelector('[data-demo=fastdemo]'); if (!d || !facts) return;
    const s = facts.strategies.find(x => x.id === 'fast'), wk = s.criteria.week.slope, mo = s.criteria.month.slope, T = window.HELP_TITLES || {};
    const list = Object.entries(T).map(([n, t]) => [n, t.closes, t.desc]); list.push(['Pic d’un jour', HM.path([[0, 100], [250, 100], [251, 100], [252, 108]], 0.001, 8), 'plat pendant un an, puis +8 % hier']);
    const rows = list.map(([n, cl, desc]) => { const w = HM.windowOf(cl, 5), m = HM.windowOf(cl, 21), okw = w.slope >= wk, okm = m.slope >= mo; return `<tr><th scope="row">${n}<br><small class="muted">${desc}</small></th><td class="n ${okw ? 'good' : 'bad'}">${HC.f1(w.slope, 3)}</td><td class="n ${okm ? 'good' : 'bad'}">${HC.f1(m.slope, 3)}</td><td><span class="badge ${okw && okm ? 'ok' : 'danger'}">${okw && okm ? 'retenu' : 'exclu'}</span></td></tr>`; }).join('');
    d.innerHTML = `<span class="fic">Titres fictifs · seuils réels</span><div class="sui-scroll"><table><thead><tr><th>Titre</th><th class="n">Pente semaine<br><small>(seuil ${HC.f1(wk, 3)})</small></th><th class="n">Pente mois<br><small>(seuil ${HC.f1(mo, 3)})</small></th><th>Verdict</th></tr></thead><tbody>${rows}</tbody></table></div><p class="small muted">Vert = la pente atteint le seuil. Il faut deux verts pour être retenu.</p>`;
  }
  ORDER.forEach(id => {
    const d = DEF[id];
    L.push({ id: 'strat-' + id, group: 'strategies', title: '', icon: I(d.icon), color: d.color, keywords: 'stratégie fiche ' + id, lead: d.lead,
      beginner: ({ H, facts }) => {
        const s = facts && facts.strategies.find(x => x.id === id), c = facts && facts.common, ser = series(d), nm = s ? s.label : id;
        if (!s) return '<div class="notice err">Réglages indisponibles pour le moment.</div>';
        const m60 = HM.windowOf(ser, 63) || {}, top = Object.entries(s.complex_weights).filter(([, v]) => v > 0).sort((a, b) => b[1] - a[1]).slice(0, 3).map(([k, v]) => `<b>${c.complex_labels[k] || k}</b> (${f(v, 0)})`).join(', ');
        const crit = critLines(s, c);
        return `<h2>L’objectif en une phrase</h2><p>${d.goal}</p>${id === 'fast' ? fastDeep(H, s, c) : ''}
        <h2>Le comportement recherché</h2><p>${d.behaviour}</p>
        ${H.fig(HC.line({ series: [{ name: 'Exemple type (fictif)', values: ser, color: d.color }], alt: 'Exemple de comportement recherché', w: 640, h: 240 }), `Courbe fictive illustrant le comportement type. Sur le dernier trimestre de cet exemple : pente ${f(m60.slope, 3)} %/séance, régularité R² = ${f(m60.r2, 2)}.`)}
        <h2>Les vrais critères de recherche</h2>
        ${crit ? `<p>Pour être <b>retenu</b>, un titre doit satisfaire :</p><ul>${crit}</ul>` : `<p><b>Aucun critère de recherche.</b> Tous les titres dont les données existent sont retenus ; c’est la note qui fait le tri.</p>`}
        <h2>Comment la note est construite</h2>
        <p>Durées utilisées pour la note : ${s.periods.map(p => `<b>${p.label}</b> (${f(100 * p.weight, 0)} %)`).join(', ')}.</p>
        <p>Dans le score complexe, ce qui pèse le plus : ${top}.</p>${weightsStack(s, c)}
        <div class="two mt-4"><div class="hdemo m-0"><b>Avantages</b><ul>${d.pros.map(x => `<li>${x}</li>`).join('')}</ul></div><div class="hdemo m-0"><b>Limites</b><ul>${d.cons.map(x => `<li>${x}</li>`).join('')}</ul></div></div>
        ${H.warn(`<ul>${d.fake.map(x => `<li>${x}</li>`).join('')}</ul>`, 'Risques de faux signaux')}
        <h2>Par rapport aux autres</h2><ul>${d.vs.map(([o, t]) => `<li>${t} <a href="#/strat-${o}">Voir la fiche</a></li>`).join('')}</ul>
        <p>Rappel : cette fiche décrit un profil de prix passé, pas une promesse. <a href="#/strat-comparaison">Comparer les 7 stratégies</a>.</p>
        ${H.jigo(`<p>Pour l’utiliser : choisissez « ${nm} » dans le sélecteur de l’<a href="index.html">Explorer</a>. Pour la régler : <a href="mes-strategies.html">Mes stratégies</a>.</p>`)}`; },
      expert: ({ H, facts }) => {
        const s = facts && facts.strategies.find(x => x.id === id), c = facts && facts.common; if (!s) return '';
        const rows = s.periods.map(p => { const k = s.criteria[p.id] || {}; return [p.label, p.sessions, f(100 * p.weight, 1) + ' %', k.slope != null ? f(k.slope, 4) + ' %/séance' : '—', k.slope != null ? pc(growth(k.slope, p.sessions)) : '—', k.r2 != null ? f(k.r2, 3) : '—']; });
        const cw = Object.entries(s.complex_weights).filter(([, v]) => v > 0).map(([k, v]) => [c.complex_labels[k] || k, f(v, 0)]);
        return `<h2>Paramètres officiels</h2>${H.table(['Durée', 'Séances', 'Poids de la durée', 'Pente min.', '≈ hausse régulière équivalente', 'R² min.'], rows)}
        <p>Mode des poids de durée : <b>${s.weights_mode === 'auto' ? 'automatique (κ = ' + f(c.kappa, 2) + ')' : 'personnalisé'}</b>. Tri par défaut dans le moteur : <code>${HC.esc(s.sort)}</code> (affichage : score complexe). Fraîcheur des données exigée : <b>${s.require_fresh ? 'oui' : 'non'}</b>.</p>
        <h3>Poids du score complexe</h3>${H.table(['Composante', 'Poids'], cw)}
        <p>Réglages : ${tuneLine(s) || '—'}. Ancrage récent λ = ${f(c.anchor, 2)}.</p>
        <h3>Comment lire ces chiffres</h3>
        <ul><li>« ≈ hausse régulière équivalente » = <code>(1 + pente/100)^n − 1</code> : ce que donnerait la pente minimale sur n séances si la courbe était une exponentielle parfaite.</li>
        ${id === 'fast' ? '<li>Pas de seuil de R² dans les critères de recherche (pente seule) ; le R² compte dans le score complexe.</li>' : ''}
        ${id === 'rebound' ? '<li>Le semestre est activé sans critère : il fournit le contexte de rebond. Note de rebond = <code>100 × clamp((20 − perf_semestre) / 30)</code> (≤ −10 % → 100, ≥ +20 % → 0).</li>' : ''}
        ${id.startsWith('mom') ? `<li>Momentum : <code>100 × (c<sub>J−21</sub> / c<sub>J−126 ou J−252</sub> − 1)</code>, note = <code>100 × clamp(m / saturation)</code> avec saturation ${c.momentum.saturation['6m']} % (6 mois) et ${c.momentum.saturation['12m']} % (12 mois) ; négatif → 0.</li>` : ''}
        ${id === 'calm' ? '<li>Volatilité et repli ne sont pas des critères de recherche : ils pèsent seulement dans le score complexe.</li>' : ''}</ul>
        ${H.warn('<p>Limites statistiques communes : mesures sur des fenêtres courtes, clôtures quotidiennes, aucune validation hors échantillon. Ne pas interpréter une note comme une probabilité de hausse.</p>')}`; },
      mount: id === 'fast' ? fastMount : null, strategyId: id });
  });
  // titres dynamiques selon les noms officiels (remplis au démarrage par aide.js via facts) : titre de repli
  const FALLBACK = { fast: 'Croissance rapide', regular: 'Croissance régulière', calm: 'Hausse calme', rebound: 'Rebond', mom6: 'Momentum 6 mois', mom12: 'Momentum 12 mois', momrisk: 'Momentum ajusté au risque' };
  L.forEach(c => { if (c.strategyId) c.title = FALLBACK[c.strategyId]; });

  L.push({
    id: 'strat-comparaison', group: 'strategies', title: 'Comparer les 7 stratégies', icon: I('scale'), color: '#2563eb', keywords: 'comparaison comparatif tableau stratégies différences laquelle choisir',
    lead: 'Un tableau et des barres construits à partir des vrais réglages, pour choisir en connaissance de cause.',
    beginner: ({ H, facts }) => {
      if (!facts) return '<div class="notice err">Réglages indisponibles.</div>'; const c = facts.common;
      const rows = facts.strategies.map(s => { const tests = s.periods.reduce((a, p) => a + Object.values(s.criteria[p.id] || {}).filter(v => v != null).length, 0), hor = s.periods.reduce((a, p) => a + p.weight * p.sessions, 0), risk = (s.complex_weights.volatility || 0) + (s.complex_weights.drawdown || 0), tot = Object.values(s.complex_weights).reduce((a, b) => a + b, 0) || 1;
        return { s, tests, hor, risk: 100 * risk / tot, dyn: 100 * ((s.complex_weights.dynamics || 0) + (s.complex_weights.momentum || 0)) / tot }; });
      const mxh = Math.max(...rows.map(r => r.hor), 1);
      return `<h2>Vue d’ensemble</h2>
      ${H.table(['Stratégie', 'Durées utilisées', 'Questions du filtrage', 'Idée'], rows.map(r => [`<a href="#/strat-${r.s.id}">${r.s.label}</a>`, r.s.periods.map(p => p.label).join(', '), r.tests ? r.tests + ' test' + (r.tests > 1 ? 's' : '') : 'aucun (note seule)', DEF[r.s.id].lead]))}
      <h2>Trois lectures en barres</h2>
      <p><b>Exigence du filtrage</b> : nombre de questions (pente, R²) qu’un titre doit passer. Plus il y en a, plus la liste est courte.</p>
      ${HC.bars(rows.map((r, i) => ({ label: r.s.label, value: r.tests, color: COLORS[i] })), { max: Math.max(...rows.map(r => r.tests), 1), fmt: v => v })}
      <p><b>Horizon moyen</b> : durée moyenne (en séances) des fenêtres de note, pondérée par leurs poids.</p>
      ${HC.bars(rows.map((r, i) => ({ label: r.s.label, value: r.hor, color: COLORS[i] })), { max: mxh, fmt: v => f(v, 0) + ' s.' })}
      <p><b>Poids du risque</b> : part de la volatilité et du repli dans le score complexe (en %).</p>
      ${HC.bars(rows.map((r, i) => ({ label: r.s.label, value: r.risk, color: COLORS[i] })), { max: 100, fmt: v => f(v, 0) + ' %' })}
      ${H.tip('<p>Ces barres comparent des <b>réglages</b>, pas des performances. Elles ne disent pas laquelle « rapporte le plus » : personne ne peut le garantir.</p>', 'Attention à la lecture')}
      <h2>Laquelle choisir ?</h2>
      ${H.table(['Si je cherche…', 'Je regarde'], [['Ce qui monte le plus vite', '<a href="#/strat-fast">Croissance rapide</a>'], ['Du solide et constant', '<a href="#/strat-regular">Croissance régulière</a>'], ['Du paisible', '<a href="#/strat-calm">Hausse calme</a>'], ['Un redémarrage', '<a href="#/strat-rebound">Rebond</a>'], ['L’élan des mois passés', '<a href="#/strat-mom6">Momentum 6</a>, <a href="#/strat-mom12">12</a>, ou <a href="#/strat-momrisk">ajusté au risque</a>']])}`; },
    expert: ({ H, facts }) => {
      if (!facts) return ''; const c = facts.common;
      const k = ['dynamics', 'r2', 'up_days', 'concentration', 'volatility', 'drawdown', 'liquidity', 'acceleration', 'momentum', 'recovery'];
      return `<h2>Poids du score complexe, par stratégie</h2>${H.table(['Stratégie'].concat(k.map(x => c.complex_labels[x] || x)), facts.strategies.map(s => [s.label].concat(k.map(x => s.complex_weights[x] ? f(s.complex_weights[x], 0) : '·'))))}
      <h2>Durées et poids (%)</h2>${H.table(['Stratégie', 'Durées : poids', 'Mode'], facts.strategies.map(s => [s.label, s.periods.map(p => p.label + ' ' + f(100 * p.weight, 0)).join(' · '), s.weights_mode === 'auto' ? 'auto (κ ' + f(c.kappa, 2) + ')' : 'personnalisé']))}`; }
  });
})();
