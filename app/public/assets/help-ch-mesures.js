/* Chapitres : lire un cours de bourse (performance, pente, régularité, risque, durées, momentum). Séries fictives calculées dans le navigateur. */
(function () {
  const I = n => J.icon(n), L = (window.HELP_CHAPTERS = window.HELP_CHAPTERS || []);
  const f = (v, d = 1) => HC.f1(v, d), pc = (v, d = 1) => (v > 0 ? '+' : '') + f(v, d) + ' %';

  L.push({
    id: 'performance', group: 'mesures', title: 'La performance : de combien ça a monté ?', icon: I('trending-up'), color: '#16a34a', keywords: 'performance rendement variation gain pourcentage hausse période',
    lead: 'La mesure la plus simple : le prix d’arrivée comparé au prix de départ. Utile, mais très incomplète.',
    beginner: ({ H }) => `
      <h2>Une seule question</h2>
      <p>La <b>performance</b> répond à : « entre le début et la fin de la période, de combien le prix a-t-il changé ? » On ne regarde que deux prix : le premier et le dernier.</p>
      <div class="hdemo" data-demo="perf"></div>
      ${H.tip('<p>Performance = (prix de fin ÷ prix de début) − 1. Elle ne dit <b>rien</b> du chemin parcouru entre les deux.</p>', 'La formule')}
      <h2>Pourquoi ce n’est pas suffisant</h2>
      <p>Deux titres peuvent finir exactement au même prix, l’un en montant tranquillement, l’autre en faisant des montagnes russes. La performance les met à égalité. Pourtant, vivre l’un ou l’autre n’est pas la même chose. C’est le sujet du chapitre suivant.</p>
      ${H.quiz('q-perf', [{ q: 'Un titre passe de 80 € à 100 €. Sa performance est…', o: ['+20 %', '+25 %', '+80 %'], a: 1, why: '100 ÷ 80 − 1 = 0,25, soit +25 %. Les 20 € d’écart représentent 25 % du prix de départ.' }, { q: 'Deux titres ont la même performance. Ont-ils eu le même parcours ?', o: ['Oui, forcément', 'Non, pas forcément'], a: 1, why: 'La performance ne regarde que le début et la fin.' }])}`,
    expert: ({ H }) => `
      <h2>Définitions</h2>
      <div class="formula">perf = 100 × (c_n / c_0 − 1)        (fenêtre de n séances, n + 1 clôtures)
croissance sur n séances = 100 × ((1 + pente/100)^n − 1)   [croissance lissée, voir « Pente »]</div>
      <p>Le moteur calcule la <b>performance brute</b> (<code>perf</code>) mais note la <b>croissance lissée</b> issue de la pente (régression), moins sensible aux deux extrémités.</p>
      ${H.example('<p>Cours 100 → 120 sur 63 séances : perf = +20 %. Par construction, perf = <code>exp(ln c<sub>n</sub> − ln c<sub>0</sub>) − 1</code>.</p>')}
      ${H.warn('<p>Limite : la performance brute dépend des deux clôtures extrêmes ; une journée atypique au début ou à la fin la déplace fortement.</p>')}`,
    mount: (el, { HC }) => {
      const d = el.querySelector('[data-demo=perf]'); if (!d) return;
      d.innerHTML = `<span class="fic">Exemple fictif · manipulez-le</span><div class="ctl"><label>Prix de début : <b id="a"></b><input id="ra" type="range" min="20" max="200" value="100"></label><label>Prix de fin : <b id="b"></b><input id="rb" type="range" min="20" max="200" value="125"></label></div><div id="out"></div>`;
      const run = () => { const a = +el.querySelector('#ra').value, b = +el.querySelector('#rb').value, p = 100 * (b / a - 1); el.querySelector('#a').textContent = a + ' €'; el.querySelector('#b').textContent = b + ' €';
        el.querySelector('#out').innerHTML = `<div class="big ${p >= 0 ? 'good' : 'bad'}">${pc(p)}</div><p>${b} ÷ ${a} − 1 = ${f(b / a - 1, 3)} → ${pc(p)}</p>` + HC.bars([{ label: 'Début', value: a, color: '#94a3b8' }, { label: 'Fin', value: b, color: p >= 0 ? '#16a34a' : '#e11d48' }], { max: 200, fmt: v => v + ' €' }); };
      el.querySelector('#ra').oninput = run; el.querySelector('#rb').oninput = run; run();
    }
  });

  /* ───── DÉMO OBLIGATOIRE : deux titres, même performance, pente et régularité différentes ───── */
  L.push({
    id: 'pente-regularite', group: 'mesures', title: 'Tendance, pente et régularité', icon: I('chart-line'), color: '#2563eb', keywords: 'pente régularité r2 r² tendance régression droite titre régulier oscillation même performance',
    lead: 'Deux titres finissent au même prix. Pourquoi Jigobourso ne les juge-t-il pas pareil ? Suivez la démonstration étape par étape.',
    beginner: ({ H }) => `
      <h2>Deux titres, un même résultat</h2>
      <p>Voici deux titres <b>inventés</b>, Aurore et Brumel. Sur 63 séances (environ trois mois) ils gagnent <b>exactement la même chose</b>. Pourtant, ils ne se comportent pas du tout pareil.</p>
      <div class="hdemo" data-demo="pr"></div>
      <h2>Ce qu’il faut retenir</h2>
      ${H.cards([{ icon: I('arrow-up-right'), bg: '#dbeafe', title: 'Performance', text: 'Écart entre le premier et le dernier prix. Identique pour Aurore et Brumel.' }, { icon: I('trending-up'), bg: '#dcfce7', title: 'Tendance et pente', text: 'La direction de la courbe et sa vitesse moyenne de montée, jour après jour.' }, { icon: I('ruler'), bg: '#ffedd5', title: 'Régularité (R²)', text: 'À quel point la courbe colle à une droite. 1 = très droite, proche de 0 = n’importe quoi.' }])}
      ${H.jigo('<p>Jigobourso ne se contente pas de la performance. Il mesure la <b>pente</b> et la <b>régularité</b> sur plusieurs durées. Un titre qui monte droit passe plus facilement les critères « régulier » (Croissance régulière, Hausse calme) qu’un titre qui oscille fortement, même avec la même performance.</p>')}
      ${H.quiz('q-pente', [{ q: 'Aurore et Brumel ont la même performance. Qu’est-ce qui les distingue le plus ?', o: ['Leur prix de départ', 'La régularité de leur montée', 'Leur nom'], a: 1, why: 'Même début, même fin : la différence est dans le chemin, que mesure la régularité (R²).' }, { q: 'Un R² proche de 1 signifie…', o: ['La courbe est presque une droite', 'Le titre va monter demain', 'Le titre est très volatil'], a: 0, why: 'R² décrit l’alignement sur la droite de tendance, pas l’avenir.' }])}`,
    expert: ({ H }) => `
      <h2>Régression sur le logarithme du cours</h2>
      <p>Sur une fenêtre de <i>n</i> séances (<i>n</i> + 1 clôtures <i>c<sub>t</sub></i>), le moteur ajuste par moindres carrés la droite <code>ln c<sub>t</sub> = a + b·t</code>.</p>
      <div class="formula">b = Σ (t − t̄)(y_t − ȳ) / Σ (t − t̄)²          avec y_t = ln c_t, t = 0…n
pente (%/séance) = 100 × (e^b − 1)
R² = Sxy² / (Sxx · Syy)      (1 si Syy = 0)</div>
      <p><b>Unités</b> : la pente est un pourcentage composé <b>par séance</b>. Une pente de 0,29 %/séance correspond à environ +20 % sur 63 séances : <code>(1 + 0,0029)^63 − 1</code>. Le R² est sans unité, entre 0 et 1.</p>
      <p><b>Pourquoi les logarithmes</b> : une croissance régulière de x % par jour devient une droite parfaite (R² = 1), quel que soit le niveau de prix.</p>
      <div class="hdemo" data-demo="pr"></div>
      ${H.fold('Calcul détaillé à la main (idée)', '<p>Sxx = Σ(t − t̄)² = n(n+1)(n+2)/12 pour t = 0…n. Pour Aurore (courbe exponentielle parfaite), les y<sub>t</sub> sont alignés : Sxy² = Sxx·Syy donc R² = 1 exactement. Pour Brumel, y<sub>t</sub> = b₀t + A·sin(2π·3t/n) : la partie sinusoïdale s’ajoute à Syy sans contribuer à Sxy, ce qui abaisse R².</p>')}
      ${H.warn('<p>Limites statistiques : R² décrit un ajustement linéaire, pas une probabilité. Sur des fenêtres courtes (&lt; 21 séances) il est bruité : le moteur le pondère par min(1, n/21). Les clôtures successives ne sont pas indépendantes, donc les intervalles de confiance usuels ne s’appliquent pas.</p>')}
      <p>Barèmes de notation : voir « Scores ». Seuils de critères : voir « Critères de recherche ».</p>`,
    mount: (el, { HM, HC, H }) => {
      const d = el.querySelector('[data-demo=pr]'); if (!d) return;
      const N = 63, TOT = 20; let step = 1, amp = 0.08;
      const A = HM.series(N, TOT, 0, 0, 100, 0.0015, 2);
      const draw = () => {
        const B = HM.series(N, TOT, amp, 3, 100, 0, 1), mA = HM.metrics(A), mB = HM.metrics(B);
        const titles = [['Aurore', A, mA, '#2563eb'], ['Brumel', B, mB, '#f97316']];
        const chart = (name, s, m, c) => HC.line({ series: [{ name, values: s, color: c }], w: 420, h: 230, alt: 'Courbe de ' + name, line: step >= 2 ? { a: m.intercept, b: m.slope_log, from: 0, to: N, label: step >= 3 ? 'pente ' + f(m.slope, 2) + ' %/séance' : '' } : null, residuals: step >= 4 ? { values: s, a: m.intercept, b: m.slope_log } : null, marks: step === 1 ? [{ x: 0, y: s[0], label: f(s[0], 0) + ' €' }, { x: N, y: s[N], label: f(s[N], 0) + ' €' }] : [] });
        const row = (label, k, fn) => `<tr><th scope="row">${label}</th>${titles.map(t => `<td class="n">${fn(t[2])}</td>`).join('')}</tr>`;
        const stepsTxt = [
          ['1. La performance', `Même départ (100 €), même arrivée (${f(A[N], 1)} €) : les deux gagnent <b>${pc(mA.perf)}</b>. À ce stade, rien ne les distingue.`],
          ['2. La tendance', 'On trace la <b>droite qui résume le mieux</b> chaque courbe (la droite de tendance, pointillés). Les deux montent en moyenne : la tendance est haussière pour les deux.'],
          ['3. La pente', `La pente est la <b>vitesse moyenne de montée</b> par séance. Aurore : <b>${f(mA.slope, 3)} %</b> par jour de bourse. Brumel : <b>${f(mB.slope, 3)} %</b>. ${Math.abs(mA.slope - mB.slope) < 0.005 ? 'Les deux pentes sont identiques.' : 'La pente de Brumel est plus faible : ses oscillations « penchent » la droite qui le résume.'} Mais la pente seule ne dit pas si la courbe est fiable ou chaotique : il faut mesurer l’écart à la droite.`],
          ['4. La régularité', `Les traits rouges sont les <b>écarts</b> entre la courbe et sa droite. Aurore colle à sa droite : <b>R² = ${f(mA.r2, 2)}</b>. Brumel s’en écarte tout le temps : <b>R² = ${f(mB.r2, 2)}</b>. La régularité est la mesure qui les sépare.`],
          ['5. Pourquoi Jigobourso les juge différemment', `Une courbe régulière est plus <b>lisible et plus fiable</b> : la hausse ne dépend pas d’un seul bon moment. Dans Jigobourso, Aurore passerait un critère comme « régularité ≥ 0,80 » (R² ${f(mA.r2, 2)}), Brumel pas (R² ${f(mB.r2, 2)}). Les scores prennent aussi en compte les écarts : volatilité ${f(mA.volatility, 2)} % contre ${f(mB.volatility, 2)} %, repli maximal ${f(mA.drawdown, 1)} % contre ${f(mB.drawdown, 1)} %.`]];
        body.innerHTML = `<div class="ctl" role="group" aria-label="Étapes">${stepsTxt.map((s, i) => `<button class="btn sm ${step === i + 1 ? 'primary' : ''}" data-step="${i + 1}">Étape ${i + 1}</button>`).join('')}</div>
          <div class="two">${titles.map(t => `<div><b data-style="color:${t[3]}">${t[0]}</b>${chart(t[0], t[1], t[2], t[3])}</div>`).join('')}</div>
          <h3 class="mt-2">${stepsTxt[step - 1][0]}</h3><p>${stepsTxt[step - 1][1]}</p>
          <div class="h-table-scroll"><table><thead><tr><th></th><th class="n">Aurore</th><th class="n">Brumel</th></tr></thead><tbody>
          ${row('Performance', 0, m => pc(m.perf))}${step >= 3 ? row('Pente (%/séance)', 0, m => f(m.slope, 3)) : ''}${step >= 4 ? row('Régularité R²', 0, m => f(m.r2, 2)) : ''}${step >= 5 ? row('Volatilité (%/séance)', 0, m => f(m.volatility, 2)) + row('Repli maximal', 0, m => f(m.drawdown, 1) + ' %') : ''}</tbody></table></div>
          <div class="ctl"><button class="btn" data-step="${Math.max(1, step - 1)}" ${step === 1 ? 'disabled' : ''}>← Étape précédente</button><button class="btn primary" data-step="${Math.min(5, step + 1)}" ${step === 5 ? 'disabled' : ''}>Étape suivante →</button></div>`;
        body.querySelectorAll('[data-step]').forEach(b => b.onclick = () => { step = +b.dataset.step; draw(); });
      };
      d.innerHTML = `<span class="fic">Titres fictifs · données inventées</span><div class="ctl"><label>Nervosité de Brumel (amplitude des oscillations) : <b id="pr-v">${f(amp * 100, 0)} %</b><input type="range" min="0" max="15" value="${Math.round(amp * 100)}" id="pr-amp"></label><span class="small muted">Mettez 0 : Brumel devient aussi régulier qu’Aurore.</span></div><div id="pr-body"></div>`;
      const body = d.querySelector('#pr-body');
      d.querySelector('#pr-amp').oninput = e => { amp = e.target.value / 100; d.querySelector('#pr-v').textContent = f(amp * 100, 0) + ' %'; draw(); };
      draw();
    }
  });

  L.push({
    id: 'risque', group: 'mesures', title: 'Volatilité et repli (drawdown)', icon: I('activity'), color: '#e11d48', keywords: 'volatilité drawdown repli risque nervosité perte maximale sommet creux',
    lead: 'Deux façons de mesurer le « mal de mer » d’un titre : la nervosité de tous les jours, et la pire chute depuis un sommet.',
    beginner: ({ H }) => `
      <h2>La volatilité : à quel point ça secoue</h2>
      <p>Imaginez deux routes qui vont toutes deux de Paris à Lyon. L’une est une autoroute droite ; l’autre, une route de montagne pleine de virages. L’arrivée est la même, mais le trajet n’a rien à voir. La <b>volatilité</b> mesure la taille moyenne des secousses d’un jour à l’autre.</p>
      <p>Elle s’exprime en % par séance. Un titre qui bouge souvent de ±3 % est plus volatil qu’un titre qui bouge de ±0,5 %.</p>
      <h2>Le repli (drawdown) : la pire chute depuis un sommet</h2>
      <p>À un moment, le titre atteint un plus haut. Ensuite il redescend, puis remonte. La plus grosse descente depuis un sommet, c’est le <b>repli maximal</b>. Il dit : « à un moment, quelqu’un qui aurait acheté au sommet aurait vu fondre X % ».</p>
      <div class="hdemo" data-demo="risk"></div>
      ${H.jigo('<p>Ces deux mesures nourrissent le score complexe. Plus la volatilité et le repli sont faibles, meilleure est leur note. Les stratégies « calmes » leur donnent plus de poids.</p>')}
      ${H.quiz('q-risque', [{ q: 'Un titre monte de 100 à 130, retombe à 104, puis remonte à 140. Quel est son repli maximal ?', o: ['20 %', '26 %', '0 %'], a: 0, why: 'Du sommet 130 au creux 104 : 104 ÷ 130 − 1 = −20 %. Le repli maximal est de 20 %.' }])}`,
    expert: ({ H }) => `
      <h2>Formules</h2>
      <div class="formula">r_t = ln(c_t / c_{t−1})        (t = 1…n)
volatilité = 100 × écart-type empirique de r_t   (dénominateur n − 1, n ≥ 3)
repli maximal = 100 × max_t (1 − c_t / max_{s ≤ t} c_s)</div>
      <p>La volatilité est <b>par séance</b>, non annualisée. Le repli est calculé sur les clôtures de la fenêtre.</p>
      <h3>Notes (0–100)</h3>
      <div class="formula">volatilité (mode absolu) = 100 × clamp((5 − vol) / 4)       1 %/séance → 100, 5 % → 0
volatilité (mode relatif) = 100 × clamp((4 − vol/max(pente, 0,3)) / 3)   rapport 1 → 100, 4 → 0
drawdown = 100 × clamp((15 − repli) / 15)                  0 % → 100, 15 % → 0</div>
      <div class="hdemo" data-demo="risk"></div>
      ${H.warn('<p>Limites : la volatilité suppose des rendements quotidiens de même ordre ; une seule journée extrême la gonfle. Le repli ne voit que la fenêtre analysée, pas les creux plus anciens. Aucune de ces mesures ne prédit une chute future.</p>')}`,
    mount: (el, { HM, HC }) => {
      const d = el.querySelector('[data-demo=risk]'); if (!d) return;
      const s = HM.path([[0, 100], [20, 130], [34, 104], [63, 140]], 0.004, 5), m = HM.metrics(s);
      let pk = 0, trough = 0, worst = 0, ps = 0; s.forEach((c, i) => { if (c > s[ps]) ps = i; const dd = 1 - c / s[ps]; if (dd > worst) { worst = dd; pk = ps; trough = i; } });
      d.innerHTML = `<span class="fic">Titre fictif</span>${HC.line({ series: [{ name: 'Titre', values: s }], highlight: { from: pk, to: trough, label: 'repli maximal ' + f(100 * worst, 1) + ' %', color: '#e11d48' }, marks: [{ x: pk, y: s[pk], label: 'sommet' }, { x: trough, y: s[trough], label: 'creux' }], alt: 'Repli maximal' })}
      <div class="two"><div class="kpi"><small>Volatilité</small><b>${f(m.volatility, 2)} % par séance</b></div><div class="kpi"><small>Repli maximal</small><b>${f(m.drawdown, 1)} %</b></div><div class="kpi"><small>Note de volatilité</small><b>${f(100 * HM.clamp((5 - m.volatility) / 4), 0)} / 100</b></div><div class="kpi"><small>Note de repli</small><b>${f(100 * HM.clamp((15 - m.drawdown) / 15), 0)} / 100</b></div></div>`;
    }
  });

  L.push({
    id: 'granularites', group: 'mesures', title: 'Les durées d’analyse (granularités)', icon: I('calendar-days'), color: '#0891b2', keywords: 'granularité durée jour semaine mois trimestre semestre année fenêtre séances',
    lead: 'Un même titre ressemble à un champion sur un mois et à un perdant sur un an. Jigobourso le regarde sous plusieurs durées.',
    beginner: ({ H }) => `
      <h2>Zoomer ou dézoomer</h2>
      <p>On peut regarder un titre « de près » (la dernière semaine) ou « de loin » (la dernière année). Chaque durée s’appelle une <b>granularité</b>. Jigobourso en connaît six :</p>
      ${H.table(['Nom', 'Séances', 'À peu près'], [['Jour', '1', 'la dernière séance'], ['Semaine', '5', 'une semaine'], ['Mois', '21', 'un mois'], ['Trimestre', '63', 'trois mois'], ['Semestre', '126', 'six mois'], ['Année', '252', 'un an']])}
      <p>Essayez : changez la durée et voyez comment le même titre (fictif) change de visage.</p>
      <div class="hdemo" data-demo="gran"></div>
      <h2>Pourquoi en regarder plusieurs ?</h2>
      <ul><li>Une durée <b>courte</b> montre ce qui se passe maintenant, mais elle est nerveuse et trompeuse.</li><li>Une durée <b>longue</b> est plus stable, mais elle réagit lentement.</li><li>Les <b>combiner</b> évite d’être fasciné par un coup de chance d’une semaine ou par un vieux succès déjà fini.</li></ul>
      ${H.jigo('<p>Chaque stratégie choisit ses durées. Vous pouvez en ajouter ou en retirer dans <b>Mes critères de recherche</b> et <b>Mes paramètres de scores</b>. « Si j’ai envie de voir une durée de plus », c’est là.</p>')}
      ${H.quiz('q-gran', [{ q: 'Combien de séances dans la granularité « Mois » ?', o: ['21', '30', '5'], a: 0, why: 'Un mois de bourse compte environ 21 séances (on ne compte pas les week-ends).' }])}`,
    expert: ({ H, facts }) => `
      <h2>Fenêtres</h2>
      <p>Une durée de <i>n</i> séances utilise les <i>n</i> + 1 dernières clôtures. Correspondance : ${facts ? Object.entries(facts.common.periods).map(([k, v]) => `${v.label} = ${v.sessions}`).join(', ') : 'jour 1, semaine 5, mois 21, trimestre 63, semestre 126, année 252'}.</p>
      <ul><li><b>Minimum</b> : ${facts ? facts.common.min_sessions : 3} séances pour R² et volatilité ; la granularité Jour (1 séance) n’a ni R², ni volatilité, ni repli, ni accélération.</li>
      <li><b>Poids automatiques</b> (voir « Scores ») : chaque durée compte pour l’anneau de séances qu’elle ajoute, avec un exposant κ&nbsp;= ${facts ? facts.common.kappa : 0.7} qui allège les longues fenêtres.</li>
      <li><b>Fiabilité du R²</b> : poids min(1, n/${facts ? facts.common.reliability_sessions : 21}).</li></ul>
      <div class="hdemo" data-demo="gran"></div>`,
    mount: (el, { HM, HC }) => {
      const d = el.querySelector('[data-demo=gran]'); if (!d) return;
      const s = HM.path([[0, 100], [130, 128], [200, 104], [252, 118]], 0.012, 7), N = s.length - 1; let k = 'month';
      const draw = () => { const n = HM.SESSIONS[k], m = n >= 3 ? HM.windowOf(s, n) : { perf: 100 * (s[N] / s[N - 1] - 1) }, from = N - n;
        const line = n >= 3 ? { a: m.intercept, b: m.slope_log, from, to: N } : null;
        d.innerHTML = `<span class="fic">Titre fictif sur 252 séances</span><div class="ctl">${Object.keys(HM.SESSIONS).map(x => `<button class="btn sm ${x === k ? 'primary' : ''}" data-k="${x}">${HM.LABELS[x]}</button>`).join('')}</div>
        ${HC.line({ series: [{ name: 'Titre', values: s }], highlight: { from, to: N, label: HM.LABELS[k] + ' (' + n + ' séance' + (n > 1 ? 's' : '') + ')' }, line, alt: 'Fenêtre ' + HM.LABELS[k] })}
        <div class="two"><div class="kpi"><small>Performance sur la fenêtre</small><b class="${m.perf >= 0 ? 'good' : 'bad'}">${pc(m.perf)}</b></div>${n >= 3 ? `<div class="kpi"><small>Pente · R²</small><b>${f(m.slope, 3)} %/séance · ${f(m.r2, 2)}</b></div>` : '<div class="kpi"><small>Pente · R²</small><b>non calculés sur 1 séance</b></div>'}</div>`;
        d.querySelectorAll('[data-k]').forEach(b => b.onclick = () => { k = b.dataset.k; draw(); }); };
      draw();
    }
  });

  L.push({
    id: 'momentum', group: 'mesures', title: 'Le momentum : l’élan', icon: I('zap'), color: '#f59e0b', keywords: 'momentum élan 6 mois 12 mois dernier mois saut vitesse',
    lead: 'Idée : ce qui a bien monté ces derniers mois a tendance à continuer un peu. Mais ce n’est pas une garantie.',
    beginner: ({ H }) => `
      <h2>Une balle lancée</h2>
      <p>Une balle lancée vers le haut continue de monter un moment avant de retomber. En bourse, on appelle <b>momentum</b> l’« élan » d’un titre qui a déjà beaucoup monté. Les chercheurs ont observé que, en moyenne, ces titres continuent parfois à surperformer à court terme. <b>Parfois</b>. Ce n’est pas une loi.</p>
      <h2>Le dernier mois est mis de côté</h2>
      <p>Jigobourso mesure la hausse sur 6 mois ou 12 mois <b>en ignorant le dernier mois</b>. Pourquoi ? Parce que juste après une grosse hausse, les titres ont l’habitude de reprendre un peu leur souffle. On laisse ce dernier mois de côté pour ne pas se laisser tromper.</p>
      <div class="hdemo" data-demo="mom"></div>
      ${H.warn('<p>Un titre à fort momentum peut aussi s’effondrer d’un coup quand la mode passe. C’est un des risques de faux signal.</p>')}
      ${H.quiz('q-mom', [{ q: 'Dans le momentum 6 mois de Jigobourso, quelle période est mise de côté ?', o: ['Le premier mois', 'Le dernier mois', 'Aucune'], a: 1, why: 'On mesure de J−126 à J−21 : le dernier mois est écarté.' }])}`,
    expert: ({ H, facts }) => { const m = facts && facts.common.momentum; return `
      <h2>Définition</h2>
      <div class="formula">momentum 6 m  = 100 × (c_{J−21} / c_{J−126} − 1)
momentum 12 m = 100 × (c_{J−21} / c_{J−252} − 1)
note = 100 × clamp(momentum / saturation)      saturation : 6 m → ${m ? m.saturation['6m'] : 60} %, 12 m → ${m ? m.saturation['12m'] : 100} %
momentum négatif → note 0 ; horizon « mixte » = moyenne des deux notes</div>
      <p>Le momentum est une <b>composante du titre</b> (une seule valeur, pas par durée) du score complexe. Poids 0 par défaut, activé par les stratégies Momentum.</p>
      <div class="hdemo" data-demo="mom"></div>
      ${H.warn('<p>Limites : fenêtre longue (126 ou 252 séances) exigeant un historique suffisant, sinon la composante est absente ; sensible aux retournements brutaux de marché (momentum crashes).</p>')}`; },
    mount: (el, { HM, HC }) => {
      const d = el.querySelector('[data-demo=mom]'); if (!d) return;
      const s = HM.path([[0, 100], [105, 140], [126, 150]], 0.006, 9), N = 126;
      d.innerHTML = `<span class="fic">Titre fictif sur 127 clôtures</span>${HC.line({ series: [{ name: 'Titre', values: s }], highlight: { from: N - 21, to: N, label: 'dernier mois ignoré', color: '#94a3b8' }, marks: [{ x: 0, y: s[0], label: 'J−126' }, { x: N - 21, y: s[N - 21], label: 'J−21' }], alt: 'Momentum' })}
      <p>Momentum 6 mois = ${f(s[N - 21], 1)} ÷ ${f(s[0], 1)} − 1 = <b>${pc(100 * (s[N - 21] / s[0] - 1))}</b> → note ${f(100 * HM.clamp(100 * (s[N - 21] / s[0] - 1) / 60), 0)} / 100 (saturation 60 %). Performance totale : ${pc(100 * (s[N] / s[0] - 1))}.</p>`;
    }
  });
})();
