# Performance v2 (TWR avec liquidités) — rapport de comparaison

Statut : **moteur validé ; intégré en local uniquement (route PHP + affichage pour les portefeuilles à liquidités). Rien n'est poussé ni déployé.** L'ancien moteur (`engine/analytics/portfolio/performance.py`, Dietz quotidien chaîné) et l'affichage des portefeuilles « ancien modèle » sont inchangés ; aucun portefeuille n'est converti automatiquement.

Code : `engine/analytics/portfolio/cash_performance.py` (calcul pur), `engine/analytics/series/cash_history.py` (adaptateur données), commande CLI `portfolio-cash-performance`, script lecture seule `scripts/compare_performance_v2.py <id>`. Tests : `tests/fast/test_cash_performance.py` (56).

## 1. Vocabulaire : trois choses à ne pas confondre

| Notion | Définition | Unité |
|---|---|---|
| Flux **externe** | capital initial, dépôt, retrait. Seuls à couper la chaîne de rendement. Jamais un gain ni une perte. | € |
| Opération **interne** | achat, vente (argent ↔ titres), dividende (gain), frais (perte). Ne sont jamais des flux quand les liquidités sont suivies. | € |
| Gain | `valeur − apports nets` = réalisé + latent + dividendes − frais de compte. Somme exacte, sans hypothèse. | € |
| Rendement (TWR) | chaîne des rendements quotidiens, flux externes neutralisés. | % |

Jamais « gain ÷ achats » ni « gain ÷ capital investi » : c'est ce qui rendait l'ancien affichage incohérent (somme des contributions ≠ % global).

## 2. Formules

