# Portefeuilles V3 — graphiques interactifs et conventions financières

## Tableau de bord et périodes

Deux espaces restent disponibles : **Mon portefeuille** et **Historique et gestion**. Le résumé, le portefeuille global, les titres, les contributions, les positions et la surveillance sont affichables/masquables dans Personnaliser. Les préférences sont stockées dans le navigateur, ainsi que l’unité, le type de lecture, les séries masquées et le tri. Les commandes de personnalisation restent accessibles même lorsque toutes les sections sont masquées.

La période principale démarre à Depuis le début et pilote résumé et tableau. Le graphique peut définir une plage agrandie ; ses contributions et son résumé de sélection sont recalculés sur **cette même plage visible**, explicitement datée, sans changer la période principale. Réinitialiser rétablit la plage complète. Un changement de période ou de lecture réinitialise le zoom. Les valeurs courantes et le résultat cumulé restent des références permanentes.

## Résultat personnel et état du titre

La valorisation et les gains restent calculés par `ledger.php`, au **prix moyen pondéré (PMP)**, frais compris et conversions historiques inchangées. Le gain total inclut les ventes. Le pourcentage global = gain / achats cumulés, frais compris. La performance d'une période = gain de la période / (valeur initiale + achats de la période), jamais diminué des produits de vente. Ce ne sont ni des rendements annualisés, ni des TWR/TRI.

L'état du titre décrit séparément les mesures réellement disponibles : tendance sur un mois, momentum 6 mois, moyennes 50/200 séances et volatilité quotidienne sur trois mois. Une plus-value personnelle n'efface pas une tendance défavorable ; une perte ne prouve pas que le marché continue de se dégrader.

Les contributions en euros incluent réalisé et latent et s’additionnent au résultat quand les données sont complètes. Le classement principal utilise les euros, jamais le pourcentage propre au titre. Toutes les contributions, y compris stables, inconnues et titres soldés, restent accessibles à côté du graphique. Les pourcentages de rendement propres aux titres ne s’additionnent pas.

Le gain net indicatif conserve l'hypothèse précédente : gain brut moins 30 % des gains réalisés positifs par année et du latent positif. Son pourcentage utilise les mêmes achats cumulés. Hors PEA, pertes reportables, dividendes et fiscalité personnelle ; ce n'est pas un montant fiscal personnalisé. Aucune liquidité ni aucun dividende n'est inventé.

## Protection des gains : conventions explicites

### Par achat encore ouvert

