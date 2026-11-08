/* Chapitres : démarrer et bases de la bourse. Tous les exemples sont fictifs. */
(function () {
  const I = n => J.icon(n), L = (window.HELP_CHAPTERS = window.HELP_CHAPTERS || []);
  L.push({
    id: 'bienvenue', group: 'demarrer', title: 'Bienvenue : à quoi sert Jigobourso ?', icon: I('book-open'), color: '#2563eb', keywords: 'introduction débuter commencer premiers pas',
    lead: 'Un guide pour apprendre la bourse pas à pas, puis utiliser Jigobourso sans rien deviner. Aucun savoir préalable n’est nécessaire.',
    beginner: ({ H }) => `
      <h2>L’idée en trois gestes</h2>
      <p>Il existe des milliers d’actions et de fonds en bourse. Impossible de les regarder un par un. Jigobourso le fait pour vous, en trois gestes :</p>
      ${H.steps([['Chercher', '<p>Vous choisissez une <b>stratégie</b> : une façon de chercher, par exemple « ce qui monte vite » ou « ce qui monte calmement ». L’appli ne garde que les titres qui correspondent. C’est le <b>filtrage</b>.</p>'],
      ['Noter', '<p>Chaque titre gardé reçoit une <b>note de 0 à 100</b> (un <b>score</b>). Plus la note est haute, plus le titre ressemble à ce que vous cherchez.</p>'],
      ['Classer et décider', '<p>Les titres sont rangés du mieux noté au moins bien noté. Vous regardez le haut de la liste, vous ouvrez une fiche, vous comparez. La décision reste la vôtre.</p>']])}
      ${H.warn('<p>Jigobourso <b>ne dit jamais « achetez »</b>. Il aide à trier et à comparer. Une bonne note décrit le passé d’un prix ; elle ne promet rien pour demain.</p>', 'À savoir avant de commencer')}
      <h2>Par où commencer ?</h2>
      <p>Cette aide se lit dans l’ordre, comme un petit cours. Chaque chapitre se termine par un mini-test. Vous pouvez aussi sauter directement à un sujet avec la recherche en haut à gauche.</p>
      ${H.cards([
        { icon: I('landmark'), bg: '#dbeafe', title: 'Je ne connais rien à la bourse', text: 'Commencez par « Action, ETF, indice » : on explique tout depuis zéro.', href: 'action-etf' },
        { icon: I('chart-line'), bg: '#dcfce7', title: 'Je veux comprendre les courbes', text: 'Allez à « Pente et régularité » : la démonstration clé de Jigobourso.', href: 'pente-regularite' },
        { icon: I('target'), bg: '#ffedd5', title: 'Je veux choisir une stratégie', text: 'Voyez les 7 stratégies, avec leurs vrais réglages.', href: 'strategies-vue' },
        { icon: I('wallet'), bg: '#f3e8ff', title: 'Je veux suivre mon portefeuille', text: 'Achats, ventes, gains : tout est expliqué avec des exemples.', href: 'portefeuille' }])}
      <h2>Deux niveaux de lecture</h2>
      <p>En haut de la page, le bouton <b>Débutant / Expert</b> change le niveau. <b>Débutant</b> : mots simples, images, exemples. <b>Expert</b> : formules exactes, paramètres, limites, calculs détaillés. Votre choix est mémorisé.</p>
      ${H.tip('<p>Les titres qui servent d’exemples dans cette aide (Zébulon, Brumel…) sont <b>inventés</b>. Les réglages des stratégies, eux, sont les <b>vrais</b> réglages lus dans le moteur.</p>', 'Exemples fictifs')}
      ${H.quiz('q-bienvenue', [{ q: 'Que fait une « stratégie » dans Jigobourso ?', o: ['Elle achète des actions à ma place', 'Elle filtre les titres puis leur donne une note', 'Elle prédit les prix de demain'], a: 1, why: 'Une stratégie filtre (garde ou écarte) puis note. Elle n’achète rien et ne prédit rien.' }])}`,
    expert: ({ H }) => `
      <h2>Architecture de lecture</h2>
      <p>Chaîne de traitement : collecte des cours de clôture (Yahoo Finance) → mesures par fenêtre (rendement, pente log, R², volatilité, repli) → <b>critères de recherche</b> (retenu / exclu / indéterminé, par durée) → <b>scores</b> (simple et complexe, 0–100) → classement. Les rangs sont calculés sur l’univers de la stratégie, puis les filtres d’affichage masquent des lignes sans les renuméroter.</p>
      <p>Chaque chapitre Expert cite les formules du code exécuté. Les constantes de stratégie sont lues dans le moteur à l’ouverture de la page (route <code>help/facts</code>), jamais recopiées.</p>
      ${H.warn('<p>Limites générales : les mesures décrivent le passé sur des fenêtres courtes, avec des clôtures quotidiennes. Aucune ne mesure un risque futur ni ne garantit un comportement.</p>')}
      ${H.fold('Stockage par utilisateur', '<p>Les adaptations de critères, de scores, les colonnes/tris et le niveau d’aide sont propres à chaque compte ; les références officielles ne sont jamais modifiées par un utilisateur.</p>')}`
  });

  L.push({
    id: 'action-etf', group: 'bourse', title: 'Action, ETF, indice : de quoi parle-t-on ?', icon: I('landmark'), color: '#0891b2', keywords: 'action etf fonds indice bourse entreprise diversification dividende cac sp500 titre',
    lead: 'Trois mots qu’on entend tout le temps. Voici ce qu’ils veulent dire, avec un gâteau pour imaginer.',
    beginner: ({ H }) => `
      <h2>L’action : un petit morceau d’entreprise</h2>
      <p>Imaginez une pizzeria qui appartient à 1 000 parts égales. Si vous achetez 1 part, vous possédez 1/1 000 de la pizzeria. Une <b>action</b>, c’est exactement ça, mais pour une grande entreprise cotée en bourse : un petit morceau de propriété.</p>
      <p>Quand l’entreprise va bien, beaucoup de gens veulent ses parts et le <b>prix monte</b>. Quand elle va mal, le prix peut <b>baisser</b>. Parfois, l’entreprise reverse une partie de ses bénéfices : c’est le <b>dividende</b>.</p>
      <h2>La bourse : le marché où les parts s’échangent</h2>
      <p>La <b>bourse</b> est un marché très organisé où acheteurs et vendeurs se rencontrent. Le prix se fixe tout seul : si beaucoup veulent acheter, il monte ; si beaucoup veulent vendre, il baisse.</p>
      <h2>L’ETF : un panier tout prêt</h2>
      <p>Choisir une seule entreprise est risqué : si elle va mal, tout votre argent en souffre. Un <b>ETF</b> (on dit « i-ti-èf ») est un <b>panier</b> qui contient des dizaines, des centaines, parfois des milliers d’actions à la fois. Vous achetez une part du panier, et vous possédez un tout petit bout de chaque action dedans.</p>
      ${H.fig(HC.stack([{ label: 'Entreprise A', value: 1, color: '#2563eb' }, { label: 'Entreprise B', value: 1, color: '#f97316' }, { label: 'Entreprise C', value: 1, color: '#16a34a' }, { label: 'Entreprise D', value: 1, color: '#9333ea' }, { label: 'Entreprise E', value: 1, color: '#e11d48' }], { alt: 'Un ETF contient plusieurs entreprises' }), 'Un ETF fictif : une seule part, cinq entreprises dedans. Si l’une chute, les quatre autres amortissent.')}
      <h2>L’indice : un thermomètre</h2>
      <p>Un <b>indice</b> (CAC 40, S&amp;P 500…) n’est pas quelque chose qu’on achète directement. C’est un <b>thermomètre</b> : il mesure comment se porte un groupe d’entreprises (par exemple les 500 plus grosses américaines). Beaucoup d’ETF copient un indice : on dit qu’ils le « répliquent ».</p>
      ${H.table(['', 'Action', 'ETF'], [['Qu’est-ce que c’est ?', 'Un morceau d’<b>une</b> entreprise', 'Un panier de <b>nombreux</b> titres'], ['Risque d’une mauvaise surprise', 'Plus fort : tout dépend d’une entreprise', 'Plus étalé (diversification)'], ['Exemple (inventé)', 'Zébulon SA', 'ETF Monde Large']])}
      ${H.jigo('<p>Jigobourso traite les actions et les ETF avec les mêmes mesures. Dans le tableau, la colonne « Type » dit s’il s’agit d’une action ou d’un ETF. La fiche d’un ETF ajoute « dans quoi il investit ».</p>')}
      ${H.quiz('q-action', [{ q: 'Un ETF, c’est…', o: ['Un panier qui contient beaucoup de titres', 'Une action très chère', 'Un indice qu’on peut acheter tel quel'], a: 0, why: 'Un ETF regroupe de nombreux titres en un seul. L’indice, lui, est seulement une mesure.' }, { q: 'Pourquoi dit-on qu’un ETF est « diversifié » ?', o: ['Parce qu’il ne coûte rien', 'Parce que l’argent est réparti sur plusieurs entreprises', 'Parce qu’il monte toujours'], a: 1, why: 'Diversifier, c’est ne pas mettre tous ses œufs dans le même panier. Cela ne garantit pas de hausse.' }])}`,
    expert: ({ H }) => `
      <h2>Compléments</h2>
      <ul><li><b>Réplication</b> : un ETF suit un indice soit en détenant les titres (physique), soit via des contrats (synthétique). L’écart entre l’ETF et l’indice s’appelle l’erreur de suivi.</li>
      <li><b>Distribution / capitalisation</b> : un ETF peut verser les dividendes (distribution) ou les réinvestir dans le cours (capitalisation). Les cours analysés par Jigobourso sont ceux de Yahoo Finance ; la comparaison de deux fonds de politique différente doit en tenir compte.</li>
      <li><b>Frais courants</b> : ils réduisent la performance du fonds ; ils sont déjà reflétés dans son cours.</li></ul>
      ${H.jigo('<p>Le type (action / ETF), le pays, le secteur et la place viennent de la base FinanceDatabase puis de Yahoo Finance ; voir « Sources de données et fiabilité ». Une catégorie manquante n’empêche pas le calcul des scores : elle limite seulement le filtrage par catégorie.</p>')}`
  });

  L.push({
    id: 'cotation', group: 'bourse', title: 'Place, séance, cours et variation', icon: I('clock'), color: '#0ea5e9', keywords: 'place mic séance cours clôture variation devise cotation ticker symbole pourcentage',
    lead: 'Où s’échangent les titres, à quel prix, et comment on dit « ça a monté de 2 % ».',
    beginner: ({ H }) => `
      <h2>La place de cotation</h2>
      <p>Un titre s’échange sur une <b>place</b> : Paris, New York, Francfort… Chaque place a ses horaires et sa monnaie. Un même titre peut exister sur plusieurs places. Dans Jigobourso, la colonne « Place » dit où le prix a été relevé.</p>
      <h2>Le symbole</h2>
      <p>Chaque titre a un court code, le <b>symbole</b> (ou « ticker »), comme une plaque d’immatriculation. Exemple fictif : <code>ZEB.PA</code> = Zébulon, coté à Paris.</p>
      <h2>La séance et la clôture</h2>
      <p>La bourse n’est pas ouverte 24 h sur 24. Une <b>séance</b>, c’est une journée de bourse, de l’ouverture à la fermeture. Le dernier prix de la journée s’appelle la <b>clôture</b>. Jigobourso utilise <b>le prix de clôture de chaque séance</b> : un prix par jour de bourse.</p>
      <p>Le week-end et les jours fériés, il n’y a pas de séance. C’est pourquoi on compte en « séances » et non en jours du calendrier : 5 séances = environ une semaine, 21 = environ un mois.</p>
      <h2>Le cours et la variation</h2>
      <p>Le <b>cours</b>, c’est le prix d’une part. La <b>variation</b> dit de combien il a bougé, en pourcentage. Regardons Zébulon (fictif) sur cinq séances :</p>
      <div class="hdemo"><span class="fic">Exemple fictif</span>
      <table><thead><tr><th>Séance</th><th class="n">Clôture</th><th class="n">Variation</th><th>Calcul</th></tr></thead><tbody>
      <tr><td>Lundi</td><td class="n">100,00 €</td><td class="n">—</td><td>point de départ</td></tr>
      <tr><td>Mardi</td><td class="n">102,00 €</td><td class="n good">+2,00 %</td><td>102 ÷ 100 − 1</td></tr>
      <tr><td>Mercredi</td><td class="n">101,00 €</td><td class="n bad">−0,98 %</td><td>101 ÷ 102 − 1</td></tr>
      <tr><td>Jeudi</td><td class="n">104,00 €</td><td class="n good">+2,97 %</td><td>104 ÷ 101 − 1</td></tr>
      <tr><td>Vendredi</td><td class="n">103,00 €</td><td class="n bad">−0,96 %</td><td>103 ÷ 104 − 1</td></tr></tbody></table></div>
      <p>Sur la semaine : de 100 à 103, soit <b>+3 %</b> (103 ÷ 100 − 1). Remarquez que les variations quotidiennes ne s’additionnent pas exactement : +2 − 0,98 + 2,97 − 0,96 ne fait pas 3. Chaque pourcentage porte sur un prix de départ différent.</p>
      ${H.tip('<p>Variation = (prix d’arrivée ÷ prix de départ) − 1. Pour passer de 100 à 150, on gagne 50 %. Mais pour revenir de 150 à 100, on perd seulement 33 %, car le départ n’est plus le même.</p>')}
      <h2>La devise</h2>
      <p>La <b>devise</b> est la monnaie du prix (euro, dollar…). Une variation en pourcentage ne dépend pas de la devise ; les montants en euros du portefeuille sont affichés en euros.</p>
      ${H.quiz('q-cotation', [{ q: 'Un titre passe de 50 € à 55 €. Quelle est la variation ?', o: ['+5 %', '+10 %', '+55 %'], a: 1, why: '55 ÷ 50 − 1 = 0,10, soit +10 %. Le +5 est un écart en euros, pas en pourcentage.' }, { q: 'Quel prix Jigobourso utilise-t-il chaque jour ?', o: ['Le plus haut de la journée', 'Le prix de clôture', 'Le prix d’ouverture'], a: 1, why: 'Un seul prix par séance : la clôture.' }])}`,
    expert: ({ H }) => `
      <h2>Conventions de données</h2>
      <ul><li><b>Place</b> : code MIC (par exemple XPAR pour Paris) ; le suffixe Yahoo du symbole (<code>.PA</code>) en découle.</li>
      <li><b>Cours</b> : clôtures quotidiennes issues de Yahoo Finance. Les dates sans séance sont absentes (pas d’interpolation). Une fenêtre de <i>n</i> séances utilise <i>n</i> + 1 clôtures.</li>
      <li><b>Variation</b> : <code>c<sub>t</sub> / c<sub>t−1</sub> − 1</code> (arithmétique) ; pour les mesures de pente et de volatilité le moteur utilise le <b>rendement logarithmique</b> <code>ln(c<sub>t</sub> / c<sub>t−1</sub>)</code>, additif dans le temps.</li></ul>
      ${H.example('<p>Aller-retour : +50 % puis −33,33 % → 1,5 × 0,6667 = 1,000. En logarithmes : ln 1,5 = +0,4055 et ln 0,6667 = −0,4055 ; la somme est nulle. C’est pourquoi le moteur travaille en logarithmes.</p>')}
      ${H.warn('<p>Une clôture manquante ou nulle rend la fenêtre non calculable : le titre est « indéterminé » pour cette durée (voir « Fiabilité »).</p>')}`
  });

  L.push({
    id: 'volume', group: 'bourse', title: 'Volume et liquidité', icon: I('chart-column'), color: '#16a34a', keywords: 'volume liquidité échangé revendre spread montant quotidien',
    lead: 'Un prix n’a de sens que si l’on peut vraiment acheter ou revendre. Le volume le mesure.',
    beginner: ({ H }) => `
      <h2>Le volume</h2>
      <p>Le <b>volume</b>, c’est le nombre de parts échangées pendant une séance. Beaucoup d’échanges = un titre très actif ; peu d’échanges = un titre calme, voire endormi.</p>
      <h2>La liquidité : pouvoir revendre quand on veut</h2>
      <p>Imaginez que vous vendez des cartes à collectionner. Si 500 personnes en veulent, vous vendez en une minute au prix affiché. Si personne n’en veut, vous devez baisser votre prix pour trouver un acheteur. La <b>liquidité</b> est la facilité à acheter ou vendre vite, sans faire bouger le prix.</p>
      ${H.fig(HC.bars([{ label: 'Titre A (très échangé)', value: 40, color: '#16a34a', note: 'M€/jour' }, { label: 'Titre B (moyen)', value: 8, color: '#f59e0b', note: 'M€/jour' }, { label: 'Titre C (peu échangé)', value: 0.4, color: '#e11d48', note: 'M€/jour' }], { max: 40, fmt: v => HC.f1(v, v < 1 ? 1 : 0) }), 'Montant échangé par jour (fictif). Le titre C est difficile à revendre rapidement sans baisser le prix.')}
      <h2>Pourquoi c’est important</h2>
      <p>Un titre peut sembler monter magnifiquement alors que quelques petits échanges suffisent à faire bouger son prix. Ce « beau mouvement » est peu fiable. Plus un titre est échangé, plus son prix est solide.</p>
      ${H.jigo('<p>Jigobourso estime la liquidité par le <b>montant échangé par jour en euros</b> (prix × volume). Il en tire une note de 0 à 100, qui compte dans le score complexe (voir le chapitre « Scores »).</p>')}
      ${H.quiz('q-volume', [{ q: 'Un titre est très peu échangé. Que peut-on craindre ?', o: ['Qu’il soit difficile à revendre au prix affiché', 'Qu’il ne monte jamais', 'Qu’il soit interdit'], a: 0, why: 'Peu d’acheteurs : pour vendre vite, il faudrait accepter un prix plus bas.' }])}`,
    expert: ({ H, facts }) => {
      const lq = facts && facts.common.liquidity;
      return `<h2>Note de liquidité</h2>
      <p>Montant médian échangé par jour <code>M</code> (en euros). Note = <code>100 × clamp( log₁₀(M / ${lq ? lq.floor_eur.toLocaleString('fr-FR') : '2 000 000'}) / log₁₀(${lq ? lq.ceil_eur.toLocaleString('fr-FR') : '50 000 000'} / ${lq ? lq.floor_eur.toLocaleString('fr-FR') : '2 000 000'}) , 0, 1 )</code>.</p>
      <p>Autrement dit : 0 en dessous du plancher, 100 au plafond, progression logarithmique entre les deux (chaque doublement du montant rapporte autant de points).</p>
      <div class="hdemo" data-demo="liq"></div>
      ${H.warn('<p>Limite : le volume Yahoo est celui de la place principale ; il ignore une partie des échanges hors marché. Une donnée absente donne une liquidité « inconnue » : la composante est alors retirée du score complexe, qui est recalculé sur les autres composantes.</p>')}`;
    },
    mount: (el, { HM, HC }) => {
      const d = el.querySelector('[data-demo=liq]'); if (!d) return;
      d.innerHTML = `<span class="fic">Calcul interactif</span><div class="ctl"><label>Montant échangé par jour : <b id="lv"></b><input type="range" id="lr" min="5" max="85" value="45"></label></div><div id="lo"></div>`;
      const run = () => { const eur = Math.pow(10, el.querySelector('#lr').value / 10), n = HM.liquidityNote(eur); el.querySelector('#lv').textContent = (eur >= 1e6 ? HC.f1(eur / 1e6, 1) + ' M€' : HC.f1(eur / 1e3, 0) + ' k€'); el.querySelector('#lo').innerHTML = `<div class="big">Note de liquidité : ${HC.f1(n, 0)} / 100</div>` + HC.bars([{ label: 'Note', value: n, color: '#16a34a' }], { max: 100 }); };
      el.querySelector('#lr').oninput = run; run();
    }
  });

  L.push({
    id: 'lire-graphique', group: 'bourse', title: 'Lire un graphique de cours', icon: I('chart-area'), color: '#7c3aed', keywords: 'graphique courbe échelle logarithmique période axe zoom',
    lead: 'Un graphique raconte une histoire. Voici comment la lire sans se tromper.',
    beginner: ({ H }) => {
      const s = HM.series(60, 18, 0.05, 2, 100, 0.012, 4);
      return `<h2>Les deux axes</h2>
      <p>En bas (axe horizontal) : le <b>temps</b>, ici en séances. À gauche (axe vertical) : le <b>prix</b>. Chaque point de la courbe dit « ce jour-là, le prix de clôture valait tant ».</p>
      ${H.fig(HC.line({ series: [{ name: 'Titre fictif', values: s }], alt: 'Courbe de cours fictive', yTitle: 'prix (€)' }), 'Un titre fictif sur 60 séances. Il finit plus haut qu’il n’a commencé, mais avec des creux en chemin.')}
      <h2>Ce qu’il faut regarder</h2>
      ${H.steps([['La direction générale', '<p>La courbe monte-t-elle, descend-elle ou stagne-t-elle ? C’est la <b>tendance</b>.</p>'], ['Les à-coups', '<p>Beaucoup de grandes dents de scie = un titre nerveux. Une courbe lisse = un titre paisible. Jigobourso mesure cela avec la <b>régularité</b> et la <b>volatilité</b>.</p>'], ['Les creux', '<p>Un recul depuis un sommet s’appelle un <b>repli</b> (drawdown). Il montre ce que vous auriez ressenti en le suivant.</p>'], ['La durée', '<p>Le même titre peut monter sur un mois et baisser sur un an. Il faut toujours dire <b>sur quelle durée</b>. Jigobourso en regarde plusieurs : ce sont les <b>granularités</b>.</p>']])}
      ${H.warn('<p>Une courbe qui a monté ne dit pas qu’elle va continuer. Elle décrit le passé.</p>')}
      ${H.fold('Échelle linéaire ou logarithmique ?', '<p>Sur une échelle <b>linéaire</b>, 1 € d’écart a toujours la même hauteur. Sur une échelle <b>logarithmique</b>, c’est le <b>pourcentage</b> qui a la même hauteur : passer de 10 à 20 (+100 %) ressemble à passer de 100 à 200. Jigobourso calcule ses pentes sur les logarithmes : une hausse « de 1 % par jour » compte pareil à 10 € ou à 1 000 €.</p>')}
      ${H.quiz('q-graphe', [{ q: 'Sur un graphique, l’axe horizontal représente…', o: ['Le temps', 'Le prix', 'Le volume'], a: 0, why: 'Temps en bas, prix à gauche.' }])}`;
    },
    expert: ({ H }) => `<h2>Conventions des graphiques de Jigobourso</h2>
      <ul><li>Fiches titres : prix de clôture sur des périodes (1 mois, 3 mois, 1 an, etc.) ; la droite de tendance tracée correspond à la régression de <code>ln(cours)</code> sur le temps (voir « Pente et régularité »).</li>
      <li>Aucune donnée n’est lissée ni interpolée ; les trous de calendrier ne sont pas comblés.</li>
      <li>Les graphiques de portefeuille tracent la valeur en euros ; les périodes d’analyse sont expliquées dans « Performance du portefeuille ».</li></ul>`
  });
})();
