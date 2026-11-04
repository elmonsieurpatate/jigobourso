# Portefeuilles V3 — graphique simple et vie des investissements

## Organisation et périodes

Deux espaces : **Mon portefeuille** et **Historique et gestion**. La période principale démarre à Depuis le début et pilote le résumé, les contributions et le tableau. Les références valeur actuelle / résultat total restent permanentes. La personnalisation du tableau de bord, l’unité et le tri restent conservés dans le navigateur.

Trois onglets immédiatement accessibles :

- **Mon portefeuille**, par défaut en % : performance hors achats/ventes, chaînée entre observations. En € : gains/pertes effectivement gagnés, ventes comprises. Ces deux unités ne sont pas deux mesures identiques.
- **Mes gains/pertes** : résultat personnel par instrument, frais, change et ventes compris, calculé à partir du registre et de l’historique existants.
- **Cours des actions** : historique boursier avant et après acquisition ; aucune performance personnelle n’est inventée avant l’achat. En % : cours normalisés à une origine commune (0 % = base 100), hors change ; en € : cours convertis au taux historique daté (au plus sept jours).

La période commune utilise sept jours calendaires pour la semaine ; mois/années retranchés avec ajustement des fins de mois. Les dates réellement couvertes sont affichées. Les valeurs manquantes restent absentes.

## Graphique local sans bibliothèque de trading

`financial-chart.js` dessine un SVG redimensionnable, sans dépendance externe, sans TradingView ni commandes de trading. Les autres graphiques existants des fiches restent disponibles.

Un glissement horizontal sélectionne directement la zone à examiner, à la souris ou au toucher. Un double-clic rétablit la période principale (touche Home au clavier). Les dates visibles sont affichées. Le zoom est **uniquement visuel** : aucune nouvelle base de calcul, aucun reclassement des contributions. Changer la période principale change les références financières de toute la page.

Le clic sur un ticker, une courbe, une contribution ou une position met le titre au premier plan, atténue les autres courbes et souligne ses transactions. Un clic sur la sélection ou dans une zone libre rétablit la vue globale (Échap également). Les six titres restent présents même lorsque leurs courbes se superposent. La sélection ajuste explicitement l’échelle à la courbe choisie : le libellé signale que d’autres courbes peuvent sortir du cadre. Aucun changement caché d’unité ou d’échelle logarithmique.

Les transactions sont issues du même registre : trait vert achat, rouge vente, marqueur mixte si les deux ont lieu le même jour. Les dates sont regroupées sans déplacement artificiel des événements hors vue. Infobulle au survol, au clic ou au focus : date, ticker, sens, quantité, prix et devise réellement saisis, frais en euros, change, résultat réalisé au PMP pour les ventes. Un lien ouvre la transaction exacte dans l’historique. Les prix des transactions restent dans leurs unités originales après split.

## Calculs et contributions

Aucun moteur comptable parallèle : `ledger.php` reste la référence pour PMP et résultats réalisés, `open_lots` pour FIFO, Python pour les historiques, les mêmes conventions pour splits et FX.

- Résultat cumulé = réalisé + latent ; rendement cumulé = résultat / achats cumulés, frais compris.
- Sur une période = différence de gains cumulés ; dénominateur = valeur au début + achats de la période, sans soustraire les ventes. Au premier jour connu, départ d’un portefeuille vide, frais initiaux inclus.
- Les courbes personnelles en % utilisent le capital propre de chaque position. Les rendements individuels ne s’additionnent pas.
- Le classement en € utilise le résultat réel par titre ; en % il affiche les **points de contribution** = 100 × gain du titre / capital engagé commun du portefeuille. Il affiche séparément le rendement propre de la position et son poids actuel. Une base nulle/inconnue reste indisponible.

Le classement conserve toutes les positions ayant contribué, y compris les titres soldés, et trie selon l’impact en euros (pas selon le rendement individuel). Les pertes principales sont identifiées. Le total des contributions calculables reste cohérent avec le résultat du moteur. Une donnée manquante est explicitement signalée.

Le résultat réalisé reste visible après liquidation, dans le résumé, le classement et la consultation des positions clôturées. Une courbe personnelle peut conserver le résultat réalisé après liquidation ; elle ne prétend pas représenter une exposition au marché pendant cette période. Les périodes de détention séparées permettent de distinguer liquidation et rachat.

