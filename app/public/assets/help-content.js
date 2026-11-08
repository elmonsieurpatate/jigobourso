/* Contenu de l'aide (un objet par rubrique : b = Débutant, e = Expert). À modifier ici seulement ; les chiffres des stratégies ne sont JAMAIS écrits ici :
   ils sont lus dans le moteur (route help/facts) et affichés par aide.js. Une rubrique `admin: true` n'est affichée qu'aux administrateurs. */
window.HELP = [
  { id: 'premiers-pas', title: 'Comprendre en 2 minutes', icon: 'rocket',
    b: `<p><b>Jigobourso en une phrase :</b> l’appli regarde l’évolution du prix de milliers d’actions et d’ETF, garde ceux qui correspondent à ce que vous cherchez, puis leur donne une note de 0 à 100 pour les classer.</p>
        <p>Tout part d’un choix : <b>choisissez une stratégie</b>. Une stratégie, c’est une façon de chercher. Elle fonctionne en <b>deux temps</b> : d’abord un <b>tri</b> (le filtrage), ensuite une <b>note</b> (les scores).</p>
        <h3>Temps 1 — Le tri : « est-ce que ce titre mérite d’être regardé ? »</h3>
        <p>La stratégie pose des questions simples sur le prix du titre, sur une ou plusieurs <b>durées</b> (on les appelle les <i>granularités</i> : une semaine, un mois, un trimestre…). Par exemple, la stratégie <b>Croissance rapide</b> demande :</p>
        <ul><li>« Est-ce que le prix a monté d’au moins <b>1,4 %</b> sur la dernière semaine ? »</li><li>« Et d’au moins <b>5,9 %</b> sur le dernier mois ? »</li></ul>
        <p>Si les réponses sont oui sur chaque durée, le titre est <b>retenu</b>. Sinon il est <b>exclu</b>. Si on manque de données pour répondre, il est <b>indéterminé</b>.</p>
        <p>Ces seuils reposent sur deux idées, expliquées dans la section « Critères de recherche » : la <b>pente</b> (la vitesse de hausse) et la <b>régularité</b> (est-ce que ça monte tout droit, ou en zigzag ?).</p>
        <h3>Temps 2 — La note : « est-il vraiment bon ? »</h3>
        <p>Les titres retenus reçoivent des notes de 0 à 100 : une note de <b>hausse</b> (de combien et à quelle régularité ça monte) et une note plus complète qui regarde aussi le <b>risque</b> (le prix fait-il des montagnes russes ? A-t-il déjà beaucoup chuté ?) et la <b>facilité à revendre</b>.</p>
        <p><b>Exemple imaginaire.</b> L’action « Zébulon » a gagné 8 % en une semaine et 20 % en un mois, avec une courbe assez droite. Avec Croissance rapide elle est retenue, sa note de hausse (score simple) est d’environ <b>47 sur 100</b> et son score complexe d’environ <b>66,5 sur 100</b>. Le détail du calcul est dans la section « Les scores ».</p>
        <h3>Temps 3 — Vous réglez tout</h3>
        <p>Si le tri ou les notes ne vous plaisent pas, vous les changez : plus ou moins exigeant, une durée de plus, d’autres priorités. La stratégie devient alors <b>« Adaptée »</b> (votre version), et vous pouvez revenir à l’officielle en un clic. Le <b>parcours guidé</b> ci-dessous montre comment faire, pas à pas.</p>
        <p class="help-note">Une bonne note ne veut pas dire « achetez ». Elle sert à comparer et à gagner du temps, c’est tout.</p>`,
    e: `<p>Chaîne de traitement : collecte des cours (Yahoo Finance), calcul des mesures par fenêtre (pente, R², rendement, volatilité, repli), <b>critères de recherche</b> (statut retenu / exclu / indéterminé, affichage seulement), puis <b>notation</b> par le moteur commun (score simple, score complexe) et classement. Les critères ne modifient jamais une note, et les notes ne dépendent pas de vos filtres.</p>
        <p>Chaque utilisateur adapte séparément les <b>critères</b> et les <b>scores</b> d’une stratégie intégrée ; la référence officielle (code + réglage administrateur) reste protégée et restaurable. Statut = Officielle si les deux sont identiques à la référence, Adaptée sinon.</p>` },
  { id: 'parcours', title: 'Parcours guidé : de la recherche à la décision', icon: 'route',
    b: `<p>Suivez ces étapes dans l’ordre. À chaque étape, un encadré « Si… alors… » vous dit quoi faire quand le résultat ne vous convient pas.</p>
      <ol class="help-path">
        <li><h3><span>1</span> Je cherche quelque chose : je choisis une stratégie</h3>
          <p>Dans <a href="index.html">Explorer</a>, ouvrez le sélecteur « Stratégie ». Chaque stratégie répond à une envie :</p>
          <ul><li>Je veux ce qui <b>monte le plus vite</b> → <b>Croissance rapide</b>.</li><li>Je veux une hausse <b>solide et régulière</b> → <b>Croissance régulière</b>.</li><li>Je veux monter <b>sans secousses</b> → <b>Hausse calme</b>.</li><li>Je cherche un titre qui <b>repart</b> après une période calme → <b>Rebond</b>.</li><li>Je mise sur la <b>tendance des 6 ou 12 derniers mois</b> → <b>Momentum 6 mois</b> ou <b>12 mois</b>.</li><li>Je veux du momentum <b>en tenant compte du risque</b> → <b>Momentum ajusté du risque</b>.</li></ul></li>
        <li><h3><span>2</span> J’ai des résultats : je les lis</h3>
          <p>Le tableau liste les titres <b>retenus</b> par la stratégie, classés par <b>score complexe</b> (puis score simple). Sous le nom du titre, vous voyez son secteur. La colonne « Tendance » montre la courbe récente. Cliquez un titre pour ouvrir sa fiche.</p>
          <p>Vous pouvez : <b>chercher</b> un nom ou un symbole, <b>filtrer</b> par pays, secteur, place ou type (action / ETF), <b>trier</b> sur une autre colonne, <b>choisir vos colonnes</b> dans <a href="mes-colonnes.html">Mes colonnes et tris</a>. Ces filtres ne changent jamais les notes.</p></li>
        <li><h3><span>3</span> Je veux voir plus (ou moins) de titres : je règle le filtrage</h3>
          <div class="help-if"><b>Si</b> la liste est trop courte → <b>alors</b> je baisse le niveau de pente (par exemple « forte » au lieu de « très forte »), je baisse le niveau de régularité, ou je retire un seuil. Plus le filtre est souple, plus il y a de titres.</div>
          <div class="help-if"><b>Si</b> la liste est trop longue ou trop bruitée → <b>alors</b> je monte la pente ou la régularité minimales.</div>
          <div class="help-if"><b>Si</b> je veux une granularité de plus (par exemple ajouter le trimestre à la semaine et au mois) → <b>alors</b> je l’active dans les critères : le titre doit maintenant passer le filtre sur <i>toutes</i> les durées. La liste raccourcit, mais les titres restants montent de façon plus durable.</div>
          <p>Le réglage se fait dans l’Explorer (panneau « Critères »). La stratégie passe en <span class="sui-badge adapted">Adaptée</span> pour les critères ; « Restaurer » revient à l’officiel.</p></li>
        <li><h3><span>4</span> Les scores ne me conviennent pas : je les modifie</h3>
          <div class="help-if"><b>Si</b> le classement met trop haut des titres trop agités → <b>alors</b> j’augmente le poids de la volatilité et du drawdown dans le score complexe.</div>
          <div class="help-if"><b>Si</b> je veux privilégier les hausses récentes → <b>alors</b> je donne plus de poids aux courtes durées (semaine, mois).</div>
          <div class="help-if"><b>Si</b> je veux une hausse très régulière → <b>alors</b> j’augmente le poids de la régularité (R²).</div>
          <p>Tout se règle dans <a href="mes-scores.html">Mes paramètres de scores</a>, avec une simulation sur un vrai titre avant d’enregistrer. Les scores passent en <span class="sui-badge adapted">Adaptée</span> ; « Restaurer » revient à l’officiel, indépendamment des critères.</p></li>
        <li><h3><span>5</span> Je garde mes réglages : mes stratégies</h3>
          <p>Dans <a href="mes-strategies.html">Mes stratégies</a>, vous voyez l’état de chaque stratégie (Officielle ou Adaptée), comparez avec l’officielle, restaurez ou créez la vôtre (<span class="sui-badge personal">Personnelle</span>), avec l’icône et le texte de votre choix.</p></li>
        <li><h3><span>6</span> Je passe à l’action</h3>
          <p>Sur la fiche d’un titre : cours, graphique, scores, points à surveiller (ETF). Pour suivre ce que vous achetez, créez un <a href="portefeuilles.html">portefeuille</a> et saisissez vos achats et ventes.</p>
          <p class="help-note">Rappel : un score aide à trier, il ne dit pas d’acheter. Vérifiez toujours le titre, son secteur, sa liquidité et le risque.</p></li>
      </ol>`,
    e: `<p>Correspondances techniques : le filtrage est le statut de critère (retenu / exclu / indéterminé), combiné en « toutes les granularités actives doivent passer » ; il n’agit que sur l’affichage, jamais sur les scores. Les granularités qui entrent dans le <i>score</i> se règlent séparément dans Mes paramètres de scores (poids automatiques recalculés selon κ, ou poids personnalisés). Les rangs affichés restent les rangs généraux, indépendants des filtres.</p>` },
  { id: 'bases', title: 'Les bases de la bourse (pour débuter)', icon: 'landmark',
    b: `<p>Si les mots de la finance sont nouveaux pour vous, commencez ici. Tout est expliqué simplement.</p>
      <h3>Ce que l’on achète</h3>
      <dl class="help-dl">
        <dt>Action</dt><dd>Une petite part d’une entreprise. Si l’entreprise prospère, la valeur de l’action peut monter ; sinon elle peut baisser. Vous pouvez perdre une partie ou la totalité de la somme investie.</dd>
        <dt>ETF (fonds indiciel coté)</dt><dd>Un panier de nombreux titres (actions, obligations…) qui s’achète comme une seule action. Il suit souvent un <i>indice</i>. Avantage : la diversification (un seul achat = beaucoup de titres). Il a des <i>frais</i> annuels.</dd>
        <dt>Indice</dt><dd>Un thermomètre d’un marché : une liste de grandes entreprises dont on suit la valeur d’ensemble (par exemple le CAC 40 pour la France).</dd>
        <dt>Obligation</dt><dd>Un prêt à une entreprise ou à un État, qui rapporte des intérêts. Moins variable qu’une action en général.</dd>
        <dt>Diversification</dt><dd>Ne pas tout mettre sur un seul titre : si l’un baisse, les autres compensent en partie.</dd>
      </dl>
      <h3>Où et comment ça s’échange</h3>
      <dl class="help-dl">
        <dt>Place de cotation (place, marché)</dt><dd>La bourse où le titre s’échange : par exemple Euronext Paris, Nasdaq ou Xetra (Allemagne). Chaque place a ses horaires et sa devise. Dans Jigobourso, la colonne « Place » affiche son code (code MIC, comme XPAR, XNAS, XETR).</dd>
        <dt>Séance</dt><dd>Une journée de bourse (du lundi au vendredi, hors jours fériés).</dd>
        <dt>Cours</dt><dd>Le prix d’un titre à un instant donné.</dd>
        <dt>Clôture</dt><dd>Le dernier cours de la séance. La « variation 1 jour » compare les deux dernières clôtures.</dd>
        <dt>Volume</dt><dd>Le nombre de titres échangés sur une période. Beaucoup de volume = beaucoup d’acheteurs et de vendeurs.</dd>
        <dt>Liquidité</dt><dd>La facilité à acheter ou vendre vite, sans faire bouger le prix. Un titre peu échangé est peu liquide : on peut avoir du mal à le revendre. Jigobourso la mesure par le montant échangé par jour, en euros.</dd>
        <dt>Écart acheteur / vendeur (spread)</dt><dd>La différence entre le prix auquel on achète et celui auquel on vend. Plus un titre est liquide, plus l’écart est faible.</dd>
        <dt>Devise</dt><dd>La monnaie dans laquelle le titre est coté (euro, dollar…). Un titre en dollar est converti en euros pour votre suivi.</dd>
        <dt>Ordre de bourse</dt><dd>Votre demande d’achat ou de vente à votre courtier. « Au marché » : au prix du moment. « À cours limité » : seulement à un prix que vous fixez.</dd>
        <dt>Symbole (ticker) et ISIN</dt><dd>Le symbole est le « surnom » court d’un titre (AAPL, MC.PA…). L’ISIN est son code d’identification international unique (12 caractères).</dd>
      </dl>
      <h3>Comment on parle d’un titre</h3>
      <dl class="help-dl">
        <dt>Secteur</dt><dd>Le domaine d’activité de l’entreprise. Exemples : <i>Technology</i> (technologie), <i>Financials</i> (banques, assurances), <i>Health Care</i> (santé), <i>Energy</i> (énergie), <i>Consumer Discretionary</i> (consommation « de confort » : mode, loisirs, automobile, restauration…), <i>Consumer Staples</i> (consommation de base : alimentation, produits d’hygiène), <i>Industrials</i> (industrie), <i>Utilities</i> (eau, électricité), <i>Real Estate</i> (immobilier), <i>Materials</i> (matières premières), <i>Communication Services</i> (télécoms, médias).</dd>
        <dt>Capitalisation</dt><dd>La valeur totale d’une entreprise en bourse (cours × nombre d’actions). Grande, moyenne ou petite capitalisation.</dd>
        <dt>Dividende</dt><dd>Une part des bénéfices que certaines entreprises versent à leurs actionnaires.</dd>
        <dt>Split (division d’action)</dt><dd>L’entreprise divise ses actions : vous en avez plus, chacune vaut moins. La valeur totale ne change pas. Jigobourso ajuste les quantités.</dd>
        <dt>Hausse / baisse, haussier / baissier</dt><dd>Un marché ou un titre « haussier » monte, « baissier » baisse.</dd>
        <dt>Performance (rendement)</dt><dd>De combien le prix a varié sur une période, en pourcentage.</dd>
        <dt>Volatilité</dt><dd>L’ampleur des variations. Un titre très volatil monte et descend beaucoup : plus de gains possibles, plus de risque.</dd>
        <dt>Drawdown (repli maximal)</dt><dd>La plus forte baisse depuis un sommet. Il mesure « jusqu’où ça a pu descendre ».</dd>
        <dt>Pente et régularité (R²)</dt><dd>Voir « Critères de recherche » : la vitesse moyenne de hausse par séance, et sa régularité.</dd>
      </dl>
      <h3>Les ETF en détail</h3>
      <dl class="help-dl">
        <dt>Frais (TER)</dt><dd>Les frais annuels de l’ETF, en pourcentage de la somme investie. Ils sont prélevés en continu ; plus ils sont bas, mieux c’est à qualité égale.</dd>
        <dt>Réplication</dt><dd>La manière dont l’ETF suit son indice : en détenant les vrais titres (physique) ou via un contrat (synthétique).</dd>
        <dt>Composition</dt><dd>Les titres que contient l’ETF. La fiche d’un ETF montre dans quoi il investit et les points à surveiller.</dd>
      </dl>
      <p class="help-note">Investir comporte un risque de perte en capital. Cette aide explique le vocabulaire et l’outil ; elle ne constitue pas un conseil en investissement.</p>`,
    e: `<p>Dans Jigobourso : « Place » = code MIC de la place de cotation ; « Secteur » vient de la catégorie du titre (secteurs GICS pour les actions, catégories pour les ETF) regroupée par la table de correspondances commune ; « Liquidité » = valeur échangée par jour en euros (échelle logarithmique entre 2 M€ et 50 M€ pour la note) ; « Var. 1J » = variation entre les deux dernières séances clôturées ; les cours en devise étrangère sont convertis en euros avec les derniers taux connus.</p>` },
  { id: 'explorer', title: 'Explorer', icon: 'compass',
    b: `<p>L’Explorer, c’est la page où vous cherchez des actions et des ETF. Vous choisissez une stratégie (une façon de chercher), et la page vous montre une liste de titres, du mieux noté au moins bien noté.</p>
        <p>Juste sous le nom de la stratégie, une petite bande vous dit si la stratégie est « Officielle » (telle que nous l’avons faite) ou « Adaptée » (vous l’avez changée). Dans le menu Explorer, vous trouvez tous vos réglages : <a href="mes-strategies.html">Mes stratégies</a>, <a href="mes-strategies.html#criteres">Mes critères de recherche</a>, <a href="mes-scores.html">Mes paramètres de scores</a>, <a href="mes-colonnes.html">Mes colonnes et tris</a>, <a href="mes-filtres.html">Mes filtres et catégories</a>.</p>`,
    e: `<p>Le tableau montre, pour la stratégie sélectionnée, les scores (simple, complexe), leurs rangs généraux (indépendants de vos filtres, du tri et de la pagination), le statut de critère de chaque titre et des mesures sur 21 séances. Filtres secondaires et recherche ne masquent que l’affichage : notes et rangs ne bougent pas.</p>
        <p>Les modifications non enregistrées d’une stratégie ne changent pas son statut (Officielle / Adaptée) : seul l’état enregistré compte.</p>` },
  { id: 'strategies', title: 'Les 7 stratégies intégrées', icon: 'target', dynamic: 'strategies',
    b: `<p>Sept stratégies officielles sont disponibles pour tous les comptes. Chacune a un nom, une icône et une fiche. Elles servent de références : vous pouvez les utiliser telles quelles, les adapter pour vous, ou créer vos propres stratégies.</p>`,
    e: `<p>Les valeurs affichées dans les fiches (seuils, poids, constantes) sont lues dans le moteur exécuté, jamais recopiées : si une valeur change, la fiche change avec elle. Les noms des trois stratégies momentum portent le suffixe « (expérimental) » dans le moteur.</p>` },
  { id: 'adaptees', title: 'Stratégies adaptées et personnelles', icon: 'user',
    b: `<p>Vous avez changé un réglage d’une stratégie ? Elle devient <span class="sui-badge adapted">Adaptée</span> : c’est « votre version ». Il n’y a jamais deux copies : une seule stratégie, avec une étiquette qui dit si c’est l’officielle ou la vôtre. Si vous remettez exactement les réglages d’origine, elle redevient <span class="sui-badge official">Officielle</span> toute seule.</p>
        <p>Une stratégie <span class="sui-badge personal">Personnelle</span> est une stratégie que vous inventez vous-même. Personne d’autre ne la voit.</p>`,
    e: `<p>Le statut est calculé en comparant l’état enregistré à la référence : <b>critères</b> (granularités actives, pente, R²…) et <b>scores</b> (périodes, poids, réglages) sont jugés indépendamment et restaurables séparément ; la stratégie est Adaptée si l’un des deux diffère. Enregistrer un profil de scores identique à la référence supprime l’adaptation.</p>
        <p>Les adaptations sont stockées par utilisateur ; un autre compte ne les voit jamais. Les stratégies personnelles (dont « Blou ») restent privées.</p>` },
  { id: 'criteres', title: 'Critères de recherche : pente, régularité, granularités', icon: 'sliders',
    b: `<p>Le critère de recherche, c’est le <b>tri d’entrée</b> d’une stratégie. Pour le comprendre, il faut trois mots.</p>
        <h3>1. La granularité = « sur quelle durée je regarde ? »</h3>
        <p>C’est la longueur de la période observée, comptée en <b>séances</b> (une séance = un jour de bourse). Une <b>semaine</b> = 5 séances, un <b>mois</b> = 21, un <b>trimestre</b> = 63, un <b>semestre</b> = 126, une <b>année</b> = 252. « Jour » (1 séance) existe aussi : il regarde seulement la variation de la dernière séance.</p>
        <p>Une stratégie peut regarder plusieurs durées <b>à la fois</b>. Alors le titre doit réussir le test sur <b>chacune</b>. Plus vous ajoutez de durées, plus le tri devient exigeant (donc moins de titres restent), mais ceux qui restent montent de façon plus solide.</p>
        <h3>2. La pente = « à quelle vitesse ça monte ? »</h3>
        <p>C’est la hausse moyenne <b>par séance</b>. Comme les petits chiffres parlent peu, voici ce que chaque niveau représente en pratique :</p>
        <div data-facts="criteria"></div>
        <p>Lecture : une pente « très forte » correspond à environ +1,4 % en une semaine, +5,9 % en un mois, +19 % en un trimestre, <i>si la hausse est régulière</i>.</p>
        <h3>3. La régularité (R²) = « est-ce que ça monte tout droit ? »</h3>
        <p>Imaginez que vous tracez la meilleure ligne droite qui passe au milieu de la courbe du prix. Le <b>R²</b> dit à quel point la courbe colle à cette ligne. Proche de <b>1</b> : la hausse est propre, régulière, comme un escalier. Proche de <b>0</b> : le prix part dans tous les sens. Trois niveaux : <b>souple</b> (au moins 0,556), <b>équilibré</b> (0,75), <b>strict</b> (0,889).</p>
        <h3>Le verdict</h3>
        <ul><li><b>Retenu</b> : le titre réussit tous les tests.</li><li><b>Exclu</b> : il rate au moins un test (par exemple : monte bien sur le mois mais a ralenti cette semaine).</li><li><b>Indéterminé</b> : il manque des données pour juger (jamais compté comme zéro).</li></ul>
        <h3>Comment le modifier ?</h3>
        <p>Dans l’Explorer, ouvrez le panneau des critères : changez le niveau de pente ou de régularité, ajoutez ou retirez une durée. Pour voir <b>plus</b> de titres : baissez un niveau ou retirez une durée. Pour en voir <b>moins</b> mais de meilleure qualité : montez un niveau ou ajoutez une durée. Les critères ne changent jamais les notes : ils décident seulement quels titres sont affichés comme retenus.</p>`,
    e: `<p>Séances par granularité : Jour 1, Semaine 5, Mois 21, Trimestre 63, Semestre 126, Année 252. Pente en % par séance ; niveaux nommés lus dans le moteur (tableau ci-dessous). Jour n’utilise que la variation de la dernière séance (ni pente, ni R²). Pas de R² ni de volatilité sous 3 séances. Les critères ne portent que sur la pente et le R² ; rendement, volatilité et repli n’y sont jamais des seuils (ils pèsent dans le score complexe).</p><div data-facts="criteria"></div>` },
  { id: 'scores', title: 'Les scores : comment les titres sont notés', icon: 'gauge',
    b: `<p>Une fois le tri fait, chaque titre reçoit <b>deux notes sur 100</b>. Reprenons notre action imaginaire <b>Zébulon</b> (stratégie Croissance rapide : on regarde la semaine et le mois). Données de l’exemple : +8 % sur la semaine, +20 % sur le mois, hausse assez régulière (R² de 0,92 puis 0,90), prix peu agité, titre très échangé.</p>
        <h3>Le score simple : « de combien et à quelle régularité ça monte »</h3>
        <ol><li><b>Note de hausse de chaque durée.</b> On compare la hausse du titre à une hausse « de référence » qui vaut 100. Avec le réglage standard, la référence est d’environ <b>17 %</b> sur une semaine, <b>36 %</b> sur un mois, <b>63 %</b> sur un trimestre. Zébulon : 8 % sur 17 % → <b>47/100</b> pour la semaine ; 20 % sur 36 % → <b>56/100</b> pour le mois.</li>
        <li><b>On fait la moyenne, avec des poids.</b> Les durées courtes comptent un peu plus : ici environ 42 % pour la semaine et 58 % pour le mois → note de hausse d’environ <b>0,52</b> (soit 52 %).</li>
        <li><b>On multiplie par la régularité</b> (le R² moyen, ici 0,90). 0,52 × 0,90 = 0,47 → score simple d’environ <b>47/100</b>.</li></ol>
        <p>Retenez : <b>score simple = hausse × régularité</b>. Un titre qui monte beaucoup mais en zigzag est puni ; un titre très régulier mais qui monte peu aussi.</p>
        <h3>Le score complexe : « est-ce un bon titre dans l’ensemble ? »</h3>
        <p>Ici on note <b>plusieurs points</b>, chacun sur 100, puis on fait une moyenne où chaque point a son poids (en %). Pour Zébulon : hausse 52, régularité 91, séances en hausse 63, gains répartis 64, prix peu agité 80, petites chutes 66, facilité à revendre 72… Avec les poids de Croissance rapide, cela donne un score complexe d’environ <b>66,5/100</b>.</p>
        <p>Voici chaque point noté : ce qu’il mesure, comment la note va de 0 à 100, et quel poids lui donne chaque stratégie.</p>
        <div data-facts="components"></div>
        <p>C’est la <b>différence de poids</b> qui fait la personnalité d’une stratégie : Hausse calme pèse très fort sur l’agitation et les chutes, Rebond sur le contexte de rebond et l’accélération, les Momentum sur la tendance passée.</p>
        <h3>Tout se modifie</h3>
        <p>Dans <a href="mes-scores.html">Mes paramètres de scores</a>, vous changez les durées utilisées, leur importance, et le poids de chaque point. Une simulation vous montre l’effet sur un vrai titre <i>avant</i> d’enregistrer. La stratégie devient « Adaptée » côté scores ; vous la restaurez quand vous voulez, sans toucher à vos critères.</p>`,
    e: `<p>Score simple = min(100, 100 × D × Q) ; D = Σ ω<sub>p</sub> × note de pente de la période p (poids renormalisés sur les périodes mesurables) ; Q = moyenne pondérée des R², chaque R² pesant min(1, n/21). Pics, séances positives, accélération, volatilité, repli et liquidité n’y entrent pas.</p>
        <p>Score complexe = moyenne pondérée des notes ci-dessous ; une composante indisponible sort du calcul et les poids restants sont renormalisés (jamais comptée zéro).</p>
        <div data-facts="components"></div><div data-facts="formulas"></div>` },
  { id: 'classements', title: 'Classements et filtres', icon: 'funnel',
    b: `<p>Le classement, c’est comme un palmarès : le titre qui a la meilleure note est en haut. Vous pouvez le trier autrement (par exemple par prix).</p>
        <p>Vous pouvez aussi cacher des lignes avec des <a href="mes-filtres.html">filtres</a> : par exemple ne garder que les entreprises d’un pays, d’un secteur ou d’une place de bourse. Cacher des lignes ne change jamais les notes : c’est juste pour mieux voir.</p>`,
    e: `<p>Rang général : calculé sur tous les titres notés, ex æquo possibles. Les filtres secondaires s’appliquent à l’affichage uniquement ; les groupes pays / secteur / place / type viennent d’une table de correspondances commune.</p>` },
  { id: 'indicateurs', title: 'Indicateurs', icon: 'chart',
    b: `<p>Voici les mots que vous verrez dans les tableaux :</p>
        <ul><li><b>Pente</b> : de combien le prix monte, en moyenne, chaque jour de bourse. Une grande pente = ça monte vite.</li>
        <li><b>R² (régularité)</b> : est-ce que le prix monte en ligne bien droite (proche de 1) ou en zigzags (proche de 0) ?</li>
        <li><b>Volatilité</b> : à quel point le prix bouge beaucoup d’un jour à l’autre. C’est comme des montagnes russes : très volatil = beaucoup de hauts et de bas.</li>
        <li><b>Drawdown</b> : la plus grosse chute qu’il y a eu depuis le point le plus haut. « Jusqu’où ça a pu descendre. »</li>
        <li><b>Liquidité</b> : est-ce facile de vendre vite ? Un titre très échangé se revend facilement. Un titre peu échangé peut être dur à revendre.</li></ul>`,
    e: `<p>Pente = pente de tendance du cours sur la fenêtre, en % par séance ; R² = qualité de l’ajustement de cette tendance ; volatilité = ampleur des variations quotidiennes ; drawdown = repli maximal ; liquidité = valeur échangée par jour en euros (échelle logarithmique entre deux bornes, voir Scores). Fenêtres plus courtes que 3 séances : pas de R² ni de volatilité.</p>` },
  { id: 'fiches', title: 'Fiches titres', icon: 'info',
    b: `<p>Quand vous cliquez sur un titre, vous ouvrez sa « fiche d’identité » : son prix, un graphique, ses notes. « Var. 1J » veut dire : de combien le prix a changé depuis la veille. Pour un ETF, la fiche explique aussi ce qu’il contient et ce qu’il faut surveiller.</p>`,
    e: `<p>« Var. 1J (%) » est la variation du cours entre les deux dernières séances clôturées. Les fiches ETF sont construites automatiquement à partir de la composition publiée.</p>` },
  { id: 'portefeuille', title: 'Portefeuille', icon: 'wallet',
    b: `<p>Un portefeuille, c’est votre « carnet de bord » : la liste de ce que vous possédez. Vous y notez ce que vous achetez et ce que vous vendez, et l’appli calcule pour vous ce que ça vaut et si vous gagnez ou perdez de l’argent. Les prix en dollars sont changés en euros.</p>
        <p class="help-note">Ce carnet ne fait aucun achat réel. C’est juste un outil pour suivre vos affaires.</p>`,
    e: `<p>Les positions sont reconstruites à partir de l’historique des transactions ; les splits sont pris en compte pour les quantités détenues.</p>` },
  { id: 'achats-ventes', title: 'Achats, ventes et lots', icon: 'wallet',
    b: `<p>Chaque fois que vous <b>achetez</b>, vous notez : quel titre, combien, à quel prix. Chaque achat s’appelle un <b>lot</b> (un petit paquet).</p>
        <p>Imaginez que vous achetez des cartes à collectionner :</p>
        <ul><li>Lundi : 10 cartes à 5 € chacune (lot 1).</li><li>Mercredi : 10 cartes à 8 € chacune (lot 2).</li></ul>
        <p>Plus tard, vous <b>vendez</b> 10 cartes. L’appli suppose que vous vendez <b>les plus anciennes en premier</b> : donc les cartes du lundi, achetées 5 €. C’est la règle « premier arrivé, premier sorti » (en anglais FIFO). Il vous reste alors 10 cartes, celles à 8 €.</p>
        <p>Et si vous essayez de vendre des cartes que vous n’avez jamais achetées ? L’appli refuse : on ne peut pas vendre ce qu’on n’a pas. Pensez donc à noter tous vos achats.</p>`,
    e: `<p>Méthode FIFO : les ventes consomment les achats les plus anciens d’abord, quantités suivies à travers les splits. Une vente sans achat connu est refusée.</p>` },
  { id: 'gains', title: 'Gains réalisés et latents', icon: 'trend',
    b: `<p>Il y a deux sortes de gains, comme dans un jeu :</p>
        <ul><li><b>Gain réalisé</b> = l’argent déjà « dans la poche ». Vous avez vendu, c’est fini, c’est sûr. Exemple : vous aviez payé 5 € une carte, vous la vendez 10 € : gain réalisé de 5 €.</li>
        <li><b>Gain latent</b> = un gain « sur le papier ». Vous possédez encore le titre, et son prix actuel est plus haut que ce que vous avez payé. Mais tant que vous n’avez pas vendu, il peut encore changer ! Exemple : payée 8 €, la carte vaut 9 € aujourd’hui : gain latent de 1 €.</li></ul>
        <p>Si le prix est plus bas que ce que vous avez payé, on parle de perte (réalisée ou latente).</p>`,
    e: `<p>Gain réalisé = produit des ventes − coût des lots consommés (FIFO). Gain latent = valeur actuelle − coût des lots restants.</p>` },
  { id: 'performances', title: 'Performances et graphiques', icon: 'chart',
    b: `<p>Les pages <a href="bilan.html">Bilans</a> et Portefeuilles montrent, avec des graphiques, comment votre argent a évolué dans le temps : combien vous avez gagné ou perdu, et ce que vaut votre portefeuille aujourd’hui. Une courbe qui monte = bonne nouvelle ; une courbe qui descend = le contraire.</p>`,
    e: `<p>Les montants sont en euros avec deux décimales. Les graphiques lisent les mêmes séries que les calculs ; aucune donnée d’exemple n’est affichée quand les données manquent.</p>` },
  { id: 'colonnes', title: 'Colonnes et tris', icon: 'cols',
    b: `<p>Les colonnes, ce sont les « colonnes » du tableau (prix, note, secteur…). Dans <a href="mes-colonnes.html">Mes colonnes et tris</a>, vous choisissez celles que vous voulez voir, dans quel ordre, et comment le tableau est trié au départ. Vous pouvez faire un réglage pour l’ordinateur et un autre pour le téléphone. Le bouton « Réinitialiser » remet tout comme au début.</p>`,
    e: `<p>Quatre configurations indépendantes : Explorer / Scores × ordinateur / mobile. Elles sont propres à votre compte ; à défaut, la configuration par défaut de l’administration s’applique.</p>` },
  { id: 'donnees', title: 'Données de marché et fiabilité', icon: 'db',
    b: `<p>Les prix viennent d’un site public, Yahoo Finance. Parfois les données d’un titre sont trop pauvres ou trop vieilles : dans ce cas, l’appli ne lui donne pas de note plutôt que de se tromper. La page <a href="donnees.html">Données</a> montre si les prix sont à jour.</p>`,
    e: `<p>Une note peut être signalée « peu fiable » quand la couverture est sous le seuil commun ; la note est quand même calculée. Qualité de série : ok, insufficient, incomplete, stale, inconsistent_adjustments, break.</p>` },
  { id: 'glossaire', title: 'Glossaire', icon: 'book',
    b: `<dl><dt>Granularité</dt><dd>Durée d’observation (jour, semaine, mois…).</dd><dt>Critère</dt><dd>Minimum à atteindre pour être retenu.</dd><dt>Score</dt><dd>Note de 0 à 100.</dd><dt>Drawdown</dt><dd>Plus forte baisse depuis un sommet.</dd><dt>Momentum</dt><dd>Variation passée du cours, dernier mois exclu.</dd><dt>FIFO</dt><dd>Premier acheté, premier vendu.</dd></dl>`,
    e: `<dl><dt>κ (kappa)</dt><dd>Priorité aux périodes courtes dans les poids automatiques.</dd><dt>R²</dt><dd>Coefficient de détermination de la régression.</dd><dt>Ancrage récent</dt><dd>Pénalité du score complexe quand la période la plus courte est faible.</dd></dl>` },
  { id: 'faq', title: 'FAQ', icon: 'help',
    b: `<details><summary>Pourquoi ma stratégie est « Adaptée » ?</summary><p>Parce que vous avez changé au moins un réglage. Allez dans Mes stratégies pour revenir à la version d’origine.</p></details>
        <details><summary>Les autres voient-ils mes réglages ?</summary><p>Non. Vos stratégies, vos colonnes et vos filtres ne sont que pour vous.</p></details>
        <details><summary>Si je cache des lignes avec un filtre, les notes changent-elles ?</summary><p>Non. Un filtre cache seulement des lignes.</p></details>
        <details><summary>Une note élevée veut-elle dire « achète » ?</summary><p>Non. Une note sert à classer. Elle ne dit pas qu’un achat est une bonne idée.</p></details>`,
    e: `<details><summary>Pourquoi Croissance rapide n’a-t-elle pas de seuil de R² ?</summary><p>Ses critères de recherche historiques ne portent que sur la pente (semaine et mois). Le R² intervient dans son score complexe, pas dans ses critères.</p></details>
        <details><summary>Que fait l’administrateur ?</summary><p>Il maintient les références officielles et les réglages communs ; l’interface d’administration technique ne contient que les outils d’exploitation.</p></details>` },
  { id: 'administration', title: 'Administration (réservé)', icon: 'shield', admin: true,
    b: `<p>Le menu d’administration regroupe : FinanceDatabase, Yahoo Finance, Actions / ETF, Cron, Journaux, Utilisateurs, Réglages.</p>`,
    e: `<p>Les routes <code>admin/*</code> exigent le rôle administrateur côté serveur ; un compte ordinaire reçoit un refus. Les adaptations personnelles passent par les routes <code>my/*</code>, <code>classement-test/*</code> et <code>table-layouts</code>, toujours limitées au compte connecté.</p>` },
];
