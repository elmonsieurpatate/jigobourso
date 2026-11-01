# Méthode de calcul (V2)

## Mesures sur une fenêtre de n séances (n+1 clôtures)
Toutes sur le logarithme du cours : une hausse de 10 % suivie d'une baisse de 10 % ne s'annule pas, et un titre à 5 € se compare à un titre à 500 €.

| Mesure | Définition |
|---|---|
| Pente | pente de la régression de ln(cours) sur le temps, en % par séance : 100·(e^b − 1) |
| R² | part de la variance de ln(cours) expliquée par cette droite (0 à 1). Mesure la **régularité** de la hausse |
| Performance | variation entre la première et la dernière clôture, en % |
| Volatilité | écart-type des variations quotidiennes de ln(cours), en % par séance (≥ 3 séances) |
| Repli maximal | plus forte baisse depuis un sommet de la fenêtre, en % |
| ER (efficacité) | rendement net / distance parcourue, en ln : +1 = montée sans repli, 0 = aller-retour, négatif = baisse |

Abandonné par rapport à l'ancien moteur : **accélération** (définition ambiguë), **exposant k** du classement. Les cours bruts et ajustés ne sont jamais mélangés (ajustés si toute la série en a). Les clôtures viennent de Yahoo Spark, déjà corrigées des splits.

## Données douteuses
Un saut de cours d'une séance à l'autre de plus de ×1,6 (ou ÷1,6), sans split connu, est une **rupture** : aucune fenêtre qui la traverse n'est évaluée, le titre est « non évaluable » sur ces périodes. Série trop courte, dernière clôture plus ancienne que celle de la place : « non évaluable » (jamais « écarté »).

### Fenêtres et séances absentes
Une fenêtre de `n` séances est désormais formée des `n+1` dates de clôture attendues par le calendrier de la place, et non des `n+1` dernières lignes présentes en base. Les calendriers Xetra, Euronext, Londres, les places américaines et les autres places prises en charge excluent week-ends et jours fériés propres au marché. Une place sans calendrier pris en charge est déclarée non évaluable : le moteur ne suppose pas qu'elle ouvre du lundi au vendredi.

La pente et le R² régressent sur l'indice réel de chaque séance attendue. Ils restent calculables si au moins `ceil(80 % × clôtures attendues)` sont présentes et si au moins trois points sont disponibles. Ce minimum laisse passer une séance manquante isolée sur une courte fenêtre (5/6) sans compresser le temps; il n'accepte pas les fenêtres extrêmement creuses. Il ne modifie aucun seuil de stratégie. La performance entre bornes exige les deux clôtures de bord. Le cas WHCA.AS atteint tout juste ce plancher sur les 64 dernières clôtures (52/64); son R² sur ces dates est 0,469, sous le seuil existant de 0,556 : le titre échoue donc au critère de régularité au lieu d'être artificiellement retenu.

La performance reste calculable entre les deux bornes si elles existent. En revanche, volatilité quotidienne, repli maximal et ER décrivent un chemin : ils sont indisponibles dès qu'une séance attendue manque, car le mouvement à l'intérieur de l'intervalle absent est inconnu. Aucune clôture n'est recopiée et aucune interpolation n'est faite. Les moyennes mobiles et la variation du jour exigent elles aussi les clôtures précises de leurs séances calendaires.

## Verdicts
- **Retenu** : tous les critères actifs de toutes les périodes actives sont satisfaits.
- **Écarté** : au moins un critère mesuré échoue (même si une autre mesure manque).
- **Non évaluable** : rien n'échoue, mais une mesure manque.
- **Exclu** (catalogue/préfiltre, pas la stratégie) : jamais évalué, jamais recommandé.
Chaque verdict conserve la liste de ses raisons (période, critère, valeur, seuil, résultat).

## Classement
Pour chaque période active, percentile du score (pente, performance, régularité ou −volatilité selon le mode) parmi les titres **retenus du même groupe** (actions ou ETF) ; score final = moyenne pondérée des percentiles (0–100). Départage : symbole.

