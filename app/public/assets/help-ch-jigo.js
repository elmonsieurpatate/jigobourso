/* Chapitres : Jigobourso — chercher (stratégies, critères), noter (scores), classer. Titres fictifs ; aucune donnée ni réglage réel n'est lu ni modifié par les démonstrations. */
(function () {
  const I = n => J.icon(n), L = (window.HELP_CHAPTERS = window.HELP_CHAPTERS || []);
  const f = (v, d = 1) => HC.f1(v, d), pc = (v, d = 1) => (v > 0 ? '+' : '') + f(v, d) + ' %';
  const TITLES = {
    'Zébulon': { desc: 'monte régulièrement et plutôt vite', closes: HM.path([[0, 100], [189, 112], [252, 150]], 0.004, 11), liquidity: 30e6 },
    'Fusée': { desc: 'endormie puis envolée ces dernières semaines', closes: HM.path([[0, 100], [200, 101], [220, 104], [252, 140]], 0.006, 13), liquidity: 8e6 },
    'Câline': { desc: 'monte très doucement, presque en ligne droite', closes: HM.series(252, 30, 0.008, 2, 100, 0.001, 5), liquidity: 12e6 },
    'Brumel': { desc: 'très nerveux : de gros zigzags', closes: HM.series(252, 38, 0.12, 9, 100, 0.004, 3), liquidity: 5e6 },
    'Dormeur': { desc: 'ne bouge presque pas, peu échangé', closes: HM.series(252, 2, 0.02, 3, 100, 0.004, 6), liquidity: 0.8e6 }
  };
  window.HELP_TITLES = TITLES;
  const COLORS = { 'Zébulon': '#2563eb', 'Fusée': '#f97316', 'Câline': '#16a34a', 'Brumel': '#9333ea', 'Dormeur': '#64748b' };
  const COMP = { dynamics: 'Dynamique', r2: 'Régularité (R²)', up_days: 'Jours de hausse', concentration: 'Concentration', volatility: 'Volatilité', drawdown: 'Repli (drawdown)', liquidity: 'Liquidité' };

  L.push({
    id: 'explorer', group: 'jigo', title: 'L’Explorer : lire la page de résultats', icon: I('compass'), color: '#2563eb', keywords: 'explorer recherche résultats tableau colonnes filtre tri rang titre tendance',
    lead: 'La page principale : choisir une stratégie, voir les titres retenus, les trier et les filtrer.',
    beginner: ({ H }) => `
      <h2>Ce que vous voyez</h2>
      <div class="hdemo"><span class="fic">Schéma simplifié</span>
      <div class="two"><div class="kpi"><small>① Le sélecteur de stratégie</small>Vous choisissez <i>comment</i> chercher. Chaque stratégie a son icône et son texte.</div>
      <div class="kpi"><small>② Le bandeau de statut</small>Dit si la stratégie est <b>Officielle</b>, <b>Adaptée</b> (vous l’avez modifiée) ou <b>Personnelle</b> (créée par vous).</div>
      <div class="kpi"><small>③ Les filtres</small>Pays, secteur, place, type (action / ETF) : pour restreindre l’affichage.</div>
      <div class="kpi"><small>④ Le tableau</small>Un titre par ligne : rang, nom, score complexe, score simple, tendance, variations…</div></div></div>
      <h2>Lire une ligne du tableau</h2>
      ${H.table(['Colonne', 'Ce qu’elle dit'], [['Rang', 'La place du titre dans le classement de la stratégie (1 = meilleur).'], ['Titre', 'Le nom ; dessous, son <b>secteur</b>.'], ['Score complexe', 'La note complète sur 100 (hausse, régularité, risque, liquidité).'], ['Score simple', 'Une note plus courte : hausse × régularité.'], ['Tendance', 'Une mini-courbe des derniers prix.'], ['Var. 1J, 1S, 1M…', 'La variation sur un jour, une semaine, un mois…']])}
      ${H.jigo('<p>Tout est personnalisable : <b>Mes colonnes et tris</b> choisit les colonnes et leur ordre ; <b>Mes filtres et catégories</b> fixe vos filtres de départ ; <b>Mes stratégies</b> règle la façon de chercher.</p>')}
      <h2>Trier ne change pas les scores</h2>
      <p>Vous pouvez trier le tableau sur n’importe quelle colonne. Cela ne change que l’ordre d’<i>affichage</i> : le <b>rang</b> et les scores restent ceux de la stratégie. Par défaut, le tri se fait sur le score complexe.</p>
      ${H.quiz('q-explorer', [{ q: 'Je filtre le tableau sur « ETF » seulement. Le rang d’un ETF change-t-il ?', o: ['Oui, il est recalculé', 'Non, le rang reste celui de la stratégie'], a: 1, why: 'Un filtre masque des lignes, il ne recalcule pas les rangs. Voir « Classements ».' }])}`,
    expert: ({ H }) => `
      <h2>Détails</h2>
      <ul><li>Les statuts de stratégie sont calculés par utilisateur (<code>strategies/status</code>) : Officielle (aucun écart avec la référence), Adaptée (critères et/ou scores différents), Personnelle.</li>
      <li>Les colonnes et tris viennent de <code>table_layouts:&lt;uid&gt;</code> ; à défaut, du défaut commun fixé par l’administration.</li>
      <li>Le tri par défaut est le score complexe ; l’ordre des options de tri suit l’ordre des colonnes.</li>
      <li>Les filtres de catégories (pays, secteur, place, type) s’appliquent à l’affichage ; les rangs sont calculés avant.</li></ul>`
  });

  L.push({
    id: 'strategies-vue', group: 'jigo', title: 'Les stratégies : filtrer puis noter', icon: I('target'), color: '#f97316', keywords: 'stratégie filtrage notation officielle adaptée personnelle choisir',
    lead: 'Une stratégie, c’est une manière de chercher, en deux temps : un tri, puis des notes.',
    beginner: ({ H }) => `
      <h2>Deux temps</h2>
      ${H.steps([['Le filtrage : « ce titre mérite-t-il un coup d’œil ? »', '<p>La stratégie pose des questions sur le prix : <i>« A-t-il monté d’au moins tant sur le dernier mois ? La courbe est-elle assez droite ? »</i> Si oui à toutes, le titre est <b>retenu</b>. Sinon, <b>exclu</b>. Si on manque de données, <b>indéterminé</b>.</p>'], ['La notation : « à quel point est-il bon ? »', '<p>Les titres retenus reçoivent des notes de 0 à 100 sur plusieurs points : hausse, régularité, risque, liquidité. Les titres sont ensuite classés.</p>']])}
      ${H.fig(`<svg viewBox="0 0 640 110" class="hc-svg" role="img" aria-label="Du filtrage au classement"><g font-size="13" fill="currentColor"><rect x="4" y="25" width="150" height="60" rx="10" fill="#dbeafe"/><text x="79" y="52" text-anchor="middle" fill="#1e3a8a" font-weight="700">Tous les titres</text><text x="79" y="70" text-anchor="middle" fill="#1e3a8a">milliers</text><path d="M158 55h50" stroke="#64748b" stroke-width="2"/><rect x="212" y="25" width="140" height="60" rx="10" fill="#ffedd5"/><text x="282" y="52" text-anchor="middle" fill="#9a3412" font-weight="700">Filtrage</text><text x="282" y="70" text-anchor="middle" fill="#9a3412">retenu / exclu</text><path d="M356 55h50" stroke="#64748b" stroke-width="2"/><rect x="410" y="25" width="100" height="60" rx="10" fill="#dcfce7"/><text x="460" y="52" text-anchor="middle" fill="#166534" font-weight="700">Notes</text><text x="460" y="70" text-anchor="middle" fill="#166534">0 à 100</text><path d="M514 55h30" stroke="#64748b" stroke-width="2"/><rect x="548" y="25" width="88" height="60" rx="10" fill="#f3e8ff"/><text x="592" y="60" text-anchor="middle" fill="#6b21a8" font-weight="700">Classement</text></g></svg>`, 'Le chemin d’un titre dans Jigobourso.')}
      <h2>Trois statuts</h2>
      ${H.cards([{ icon: I('badge-check'), bg: '#dbeafe', title: 'Officielle', text: 'La stratégie telle que définie par Jigobourso. Vous n’y avez rien changé.' }, { icon: I('sliders-horizontal'), bg: '#ffedd5', title: 'Adaptée', text: 'Vous avez modifié ses critères ou ses scores. Vous pouvez revenir à l’officiel en un clic.' }, { icon: I('user'), bg: '#f3e8ff', title: 'Personnelle', text: 'Une stratégie que vous avez créée, visible de vous seul.' }])}
      <p>Les <b>7 stratégies officielles</b> sont présentées une par une dans le groupe « Les 7 stratégies », avec leurs vrais réglages.</p>
      ${H.cards([{ icon: I('rocket'), bg: '#ffedd5', title: 'Croissance rapide', text: 'Ce qui monte vite.', href: 'strat-fast' }, { icon: I('trending-up'), bg: '#dcfce7', title: 'Croissance régulière', text: 'Hausse solide et constante.', href: 'strat-regular' }, { icon: I('waves'), bg: '#cffafe', title: 'Hausse calme', text: 'Monter sans secousses.', href: 'strat-calm' }, { icon: I('refresh-cw'), bg: '#fef3c7', title: 'Rebond', text: 'Repart après une pause.', href: 'strat-rebound' }, { icon: I('hourglass'), bg: '#ede9fe', title: 'Momentum 6 mois', text: 'L’élan du semestre.', href: 'strat-mom6' }, { icon: I('calendar-days'), bg: '#e0e7ff', title: 'Momentum 12 mois', text: 'L’élan de l’année.', href: 'strat-mom12' }, { icon: I('shield-check'), bg: '#ccfbf1', title: 'Momentum ajusté au risque', text: 'L’élan, corrigé du risque.', href: 'strat-momrisk' }])}
      <p>Pour les comparer d’un coup d’œil : <a href="#/strat-comparaison">comparaison des 7 stratégies</a>.</p>
      ${H.quiz('q-strat', [{ q: 'Une stratégie « Adaptée », c’est…', o: ['Une stratégie créée de zéro', 'Une stratégie officielle que j’ai modifiée', 'Une stratégie recommandée'], a: 1, why: 'Adaptée = officielle + vos modifications. Restaurer supprime l’adaptation.' }])}`,
    expert: ({ H }) => `
      <h2>Modèle</h2>
      <ul><li><b>Critères de recherche</b> par durée (pente min, R² min, parfois rendement min/max) : verdict <code>retenu / exclu / indéterminé</code> (voir « Critères »).</li>
      <li><b>Profil de scores</b> par stratégie : durées actives et leurs poids (auto ou personnalisés), poids des 10 composantes du score complexe, réglages (A de saturation, k d’accélération, mode de volatilité, horizon de momentum).</li>
      <li>Les deux couches sont <b>indépendantes</b> : adapter les scores ne change pas qui est retenu, et inversement.</li>
      <li>Stockage par compte : <code>ct_strategies:&lt;uid&gt;</code> (critères), <code>scores_profiles_u&lt;uid&gt;</code> (scores). Revenir exactement aux valeurs officielles supprime l’entrée.</li></ul>`
  });

  L.push({
    id: 'criteres', group: 'jigo', title: 'Les critères de recherche', icon: I('filter'), color: '#f97316', keywords: 'critères seuil pente régularité retenu exclu indéterminé niveau doux modéré fort filtrage',
    lead: 'Les seuils qui décident si un titre est retenu ou exclu. Réglez-les vous-même sur cinq titres fictifs.',
    beginner: ({ H, facts }) => `
      <h2>Un critère = une question oui/non</h2>
      <p>Pour chaque durée, la stratégie pose une ou deux questions :</p>
      <ul><li><b>Pente minimale</b> : le titre monte-t-il au moins aussi vite que ça ?</li><li><b>Régularité minimale</b> (R²) : la courbe est-elle au moins aussi droite que ça ?</li></ul>
      <p>Il faut répondre oui à <b>toutes</b> les questions de <b>toutes</b> les durées activées pour être retenu.</p>
      ${facts ? `<h3>Les niveaux proposés</h3><p>Pour ne pas manipuler des nombres abstraits, Jigobourso propose des <b>niveaux</b> nommés :</p>${levels(facts)}` : ''}
      <h2>À vous de jouer</h2>
      <p>Les cinq titres ci-dessous sont inventés. Déplacez les seuils et regardez qui est retenu.</p>
      <div class="hdemo" data-demo="crit"></div>
      ${H.warn('<p>Remarquez : un titre peut être <b>exclu</b> tout en ayant une <b>très bonne note</b>. Le filtrage et la notation sont deux étapes séparées : le premier décide d’afficher ou non, la seconde mesure la qualité. Voir « Scores ».</p>', 'Exclu ne veut pas dire mauvais')}
      ${H.jigo('<p>Vos réglages se font dans <b>Mes critères de recherche</b>. « Si la liste est trop courte » : baissez la pente ou la régularité demandées, ou retirez une durée. « Si elle est trop longue » : faites l’inverse.</p>')}
      ${H.quiz('q-crit', [{ q: 'Je veux plus de résultats. Que faire ?', o: ['Exiger une pente plus forte', 'Baisser le niveau de pente ou de régularité demandé', 'Ajouter des durées activées'], a: 1, why: 'Moins on est exigeant, plus de titres passent. Ajouter une durée ajoute une condition : ça réduit la liste.' }])}`,
    expert: ({ H, facts }) => `
      <h2>Règles du verdict</h2>
      <ul><li>Pour chaque durée activée, tests <code>pente ≥ seuil</code> et <code>R² ≥ seuil</code> (selon la stratégie), et éventuellement <code>perf ≥ min</code> ou <code>perf ≤ max</code>.</li>
      <li>Retenu si <b>tous</b> les tests de <b>toutes</b> les durées activées sont vrais ; exclu si au moins un est faux ; indéterminé si une mesure nécessaire manque (historique insuffisant) et qu'aucun test n'est déjà faux.</li>
      <li>Les seuils de pente sont en <b>% par séance</b> (composé) ; les niveaux nommés sont définis par le temps de doublement : douce 8 ans, modérée 4 ans, forte 2 ans, très forte 1 an (252 séances/an) : <code>100 × (2^(1/(ans·252)) − 1)</code>.</li>
      <li>Les niveaux de régularité viennent d'un rapport de dispersion résiduelle <i>ρ</i> : R² = 1 − ρ² avec ρ = 2/3 (souple), 1/2 (équilibré), 1/3 (strict).</li></ul>
      ${facts ? levels(facts) : ''}
      <div class="hdemo" data-demo="crit"></div>
      ${H.warn('<p>Limite : un seuil de pente appliqué à une fenêtre courte est très sensible au bruit ; c’est pourquoi les stratégies combinent plusieurs durées.</p>')}`,
    mount: (el, { HM, HC, facts }) => {
      const d = el.querySelector('[data-demo=crit]'); if (!d) return;
      const sl = facts ? facts.common.slope_levels : { gentle: 0.0344, moderate: 0.0688, strong: 0.1376, very_strong: 0.2754 }, r2 = facts ? facts.common.r2_levels : { flexible: 0.556, balanced: 0.75, strict: 0.889 };
      const st = { dur: 'quarter', slope: sl.moderate, r2: r2.strict };
      const draw = () => { const n = HM.SESSIONS[st.dur];
        const rows = Object.entries(TITLES).map(([name, t]) => { const m = HM.windowOf(t.closes, n), ok = m.slope >= st.slope && m.r2 >= st.r2, e = HM.evaluate(t, ['week', 'month', 'quarter', 'half']); return { name, m, ok, score: e.complex.score }; });
        d.querySelector('#crit-out').innerHTML = `<div class="sui-scroll"><table><thead><tr><th>Titre</th><th class="n">Pente (%/séance)</th><th class="n">R²</th><th>Verdict</th><th class="n">Score complexe</th></tr></thead><tbody>${rows.map(r => `<tr><th scope="row">${r.name}<br><small class="muted">${TITLES[r.name].desc}</small></th><td class="n ${r.m.slope >= st.slope ? 'good' : 'bad'}">${f(r.m.slope, 3)}</td><td class="n ${r.m.r2 >= st.r2 ? 'good' : 'bad'}">${f(r.m.r2, 2)}</td><td><span class="badge ${r.ok ? 'ok' : 'ko'}">${r.ok ? 'retenu' : 'exclu'}</span></td><td class="n">${f(r.score, 0)}</td></tr>`).join('')}</tbody></table></div>`;
        const mx = rows.filter(r => !r.ok).sort((a, b) => b.score - a.score)[0];
        d.querySelector('#crit-note').innerHTML = mx && mx.score >= 40 ? `<b>${mx.name}</b> est <b>exclu</b> avec ces seuils, mais son score complexe est de <b>${f(mx.score, 0)}</b> : le filtrage et la note sont deux choses différentes.` : '';
        d.querySelector('#crit-s').textContent = f(st.slope, 3) + ' %/séance (≈ ' + pc(100 * (Math.pow(1 + st.slope / 100, n) - 1), 1) + ' sur ' + n + ' séances)'; d.querySelector('#crit-r').textContent = f(st.r2, 2); };
      d.innerHTML = `<span class="fic">Titres fictifs · vos vrais réglages ne bougent pas</span><div class="ctl"><label>Durée testée<select id="crit-d">${['week', 'month', 'quarter', 'half'].map(k => `<option value="${k}" ${k === st.dur ? 'selected' : ''}>${HM.LABELS[k]} (${HM.SESSIONS[k]} séances)</option>`).join('')}</select></label>
      <label>Pente minimale : <b id="crit-s"></b><input id="crit-sr" type="range" min="0" max="60" value="${Math.round(st.slope * 100)}"></label><label>Régularité minimale (R²) : <b id="crit-r"></b><input id="crit-rr" type="range" min="0" max="100" value="${Math.round(st.r2 * 100)}"></label></div>
      <div class="ctl"><button class="btn sm" id="crit-lo">Doux</button><button class="btn sm" id="crit-mid">Équilibré</button><button class="btn sm" id="crit-hi">Strict</button></div><div id="crit-out"></div><p id="crit-note" class="small"></p>`;
      const set = (s, r) => { st.slope = s; st.r2 = r; d.querySelector('#crit-sr').value = Math.round(s * 100); d.querySelector('#crit-rr').value = Math.round(r * 100); draw(); };
      d.querySelector('#crit-d').onchange = e => { st.dur = e.target.value; draw(); }; d.querySelector('#crit-sr').oninput = e => { st.slope = e.target.value / 100; draw(); }; d.querySelector('#crit-rr').oninput = e => { st.r2 = e.target.value / 100; draw(); };
      d.querySelector('#crit-lo').onclick = () => set(sl.gentle, r2.flexible); d.querySelector('#crit-mid').onclick = () => set(sl.moderate, r2.balanced); d.querySelector('#crit-hi').onclick = () => set(sl.strong, r2.strict);
      draw();
    }
  });
  function levels(facts) {
    const c = facts.common, N = { gentle: 'douce', moderate: 'modérée', strong: 'forte', very_strong: 'très forte' }, R = { flexible: 'souple', balanced: 'équilibrée', strict: 'stricte' }, g = (s, n) => 100 * (Math.pow(1 + s / 100, n) - 1);
    return `<div class="sui-scroll"><table class="sui-cmp"><caption class="small muted ta-left">Niveaux de pente et hausse correspondante si la montée est régulière</caption><thead><tr><th>Niveau</th><th>Par séance</th><th>1 semaine</th><th>1 mois</th><th>1 trimestre</th></tr></thead><tbody>${Object.entries(c.slope_levels).map(([k, v]) => `<tr><th scope="row">${N[k]}</th><td>${f(v, 3)} %</td><td>${pc(g(v, 5))}</td><td>${pc(g(v, 21))}</td><td>${pc(g(v, 63))}</td></tr>`).join('')}</tbody></table></div>
    <div class="sui-scroll"><table class="sui-cmp"><caption class="small muted ta-left">Niveaux de régularité (R² minimal, de 0 à 1)</caption><thead><tr><th>Niveau</th><th>R² minimal</th></tr></thead><tbody>${Object.entries(c.r2_levels).map(([k, v]) => `<tr><th scope="row">${R[k]}</th><td>${f(v, 3)}</td></tr>`).join('')}</tbody></table></div>`;
  }

  /* ───── SCORES + simulateur ───── */
  L.push({
    id: 'scores', group: 'jigo', title: 'Les scores : comment la note est calculée', icon: I('gauge'), color: '#16a34a', keywords: 'score simple complexe note pondération poids composantes dynamique liquidité simulateur κ ancrage',
    lead: 'Une note de 0 à 100 pour comparer. D’où vient-elle, pourquoi est-elle bonne ou mauvaise, et comment la régler ?',
    beginner: ({ H }) => `
      <h2>Pourquoi des notes ?</h2>
      <p>Le filtrage dit « oui ou non ». Mais parmi les « oui », certains sont meilleurs que d’autres. La note les départage, un peu comme une moyenne de plusieurs matières à l’école.</p>
      <h2>Deux notes</h2>
      ${H.cards([{ icon: I('gauge'), bg: '#dbeafe', title: 'Score simple', text: '<b>Hausse × régularité.</b> Il faut monter ET de façon droite. Si l’un des deux est faible, la note chute. Facile à comprendre.' }, { icon: I('layers'), bg: '#dcfce7', title: 'Score complexe', text: 'Une <b>moyenne pondérée</b> de sept « matières » : hausse, régularité, jours de hausse, concentration, volatilité, repli, liquidité. Plus complet.' }])}
      <h2>Les sept matières du score complexe</h2>
      ${H.table(['Matière', 'Question posée', 'Poids par défaut'], [['Dynamique', 'La hausse est-elle forte pour cette durée ?', '40'], ['Régularité (R²)', 'La courbe est-elle droite ?', '15'], ['Jours de hausse', 'Y a-t-il beaucoup de jours en hausse ?', '5'], ['Concentration', 'La hausse vient-elle de partout, ou d’un seul jour miracle ?', '7'], ['Volatilité', 'Les secousses quotidiennes sont-elles petites ?', '15'], ['Repli', 'La pire chute depuis un sommet est-elle petite ?', '8'], ['Liquidité', 'Le titre est-il bien échangé ?', '10']])}
      <p>Chaque matière est notée de 0 à 100, puis multipliée par son <b>poids</b>. Un poids de 40 sur 100 signifie : « 40 % de la note finale vient de cette matière ». Les poids sont réglables.</p>
      <h2>Les durées comptent aussi</h2>
      <p>Chaque matière est calculée pour <b>chaque durée</b> (semaine, mois, trimestre…). Les durées ont elles aussi un <b>poids</b>. Par défaut, les longues durées pèsent plus, mais pas trop : une année ne compte pas 252 fois plus qu’un jour.</p>
      <h2>Faites-le vous-même : le simulateur</h2>
      <p>Cinq titres fictifs, vos propres poids. Changez-les et regardez les notes et le classement bouger. Rien de ce que vous faites ici ne modifie vos vrais réglages (ceux-ci se changent dans <b>Mes paramètres de scores</b>).</p>
      <div class="hdemo" data-demo="sim"></div>
      <h2>Pourquoi un score est bon ou mauvais ?</h2>
      ${H.steps([['Il monte fort', '<p>La dynamique est haute, et c’est la matière qui pèse le plus (40).</p>'], ['Il monte droit', '<p>R² élevé, beaucoup de jours de hausse, pas de jour miracle.</p>'], ['Il ne fait pas peur', '<p>Petite volatilité et petit repli.</p>'], ['On peut le revendre', '<p>Liquidité suffisante.</p>']])}
      <p>Un mauvais score vient de l’inverse : hausse faible, courbe chaotique, grosses chutes ou titre peu échangé. Le détail de chaque titre est dans sa <b>fiche</b>.</p>
      ${H.tip('<p>Le score <b>ne dépend pas</b> des filtres que vous appliquez à l’écran, ni de l’ordre d’affichage. Il ne dépend que du prix du titre et des réglages de la stratégie.</p>')}
      ${H.quiz('q-scores', [{ q: 'Si j’augmente le poids de la volatilité dans le simulateur, quels titres progressent ?', o: ['Les plus nerveux', 'Les plus calmes', 'Aucun'], a: 1, why: 'La note de volatilité est meilleure quand les secousses sont petites : donner plus de poids à cette matière avantage les titres calmes.' }, { q: 'Quel est l’effet du poids d’une durée ?', o: ['Il choisit les titres retenus', 'Il dit combien cette durée compte dans la moyenne', 'Il change le prix du titre'], a: 1, why: 'Les durées pondèrent la moyenne des notes. Le filtrage est une autre étape.' }])}`,
    expert: ({ H, facts }) => { const c = facts ? facts.common : null; return `
      <h2>Notes d'une période (n séances)</h2>
      <div class="formula">croissance g = 100 × ((1 + pente/100)^n − 1)
saturation S(n) = A × (n/5)^${c ? c.saturation.b : 0.52}     A = ${c ? c.saturation.a : 17} % (réglable par stratégie)
dynamique = 100 × clamp(g / S(n))              porte (gate) = clamp(dynamique / ${c ? c.gate_floor : 32})
régularité = 100 × clamp((R² − 0,5) / 0,45)
jours de hausse = 100 × clamp((part − 0,4) / 0,4)
concentration = 100 × clamp((0,60 − part de la meilleure séance dans la hausse) / 0,50)
volatilité = 100 × clamp((5 − vol) / 4)          drawdown = 100 × clamp((15 − repli) / 15)</div>
      <p>La « porte » amortit régularité et risque d'une période dont la dynamique est faible (sous ${c ? c.gate_floor : 32}/100) : on ne récompense pas la douceur d'une courbe plate. La dynamique elle-même n'est pas amortie.</p>
      <h2>Poids des durées</h2>
      <div class="formula">poids brut(n_p) = n_p^(1−κ) − n_{p−1}^(1−κ)      (n_0 = 1)       puis normalisation à 1
κ = ${c ? c.kappa : 0.7} (réglage commun fixé par l'administration)</div>
      <h2>Score simple</h2>
      <div class="formula">D = Σ_p w_p · dynamique_p / 100
Q = Σ_p w_p · fiab_p · R²_p / Σ_p w_p · fiab_p        fiab_p = min(1, n_p / ${c ? c.reliability_sessions : 21})
score simple = 100 × D × Q    (plafonné à 100)</div>
      <h2>Score complexe</h2>
      <div class="formula">pour chaque composante k (poids W_k normalisés sur celles disponibles) :
  s_k = Σ_p ŵ_p · porte_p · note_{k,p} / Σ_p ŵ_p        (porte = 1 pour la dynamique et l'accélération)
base = Σ_k W_k · s_k / 100 / Σ_k W_k                      (composantes absentes retirées)
score complexe = 100 × base × [1 − λ · (1 − porte de la durée la plus courte)]    λ = ancrage = ${c ? c.anchor : 0.5}</div>
      <p>Composantes <b>du titre</b> (une seule valeur) : liquidité, momentum, contexte de rebond. Les durées sans mesure sont retirées et les poids restants renormalisés ; le seuil de couverture (${c ? c.threshold : 0.75}) n'est qu'un indicateur de fiabilité et ne supprime aucune note.</p>
      <div class="hdemo" data-demo="sim"></div>
      ${H.warn('<p>Limites : les barèmes (saturation, bornes de volatilité et de repli) sont des choix, calibrés sur les titres observés ; ils ne sont pas des lois. Un score élevé décrit un profil de prix passé.</p>')}`; },
    mount: (el, { HM, HC, facts }) => {
      const d = el.querySelector('[data-demo=sim]'); if (!d) return;
      const base = Object.assign({}, HM.COMPLEX_DEFAULT), st = { cw: Object.assign({}, base), kappa: facts ? facts.common.kappa : 0.7, anchor: facts ? facts.common.anchor : 0.5, ids: ['week', 'month', 'quarter', 'half'] };
      const draw = () => {
        const ev = Object.entries(TITLES).map(([name, t]) => [name, HM.evaluate(t, st.ids, { cw: st.cw, kappa: st.kappa, anchor: st.anchor })]);
        const rk = HM.ranks(Object.fromEntries(ev.map(([n, e]) => [n, e.complex.score])));
        const w = ev[0][1].weights;
        d.querySelector('#sim-out').innerHTML = `<div class="sui-scroll"><table><thead><tr><th>Titre</th><th class="n">Simple</th><th class="n">Complexe</th><th class="n">Rang</th><th></th></tr></thead><tbody>${ev.slice().sort((a, b) => (rk[a[0]] || 99) - (rk[b[0]] || 99)).map(([n, e]) => `<tr><th scope="row"><span data-style="color:${COLORS[n]}">●</span> ${n}</th><td class="n">${e.simple.score == null ? '—' : f(e.simple.score, 0)}</td><td class="n"><b>${e.complex.score == null ? '—' : f(e.complex.score, 0)}</b></td><td class="n">${rk[n] || '—'}</td><td data-style="width:35%">${HC.bars([{ label: '', value: e.complex.score || 0, color: COLORS[n] }], { max: 100, fmt: () => '' })}</td></tr>`).join('')}</tbody></table></div>
        <p class="small muted">Poids des durées : ${st.ids.map(i => HM.LABELS[i] + ' ' + f(100 * w[i], 0) + ' %').join(' · ')}</p>`; };
      const tot = () => Object.values(st.cw).reduce((a, b) => a + b, 0) || 1;
      d.innerHTML = `<span class="fic">Titres fictifs · n’affecte pas vos réglages</span>
        <div class="two">${Object.keys(base).map(k => `<label class="small"><b>${COMP[k]}</b> : <span id="sv-${k}"></span><input type="range" min="0" max="100" value="${base[k]}" data-k="${k}" data-style="width:100%"></label>`).join('')}</div>
        <div class="ctl"><label>κ (poids des longues durées) : <b id="sv-kappa">${f(st.kappa, 2)}</b><input type="range" id="sim-kappa" min="0" max="95" value="${Math.round(st.kappa * 100)}"></label>
        <label>Ancrage récent : <b id="sv-anchor">${f(st.anchor, 2)}</b><input type="range" id="sim-anchor" min="0" max="100" value="${Math.round(st.anchor * 100)}"></label></div>
        <div class="ctl">${['week', 'month', 'quarter', 'half', 'year'].map(k => `<label data-style="display:flex;gap:4px;flex-direction:row;align-items:center"><input type="checkbox" data-id="${k}" ${st.ids.includes(k) ? 'checked' : ''}> ${HM.LABELS[k]}</label>`).join('')}<button class="btn sm" id="sim-reset">Réinitialiser</button></div>
        <div id="sim-out"></div>`;
      const labels = () => Object.keys(base).forEach(k => { d.querySelector('#sv-' + k).textContent = f(100 * st.cw[k] / tot(), 0) + ' %'; });
      d.querySelectorAll('input[data-k]').forEach(i => i.oninput = () => { st.cw[i.dataset.k] = +i.value; labels(); draw(); });
      d.querySelector('#sim-kappa').oninput = e => { st.kappa = e.target.value / 100; d.querySelector('#sv-kappa').textContent = f(st.kappa, 2); draw(); };
      d.querySelector('#sim-anchor').oninput = e => { st.anchor = e.target.value / 100; d.querySelector('#sv-anchor').textContent = f(st.anchor, 2); draw(); };
      d.querySelectorAll('input[data-id]').forEach(i => i.onchange = () => { const ids = [...d.querySelectorAll('input[data-id]:checked')].map(x => x.dataset.id); if (!ids.length) { i.checked = true; return; } st.ids = ids; draw(); });
      d.querySelector('#sim-reset').onclick = () => { st.cw = Object.assign({}, base); d.querySelectorAll('input[data-k]').forEach(i => { i.value = base[i.dataset.k]; }); st.kappa = facts ? facts.common.kappa : 0.7; st.anchor = facts ? facts.common.anchor : 0.5; d.querySelector('#sim-kappa').value = Math.round(st.kappa * 100); d.querySelector('#sim-anchor').value = Math.round(st.anchor * 100); d.querySelector('#sv-kappa').textContent = f(st.kappa, 2); d.querySelector('#sv-anchor').textContent = f(st.anchor, 2); labels(); draw(); };
      labels(); draw();
    }
  });

  L.push({
    id: 'classements', group: 'jigo', title: 'Les classements et les filtres', icon: I('list-checks'), color: '#9333ea', keywords: 'classement rang filtre tri ex æquo exclu retenu catégorie pays secteur',
    lead: 'Pourquoi le rang d’un titre ne change pas quand on filtre, et comment lire un classement.',
    beginner: ({ H }) => `
      <h2>Le rang</h2>
      <p>Le <b>rang</b> classe les titres de la stratégie du meilleur score (rang 1) au moins bon. Si deux titres ont exactement le même score, ils partagent le même rang.</p>
      <h2>Filtrer ne reclasse pas</h2>
      <p>Imaginez une course de 100 coureurs. Le coureur arrivé 12<sup>e</sup> reste 12<sup>e</sup> même si vous décidez de n’afficher que les athlètes de votre pays. Il apparaîtra peut-être en 3<sup>e</sup> ligne de votre liste, mais son <b>rang</b> reste 12. Essayez :</p>
      <div class="hdemo" data-demo="rank"></div>
      ${H.jigo('<p>C’est volontaire : le rang décrit la place du titre dans <i>toute</i> la stratégie, pas dans la liste que vous avez à l’écran. Cela permet de comparer ce que vous voyez à l’ensemble.</p>')}
      <h2>Trois choses à ne pas confondre</h2>
      ${H.table(['', 'Ce que c’est', 'Qui le décide'], [['Retenu / exclu', 'Le titre passe-t-il les critères ?', 'La stratégie (critères de recherche)'], ['Score et rang', 'Sa note et sa place dans la stratégie', 'Les paramètres de scores'], ['Affichage', 'Quelles lignes vous voyez, dans quel ordre', 'Vos filtres, votre tri']])}
      ${H.quiz('q-rank', [{ q: 'Je masque tous les titres sauf trois. Le meilleur des trois a le rang 7. Que signifie ce « 7 » ?', o: ['Il est 7e parmi tous les titres de la stratégie', 'Il est 7e parmi les trois affichés'], a: 0, why: 'Le rang est calculé avant les filtres d’affichage.' }])}`,
    expert: ({ H }) => `
      <h2>Règles</h2>
      <ul><li><b>Rang</b> = 1 + nombre de titres avec un score strictement supérieur (les ex æquo partagent le rang).</li>
      <li>Univers du classement : les titres notés de la stratégie ; les filtres de catégories (pays, secteur, place, type) et la recherche textuelle s'appliquent <b>après</b>.</li>
      <li>Un titre exclu par les critères peut avoir un score (il est noté dès que ses mesures existent) ; l'affichage du statut « exclu » est un verdict séparé.</li></ul>
      <div class="hdemo" data-demo="rank"></div>`,
    mount: (el, { HM }) => {
      const d = el.querySelector('[data-demo=rank]'); if (!d) return;
      const ev = Object.entries(TITLES).map(([n, t]) => [n, HM.evaluate(t, ['week', 'month', 'quarter', 'half']).complex.score]), rk = HM.ranks(Object.fromEntries(ev));
      const all = ev.slice().sort((a, b) => b[1] - a[1]); let hide = new Set();
      const draw = () => { const shown = all.filter(([n]) => !hide.has(n));
        d.innerHTML = `<span class="fic">Titres fictifs</span><div class="ctl">${all.map(([n]) => `<label data-style="flex-direction:row;display:flex;gap:4px;align-items:center"><input type="checkbox" data-n="${n}" ${hide.has(n) ? '' : 'checked'}> ${n}</label>`).join('')}</div>
        <div class="sui-scroll"><table><thead><tr><th class="n">Ligne affichée</th><th class="n">Rang (stratégie)</th><th>Titre</th><th class="n">Score complexe</th></tr></thead><tbody>${shown.map(([n, s], i) => `<tr><td class="n">${i + 1}</td><td class="n"><b>${rk[n]}</b></td><th scope="row">${n}</th><td class="n">${f(s, 0)}</td></tr>`).join('')}</tbody></table></div><p class="small muted">Décochez des titres : la colonne « Rang » ne bouge pas.</p>`;
        d.querySelectorAll('input[data-n]').forEach(i => i.onchange = () => { if (i.checked) hide.delete(i.dataset.n); else hide.add(i.dataset.n); draw(); }); };
      draw();
    }
  });

  L.push({
    id: 'indicateurs', group: 'jigo', title: 'Les indicateurs du tableau', icon: I('activity'), color: '#0891b2', keywords: 'indicateurs colonnes var 1j tendance volatilité repli r2 pente liquidité couverture',
    lead: 'Le sens de chaque colonne que vous pouvez afficher.',
    beginner: ({ H }) => `
      <p>Chacune de ces colonnes se calcule sur une durée (jour, semaine, mois, trimestre, semestre, année). Les chapitres précédents expliquent chaque notion ; voici un mémo.</p>
      ${H.table(['Indicateur', 'En une phrase', 'Chapitre'], [['Variation / performance', 'De combien le prix a changé entre le début et la fin de la durée.', '<a href="#/performance">La performance</a>'], ['Pente', 'Vitesse moyenne de hausse, par séance.', '<a href="#/pente-regularite">Pente et régularité</a>'], ['Régularité (R²)', 'À quel point la courbe est droite.', '<a href="#/pente-regularite">Pente et régularité</a>'], ['Volatilité', 'Taille des secousses quotidiennes.', '<a href="#/risque">Volatilité et repli</a>'], ['Repli (drawdown)', 'Pire chute depuis un sommet.', '<a href="#/risque">Volatilité et repli</a>'], ['Liquidité', 'Facilité à acheter et revendre.', '<a href="#/volume">Volume et liquidité</a>'], ['Momentum', 'Élan sur 6 ou 12 mois hors dernier mois.', '<a href="#/momentum">Le momentum</a>'], ['Tendance (mini-courbe)', 'Aperçu des derniers prix.', '<a href="#/lire-graphique">Lire un graphique</a>']])}
      ${H.tip('<p>Une cellule vide (« — ») ne signifie pas zéro : elle veut dire « pas assez de données pour calculer ». Voir « Fiabilité ».</p>')}`,
    expert: ({ H }) => `<p>Mesures par durée issues de <code>engine/analytics/series/measures.py</code> : perf, pente (%/séance), R², volatilité (%/séance), repli maximal (%), part de séances en hausse, poids de la meilleure séance dans la hausse (concentration). Voir les chapitres correspondants pour les formules et unités. Les colonnes de variation « 1J » et la granularité Jour utilisent seulement la dernière variation de clôture.</p>`
  });

  L.push({
    id: 'fiches', group: 'jigo', title: 'La fiche d’un titre', icon: I('file-chart-line'), color: '#2563eb', keywords: 'fiche titre etf investit points à surveiller graphique',
    lead: 'Cliquez sur un titre : sa fiche réunit tout ce qu’il faut pour juger.',
    beginner: ({ H }) => `
      <h2>Ce que contient une fiche</h2>
      ${H.cards([{ icon: I('chart-line'), bg: '#dbeafe', title: 'Le graphique', text: 'La courbe des prix sur plusieurs périodes, avec sa droite de tendance.' }, { icon: I('gauge'), bg: '#dcfce7', title: 'Les scores', text: 'Score simple et complexe, avec le détail : quelles matières tirent la note vers le haut ou le bas.' }, { icon: I('list-checks'), bg: '#ffedd5', title: 'Les verdicts', text: 'Retenu, exclu ou indéterminé pour chaque stratégie, avec la raison.' }, { icon: I('landmark'), bg: '#f3e8ff', title: 'Pour un ETF', text: 'Dans quoi il investit et les points à surveiller.' }])}
      <p>Utilisez la fiche pour comprendre <b>pourquoi</b> un titre est bien ou mal noté : regardez la matière la plus faible, et retournez au graphique pour voir si cela se voit dans la courbe.</p>
      ${H.warn('<p>Une fiche résume des données passées. Elle ne remplace pas une recherche sur l’entreprise ou le fonds.</p>')}`,
    expert: ({ H }) => `<p>La fiche présente les mesures par durée, la décomposition du score (contribution de chaque composante au score complexe), les verdicts par stratégie et, pour les ETF, une fiche automatique issue des données publiques (composition, frais). Les éléments manquants sont signalés plutôt que remplacés par une valeur par défaut.</p>`
  });

  L.push({
    id: 'adapter', group: 'jigo', title: 'Adapter une stratégie à ma façon', icon: I('sliders-horizontal'), color: '#f97316', keywords: 'adapter personnaliser mes stratégies paramètres scores critères restaurer personnelle blou voir plus de titres granularité de plus',
    lead: 'Pas assez de résultats ? Trop ? Notes décevantes ? Voici quoi toucher, dans quel ordre.',
    beginner: ({ H }) => `
      <h2>Si… alors…</h2>
      ${H.table(['Si…', 'Alors…', 'Où'], [['La liste est trop courte', 'Baissez le niveau de pente ou de régularité demandé, ou retirez une durée.', 'Mes critères de recherche'], ['La liste est trop longue', 'Montez les niveaux, ou ajoutez une durée.', 'Mes critères de recherche'], ['Je veux voir une durée de plus', 'Activez-la : elle ajoute une condition, donc moins de titres, mais plus solides.', 'Mes critères + Mes paramètres de scores'], ['Les scores ne me plaisent pas', 'Changez les poids (plus de poids au calme, ou à la hausse…).', 'Mes paramètres de scores'], ['Je veux autre chose', 'Créez une stratégie personnelle.', 'Mes stratégies'], ['J’ai tout cassé', 'Restaurez les valeurs officielles en un clic.', 'Mes stratégies']])}
      ${H.jigo('<p>Une stratégie que vous modifiez devient <b>Adaptée</b>. Si vous revenez exactement aux valeurs officielles, elle redevient <b>Officielle</b> automatiquement. Les modifications non enregistrées ne changent rien.</p>')}
      ${H.tip('<p>Avant de modifier, utilisez les simulateurs de cette aide pour sentir l’effet d’un réglage.</p>')}`,
    expert: ({ H }) => `<ul><li>Critères et scores sont deux profils distincts ; chacun a son bouton de restauration.</li><li>Les réglages communs (κ, seuil de couverture, ancrage) sont fixés par l'administration et en lecture seule côté utilisateur.</li><li>Les stratégies personnelles sont privées et ne modifient jamais les références officielles.</li></ul>`
  });

  L.push({
    id: 'parcours', group: 'jigo', title: 'Parcours : de la recherche à la décision', icon: I('route'), color: '#16a34a', keywords: 'parcours guidé étapes décision chercher filtrer voir plus',
    lead: 'Un exemple complet, étape par étape, avec les questions qu’on se pose.',
    beginner: ({ H }) => `
      ${H.steps([['Je choisis une stratégie', '<p>Je veux ce qui monte vite ? <a href="#/strat-fast">Croissance rapide</a>. Du solide ? <a href="#/strat-regular">Croissance régulière</a>. Du calme ? <a href="#/strat-calm">Hausse calme</a>.</p>'], ['Je lis les résultats', '<p>Je regarde les titres du haut de la liste (meilleurs scores), leur secteur, leur mini-courbe.</p>'], ['Je filtre', '<p>Je ne veux que des ETF ? Que la France ? J’utilise les filtres. Les rangs ne changent pas.</p>'], ['J’ouvre une fiche', '<p>Je regarde le graphique, la décomposition du score, le verdict.</p>'], ['Je compare', '<p>Je mets deux ou trois titres côte à côte : régularité, risque, liquidité.</p>'], ['Je décide', '<p>Seul vous décidez. Jigobourso a fait le tri ; il ne connaît ni votre budget, ni votre horizon, ni votre tolérance au risque.</p>']])}
      ${H.warn('<p>Si les résultats ne vous plaisent pas : consultez « Adapter une stratégie » pour savoir quoi modifier.</p>')}
      ${H.cards([{ icon: I('sliders-horizontal'), bg: '#ffedd5', title: 'Adapter une stratégie', text: 'Trop ou pas assez de résultats ?', href: 'adapter' }, { icon: I('gauge'), bg: '#dcfce7', title: 'Comprendre les scores', text: 'Pourquoi cette note ?', href: 'scores' }])}`,
    expert: null
  });
})();