Les ventes consomment les quantités FIFO ; le coût historique du lot est diminué proportionnellement à la quantité vendue. Les splits ajustent les quantités sans changer ce coût. Le suivi considère **les seules quantités encore détenues**, sur des clôtures corrigées des splits depuis la date propre à ce lot, converties avec le change connu à la date observée (au plus sept jours d'antériorité). Le cours actuel peut compléter les observations. Il ne s'agit pas du plus haut intraday historique de l'instrument.

Pour un lot de coût restant C et de quantité q :

- gain actuel = q × dernier cours en EUR − C ; rendement = gain / C ;
- meilleur gain observé = maximum des q × cours daté en EUR − C ;
- gain positif rendu (points) = max(0, meilleur rendement) − max(0, rendement actuel), borné à zéro ;
- recul du cours = 100 × (1 − cours actuel en devise / plus haute clôture observée en devise).

Exemple 100 → 108 → 104, sans frais/change : meilleur gain 8 %, actuel 4 %, rendu **4 points**, recul **3,7037 %**. Si le cours finit à 90, les 8 points de gain positif ont été rendus ; les 10 % de perte sont affichés séparément, pas présentés comme 18 points de gains qui auraient existé. En devise étrangère, gain personnel et recul du cours peuvent diverger ; le premier inclut frais et change, le second décrit le titre.

### Position agrégée

Le résultat affiché reste au PMP. Pour éviter de sommer des sommets atteints à des dates différentes ou d'utiliser un achat avant son acquisition, la protection agrégée fixe les quantités **actuellement détenues**, prend le coût PMP actuel comme base et compare les observations à partir du **dernier achat encore ouvert**. Les mesures par lot gardent leur date et leur coût FIFO. Les deux références sont affichées dans le détail ; leurs pourcentages ne sont pas substitués l'un à l'autre.

Les coûts restants FIFO sont des données dérivées en mémoire, sans modification du registre ni nouvelle table. Les références ne changent pas lors d'un changement de stratégie.

### Indisponibilité plutôt que faux sommet

Début d'historique non conservé, séances attendues absentes, calendrier non pris en charge, taux historique absent, coût nul/inconnu ou cours absent rendent le suivi du sommet indisponible. Les observations futures sont exclues. Une correction manuelle de split reconnue garde sa valorisation PMP correcte mais le détail de protection par lot est déclaré non comparable, plutôt que d'attribuer un rendement fictif à un achat gratuit. L'historique réel conservé étant borné, un sommet depuis un achat ancien peut rester indéterminé.

## Surveillance explicable, sans nouveau score

- **Normal** : données fiables, aucun signal notable selon les règles disponibles.
- **À surveiller** : alerte `watch` existante ou contexte de dégradation défini par les indicateurs déjà présents.
- **À examiner** : alerte `act` existante ou filet personnel atteint. Ce n'est pas un ordre de vente.
- **Données insuffisantes** : cotation/indicateurs anciens, qualité non fiable ou mesures nécessaires absentes. Des alertes connues restent expliquées, mais aucun diagnostic rassurant n'est produit.

Les seuils de durée/recul et sorties Momentum/MA50 restent ceux des achats/stratégies existants (`alerts.py`). Le Momentum reste en points de pourcentage. Les critères de volatilité/repli maximal reprennent **les plafonds du profil choisi** (`strategy.preset` ou configuration personnelle), sur leurs fenêtres actives. Aucun plafond universel nouveau n'est appliqué : le plafond 1,5 % de volatilité quotidienne de Hausse calme ne s'applique pas à Croissance rapide.

Le signal préventif de contradiction réutilise `signals.contradiction` : repli récent de 5 % ou plus sur 5/21 séances dans une progression de fond d'au moins 10 %, ou rebond d'au moins 10 % dans une baisse de fond d'au moins 10 %. Le repli appelle une surveillance ; le rebond est informatif. Ces seuils existaient déjà dans le moteur et ne changent aucun classement. Sortie du Top 50 : information seulement. La volatilité est contextualisée, sans inventer un « score de risque » ni un stop optimal prédit.

Les raisons identiques sont regroupées en conservant la sévérité la plus forte ; les rappels communs sont comptés. Les réglages sont regroupés par stratégie et règles effectives dans Gestion. Les réglages individuels restent accessibles. Une surveillance entièrement désactivée est indiquée, pas affichée comme un avis favorable.

La fraîcheur reprend `service.expected_close` et `last_collection`, y compris le cas d'un titre peu échangé dont la collecte est à jour. Une quote récente ne rend pas des indicateurs historiques anciens fiables. Aucune règle n'envoie d'ordre.

## Trois lectures et unités compatibles

- **Performance personnelle** : gain après transactions, frais et conversions historiques ; en %, gain / capital engagé propre à chaque série. Le portefeuille global et les titres peuvent être affichés ensemble, avec la même méthode et les mêmes dates ; leurs rendements propres ne s’additionnent pas.
- **Évolution des cours** : toute l’histoire de marché conservée, même avant les acquisitions. En %, variation normalisée depuis une même date (`100 × cours / cours_initial − 100`, équivalent à une base 100 exprimée en variation). En €, chaque cours est converti avec le change connu à la date observée, âgé de sept jours au plus ; ce ne sont pas les conversions de l’achat. Les séries réutilisent `prepare_series` : corrections des splits et éventuels cours ajustés du fournisseur, dans les unités actuelles. Les marqueurs gardent les prix réellement enregistrés dans les unités de la transaction. Une base absente ou une rupture non résolue rend la normalisation indisponible. Le portefeuille global n’a pas de cours boursier unique et n’est pas superposé dans cette lecture.
- **Contribution au portefeuille** : mêmes gains en euros que le moteur ; en %, contribution = `100 × gain_du_titre / capital_engagé_du_portefeuille`. La ligne globale et toutes les contributions complètes s’additionnent alors en points de rendement.

Le classement affiche toujours les contributions réelles, triées par impact **en euros**, avec le poids actuel et la sélection du titre. Son unité suit € / % : euros ou points de pourcentage de rendement global, jamais le rendement propre du titre. Le dénominateur commun = valeur du portefeuille au début + achats pendant la plage, ou achats cumulés depuis un portefeuille vide. Les ventes ne sont pas déduites du dénominateur. Une base nulle ou non valorisable produit une indisponibilité explicite ; aucune division de remplacement n’est inventée.

La variation d’un cours normalisé n’est donc ni une contribution, ni un rendement personnel. Les libellés du graphique et du classement décrivent cette distinction. Les courbes incompatibles ne sont pas superposées sur une échelle monétaire commune.

## Historique et détention

1 semaine = sept jours calendaires ; les mois/années retranchent les mois avec ajustement de fin de mois. Les dates réellement couvertes sont affichées. La fenêtre boursière est indépendante de la première transaction : un achat récent ne tronque plus un an de cours disponibles. Les montants personnels restent limités aux périodes détenues. Les quantités quotidiennes du moteur ajustées des splits interrompent les courbes entre vente totale et rachat ; le résultat réalisé reste dans le total et les contributions.

Une plage entièrement antérieure au premier achat n’a aucun capital personnel engagé : contribution en euros nulle et pourcentage non défini. Les cours antérieurs restent consultables. Un zoom réévalue les gains, les bases et les contributions à ses bornes réelles. À une borne quotidienne, l’état de référence inclut les transactions du jour ; quand la plage couvre le premier jour, les frais initiaux sont inclus depuis un portefeuille vide, comme dans le moteur existant.

Les points de marché et conversions manquants restent absents. La fenêtre graphique affiche sa couverture réelle. « Compléter l’historique du titre sélectionné » appelle, sur demande explicite, les collecteurs quotidiens et intraday existants pour **un seul titre actuellement détenu et autorisé**, avec verrou et délai de quinze minutes partagé par titre. Aucun changement de période, zoom ou sélection ne déclenche de collecte. Le fournisseur peut ne pas disposer des séances demandées ; ni l’historique, ni le change ne sont simulés. La récupération ne modifie aucun classement ni stratégie ; leur maintenance demeure celle du moteur existant.

## Graphique et achats

Le graphique principal utilise **TradingView Lightweight Charts 5.0.9**, livré localement, Apache-2.0, avec licence, NOTICE et attribution/lien visibles. Choix limité au portefeuille : le composant apporte les échelles financières, le zoom molette/pincement, le déplacement et le curseur synchronisé. Les graphiques existants des fiches et de gestion restent disponibles. Aucun CDN ni nouvelle dépendance serveur n’est requis. Voir `app/public/assets/vendor/lightweight-charts/README.md`.

Le wrapper ajoute les commandes zoom/dézoom, déplacement, sélection d’une zone et réinitialisation, les infobulles et les véritables achats. Les lignes verticales sont repositionnées à chaque changement d’échelle ; les dates hors vue sont exclues, sans rabattement sur la première barre. Les achats du même jour sont regroupés. Date, ticker, quantité, prix, devise, frais et premier achat/complément sont accessibles au clavier et au toucher. Leurs unités restent celles de la transaction, même après split.

Les cases des séries masquent/affichent portefeuille ou titres ; les étoiles mettent plusieurs titres en évidence simultanément, avec contraste conservé. Le clic sur contribution/tableau relie courbe, achats et détail. Le zoom, la normalisation en %, l’isolement des séries et la sélection de plage permettent d’examiner une forte variation sans perdre les autres positions dans le tableau.

## 1 jour : données réelles de quinze minutes

L’historique charge les dernières barres conservées par titre, sans dépendre d’une fenêtre arbitraire à partir d’aujourd’hui. La date de la dernière séance enregistrée est affichée : elle n’est jamais assimilée automatiquement à une séance actuelle.

Pour les positions dont les quantités n’ont pas changé pendant **ou après** cette séance, variation indicative = quantité × variation du prix observé × change quotidien de la séance. Le % propre utilise la valeur initiale de cette position. Les contributions en points utilisent la valeur initiale du portefeuille, lorsque toutes ses lignes sont valorisables. Les frais anciens ne sont pas refacturés à chaque barre. Le change est figé pour la séance : aucune variation de change intraday n’est prétendue connue.

Les barres doivent exister : pas de remplissage par la dernière clôture ou par le prix d’achat. Une cotation absente à l’origine commune rend le calcul concerné indisponible ; un trou ultérieur demeure null. Une transaction à la date de séance ou ultérieure, ou un split postérieur, empêche de rejouer les quantités actuelles comme si elles étaient historiques. La ligne concernée et le résultat global exact sont indisponibles ; les titres sans mouvement et les cours de marché restent consultables. Ces limites sont affichées par titre, avec les absences de barres ou de taux daté exploitable. Le 1J n’est plus systématiquement désactivé.

## Validation reproductible

`make fast`, `make integ` en base locale jetable, puis `portfolio_audit_seed.py` avec `JIGO_TEST_DATABASE=1`, hôte 127.0.0.1 et base autorisée. Les trois suites navigateur utilisent Chromium à 1280, 390 et 375 px :

- `portfolio-interactive.cjs` : année avant achat, modes/€, %, dénominateur des contributions, zoom molette et commandes, sélection de zone, navigation/réinitialisation, repères après zoom, achats groupés, masquage, plusieurs mises en évidence, préférences persistantes, 1J fiable/transactions/absences, variation extrême, récupération explicite limitée et pincement tactile.
- `portfolio-audit.cjs` : 75 combinaisons et les régressions financières (PMP/FIFO/splits, pourcentages après ventes, Momentum, absence de cours, géométrie mobile, intraday réel).
- `portfolio-cockpit.cjs` : résumé/tableau synchronisés, gestion/CSV, lots et réglages préservant les coûts, cours approfondis, positions soldées, données partielles et portefeuille vide.

Les tests rapides ont des oracles indépendants pour le FX daté, les variations intraday, les transactions/splits invalidants, le dénominateur commun et une vue avant acquisition. Les tests API réels vérifient la séance et les protections de la récupération ciblée sans appel fournisseur. Le smoke financier de GitHub Actions conserve Explorer, ETF, comptes, deux espaces et absence de débordement. Aucune fixture ne touche à la production.

## Préparation des indicateurs lors d’une livraison

Le contrôle strict de livraison compare les mesures mémorisées aux calculs actuels des titres de référence. Si ce cache ne correspond plus aux cours enregistrés, la préparation invoque une fois le traitement **metrics** existant, sous ses verrous habituels, puis exige à nouveau la même validation en lecture seule, avec la même tolérance. Aucun cours, compte ou enregistrement de transaction n’est réécrit ; aucun fournisseur n’est appelé par ce recalcul. Un échec persistant bloque toujours la livraison et conserve le retour arrière automatique. Les diagnostics publics ne contiennent que le symbole de référence, la fenêtre et le champ en défaut.