## Performance hors achats et ventes

Le résumé distingue désormais **gains en euros**, **rendement sur les achats cumulés** et **performance hors achats/ventes**. Réalisé, latent, capital restant et fiscalité indicative conservent les calculs du registre. Les contributions en euros s’additionnent au gain ; les points de contribution sur capital engagé s’additionnent au rendement sur capital, **pas** à la nouvelle performance chaînée.

`performance.py` consomme en lecture seule les valorisations non arrondies du même historique et les mêmes transactions converties en euros. Il ne modifie ni une opération, ni un cours, ni un taux enregistré. Les achats (frais compris) sont des entrées dans la poche de titres ; le produit net des ventes en est une sortie. L’application ne tient pas un compte espèces : ce n’est pas un rendement de compte complet avec liquidités ou dividendes.

Faute de valorisation de tout le portefeuille immédiatement avant chaque opération, il serait faux d’annoncer un TWR exact. La méthode utilisée est le **Modified Dietz chaîné quotidiennement** : pour chaque intervalle, `r = (valeur_fin − valeur_début − somme_flux) / (valeur_début + somme(poids × flux))`, puis multiplication des `1+r`. Le poids correspond à la fraction de l’intervalle restant après l’heure UTC enregistrée de la transaction, avec frontières de jour UTC pour les valorisations quotidiennes. Un intervalle sans mouvement est le rendement des deux valorisations observées ; les jours de mouvement sont **estimés**, et cette limite est affichée.

À l’entrée depuis une poche vide, le capital de référence est le total des achats : on ne double pas artificiellement une variation initiale parce qu’un premier achat a été saisi à midi. Une liquidation complète sans nouvel achat utilise la valeur de départ et le produit net de vente. Une poche vide sans mouvement garde un facteur neutre ; un rachat ultérieur conserve le rendement historique tout en commençant une nouvelle exposition. Les frais restent des dépenses. Un dénominateur non positif, une valorisation absente ou un historique de change invalide ne produit pas un rendement inventé.

Les cours et taux vieux de plus de sept jours rendent les observations concernées indisponibles pour cette nouvelle performance, sans modifier les anciens totaux. Un trou n’est jamais franchi artificiellement dans la performance depuis le début ; une période ultérieure entièrement couverte peut être rebased à sa propre origine. Les splits restent traités par l’historique existant (prix et quantités dans des unités cohérentes).

Exemple testé : achat 200 €, valeur 210 € (+5 %), nouvel achat 200 € à prix inchangé. Valeur 410 €, gain 10 €, rendement sur achats 2,5 %, performance hors mouvements toujours 5 %. Une variation de marché ou des frais le même jour peuvent légitimement changer cette dernière : seule la dilution mécanique par l’achat est neutralisée.

Le graphique principal n’ajoute aucun mode : % montre cette performance, € garde le gain. La période globale rebase les rendements chaînés ; le zoom reste visuel. Le 1J réutilise l’estimation intrajournalière existante uniquement quand elle est calculable, avec ses limites sur transactions, FX et données absentes.

## Achats, ventes et traçabilité

Acheter / Vendre sont accessibles dans chaque ligne et dans la fiche. Le formulaire existant est prérempli avec le titre ; Vendre reprend la quantité actuelle, contrôlée à la date choisie. Ce sont des écritures de suivi, jamais des ordres à un courtier.

L’aperçu `tx/preview` est une simulation en lecture seule. Il appelle le **même** `portfolio_valuation` sur une copie du registre jusqu’à la transaction candidate et le même `validate_transaction_history` sur **tout** le registre, opérations ultérieures comprises. Il ne crée aucune transaction et ne remplace pas la validation sérialisée à l’enregistrement. Les splits postérieurs à la date simulée ne modifient pas la quantité annoncée à la date de vente. L’aperçu présente quantité détenue/restante, produit net, coût attribué PMP, résultat et pourcentage (gain/coût sorti), change. Frais en euros ; coût/FX incomplet bloque l’aperçu plutôt que d’inventer une plus-value.

Plusieurs achats d’un instrument restent une seule position et plusieurs lots FIFO avec leurs réglages existants. Le tableau permet Positions ouvertes / Positions clôturées / Toutes. La fiche conserve tous les achats et ventes, ainsi que les périodes de détention (dates, achats, produit net, frais, réalisé), sans renommer ou dupliquer l’instrument après rachat.