## Stratégies de départ (propositions, modifiables)
Niveaux de pente = temps pour doubler à ce rythme : doux 8 ans (0,034 %/séance), modéré 4 ans (0,069 ≈ +19 %/an), fort 2 ans (0,138), très fort 1 an (0,276 %/séance = 100·(2^(1/252)−1) ≈ +100 %/an). Régularité par résidu de la droite : souple (R² ≥ 0,56), équilibrée (≥ 0,75), stricte (≥ 0,89).
- **Croissance régulière** : mois et trimestre, pente modérée (≥ 0,069 %/séance), R² souple (≥ 0,56). Classement par régularité. → 191 actions et 67 ETF retenus (≈ 4 %).
- **Croissance rapide** : semaine (pente très forte, performance ≥ 0) et mois (pente très forte, performance ≥ 12 %). Classement par performance. → 389 actions, 11 ETF (≈ 8 %).
- **Rebond** : semaine et mois en hausse douce (R² souple) alors que le semestre n'a pas progressé de plus de 10 %. Classement par pente. → 196 actions, 497 ETF.
- **Hausse calme** : mois et trimestre, pente douce, R² souple, volatilité ≤ 1,5 %/séance (≈ 24 % annualisée), repli ≤ 20 %. Classement par stabilité. → 38 actions, 45 ETF.

Calibrage du 28/10/2026 sur 9 700 titres réels. Avec les seuils initiaux, « régulière » ne retenait que 52 actions (R² 0,75 sur deux périodes) et « calme » 4 : trop peu pour offrir un choix. Variantes testées : voir l'historique du calibrage dans ce paragraphe ; les réglages restent modifiables par l'utilisateur.

## Stratégies « Momentum 6 mois » et « Momentum 12 mois » (essai, 31/10/2026)

- **Mesure** : variation du cours, en %, entre J−126 et J−21 séances (6 mois) ou entre J−252 et J−21 séances (12 mois). Le dernier mois est volontairement ignoré. Aucun seuil : seul le rang compte (percentile parmi les titres retenus du même groupe, actions et ETF classés séparément).
- **Fiabilité** : la mesure utilise le calendrier de la place (127 ou 253 séances attendues). Une clôture absente à l'une des deux dates, un historique trop court ou une rupture de cours non expliquée après le début de la fenêtre rendent le titre « non évaluable » : jamais d'estimation, jamais de cours futur.
- **Même définition que les tests** : ce qui est calculé est le signal `mom_6_1` / `mom_12_1` de `scripts/backtest_walkforward.py` (rapport `c[-22] / c[-127] - 1` et `c[-22] / c[-253] - 1` sur les clôtures visibles).
- **Stockage** : `series_state.momentum_6m` et `series_state.momentum_12m`, recalculés avec les autres indicateurs (migrations additives `20261031_momentum_6m.sql` et `20261101_momentum_12m.sql`).
- **Ce que l'historique a montré** (titres encore cotés aujourd'hui, périodes déjà consultées, donc à lire avec prudence) : le classement du Momentum 6-1 a présenté un avantage moyen sur l'ensemble des titres négociables, qui diminue quand la liquidité exigée augmente et après frais (excès net d'environ +0,5 point par mois pour un rééquilibrage mensuel, non établi statistiquement) ; pertes brutales possibles (mois à plus de −25 %, baisses de plus de 50 % depuis un sommet) ; sélections concentrées sur des titres volatils et sur un même pays. Le Momentum 12-1 donne des résultats voisins, sans différence statistiquement établie avec le 6-1. **Aucune performance n'est promise** ; les profils sont signalés « essai » dans l'interface et le suivi réel (page Suivi, 21 et 63 séances) servira à les confirmer sur des observations nouvelles.
- **Les quatre profils existants ne changent pas** (empreintes vérifiées par test).