- Valeur `V(t) = liquidités(t) + Σ quantité × cours EUR` ; apports nets `= capital + dépôts − retraits`.
- Gain journalier d'un titre `k` : `q_fin·c_fin − q_début·c_veille − (achats bruts − ventes brutes) + dividendes − frais`. Achat : `q·(c_fin − prix d'exécution)` ; vente : `q·(prix d'exécution − c_veille)`. Somme des titres − frais de compte `= ΔV − flux externes` (identité vérifiée à chaque jour, écart max observé 1e-13).
- Réalisé au prix de revient moyen pondéré (frais d'achat inclus dans le coût, frais de vente déduits du produit).
- **TWR** : jour sans flux externe `facteur = V_fin / V_début` (exact). Jour avec flux : produit des sous-périodes `V(avant flux) / V(après flux précédent)`. L'heure des cours du jour étant inconnue, `V(avant flux)` est évalué avec trois hypothèses (interpolation linéaire entre veille, prix d'exécution et clôture : **valeur centrale** ; titre figé au dernier point connu ; titre déjà au point suivant : **bornes**). Le jour est marqué **« estimé »** seulement si les bornes diffèrent.
- **Contributions** (Cariño) : `gain_k du jour ÷ base du jour × K_i / K_t`, avec `K = ln(1+r)/r`. Somme des contributions (titres, y compris vendus, + frais de compte) `= TWR` exactement.
- **Rendement d'un titre** : chaîne de `gain_k / (q_début·c_veille + achats au prix d'exécution)`. Exact pour un titre isolé (prix d'exécution connus).
- **MWR** (rendement des euros investis) : `Σ F_k (1+g)^(1−u_k) = V_fin`, ramené à la période, jamais annualisé.

## 3. Exemples chiffrés à vérifier à la main

**Ex. 1 — GIBO, rendement du titre (prod, portefeuille principal).** Achat 4 nov. 95,99 USD × 0,8904 = **85,47 €** ; vente 10 nov. 145,0002 USD × 0,8965 = **129,99 €**. Gain réalisé `129,99 − 85,47 = 44,52 €`. Rendement `129,99 / 85,47 − 1 = +52,09 %` — le moteur donne +52,09 % (chaîne des rendements quotidiens du titre = le même nombre). Le rendement du *portefeuille* est autre chose : GIBO y pèse peu.

**Ex. 2 — Jour de vente, 10 nov.** Valeur 9 nov. 421,54 € → 10 nov. 250,60 € ; vente de 129,99 €.
Ancien moteur : vente = retrait pondéré 0,5. Gain `250,60 − 421,54 + 129,99 = −40,95` ; dénominateur `421,54 − 129,99 × 0,5 = 356,55` ; facteur `1 − 40,95/356,55 = 0,88515`.
Nouveau : la valeur est mesurée **à l'heure de la vente** : `V_avant ≈ 379,8 €` (déduit : `0,9038 = 379,8/421,54 × 250,60/(379,8 − 129,99)`), facteur **0,9038** (bornes 0,9029–0,9048). Le jour reste « estimé » car le retrait synthétique de l'ancien modèle a une heure supposée ; l'écart de 0,019 vient de la pondération fixe 0,5 de l'ancien moteur, qui ignore que GIBO valait déjà 129,99 € à la vente.

**Ex. 3 — Scénario liquidités (test et e2e).** 1 000 € ; achat 200 € → 800 ; vente 250 € → 1 050. Réalisé 50 €, gain 50 €, TWR +5 % (`1050/1000 − 1`), aucun flux externe après le capital : exact, pas « estimé ».

**Ex. 4 — Jour avec dépôt (test).** 10 titres de 100 → 110, dépôt de 1 000 € : si le dépôt précède la hausse du jour `+5,00 %`, s'il la suit `+10,00 %`, central `+7,56 %` (`1,05 × 2100/2050`, titre valorisé 105 à midi). Le gain en euros (100 €) est exact dans tous les cas : seul le % est incertain, d'où l'intervalle.

**Ex. 5 — Frais et dividende (test).** Achat de 5 × 100 avec 2 € de frais, cours stable : valeur 998, TWR −0,2 %, gain −2 €. Dividende 5 € sur 10 titres + frais de compte 1 € : gain +4 €, TWR +0,4 %, contributions titre +0,4998 pt / frais −0,1002 pt (somme exacte 0,4 pt).

## 3 bis. Validation sur de vrais portefeuilles à liquidités (6 scénarios)

Données déterministes dans `tests/seeds/cash_scenarios.py`, assertions chiffrées dans `tests/fast/test_cash_scenarios.py` (12 tests), tableau régénérable par `PYTHONPATH=. python scripts/scenarios_performance_v2.py`. Calcul pur : chaque valeur attendue est écrite à la main dans les commentaires des tests.

| Scénario | Capital | Dépôts | Retraits | Apports nets | Liquidités finales | Titres | Positions ouvertes | Valeur finale | Gain € | dont réalisé | dont latent | TWR | Jours estimés |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1. Virtuel 1 000 €, achat 200 €, vente 250 € | 1 000 | 0 | 0 | 1 000 | 1 050 | 0 | aucune | 1 050 | **+50** | 50 | 0 | **+5,00 %** | 0 |
| 2. Scénario 1 + dépôt 500 € + retrait 100 € | 1 000 | 500 | 100 | 1 400 | 1 450 | 0 | aucune | 1 450 | **+50** | 50 | 0 | **+5,00 %** | 0 |
| 3. Achats/ventes successifs, réinvestissement | 1 000 | 0 | 0 | 1 000 | 690 | 440 | A × 4 | 1 130 | +130 | 110 | 20 | +13,00 % | 0 |
| 4. Vente complète, gain conservé | 1 000 | 0 | 0 | 1 000 | 1 300 | 0 | aucune | 1 300 | +300 | 300 | 0 | +30,00 % | 0 |
| 5. Contributions et liquidités | 1 000 | 0 | 0 | 1 000 | 200 | 884 | A × 4, B × 4, C × 10 | 1 084 | +84 | 0 | 84 | +8,40 % | 0 |
| 6. Titre en dollars, 0,90 → 0,95 | 1 000 | 0 | 0 | 1 000 | 1 145 | 0 | aucune | 1 145 | +145 | 145 | 0 | +14,50 % | 0 |

**Ce que chaque scénario démontre**
1. Achat 2 × 100 = 200 € (liquidités 800), vente 2 × 125 = 250 € (liquidités 1 050). Valeur 1 050, gain 50, TWR `1050/1000 − 1 = +5 %`. Aucun flux externe après le capital : rendement **exact**, 0 jour estimé.
2. Le dépôt (+500) et le retrait (−100) changent liquidités et apports nets (1 400) mais ni le gain (50) ni le TWR (5 %). Aucune position ouverte à ces dates : pas d'incertitude horaire.
3. Réinvestissement : A acheté 500, vendu 550 (réalisé +50) ; B acheté 500 avec le produit, soldé 560 (+60) ; A racheté 420, vaut 440 (latent +20). Liquidités `1000 − 500 + 550 − 500 − 420 + 560 = 690`, valeur `690 + 440 = 1130`, gain `50 + 60 + 20 = 130`, TWR 13 %.
4. A acheté 100, vendu 130 (+300), puis tombe à 80 : la valeur reste 1 300, le gain réalisé est conservé, la position est « clôturée » (rendement du titre +30 %, visible seulement pendant sa détention).
5. Gains par titre : A `4 × (121 − 100) = +84`, B `4 × (45 − 50) = −20`, C `10 × (22 − 20) = +20`, total +84 ; liquidités 200 sans rendement. Contributions affichables : A +8,44 pt, B −1,98 pt, C +1,94 pt, liquidités 0 pt, **somme +8,40 %** = TWR.
6. Dollar : prix `10 × (110 − 100) × 0,90 = 90 €` + change `10 × 110 × (0,95 − 0,90) = 55 €` = **145 €** (TWR +14,5 %, rendement du titre en euros `1045/900 − 1 = +16,11 %`).

**Comment lire les pourcentages affichés (proposition de libellés)**
- « Performance du portefeuille » = TWR : le rendement des euros réellement placés sur la période, que vous ayez ajouté ou retiré de l'argent (scénario 2 : +5 % comme au scénario 1).
- « Contribution » d'un titre = sa part du TWR, en **points de pourcentage** : « +8,44 pt » signifie « ce titre a apporté 8,44 points aux +8,40 % du portefeuille ». La somme des contributions (titres, frais) est exactement le TWR ; les liquidités contribuent 0 pt mais freinent le rendement (200 € sur 1 000 € ne travaillent pas). Les parts diffèrent de `gain ÷ capital` (8,40 / −2,00 / +2,00) de moins de 0,1 pt : c'est le lissage de Cariño, qui répartit la capitalisation jour après jour.
- « Rendement du titre » = ce qu'a rapporté ce titre pendant sa détention, rapporté à ce qui y était investi (A +21 %, B −10 %, C +10 %) : à ne pas additionner.
- Gain en euros ≠ rendement en % : scénario 2, gain 50 € mais valeur 1 450 € ; le % reste 5 %.

## 4. Comparatif ancien / nouveau sur la prod (lecture seule, 18 nov. 2026, portefeuille principal)

| | Ancien (Dietz chaîné) | Nouveau (TWR v2, hypothèse « ancien modèle ») |
|---|---|---|
| Rendement | **+19,54 %** | **+21,49 %**, intervalle +20,43 % à +23,16 % (4 jours estimés) |
| Gain en euros | 58,50 € | 58,50 € (identique, = réalisé 44,22 + latent 14,28) |
| Rendement des euros investis (MWR période) | — | +24,42 % |
| Titres ouverts seuls | — | +34,63 % |
| GIBO | — | +52,09 %, contribution +14,59 pt |

Lecture des écarts :
1. **Même gain en euros (58,50 €)** : seule la méthode de rendement diffère.
2. Les jours **sans achat ni vente** (la grande majorité), facteurs identiques à 1e-15 près ; l'écart naît uniquement les jours d'opérations (3 et 4 nov., 10 nov., 15 nov.).
3. L'ancien moteur donne 12 h de poids fixe à chaque transaction ; le nouveau valorise à l'heure. Résultat : +1,95 pt, dont l'essentiel le 10 nov. (Ex. 2) et le 4 nov. (achat GIBO).
4. L'intervalle est large (2,7 pt) car, en hypothèse « ancien modèle », **chaque achat et chaque vente est un flux synthétique** dont l'heure est supposée. C'est précisément ce que supprime le modèle à liquidités : avec un capital initial, une vente n'est plus un flux ; seuls restent incertains les jours de dépôt/retrait. Sur un portefeuille converti ou créé en mode liquidités, l'intervalle se réduit aux jours de dépôt/retrait.
5. L'ancien +19,58 % cité plus tôt et le +20,84 % « aux prix d'exécution » étaient des instantanés/cas de calcul différents (cours du jour, hypothèse de valeur des titres non échangés) ; ce rapport remplace ces chiffres, générés par le script reproductible ci-dessus.

Contrôles intégrés au calcul (prod) : `identity_max_abs_error = 9e-14`, `contribution_sum_max_abs_error = 3e-16`.

Reproduire : `PYTHONPATH=. python scripts/compare_performance_v2.py <id> [--json]` (SELECT uniquement).

## 5. Tests exécutés

- `tests/fast/test_cash_performance.py` : 56 tests, verts. Couvrent : achat/vente/conservation du produit en liquidités ; flux externes sans effet sur le rendement ; jour de flux avec intervalle et gain exact ; multidevise (change d'exécution et variation de change) ; **plusieurs transactions le même jour** (prix d'exécution, PMP) ; ordre de traitement à horodatage égal ; périodes sans position (aucun rendement inventé) ; portefeuille vidé puis recrédité ; frais ; dividendes ; trou de cours (chaîne coupée, aucune liaison) ; MWR (solution analytique) ; **40 historiques aléatoires** : identités `valeur = apports nets + réalisé + latent + dividendes − frais`, `liquidités + titres = valeur`, somme des contributions = TWR ; adaptateur : valeurs et gains identiques à l'ancien moteur (`history.build`) sur mêmes données, mode liquidités avec capital initial.
- `make check` (lint + tests rapides) : 886 verts (884 avant les 2 tests d'adaptateur ; garde de taille de fonction respectée : `analyse` scindée en helpers).
- Comparatif prod lecture seule (ci-dessus). Suite d'intégration et e2e : non relancées pour cette étape (aucun code existant modifié hors enregistrement de la commande CLI).

## 6. Limites et écarts connus

- Jours avec dépôt/retrait : rendement **estimé** (intervalle), jamais présenté comme exact. Le gain en euros reste exact.
- Hypothèse « ancien modèle » : retraits/apports synthétiques aux heures supposées (12 h par défaut) ; c'est une approximation de comparaison, pas un modèle de vérité.
- Dividendes et frais de compte : aucun dans la prod actuelle, validés uniquement par tests.
- Valeur négative (découvert supérieur aux titres) : rendement indisponible (`None`) plutôt qu'inventé.
- Cours manquant : chaîne coupée, pas de liaison artificielle.
- Pas encore de route PHP ni d'affichage : à décider après validation du comparatif.

## 7. Échec intermittent `portfolio-v5` — diagnostic

**Cause identifiée par reproduction : saturation du processeur de la machine de test, pas un défaut de l'application.** Le parcours n'attend que 20 s (`waitFor` par défaut) la zone `.px-zones` ; sous charge, l'ouverture d'une page portefeuille dépasse ce seuil.

| Mesure (sonde `v5probe.cjs`, 10 portefeuilles d'audit, navigateur réel) | Machine au repos | Machine chargée (1 boucle de calcul par cœur) |
|---|---|---|
| Ouvertures mesurées | 120 | 20 |
| Minimum / médiane / p95 / maximum | 0,9 s / 2,1 s / 3,6 s / 5,7 s | 2,8 s / 5,3 s / 20,2 s / **20,2 s** |
| Échec ou page vide | 0 | 0 (mais 1 ouverture à 20,2 s, première page, chargement à froid) |
| Réponses API ≥ 400 ou > 1,5 s | 0 | 0 |
| Erreurs JavaScript | 0 | 0 |

Lecture : aucune requête n'échoue ni n'est lente prise isolément ; c'est le navigateur et le serveur, affamés de CPU, qui rendent la page en 20 s. La première ouverture (démarrage à froid du moteur Python et des caches) est la plus exposée, ce qui correspond à l'échec observé (`Timeout 20000ms … .px-zones`) lors du premier groupe lancé alors que d'autres tâches tournaient en parallèle sur la machine. Ce dernier point (charge concurrente au moment exact de l'incident) est une déduction : l'incident d'origine n'avait pas été journalisé.

Boucle de répétition du parcours complet (avant la sonde) : 4 exécutions sur 10 prévues, **4 réussies** (228 s, 209 s, 204 s, 177 s ; 0 réponse 5xx ; 672 requêtes chacune). Elle a été arrêtée volontairement : la sonde apporte plus d'information (140 ouvertures) et la cause est établie. Aucun processus de test ne reste actif.

Suite possible (non faite, à décider) : passer le délai du premier chargement à 60 s ou réchauffer le moteur avant le parcours, pour que le test ne dépende plus de la charge de la machine.

## 8. Intégration locale (PHP + affichage)

**Route** `GET api.php?r=portfolio/performance&id=<n>` (lecture seule, `app/services/portfolios.php:pf_performance`) → commande moteur `portfolio-cash-performance` (`engine/analytics/series/cash_history.py`, charge utile `compact`). Portefeuille « ancien modèle » : réponse `{"model":"legacy"}`, aucun calcul. Portefeuille à liquidités : valeur, liquidités, titres, apports nets, gains (réalisé, latent, dividendes, frais), TWR (central/bas/haut), indicateur « estimé » par jour, contributions par titre (vendus compris), MWR, contrôles comptables.

**Affichage** (`app/public/assets/pf-perf2.js`, section « Bilan avec liquidités » de la vue d'ensemble, **uniquement** pour les portefeuilles à liquidités) :
1. Valeur totale (liquidités comprises), dont liquidités et titres ; capital initial, dépôts, retraits, apports nets.
2. Gain total, gains réalisés (titres vendus), gains latents (positions ouvertes), dividendes et frais le cas échéant.
3. Performance globale (TWR) avec badge « exact » ou « estimé » (+ intervalle « entre x % et y % »), rendement des euros investis, et explication de la méthode repliée.
4. Graphique unique des contributions par titre (composant partagé `J.financialChart`) : un titre vendu garde sa courbe, plate après la vente ; légende cliquable comme les autres graphiques.
5. Tableau « Détail par titre » (composant commun `J.table`) : statut Ouverte/Vendue, période de détention, rendement du titre, gain, dont réalisé / latent, contribution en points ; ligne Liquidités (0 pt) ; ligne Total = performance globale.

Les graphiques et le bloc de synthèse existants ne sont pas modifiés ni dupliqués.

**Défaut trouvé par le parcours navigateur et corrigé** : à horodatage identique, la vente passait avant l'achat (priorité « vente avant achat » du solde de liquidités), d'où une vente de titres non détenus. L'ordre achats/ventes suit désormais le registre (test unitaire + test d'intégration + parcours).

**`portfolio-v5`** : le premier chargement a 60 s (une seule fois, erreurs JavaScript/HTTP toujours contrôlées) ; le délai global du parcours dans `scripts/e2e_browser.sh` passe de 240 s à 420 s (le parcours dure 177–228 s : la marge était quasi nulle, deuxième cause possible de l'échec).

**Changements visuels antérieurs, sans rapport avec la validation financière** (identifiés, non mélangés) :
- Pastille d'état du suivi → `.badge` (nouveau ton `caution`) : `app/styles/components/badges.css`, `plan-suivi.js`, `pf-home.js`, suppression des CSS `.px-w` et `.ps-state` (`app/styles/{layout,features}/{pf,plan-suivi}.css`).
- « Suivi des positions » en vrai tableau (`J.table.head`, un `<tbody>` par position) : `plan-suivi.js`, `pf-home.js`, `app/styles/*/plan-suivi.css`.
- « Mes portefeuilles » : `J.init` (menu), cartes de « Mes stratégies », icône dans le sous-menu : `mes-portefeuilles.js/.html`, `app.js`.
- Tests e2e adaptés en conséquence (`plan-suivi.cjs`, `portfolio-cash.cjs`).
Le chantier CSS global est suspendu.

## 9. Interface unique des portefeuilles à liquidités

Pour un portefeuille à liquidités, la page affiche quatre cartes (valeur totale, liquidités, gains totaux, performance TWR), **un** graphique (vue « Portefeuille complet » ou « Positions actuelles », modes Valeur / Performance / Gains) et trois onglets (Positions ouvertes, Positions clôturées, Suivi des positions). Les portefeuilles « ancien modèle » gardent leur affichage. Code : `app/public/assets/pf-perf2.js` (cartes, graphique, positions clôturées) et `pf-home.js` (onglets, tableau des positions, suivi). Séries : `engine/analytics/series/cash_history.py` (`_chart`), route `portfolio/performance`.

### 9.1 Vue « Positions actuelles » : performance agrégée

Sous-portefeuille reconstitué **rétrospectivement** : uniquement les titres détenus aujourd'hui, mêmes dates, quantités et prix que les opérations, sans liquidités ni frais de compte. Même moteur (`cash_performance.analyse`), événements fournis par `open_sleeve_events` :

| Cas | Traitement |
|---|---|
| Dates d'achat différentes | un titre n'entre qu'à son premier achat ; son achat est un apport neutralisé |
| Achats supplémentaires | apport neutralisé : seule la variation de cours sur le capital en place compte |
| Ventes partielles | retrait neutralisé ; le gain encaissé reste dans « dont réalisé », le non encaissé dans « dont latent » |
| Titre entièrement vendu | exclu (valeur, gains, courbe) |
| Dividendes d'un titre détenu | encaissés puis retirés : comptés dans le rendement, jamais de liquidités |

Un jour sans opération est exact (valeur du soir ÷ valeur de la veille). Un jour avec achat ou vente est une estimation bornée (cours de l'instant du flux interpolé, bornes cours de la veille / du soir), comme pour le bilan complet.

**Rétrospectif, pas immuable** : si un titre est entièrement vendu demain, il disparaît aussi de cette vue. Ce n'est pas l'historique de ce qui était détenu à chaque date (pour cela : « Portefeuille complet »). Ces pourcentages ne se comparent pas à la performance globale (ni liquidités ni titres vendus).

Distinctions : *rendement d'un titre* (son propre TWR depuis l'achat, non additif) · *contribution* (points du TWR global, additive, titres vendus compris) · *performance agrégée des positions actuelles* (TWR du sous-portefeuille).

### 9.2 Test de référence et intervalle

`tests/fast/test_cash_performance.py`, section « sous-portefeuille » : A (achats puis vente partielle), B (vendu, exclu), C (acheté plus tard). Ordres à 00:00 au cours de la veille, donc exacts :
facteurs 1 · 2100/2000 · 2650/2650 · 2552/2320 · 2652/2552, TWR = **+20,0259 %**, intervalle réduit au point (aucun flux en cours de journée), valeur finale 2 652 €, gain 2 652 − 2 220 €, réalisé 20 € (vente partielle de 3 titres à 110 € pour un PMP de 103,33 €). Un second test montre l'intervalle qui s'ouvre quand un achat a lieu à midi (bornes cours de la veille / du soir d'un autre titre détenu) alors que le gain en euros reste exact.
Sur la copie de démonstration du Portefeuille principal (5 titres détenus) : **+9,83 %**, intervalle **+9,77 % à +10,33 %** (2 jours estimés), valeur 251,22 €, gain latent 20,81 €.

### 9.3 Coupures de courbes : diagnostic

Reproduit sur 112 combinaisons mode / unité / période pour les portefeuilles 1 et 5 : aucune coupure en « Mon investissement » ni en historique journalier. Une seule coupure : « Historique des cours », périodes 5J et 1S, ASO et TTAN, le 05/11/2026 à 18:30. Cause : 5 à 6 créneaux de 15 minutes non collectés ce jour-là (21–22 barres au lieu de 27) ; l'axe réunit les créneaux de tous les titres, d'où une valeur vide à 18:30 pour les deux titres sans barre. Correction (affichage seulement, `fillSessionHoles` dans `pf-home.js`) : un créneau manquant au milieu d'une séance reprend le dernier cours connu, sans franchir une clôture, avec une note. Cours enregistrés, transactions et calculs ne sont pas modifiés.