Historique et gestion conserve les modifications/suppressions contrôlées, l’export CSV, les ventes, lots et réglages, répartitions et analyses ETF. Les transactions sont filtrables par titre, achat/vente et dates, avec résultat réalisé par vente et totaux sur les opérations filtrées. Les liens graphique ↔ transaction utilisent les identifiants du registre.

La récupération ciblée de l’historique reste accessible dans la fiche d’une position ouverte liée au catalogue. Elle réutilise les collecteurs existants avec verrou et délai de quinze minutes par titre. Aucun zoom, changement de période ou sélection ne déclenche de collecte.

Le gain net d’impôt conserve l’estimation forfaitaire existante, non personnalisée. Les diagnostics et stratégies Explorer restent inchangés.

## 1 jour : données réelles de quinze minutes

L’historique charge les dernières barres conservées par titre, sans dépendre d’une fenêtre arbitraire à partir d’aujourd’hui. La date de la dernière séance enregistrée est affichée : elle n’est jamais assimilée automatiquement à une séance actuelle.

Pour les positions dont les quantités n’ont pas changé pendant **ou après** cette séance, variation indicative = quantité × variation du prix observé × change quotidien de la séance. Le % propre utilise la valeur initiale de cette position. Les contributions en points utilisent la valeur initiale du portefeuille, lorsque toutes ses lignes sont valorisables. Les frais anciens ne sont pas refacturés à chaque barre. Le change est figé pour la séance : aucune variation de change intraday n’est prétendue connue.

Les barres doivent exister : pas de remplissage par la dernière clôture ou par le prix d’achat. Une cotation absente à l’origine commune rend le calcul concerné indisponible ; un trou ultérieur demeure null. Une transaction à la date de séance ou ultérieure, ou un split postérieur, empêche de rejouer les quantités actuelles comme si elles étaient historiques. La ligne concernée et le résultat global exact sont indisponibles ; les titres sans mouvement et les cours de marché restent consultables. Ces limites sont affichées par titre, avec les absences de barres ou de taux daté exploitable. Le 1J n’est plus systématiquement désactivé.

## Préparation des indicateurs lors d’une livraison

Le contrôle strict de livraison compare les mesures mémorisées aux calculs actuels des titres de référence. Si ce cache ne correspond plus aux cours enregistrés, la préparation invoque une fois le traitement **metrics** existant, sous ses verrous habituels, puis exige à nouveau la même validation en lecture seule, avec la même tolérance. Aucun cours, compte ou enregistrement de transaction n’est réécrit ; aucun fournisseur n’est appelé par ce recalcul. Un échec persistant bloque toujours la livraison et conserve le retour arrière automatique. Les diagnostics publics ne contiennent que le symbole de référence, la fenêtre et le champ en défaut.

## Validation reproductible

`make fast`, `make integ` sur la base jetable, puis `portfolio_audit_seed.py` avec `JIGO_TEST_DATABASE=1`, hôte 127.0.0.1 et base autorisée. Tests Chromium desktop 1280 px et mobile émulé 390 / 375 px :

- `portfolio-interactive.cjs` : absence de TradingView, trois onglets, six courbes dont chevauchements exacts, sélection naturelle et échelle explicite, zoom direct/double-clic, glissement tactile réel, classement et résumé invariants pendant le zoom, périodes/unités, cours avant achats, 1J réel/transactions/données absentes, achat complémentaire, vente totale avec aperçu et refus du dépassement, clôture, historique filtré, repères liés à l’historique, rachat après liquidation.
- `portfolio-audit.cjs` : 75 combinaisons avec oracle indépendant des gains/dénominateurs, PMP/FIFO/splits, pourcentages après ventes, Momentum, cours manquants, géométrie mobile.
- `portfolio-cockpit.cjs` : navigation, résumé/tableau, gestion/CSV, lots et stratégies par achat, graphiques approfondis, positions soldées, données partielles et portefeuille vide.

Les tests API d’aperçu vérifient l’absence d’écriture, le PMP distinct du FIFO, les frais/FX, la quantité à la date malgré un split ultérieur, la validation des opérations futures, la modification d’une vente et l’isolation des utilisateurs. Les cycles clôture/rachat conservent le réalisé. Aucun test ne modifie les données de production.
