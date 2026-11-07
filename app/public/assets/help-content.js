/* Contenu de l'aide (un objet par rubrique : b = Débutant, e = Expert). À modifier ici seulement ; les chiffres des stratégies ne sont JAMAIS écrits ici :
   ils sont lus dans le moteur (route help/facts) et affichés par aide.js. Une rubrique `admin: true` n'est affichée qu'aux administrateurs. */
window.HELP = [
  { id: 'premiers-pas', title: 'Premiers pas', icon: 'rocket',
    b: `<p>Jigobourso note chaque action et chaque ETF suivi, puis les classe selon la <b>stratégie</b> que vous choisissez. Commencez par la page <a href="index.html">Explorer</a> : choisissez une stratégie, parcourez le classement, ouvrez une fiche titre.</p>
        <ol><li>Choisissez une stratégie dans le sélecteur (7 stratégies intégrées).</li><li>Regardez les titres les mieux classés et leurs scores de 0 à 100.</li><li>Ouvrez une fiche pour voir le détail.</li><li>Enregistrez vos achats dans un portefeuille pour suivre vos gains.</li></ol>
        <p class="help-note">Les scores aident à trier des titres ; ils ne sont pas un conseil d’investissement.</p>`,
    e: `<p>Chaîne de traitement : collecte des cours (Yahoo Finance), calcul des mesures par fenêtre (pente, R², rendement, volatilité, repli), notation par le moteur commun (<i>score simple</i> et <i>score complexe</i>), puis classement. Les critères de recherche (pente et R² minimaux par granularité) ne modifient jamais une note : ils classent chaque titre en <i>retenu / exclu / indéterminé</i>.</p>
        <p>Chaque utilisateur peut adapter séparément les <b>critères</b> et les <b>scores</b> d’une stratégie intégrée ; la référence officielle reste protégée et restaurable.</p>` },
  { id: 'explorer', title: 'Explorer', icon: 'compass',
    b: `<p>L’Explorer affiche le classement des titres pour la stratégie choisie. Le <b>bandeau</b> sous le sélecteur indique si les critères et les scores sont officiels ou adaptés. La roue <i>info</i> à côté du nom ouvre un résumé de la stratégie.</p>
        <p>Vos réglages se trouvent dans le menu Explorer : <a href="mes-strategies.html">Mes stratégies</a>, <a href="mes-strategies.html#criteres">Mes critères de recherche</a>, <a href="mes-scores.html">Mes paramètres de scores</a>, <a href="mes-colonnes.html">Mes colonnes et tris</a>, <a href="mes-filtres.html">Mes filtres et catégories</a>.</p>`,
    e: `<p>Le tableau montre, pour la stratégie sélectionnée, les scores (simple, complexe), leurs rangs généraux (indépendants de vos filtres, du tri et de la pagination), le statut de critère de chaque titre et des mesures sur 21 séances. Filtres secondaires et recherche ne masquent que l’affichage : notes et rangs ne bougent pas.</p>
        <p>Les modifications non enregistrées d’une stratégie ne changent pas son statut (Officielle / Adaptée) : seul l’état enregistré compte.</p>` },
  { id: 'strategies', title: 'Les 7 stratégies intégrées', icon: 'target', dynamic: 'strategies',
    b: `<p>Sept stratégies officielles sont disponibles pour tous les comptes. Chacune a un nom, une icône et une fiche. Elles servent de références : vous pouvez les utiliser telles quelles, les adapter pour vous, ou créer vos propres stratégies.</p>`,
    e: `<p>Les valeurs affichées dans les fiches (seuils, poids, constantes) sont lues dans le moteur exécuté, jamais recopiées : si une valeur change, la fiche change avec elle. Les noms des trois stratégies momentum portent le suffixe « (expérimental) » dans le moteur.</p>` },
  { id: 'adaptees', title: 'Stratégies adaptées et personnelles', icon: 'user',
    b: `<p>Une stratégie intégrée devient <span class="sui-badge adapted">Adaptée</span> dès que vous modifiez ses critères ou ses scores. Elle reste <b>une seule entrée</b> : jamais de doublon « officielle + adaptée ». Si vous remettez exactement les valeurs officielles, elle redevient <span class="sui-badge official">Officielle</span> toute seule.</p>
        <p>Une <span class="sui-badge personal">Personnelle</span> est une stratégie que vous créez : elle n’existe que dans votre compte.</p>`,
    e: `<p>Le statut est calculé en comparant l’état enregistré à la référence : <b>critères</b> (granularités actives, pente, R²…) et <b>scores</b> (périodes, poids, réglages) sont jugés indépendamment et restaurables séparément ; la stratégie est Adaptée si l’un des deux diffère. Enregistrer un profil de scores identique à la référence supprime l’adaptation.</p>
        <p>Les adaptations sont stockées par utilisateur ; un autre compte ne les voit jamais. Les stratégies personnelles (dont « Blou ») restent privées.</p>` },
  { id: 'criteres', title: 'Critères et granularités', icon: 'sliders',
    b: `<p>Une <b>granularité</b> est une durée d’observation : Jour, Semaine, Mois, Trimestre, Semestre, Année. Un <b>critère de recherche</b> fixe un minimum à atteindre sur une granularité (par exemple une hausse moyenne minimale par séance). Les titres qui l’atteignent sont <i>retenus</i>.</p>`,
    e: `<p>Séances par granularité : Jour 1, Semaine 5, Mois 21, Trimestre 63, Semestre 126, Année 252. Seuils de pente (% par séance) et de R² : niveaux nommés lus dans le moteur (voir le tableau comparatif). Jour n’utilise que la variation de la dernière séance (ni pente, ni R²). Une donnée manquante donne « indéterminé », jamais zéro.</p>` },
  { id: 'scores', title: 'Scores simple et complexe', icon: 'gauge',
    b: `<p>Chaque titre reçoit deux notes de 0 à 100. Le <b>score simple</b> mesure surtout la force de la hausse. Le <b>score complexe</b> ajoute la régularité, les séances positives, le risque (volatilité, repli) et la liquidité. Plus la note est haute, mieux le titre colle à la stratégie.</p>
        <p>Vous pouvez adapter les poids dans <a href="mes-scores.html">Mes paramètres de scores</a>.</p>`,
    e: `<div data-facts="formulas"></div>` },
  { id: 'classements', title: 'Classements et filtres', icon: 'funnel',
    b: `<p>Le classement trie les titres par score. Vos <a href="mes-filtres.html">filtres et catégories</a> (pays, secteur, place, type) masquent des lignes sans changer les notes.</p>`,
    e: `<p>Rang général : calculé sur tous les titres notés, ex æquo possibles. Les filtres secondaires s’appliquent à l’affichage uniquement ; les groupes pays / secteur / place / type viennent d’une table de correspondances commune.</p>` },
  { id: 'indicateurs', title: 'Indicateurs', icon: 'chart',
    b: `<ul><li><b>Pente</b> : hausse moyenne par séance.</li><li><b>R²</b> : régularité de la hausse (proche de 1 = très régulière).</li><li><b>Volatilité</b> : ampleur des secousses.</li><li><b>Drawdown</b> : plus forte baisse depuis un sommet.</li><li><b>Liquidité</b> : montant échangé par jour.</li></ul>`,
    e: `<p>Pente = pente de tendance du cours sur la fenêtre, en % par séance ; R² = qualité de l’ajustement de cette tendance ; volatilité = ampleur des variations quotidiennes ; drawdown = repli maximal ; liquidité = valeur échangée par jour en euros (échelle logarithmique entre deux bornes, voir Scores). Fenêtres plus courtes que 3 séances : pas de R² ni de volatilité.</p>` },
  { id: 'fiches', title: 'Fiches titres', icon: 'info',
    b: `<p>Cliquez un titre pour ouvrir sa fiche : cours, graphique, variation sur 1 jour (« Var. 1J »), scores, et pour les ETF, ce dans quoi ils investissent et les points à surveiller.</p>`,
    e: `<p>« Var. 1J (%) » est la variation du cours entre les deux dernières séances clôturées. Les fiches ETF sont construites automatiquement à partir de la composition publiée.</p>` },
  { id: 'portefeuille', title: 'Portefeuille', icon: 'wallet',
    b: `<p>Un portefeuille regroupe vos positions. Ajoutez vos achats et ventes ; les valeurs sont converties en euros.</p>`,
    e: `<p>Les positions sont reconstruites à partir de l’historique des transactions ; les splits sont pris en compte pour les quantités détenues.</p>` },
  { id: 'achats-ventes', title: 'Achats, ventes et lots', icon: 'wallet',
    b: `<p>Chaque achat forme un <b>lot</b>. Quand vous vendez, les lots les plus anciens sont vendus en premier.</p>`,
    e: `<p>Méthode FIFO : les ventes consomment les achats les plus anciens d’abord, quantités suivies à travers les splits. Une vente sans achat connu est refusée.</p>` },
  { id: 'gains', title: 'Gains réalisés et latents', icon: 'trend',
    b: `<p>Le <b>gain réalisé</b> vient de ce que vous avez déjà vendu. Le <b>gain latent</b> concerne ce que vous détenez encore : il change avec le cours.</p>`,
    e: `<p>Gain réalisé = produit des ventes − coût des lots consommés (FIFO). Gain latent = valeur actuelle − coût des lots restants.</p>` },
  { id: 'performances', title: 'Performances et graphiques', icon: 'chart',
    b: `<p>Les pages <a href="bilan.html">Bilans</a> et Portefeuilles montrent l’évolution de votre patrimoine et de vos gains.</p>`,
    e: `<p>Les montants sont en euros avec deux décimales. Les graphiques lisent les mêmes séries que les calculs ; aucune donnée d’exemple n’est affichée quand les données manquent.</p>` },
  { id: 'colonnes', title: 'Colonnes et tris', icon: 'cols',
    b: `<p>Dans <a href="mes-colonnes.html">Mes colonnes et tris</a>, choisissez les colonnes visibles, leur ordre, leur largeur et le tri de départ, pour ordinateur et mobile. « Réinitialiser » revient à la présentation par défaut.</p>`,
    e: `<p>Quatre configurations indépendantes : Explorer / Scores × ordinateur / mobile. Elles sont propres à votre compte ; à défaut, la configuration par défaut de l’administration s’applique.</p>` },
  { id: 'donnees', title: 'Données de marché et fiabilité', icon: 'db',
    b: `<p>Les cours viennent de Yahoo Finance. Un titre dont les données sont insuffisantes n’est pas noté. Voir <a href="donnees.html">Données</a> pour la fraîcheur et la couverture.</p>`,
    e: `<p>Une note peut être signalée « peu fiable » quand la couverture est sous le seuil commun ; la note est quand même calculée. Qualité de série : ok, insufficient, incomplete, stale, inconsistent_adjustments, break.</p>` },
  { id: 'glossaire', title: 'Glossaire', icon: 'book',
    b: `<dl><dt>Granularité</dt><dd>Durée d’observation (jour, semaine, mois…).</dd><dt>Critère</dt><dd>Minimum à atteindre pour être retenu.</dd><dt>Score</dt><dd>Note de 0 à 100.</dd><dt>Drawdown</dt><dd>Plus forte baisse depuis un sommet.</dd><dt>Momentum</dt><dd>Variation passée du cours, dernier mois exclu.</dd><dt>FIFO</dt><dd>Premier acheté, premier vendu.</dd></dl>`,
    e: `<dl><dt>κ (kappa)</dt><dd>Priorité aux périodes courtes dans les poids automatiques.</dd><dt>R²</dt><dd>Coefficient de détermination de la régression.</dd><dt>Ancrage récent</dt><dd>Pénalité du score complexe quand la période la plus courte est faible.</dd></dl>` },
  { id: 'faq', title: 'FAQ', icon: 'help',
    b: `<details><summary>Pourquoi ma stratégie est « Adaptée » ?</summary><p>Parce que vous avez enregistré au moins un critère ou un réglage de score différent de la référence. Restaurez-les depuis Mes stratégies.</p></details>
        <details><summary>Un autre utilisateur voit-il mes réglages ?</summary><p>Non. Stratégies, adaptations, colonnes, tris et filtres sont propres à chaque compte.</p></details>
        <details><summary>Les scores changent-ils quand je filtre ?</summary><p>Non, les filtres ne masquent que l’affichage.</p></details>`,
    e: `<details><summary>Pourquoi Croissance rapide n’a-t-elle pas de seuil de R² ?</summary><p>Ses critères de recherche historiques ne portent que sur la pente (semaine et mois). Le R² intervient dans son score complexe, pas dans ses critères.</p></details>
        <details><summary>Que fait l’administrateur ?</summary><p>Il maintient les références officielles et les réglages communs ; l’interface d’administration technique ne contient que les outils d’exploitation.</p></details>` },
  { id: 'administration', title: 'Administration (réservé)', icon: 'shield', admin: true,
    b: `<p>Le menu d’administration regroupe : FinanceDatabase, Yahoo Finance, Actions / ETF, Cron, Journaux, Utilisateurs, Réglages.</p>`,
    e: `<p>Les routes <code>admin/*</code> exigent le rôle administrateur côté serveur ; un compte ordinaire reçoit un refus. Les adaptations personnelles passent par les routes <code>my/*</code>, <code>classement-test/*</code> et <code>table-layouts</code>, toujours limitées au compte connecté.</p>` },
];