## Pastilles, filtres de niveau et résumé du profil
Information seulement : rien de ce qui suit n'entre dans un score, un classement, un critère ou un filtre de stratégie.
- **Période des pastilles.** Régularité (R²) et volatilité/repli se mesurent sur la période de la stratégie active (la plus longue période cochée, ramenée à 1 semaine, 1 mois, 3 mois, 6 mois ou 1 an) : la pastille l'indique (« Régulière · 1 mois »). La négociabilité se mesure sur une autre durée, indépendante de la stratégie : volume moyen 3 mois × cours (« Facilement négociable · 3 mois »).
- **Filtres Régularité / Volatilité / Négociabilité** (Explorer, filtres avancés). Listes à choix multiple comme Pays et Catégorie : rien de coché = tout (même chose que tout cocher). Niveaux = ceux des pastilles (vert, orange, rouge, inconnu), avec leurs effectifs. Ils **masquent seulement**, après le classement, comme le filtre « Titres facilement négociables » : rang et score du catalogue inchangés, ordre relatif inchangé ; un titre retrouvé par son symbole ou son ISIN exact n'est jamais masqué. Ils se cumulent entre eux et avec les autres filtres. Coût : ≈ 90 ms pour les 9 600 titres.
- **Résumé du profil** (fiche d'un titre). « Points forts », « Points de vigilance » et une appréciation descriptive : **Très favorable, Favorable, Mitigé, Défavorable, Indéterminé**. Ce n'est ni une note chiffrée, ni une consigne d'achat ou de vente. Règles, dans l'ordre :
  1. *Indéterminé* : tendance non mesurée sur la période, historique court, ou au moins deux des trois pastilles inconnues (l'inconnu reste inconnu).
  2. *Défavorable* : courbe en baisse sur la période, ou trois risques importants (rouges) ou plus.
  3. *Mitigé* : pas de tendance nette, ou un à deux risques importants, ou une tendance récente qui contredit celle de fond, ou au moins deux points de vigilance (oranges).
  4. *Très favorable* : hausse forte (pente ≥ « fort », temps pour doubler ≤ 2 ans) et régularité, volatilité, négociabilité toutes vertes, aucun autre point de vigilance, aucune pastille inconnue.
  5. *Favorable* : le reste des cas en hausse, avec au plus un point de vigilance.
  Un risque important (rouge) interdit donc « Favorable » et « Très favorable », même pour une très forte hausse. Une hausse ≥ 100 % sur la période est signalée comme point de vigilance (un mouvement aussi rapide peut se retourner vite). La rupture de cours est un risque important ; un historique incomplet ou un cours ancien un point de vigilance.
  *Tendance récente contre tendance de fond* : d'après les performances déjà mesurées sur 1 semaine, 1 mois, 3 mois, 6 mois et 1 an, on signale un repli récent (≤ −5 % sur 1 mois ou 1 semaine) dans une hausse de fond (≥ +10 % sur une période plus longue), ou un rebond récent (≥ +10 %) dans une baisse de fond (≤ −10 %). Sans mesure de fond, rien n'est affirmé. Les avis des analystes n'entrent pas dans l'appréciation.

## Préfiltre de liquidité (réglable en Administration)
Cours ≥ 2 € ; liquidité (cours × volume moyen 3 mois, en euros) ≥ 1 M€/jour pour une action, ≥ 250 k€/jour pour un ETF. Sans cotation Yahoo : pas de décision (le titre n'est ni collecté ni recommandé). Exemple : DVDG.DE, 131 titres/jour à 42 € ≈ 5 520 €/jour → exclu.

## Cotation principale (règle R1)
Place d'origine (pays de l'émetteur) si le produit y est coté ; sinon plus forte liquidité en euros ; départage : devise euro, puis ordre alphabétique. Exemple : SAP → Xetra (SAP.DE).

## Collecte
Tick toutes les 15 minutes : barres de 15 min des places ouvertes (+ dernier créneau), clôtures quotidiennes une fois la séance publiée (30 min après la fermeture). Nuit (02 h UTC) : Quote, taux de change, préfiltre, cotation principale, mesures, détection/réparation des trous, rétention (580 jours / 20 séances). Un jour sans aucune barre pour une place est un jour férié, pas un trou.

**Clôtures manquantes.** La collecte quotidienne utilise le point d'accès groupé « spark » de Yahoo, qui omet parfois des jours au milieu de l'année ; le point d'accès « chart » (un titre par appel) les possède. L'étape d'entretien « Clôtures manquantes » interroge « chart » pour les titres dont l'année est incomplète (`series_state.coverage_252 < 1`), les moins troués d'abord, par lots de 150 (60 s maximum, arrêt au premier 429, un même titre n'est repris qu'après 30 jours). Elle n'ajoute que les jours absents et réglés (`INSERT IGNORE`) : une clôture existante n'est jamais modifiée. Les titres qui deviennent complets deviennent évaluables aux calculs suivants (leurs rangs peuvent changer). Administration → carte C → « Combler les clôtures manquantes » traite d'un coup tout le catalogue (sans plafond ni délai), puis recalcule les indicateurs ; relançable si Yahoo limite les appels. Mesure sur 120 titres incomplets : 302 clôtures ajoutées, 77 titres complets, 36 s ; les titres à plus de 5 trous sont surtout de vrais manques de Yahoo.

## Ordre de la recherche (Explorer et fiche)
1. Univers : toutes les cotations éligibles (`v_recommendable` : sélectionnées et principales). Jamais une cotation exclue, quels que soient les critères ou les filtres.
2. Filtres de l'utilisateur (type, place, pays, catégorie, PEA, détenus, place ouverte, budget, prix, volatilité et repli maximaux, volume, données à jour) : ils déterminent les titres examinés. Les filtres numériques utilisent les mesures de la plus longue période active.
3. Évaluation de ces titres selon la configuration réellement choisie (périodes, seuils, filtres techniques). Un profil prédéfini ne fait que préremplir cette configuration : modifiée, elle est appliquée telle quelle (`name` = `custom`). « Recherche libre » = aucun critère de départ.
4. Classement : rang et score sont des percentiles parmi les titres retenus de la sélection, par groupe (actions / ETF). Changer les filtres change donc le classement ; le score minimum s'applique après.
5. Pagination, uniquement après les étapes précédentes. Les nombres « titres examinés sur N » et « résultats » sont affichés.
La fiche d'un titre reçoit la même configuration et les mêmes filtres (depuis l'Explorer : `titre.html?src=explorer`) ; elle annonce « Verdict calculé selon … » et permet de choisir un profil ou la stratégie d'un portefeuille. Sans configuration transmise, le réglage par défaut est annoncé comme tel.
Recherches enregistrées : critères + filtres + tri (`saved_searches`).

## Limites connues des données et des calculs (audit fonctionnel du 29/10/2026)
- **Rendements hors dividendes.** Les clôtures viennent de Yahoo (Spark) : ajustées des splits par Yahoo, pas des dividendes (`adj_close_px` reste vide). Un fonds ou une action qui distribue est donc désavantagé par rapport à une part de capitalisation de même performance totale.
- **Splits.** Les cours de Yahoo (Spark et Chart) ne sont pas toujours ajustés des splits : pour certains titres (constaté : DHY, TACK) le saut reste dans les données et le split est déclaré à part (`events.splits` de l'API Chart). `adj_close_px` reste donc vide et ne sert pas à corriger. Un saut de cours qui ressemble à un ratio usuel (×2, ÷10, ×3/2…) est noté dans `split_log` ; Yahoo est ensuite interrogé : un split déclaré à la même date (± 5 jours) dont le ratio explique le saut (± 15 %) est confirmé et écrit dans `corporate_events` ; le calcul des séries divise alors les clôtures antérieures par ce ratio. Sans déclaration, le saut est un « vrai mouvement » : rien n'est corrigé et le titre reste « non évaluable » sur les fenêtres qui le traversent (seuil : variation d'une séance au-delà de ×1,6 ou ÷1,6).
- **Portefeuilles et splits.** Un split ou un regroupement confirmé par le fournisseur (`split_log`, statut « confirmed ») est appliqué automatiquement par le registre : à la date de l'événement, la quantité détenue est multipliée par le ratio, le coût total ne change pas, et une vente d'après-split est contrôlée sur la quantité ajustée. Une correction faite à la main avant (achat à prix 0 à partir de la date du split) est reconnue et n'est pas comptée deux fois. Dividendes et liquidités ne sont pas gérés.
- **Totaux d'un portefeuille et du Bilan.** Coût, plus-values et gains ne portent que sur les positions calculables : une transaction sans taux de change historique (ou une vente supérieure à la quantité détenue) exclut **ce titre** de ces totaux, signalé nommément, sans effacer les résultats des autres titres ni des autres portefeuilles. La valeur totale compte toutes les positions.
- **Jours fériés.** Il n'y a pas de calendrier : un jour est considéré férié quand la collecte quotidienne de la place est passée après la clôture, presque sans erreur, et que moins de 5 % des titres suivis ont une clôture ce jour-là. Une panne de Yahoo (beaucoup d'erreurs) n'est jamais prise pour un férié.
- **PEA.** « PEA probable » = action d'une société de l'UE ou de l'EEE (siège d'après FinanceDatabase) cotée sur une place européenne. Les ETF sont toujours « à vérifier » : leur éligibilité dépend de l'indice et du domicile, que les données ne donnent pas.
- **Catalogue.** Les noms servent à écarter bons de souscription, droits, unités de SPAC et ETF à effet de levier ; « Multi Units Luxembourg - Lyxor… » ou « Short Duration » ne sont plus pris pour des dérivés. Après modification des règles : refaire « Filtrer FinanceDatabase », « Importer les informations Yahoo » puis « Filtrer Yahoo » pour réintégrer les titres libérés.
- **Suivi des classements.** L'écart à l'univers compare moyenne à moyenne. Les classements de jours voisins se chevauchent (« Cas » n'est pas un nombre d'observations indépendantes) et la plupart des jours sont « reconstitués » à partir de l'univers actuel (biais de survie) : à lire comme une description, pas comme une preuve.
- **Sources.** Yahoo est interrogé par des points d'accès non officiels ; FinanceDatabase peut être épinglé avec `JIGO_FDB_REF` (commit ou étiquette) pour un catalogue reproductible.
- **« Cours ancien ».** Un titre peu échangé (ETF de niche) peut n'avoir aucune transaction depuis 30 minutes sans que rien ne soit anormal : son cours est alors le dernier échange, toujours d'actualité. Le cours est « ancien » si son dernier échange date d'avant la dernière clôture due, ou, pendant la séance, si NI le dernier échange NI la dernière collecte de 15 minutes de la place ne datent de moins de 30 minutes (donnée réellement ancienne : collecte arrêtée). L'heure de référence est l'horloge UTC du serveur ; les heures d'ouverture sont celles de la place (`market/hours.py`).
- **Erreurs de données corrigées (affichées sur la fiche, « Données corrigées »).** (1) Un saut de ×100 ou ÷100 (± 6 %) est un changement d'unité (livres/pence, rands/cents…) : l'historique antérieur est mis à l'échelle de la dernière unité, le vrai mouvement restant est conservé. (2) Un cours isolé à plus de ×4 ou ÷4 de ses deux voisines, qui se ressemblent (à ×1,6 près), est une erreur ponctuelle : il est ignoré, sans être remplacé par un prix inventé. Rien d'autre n'est modifié : un vrai mouvement, même violent, reste une rupture (« non évaluable » sur les fenêtres qui le traversent). Effet mesuré sur la production : 14 titres concernés, les mesures de tous les autres sont identiques, aucun changement dans les 20 premiers des quatre profils.

## Négociabilité : le filtre « Titres facilement négociables »

- **Mesure unique** : valeur échangée par jour ≈ volume moyen sur 3 mois (Yahoo Quote) × cours converti en euros. C'est une estimation fournisseur, pas du volume exécuté. C'est la seule donnée de volume fiable que nous stockons (pas de volume journalier, pas de spread).
- **Trois niveaux, un seul calcul** (`engine.analytics.signals.liquidity`, utilisé par le filtre, la pastille du classement et la fiche) : *facilement négociable* ≥ 4 × le minimum du préfiltre, *à surveiller* entre 2 × et 4 ×, *négociabilité limitée* en dessous de 2 ×. Avec les minimums actuels (1 M€ action, 250 k€ ETF) : actions 2 M€ / 4 M€, ETF 500 k€ / 1 M€. Justification : un ordre de 10 000 € ne doit pas dépasser environ 0,5 % de la valeur échangée en un jour pour une action et 2 % pour un ETF (les teneurs de marché élargissent la liquidité réelle des ETF).
- **Données absentes ou plus vieilles que 10 jours** : « négociabilité non déterminée », jamais « limitée ». Ces titres restent affichés.
- **Le filtre masque seulement, après le classement.** Rang et score restent ceux du catalogue (aucun recalcul) ; les suivants remontent dans la liste (colonne « # » = position dans la liste filtrée). Désactivé, l'ordre et les scores sont identiques à avant. La pagination s'applique après le filtre. Un titre détenu n'est jamais masqué ; un titre trouvé par son symbole ou son ISIN exact reste affiché avec sa mention. Le Suivi des classements n'est pas filtré.
- **Indicateurs complémentaires, jamais des critères** : part des créneaux de 15 min avec une bougie (note de fiche sous 70 %), et, pour un ETF européen dont le nom indique des actions américaines, rappel que les échanges peuvent être moins fréquents avant l'ouverture de Wall Street. Une bougie manquante n'est pas une absence d'échange.
- **Limites** : un seul chiffre de volume par titre (moyenne 3 mois) ; pas de spread ; pas de volume par créneau horaire ; l'exposition américaine d'un ETF n'est déduite que de son nom.


## Avis des analystes, taille et activité récente (30/10/2026)

- **Analystes** : consensus relevé par Yahoo pour les ACTIONS seulement (« 1.8 - Buy » devient « Achat (1,8) » ; 1 = achat fort, 5 = vente forte). Information externe : ce n'est pas une recommandation de Jigobourso et il n'entre dans aucun score, filtre ou classement. Absent = « — », jamais un défaut du titre. Jamais affiché pour un ETF.
- **Catégorie de taille** (fiche action) : d'après la capitalisation convertie en euros (micro < 300 M€, petite < 2 Md€, moyenne < 10 Md€, grande < 200 Md€, très grande au-delà) ; non indiquée quand la devise est en pence.
- **Activité récente** : le volume moyen sur 10 jours est comparé à celui sur 3 mois ; au-delà de ×1,5 ou en dessous de ×0,67, la fiche l'explique. C'est un signal d'activité, pas de liquidité durable ni de volatilité. Les seuils du filtre « Titres facilement négociables » ne changent pas.
- Non retenus faute de fiabilité (inventaire du 30/10/2026) : bid/ask (valeurs à 0, ask inférieur au bid), rendement de distribution et ratio cours/valeur comptable des ETF, indice suivi (absent de la réponse).
