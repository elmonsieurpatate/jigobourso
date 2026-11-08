/* Chapitres : portefeuille. Méthodes réellement utilisées : prix de revient moyen pondéré (ledger.php) pour gains ; FIFO pour lots/alertes (transactions.php) ; Modified Dietz quotidien chaîné pour la performance hors apports (performance.py). Données fictives. */
(function () {
  const I = n => J.icon(n), L = (window.HELP_CHAPTERS = window.HELP_CHAPTERS || []);
  const f = (v, d = 2) => HC.f1(v, d), eur = v => f(v, 2) + ' €', pc = (v, d = 1) => (v > 0 ? '+' : '') + f(v, d) + ' %';

  L.push({
    id: 'portefeuille', group: 'patrimoine', title: 'Le portefeuille : à quoi ça sert', icon: I('wallet'), color: '#9333ea', keywords: 'portefeuille position transaction achat vente valeur',
    lead: 'Votre cahier de comptes de bourse : ce que vous détenez, ce que ça a coûté, ce que ça vaut.',
    beginner: ({ H }) => `
      <h2>Un cahier de comptes</h2>
      <p>Le portefeuille de Jigobourso ne passe aucun ordre. Il note ce que <b>vous</b> avez acheté et vendu, puis calcule pour vous : ce que vous détenez, combien ça vous a coûté, ce que ça vaut aujourd’hui.</p>
      ${H.cards([{ icon: I('banknote'), bg: '#dbeafe', title: 'Une transaction', text: 'Un achat ou une vente : date, titre, quantité, prix, frais.' }, { icon: I('layers'), bg: '#dcfce7', title: 'Une position', text: 'Ce que vous détenez d’un titre après toutes les transactions.' }, { icon: I('calculator'), bg: '#ffedd5', title: 'Un prix de revient', text: 'Ce que la position vous a coûté en moyenne par part.' }, { icon: I('chart-line'), bg: '#f3e8ff', title: 'Une valeur', text: 'Quantité × cours d’aujourd’hui, en euros.' }])}
      ${H.warn('<p>Toutes les démonstrations qui suivent utilisent des chiffres inventés. Elles ne lisent ni ne modifient votre portefeuille réel.</p>')}
      <p>Suite : <a href="#/achats-ventes">Achats, ventes et prix de revient</a>, puis <a href="#/gains">gains latents et réalisés</a>, puis <a href="#/performance-portefeuille">la performance</a>.</p>`,
    expert: ({ H }) => `<ul><li>Registre : transactions en euros avec taux de change historique ; un taux manquant rend prix de revient et plus-value du titre non calculables (signalé, jamais inventé).</li><li>Ventes supérieures à la quantité détenue : refusées par la validation de l'historique.</li><li>Les splits confirmés ajustent les quantités.</li></ul>`
  });

  L.push({
    id: 'achats-ventes', group: 'patrimoine', title: 'Achats, ventes et prix de revient', icon: I('calculator'), color: '#ea580c', keywords: 'achat vente prix de revient pmp moyen pondéré lot lots fifo frais successifs',
    lead: 'Vous achetez en plusieurs fois à des prix différents. Quel est alors votre prix ? Essayez avec un calculateur.',
    beginner: ({ H }) => `
      <h2>Acheter en plusieurs fois</h2>
      <p>Lundi vous achetez 10 parts à 100 €. Plus tard, le prix a monté : vous en achetez 10 de plus à 120 €. Chaque achat est un <b>lot</b>. Vous détenez 20 parts, mais elles ne vous ont pas coûté le même prix.</p>
      <h2>Le prix de revient moyen</h2>
      <p>Pour savoir ce que vous avez payé « en moyenne », Jigobourso utilise le <b>prix de revient moyen pondéré</b> : total dépensé (frais compris) ÷ nombre de parts. Ici : (10 × 100 + 10 × 120) ÷ 20 = <b>110 €</b> par part.</p>
      <h2>Quand on vend</h2>
      <p>Vous vendez 5 parts. Jigobourso considère que ces 5 parts coûtaient le prix moyen (110 €), quel que soit le lot d’origine. Le prix de revient des parts restantes reste 110 €.</p>
      <div class="hdemo" data-demo="pmp"></div>
      ${H.tip('<p>Les <b>lots</b> existent aussi : l’ordre FIFO (« premier acheté, premier vendu ») sert à suivre vos lots encore ouverts et à déclencher des alertes de suivi. Il ne sert pas au calcul du prix de revient.</p>', 'Moyenne ou FIFO ?')}
      ${H.quiz('q-pmp', [{ q: 'J’achète 10 parts à 100 € puis 10 à 120 €, sans frais. Mon prix de revient moyen est…', o: ['100 €', '110 €', '120 €'], a: 1, why: '(10×100 + 10×120) ÷ 20 = 110 €.' }, { q: 'Je vends une partie de mes parts. Le prix de revient des parts restantes…', o: ['Ne change pas (méthode du prix moyen)', 'Devient le prix du dernier achat'], a: 0, why: 'La vente sort des parts au coût moyen : le coût moyen par part restante reste le même.' }])}`,
    expert: ({ H }) => `
      <h2>Méthode (ledger.php)</h2>
      <div class="formula">Achat :  stock_coût += prix × qté × change + frais ;  stock_qté += qté
Vente :  coût_moyen = stock_coût / stock_qté
         coût_sorti = coût_moyen × qté_vendue
         plus-value réalisée = (prix × qté × change − frais) − coût_sorti
         stock_coût −= coût_sorti ;  stock_qté −= qté_vendue</div>
      <p>Les frais d'achat sont intégrés au coût ; les frais de vente réduisent le produit net. FIFO (<code>open_lots</code>, transactions.php) suit les lots ouverts pour les alertes, hors calcul comptable.</p>
      <div class="hdemo" data-demo="pmp"></div>
      ${H.warn('<p>Cette méthode n\'est pas nécessairement celle de votre déclaration fiscale (qui dépend du pays et du type de compte). Jigobourso ne produit pas de calcul fiscal.</p>')}`,
    mount: (el, { HM }) => {
      const d = el.querySelector('[data-demo=pmp]'); if (!d) return;
      const st = { q1: 10, p1: 100, q2: 10, p2: 120, fee: 0, sq: 5, sp: 130 };
      const row = (k, label, min, max, step = 1) => `<label>${label} : <b id="v-${k}"></b><input type="range" data-k="${k}" min="${min}" max="${max}" step="${step}" value="${st[k]}"></label>`;
      d.innerHTML = `<span class="fic">Exemple fictif · calculateur</span><div class="ctl">${row('q1', 'Achat 1 : parts', 1, 50)}${row('p1', 'Achat 1 : prix (€)', 10, 300)}</div><div class="ctl">${row('q2', 'Achat 2 : parts', 0, 50)}${row('p2', 'Achat 2 : prix (€)', 10, 300)}${row('fee', 'Frais par achat (€)', 0, 20)}</div><div class="ctl">${row('sq', 'Vente : parts', 0, 100)}${row('sp', 'Vente : prix (€)', 10, 300)}</div><div id="o"></div>`;
      const run = () => { Object.keys(st).forEach(k => { d.querySelector('#v-' + k).textContent = st[k]; });
        const qty = st.q1 + st.q2, cost = st.q1 * st.p1 + st.q2 * st.p2 + st.fee * (st.q1 > 0) + st.fee * (st.q2 > 0), avg = qty ? cost / qty : 0, sold = Math.min(st.sq, qty), out = avg * sold, net = sold * st.sp - (sold > 0 ? st.fee : 0), gain = net - out, left = qty - sold;
        const ff = HM.fifo([{ qty: st.q1, price: st.p1 }, { qty: st.q2, price: st.p2 }], sold ? [{ qty: sold, price: st.sp }] : []);
        d.querySelector('#o').innerHTML = `<div class="two"><div class="kpi"><small>Total dépensé (frais compris)</small><b>${eur(cost)}</b></div><div class="kpi"><small>Prix de revient moyen</small><b>${eur(avg)} / part</b></div><div class="kpi"><small>Parts restantes</small><b>${f(left, 0)}</b></div><div class="kpi"><small>Coût des parts vendues</small><b>${eur(out)}</b></div><div class="kpi"><small>Produit net de la vente</small><b>${eur(net)}</b></div><div class="kpi"><small>Plus-value réalisée</small><b class="${gain >= 0 ? 'good' : 'bad'}">${eur(gain)}</b></div></div>
        <p class="small muted">Pour comparaison, avec l’ordre FIFO (hors frais) les parts vendues viendraient d’abord de l’achat 1 : plus-value ${eur(ff.error ? 0 : ff.realized)}. Jigobourso utilise le prix moyen pour ses gains.</p>`; };
      d.querySelectorAll('input[data-k]').forEach(i => i.oninput = () => { st[i.dataset.k] = +i.value; run(); }); run();
    }
  });

  L.push({
    id: 'gains', group: 'patrimoine', title: 'Gains latents et gains réalisés', icon: I('piggy-bank'), color: '#16a34a', keywords: 'gain latent réalisé plus-value moins-value valeur cours position vendu',
    lead: 'Un gain « sur le papier » n’est pas un gain encaissé. La différence tient en un mot : vendre.',
    beginner: ({ H }) => `
      <h2>Latent : tant qu’on n’a pas vendu</h2>
      <p>Vous avez acheté 10 parts à 100 € (1 000 €). Elles valent aujourd’hui 130 € chacune (1 300 €). Vous êtes « en gain de 300 € »… mais c’est un gain <b>latent</b> : si le prix redescend demain, il fond. Il n’est pas dans votre poche.</p>
      <h2>Réalisé : une fois vendu</h2>
      <p>Si vous vendez ces 10 parts à 130 €, vous encaissez 1 300 € et le gain de 300 € devient <b>réalisé</b>.</p>
      ${H.table(['', 'Latent', 'Réalisé'], [['Quand ?', 'Titre encore détenu', 'Après une vente'], ['Calcul', 'Valeur actuelle − coût de ce qu’on détient', 'Produit net de la vente − coût des parts vendues'], ['Peut disparaître ?', 'Oui, si le cours baisse', 'Non, c’est acquis']])}
      <div class="hdemo" data-demo="gl"></div>
      ${H.quiz('q-gain', [{ q: 'J’ai acheté à 50 €, le titre vaut 60 €, je n’ai rien vendu. Mon gain est…', o: ['Réalisé', 'Latent'], a: 1, why: 'Tant qu’on n’a pas vendu, c’est latent.' }])}`,
    expert: ({ H }) => `<div class="formula">latent = quantité × cours_€ − coût_stock       latent % = 100 × latent / coût_stock
réalisé  = Σ (produit net des ventes − coût moyen sorti)</div><p>Total = latent + réalisé (hors dividendes et liquidités, non enregistrés). Un titre sans cours disponible n'a pas de valeur ni de latent : indiqué plutôt que mis à zéro.</p><div class="hdemo" data-demo="gl"></div>`,
    mount: (el) => {
      const d = el.querySelector('[data-demo=gl]'); if (!d) return;
      d.innerHTML = `<span class="fic">Exemple fictif</span><div class="ctl"><label>Cours actuel : <b id="a"></b><input type="range" id="r" min="60" max="180" value="130"></label><label>Parts vendues (sur 10) : <b id="b"></b><input type="range" id="s" min="0" max="10" value="0"></label></div><div id="o"></div>`;
      const run = () => { const p = +d.querySelector('#r').value, s = +d.querySelector('#s').value; d.querySelector('#a').textContent = p + ' €'; d.querySelector('#b').textContent = s;
        const real = s * (p - 100), lat = (10 - s) * (p - 100); d.querySelector('#o').innerHTML = `<div class="two"><div class="kpi"><small>Gain réalisé (vendu)</small><b class="${real >= 0 ? 'good' : 'bad'}">${eur(real)}</b></div><div class="kpi"><small>Gain latent (encore détenu)</small><b class="${lat >= 0 ? 'good' : 'bad'}">${eur(lat)}</b></div></div><p class="small muted">Prix d’achat : 100 € par part, 10 parts, sans frais.</p>`; };
      d.querySelector('#r').oninput = run; d.querySelector('#s').oninput = run; run();
    }
  });

  L.push({
    id: 'performance-portefeuille', group: 'patrimoine', title: 'Performance : avec ou sans les apports', icon: I('chart-no-axes-combined'), color: '#2563eb', keywords: 'performance portefeuille dietz apports retraits capital investi rendement hors mouvements périodes',
    lead: 'Si j’ajoute de l’argent, mon portefeuille grossit. Est-ce de la performance ? Non : il faut savoir séparer les deux.',
    beginner: ({ H }) => `
      <h2>Le piège des apports</h2>
      <p>Vous avez 1 000 €, ils montent à 1 100 € (+10 %). Vous ajoutez 1 000 € : vous avez 2 100 €. Puis le marché ne bouge plus. Votre portefeuille a « doublé » en valeur… mais votre <b>performance</b> n’a rien à voir avec les 1 000 € ajoutés.</p>
      <h2>Deux manières de mesurer</h2>
      ${H.cards([{ icon: I('wallet'), bg: '#dbeafe', title: 'Rendement du capital investi', text: 'Gain total ÷ argent mis. Facile à comprendre. Mais dépend du moment où vous avez ajouté de l’argent.' }, { icon: I('chart-line'), bg: '#dcfce7', title: 'Performance hors mouvements', text: 'Mesure ce que le marché a fait de l’argent présent, jour après jour, sans compter vos apports ni retraits. C’est celle de Jigobourso pour les graphiques.' }])}
      <div class="hdemo" data-demo="perf2"></div>
      ${H.jigo('<p>Pour la performance hors mouvements, Jigobourso enchaîne jour après jour une version de la méthode « Dietz modifiée » : le gain du jour est rapporté au capital présent ce jour-là, en tenant compte de l’heure des apports. Les jours d’achat ou de vente, le résultat est une <b>estimation</b>, indiquée comme telle.</p>')}
      <h2>Lire les périodes</h2>
      <p>Changer de période (1 mois, 1 an, depuis le début) ne change pas les données : on regarde un morceau plus ou moins long de la même histoire. Une perf de +5 % sur 1 mois et de −3 % sur 1 an sont compatibles.</p>
      ${H.quiz('q-perf2', [{ q: 'J’ajoute 5 000 € à mon portefeuille. Ma performance « hors mouvements »…', o: ['Augmente de 5 000 €', 'Ne bouge pas à cause de cet apport', 'Diminue'], a: 1, why: 'L’apport change la valeur du portefeuille, pas la performance des placements.' }])}`,
    expert: ({ H }) => `
      <h2>Modified Dietz quotidien chaîné (performance.py)</h2>
      <div class="formula">Pour un jour j :  gain_j = V_j − V_{j−1} − F_j            F_j = flux nets (achats + frais ; ventes nettes en négatif)
                   dénominateur_j = V_{j−1} + Σ F_i · w_i       w_i = fraction du jour restante après l'opération
                   facteur_j = 1 + gain_j / dénominateur_j
indice = Π facteur_j</div>
      <p>Cas particuliers : première détention (V<sub>j−1</sub> = 0) → dénominateur = achats du jour ; liquidation complète → dénominateur = V<sub>j−1</sub>. Jour sans valorisation fiable : facteur indisponible, pas de liaison artificielle. Frais = dépenses. Ni dividendes ni liquidités ne sont enregistrés : ce n'est pas un rendement de compte-titres complet.</p>
      <div class="hdemo" data-demo="perf2"></div>
      ${H.warn('<p>Un vrai TWR exigerait la valorisation juste avant chaque flux ; seules des valorisations quotidiennes existent, d\'où l\'estimation les jours de mouvement.</p>')}`,
    mount: (el, { HM }) => {
      const d = el.querySelector('[data-demo=perf2]'); if (!d) return;
      d.innerHTML = `<span class="fic">Exemple fictif</span><div class="ctl"><label>Apport en milieu de période : <b id="a"></b><input type="range" id="r" min="0" max="3000" step="100" value="1000"></label></div><div id="o"></div>`;
      const run = () => { const F = +d.querySelector('#r').value; d.querySelector('#a').textContent = eur(F);
        // départ 1000 ; période 1 : +10 % ; apport F ; période 2 : -5 % sur le capital présent
        const v1 = 1100, v1b = v1 + F, v2 = v1b * 0.95, gain = v2 - 1000 - F, ret = 100 * gain / (1000 + F), twr = 100 * (1.10 * 0.95 - 1);
        d.querySelector('#o').innerHTML = `<p>Départ 1 000 € → +10 % → 1 100 €. Apport de ${eur(F)}. Puis −5 % sur le tout.</p><div class="two"><div class="kpi"><small>Valeur finale</small><b>${eur(v2)}</b></div><div class="kpi"><small>Rendement du capital investi (gain ÷ argent mis)</small><b class="${ret >= 0 ? 'good' : 'bad'}">${pc(ret)}</b></div><div class="kpi"><small>Performance hors mouvements (1,10 × 0,95 − 1)</small><b class="${twr >= 0 ? 'good' : 'bad'}">${pc(twr)}</b></div></div><p class="small muted">La performance hors mouvements ne dépend pas de l’apport. Le rendement du capital investi, si : plus l’apport arrive tôt avant la baisse, plus il pèse.</p>`; };
      d.querySelector('#r').oninput = run; run();
    }
  });

  L.push({
    id: 'graphiques', group: 'patrimoine', title: 'Lire les graphiques du portefeuille', icon: I('chart-area'), color: '#0891b2', keywords: 'graphique portefeuille valeur courbe période répartition',
    lead: 'Trois graphiques, trois questions.',
    beginner: ({ H }) => `${H.table(['Graphique', 'Il répond à…', 'Piège'], [['Valeur en euros', 'Combien vaut mon portefeuille chaque jour ?', 'Monte aussi quand vous ajoutez de l’argent.'], ['Performance hors mouvements', 'Mes placements ont-ils bien travaillé, indépendamment de mes apports ?', 'Estimation les jours d’achat/vente.'], ['Répartition', 'Où est mon argent (titres, pays, secteurs) ?', 'Un portefeuille « divers » peut être concentré sur un seul secteur.']])}
      <p>Avant d’interpréter un graphique, vérifiez toujours la <b>période</b> affichée et l’<b>unité</b> (euros ou pourcentage).</p>
      ${H.tip('<p>Si la valeur monte mais la performance non, la hausse vient de vos apports, pas du marché.</p>')}`,
    expert: null
  });
})();
